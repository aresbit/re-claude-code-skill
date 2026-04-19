from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import sys


@dataclass(frozen=True)
class ChunkSpec:
    output: str
    anchors: tuple[str, ...]
    pad_before: int = 20000
    pad_after: int = 40000
    position_mode: str = "all"


CHUNKS: tuple[ChunkSpec, ...] = (
    ChunkSpec(
        "commands/cli/root-commands.js",
        (
            '$.command("mcp")',
            '$.command("plugin")',
            '$.command("remote-control"',
            "async function gt1(",
            "async function lt1(",
        ),
        pad_before=30000,
        pad_after=90000,
    ),
    ChunkSpec(
        "commands/review/ultrareview.js",
        (
            '"/ultrareview"',
            "Remote review did not produce output",
            "free ultrareviews",
            'remoteTaskType:"ultrareview"',
        ),
        pad_before=40000,
        pad_after=90000,
    ),
    ChunkSpec(
        "commands/plugin/plugin-cli.js",
        (
            '$.command("plugin")',
            '.command("marketplace")',
            "pluginInstallHandler",
            "pluginUpdateHandler",
        ),
        pad_before=25000,
        pad_after=70000,
    ),
    ChunkSpec(
        "hooks/schemas.js",
        (
            'hook_event_name:E.literal("PreToolUse")',
            'hook_event_name:E.literal("PermissionDenied")',
            'hook_event_name:E.literal("PreCompact")',
        ),
        pad_before=25000,
        pad_after=50000,
    ),
    ChunkSpec(
        "hooks/execution.js",
        (
            "executePreCompactHooks",
            "executePostCompactHooks",
            "executePermissionDeniedHooks",
            "TOOL_HOOK_EXECUTION_TIMEOUT_MS",
        ),
        pad_before=25000,
        pad_after=90000,
    ),
    ChunkSpec(
        "hooks/stop-hooks.js",
        (
            "Stop hook blocking error",
            "executeStopHooks",
            "executeStopFailureHooks",
        ),
        pad_before=25000,
        pad_after=50000,
    ),
    ChunkSpec(
        "hooks/stop-schemas.js",
        (
            'hook_event_name:E.literal("Stop")',
            'hook_event_name:E.literal("StopFailure")',
            "stop_hook_active:E.boolean()",
        ),
        pad_before=15000,
        pad_after=25000,
    ),
    ChunkSpec(
        "remote-control/constants.js",
        (
            "BRIDGE_LOGIN_ERROR",
            "REMOTE_CONTROL_DISCONNECTED_MSG",
        ),
        pad_before=20000,
        pad_after=30000,
        position_mode="first",
    ),
    ChunkSpec(
        "remote-control/server-cli.js",
        (
            "Remote Control runs as a persistent server",
            "Connect your local environment to claude.ai/code",
            "Remote Control lets you access this CLI session from the web",
        ),
        pad_before=25000,
        pad_after=60000,
    ),
    ChunkSpec(
        "remote-control/runtime.js",
        (
            "Lost sync with Remote Control",
            "Remote Control initialization failed",
            "Remote Control connection lost",
            "events could not be delivered",
        ),
        pad_before=30000,
        pad_after=45000,
    ),
    ChunkSpec(
        "remote-control/session-banner.js",
        (
            "/remote-control is active",
            "Code in CLI or at ",
        ),
        pad_before=12000,
        pad_after=22000,
        position_mode="first",
    ),
    ChunkSpec(
        "remote-control/callouts.js",
        (
            "Enable Remote Control for this session",
            'title:"Remote Control"',
            "Remote Control lets you access this CLI session from the web",
        ),
        pad_before=16000,
        pad_after=30000,
    ),
    ChunkSpec(
        "remote-control/push-notification.js",
        (
            "PushNotification",
            "when Remote Control is connected, also push to their mobile device",
            "This tool sends a desktop notification in the user's terminal.",
        ),
        pad_before=20000,
        pad_after=22000,
        position_mode="first",
    ),
)


BOUNDARY_RE = re.compile(r"(?:^|;)(?:async function |function |var |class )")


def find_occurrences(text: str, needle: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    return positions


def build_boundaries(text: str) -> list[int]:
    boundaries = [0]
    for match in BOUNDARY_RE.finditer(text):
        pos = match.start()
        if pos not in boundaries:
            boundaries.append(pos)
    boundaries.append(len(text))
    return sorted(set(boundaries))


def snap_start(boundaries: list[int], target: int) -> int:
    best = 0
    for pos in boundaries:
        if pos > target:
            break
        best = pos
    return best


def snap_end(boundaries: list[int], target: int) -> int:
    for pos in boundaries:
        if pos > target:
            return pos
    return boundaries[-1]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python extract_semantic_chunks.py <bundle_js> <output_dir>")
        return 2

    bundle_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    text = bundle_path.read_text(encoding="utf-8", errors="ignore")
    boundaries = build_boundaries(text)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "bundle": str(bundle_path),
        "chunks": [],
    }

    for spec in CHUNKS:
        hits: list[dict[str, object]] = []
        positions: list[int] = []
        for anchor in spec.anchors:
            found = find_occurrences(text, anchor)
            if spec.position_mode == "first" and found:
                found = found[:1]
            elif spec.position_mode == "last" and found:
                found = found[-1:]
            if found:
                positions.extend(found)
                hits.append({"anchor": anchor, "positions": found[:10], "count": len(found)})
            else:
                hits.append({"anchor": anchor, "positions": [], "count": 0})

        if not positions:
            manifest["chunks"].append(
                {
                    "output": spec.output,
                    "found": False,
                    "anchors": hits,
                }
            )
            continue

        start_target = max(0, min(positions) - spec.pad_before)
        end_target = min(len(text), max(positions) + spec.pad_after)
        start = snap_start(boundaries, start_target)
        end = snap_end(boundaries, end_target)
        fragment = text[start:end]

        header = [
            "/*",
            f" semiauto-extracted from {bundle_path.name}",
            f" output: {spec.output}",
            f" start: {start}",
            f" end: {end}",
            " anchors:",
        ]
        for item in hits:
            header.append(
                f"  - {item['anchor']} (count={item['count']}, positions={item['positions'][:3]})"
            )
        header.append("*/")
        header_text = "\n".join(header) + "\n"

        output_path = out_dir / spec.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(header_text + fragment, encoding="utf-8")

        manifest["chunks"].append(
            {
                "output": spec.output,
                "found": True,
                "start": start,
                "end": end,
                "length": len(fragment),
                "anchors": hits,
            }
        )

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
