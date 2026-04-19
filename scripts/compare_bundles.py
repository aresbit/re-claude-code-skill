from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re
import sys


FEATURE_RE = re.compile(r'feature\("([A-Z0-9_]+)"\)')
COMMAND_NAME_RE = re.compile(r'name:\s*"([a-z0-9][a-z0-9-]*)"', re.IGNORECASE)
URL_RE = re.compile(r"https://[^\s\"'`<>\\]+")
PROMPT_HINT_RE = re.compile(r"/[a-z0-9][a-z0-9-]*", re.IGNORECASE)


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_summary(text: str) -> dict[str, object]:
    features = sorted(set(FEATURE_RE.findall(text)))
    command_names = Counter(COMMAND_NAME_RE.findall(text))
    slash_like = Counter(
        s[1:]
        for s in PROMPT_HINT_RE.findall(text)
        if len(s) > 2 and not s.startswith("//")
    )
    urls = sorted(set(URL_RE.findall(text)))
    return {
        "bytes": len(text.encode("utf-8")),
        "chars": len(text),
        "features": features,
        "command_names": sorted(command_names),
        "top_slash_like": [k for k, _ in slash_like.most_common(200)],
        "urls": urls,
    }


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: python compare_bundles.py <official_js> <baseline_js> <report_json>")
        return 2

    official_path = Path(sys.argv[1])
    baseline_path = Path(sys.argv[2])
    report_path = Path(sys.argv[3])

    official = extract_summary(load_text(official_path))
    baseline = extract_summary(load_text(baseline_path))

    official_features = set(official["features"])
    baseline_features = set(baseline["features"])
    official_commands = set(official["command_names"])
    baseline_commands = set(baseline["command_names"])
    official_slash = set(official["top_slash_like"])
    baseline_slash = set(baseline["top_slash_like"])

    report = {
        "official_path": str(official_path),
        "baseline_path": str(baseline_path),
        "official": official,
        "baseline": baseline,
        "diff": {
            "features_only_in_official": sorted(official_features - baseline_features),
            "features_only_in_baseline": sorted(baseline_features - official_features),
            "commands_only_in_official": sorted(official_commands - baseline_commands),
            "commands_only_in_baseline": sorted(baseline_commands - official_commands),
            "slash_like_only_in_official": sorted(official_slash - baseline_slash),
            "slash_like_only_in_baseline": sorted(baseline_slash - official_slash),
            "common_feature_count": len(official_features & baseline_features),
            "common_command_count": len(official_commands & baseline_commands),
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["diff"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
