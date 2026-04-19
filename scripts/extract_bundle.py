from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys


def find_printable_runs(data: bytes, min_len: int = 2000) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, b in enumerate(data):
        ok = 32 <= b <= 126 or b in (9, 10, 13)
        if ok:
            if start is None:
                start = i
        elif start is not None:
            if i - start >= min_len:
                runs.append((start, i - start))
            start = None
    if start is not None and len(data) - start >= min_len:
        runs.append((start, len(data) - start))
    return runs


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python extract_bundle.py <input_exe> <output_js>")
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    data = input_path.read_bytes()

    marker = b"// @bun @bytecode @bun-cjs"
    markers: list[int] = []
    search_from = 0
    while True:
        pos = data.find(marker, search_from)
        if pos == -1:
            break
        markers.append(pos)
        search_from = pos + 1
    if not markers:
        raise SystemExit("bundle marker not found")

    runs = find_printable_runs(data)
    candidates = [
        (start, length)
        for start, length in runs
        if any(start <= marker_pos < start + length for marker_pos in markers)
    ]
    if not candidates:
        raise SystemExit("printable run containing bundle marker not found")
    start, length = max(candidates, key=lambda item: item[1])

    chunk = data[start : start + length]
    text = chunk.decode("latin1")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")

    duplicates = []
    chunk_hash = hashlib.sha256(chunk).hexdigest()
    search_from = 0
    while True:
        pos = data.find(chunk, search_from)
        if pos == -1:
            break
        duplicates.append(pos)
        search_from = pos + 1

    meta = {
        "input": str(input_path),
        "output": str(output_path),
        "bundle_start": start,
        "bundle_length": length,
        "sha256": chunk_hash,
        "duplicate_offsets": duplicates,
    }
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
