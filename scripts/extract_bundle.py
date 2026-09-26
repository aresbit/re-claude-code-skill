from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys


# Claude Code 2.x packs its sources as a Bun virtual filesystem: every chunk is
# prefixed with this banner, and the chunks sit back to back inside the binary.
BANNER = b"// @bun @bytecode\n// Claude Code is a Beta product"

# Older packing emitted a single bundle headed by this combined marker. It also
# appears in Bun's own internal string table, so a hit alone proves nothing and
# the containing printable run has to be checked.
COMBINED = b"// @bun @bytecode @bun-cjs"

VERSION_RE = re.compile(r"// Version: ([\d][\w.\-]*)")


def printable(byte: int) -> bool:
    return 32 <= byte <= 126 or byte in (9, 10, 13)


def find_all(data: bytes, needle: bytes) -> list[int]:
    hits: list[int] = []
    search_from = 0
    while True:
        pos = data.find(needle, search_from)
        if pos == -1:
            return hits
        hits.append(pos)
        search_from = pos + 1


def find_printable_runs(data: bytes, min_len: int = 2000) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, b in enumerate(data):
        if printable(b):
            if start is None:
                start = i
        elif start is not None:
            if i - start >= min_len:
                runs.append((start, i - start))
            start = None
    if start is not None and len(data) - start >= min_len:
        runs.append((start, len(data) - start))
    return runs


def scan_text_end(data: bytes, last_banner: int, gap_tolerance: int = 400) -> int:
    """End of the source region: past the last banner, up to the first long
    stretch of non-printable bytes (the trailing bytecode/metadata section)."""
    run = 0
    pos = last_banner
    while pos < len(data):
        if printable(data[pos]):
            run = 0
        else:
            run += 1
            if run > gap_tolerance:
                break
        pos += 1
    return pos - run


def extract_banner_region(data: bytes) -> dict:
    """2.x packing: many banner-prefixed chunks forming one contiguous region."""
    banners = find_all(data, BANNER)
    if not banners:
        raise SystemExit("banner marker not found")
    start = banners[0]
    end = scan_text_end(data, banners[-1])
    chunk_count = len(banners)
    return {
        "mode": "bunfs-chunks",
        "start": start,
        "length": end - start,
        "chunk_count": chunk_count,
    }


def extract_combined_bundle(data: bytes) -> dict:
    """Legacy packing: the bundle is the largest printable run holding the
    combined marker. A marker inside Bun's string table lands in a short run and
    is rejected here."""
    markers = find_all(data, COMBINED)
    if not markers:
        raise SystemExit("neither banner marker nor combined marker found")
    runs = find_printable_runs(data)
    candidates = [
        (start, length)
        for start, length in runs
        if any(start <= pos < start + length for pos in markers)
    ]
    if not candidates:
        raise SystemExit(
            "combined marker found only outside a printable run of >=2000 bytes; "
            "this looks like Bun's internal string table and not an embedded bundle"
        )
    start, length = max(candidates, key=lambda item: item[1])
    return {
        "mode": "combined-marker",
        "start": start,
        "length": length,
        "chunk_count": 1,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python extract_bundle.py <input_exe> <output_js>")
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    data = input_path.read_bytes()

    # Prefer the banner, fall back to the combined marker, then die with a
    # message that says which shapes were searched for.
    try:
        region = extract_banner_region(data)
    except SystemExit:
        region = extract_combined_bundle(data)

    start, length = region["start"], region["length"]
    chunk = data[start : start + length]
    text = chunk.decode("latin1")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")

    duplicates: list[int] = []
    search_from = 0
    while True:
        pos = data.find(chunk, search_from)
        if pos == -1:
            break
        duplicates.append(pos)
        search_from = pos + 1

    version_match = VERSION_RE.search(text[:4096])
    # Bytes swept in from between chunks. Non-zero is expected in the 2.x layout
    # and small; a large value means the region boundary is wrong.
    binary_bytes = sum(1 for b in chunk if not printable(b))

    meta = {
        "input": str(input_path),
        "output": str(output_path),
        "mode": region["mode"],
        "bundle_start": start,
        "bundle_length": length,
        "sha256": hashlib.sha256(chunk).hexdigest(),
        "duplicate_offsets": duplicates,
        "chunk_count": region["chunk_count"],
        "binary_bytes": binary_bytes,
        "version": version_match.group(1) if version_match else None,
    }
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
