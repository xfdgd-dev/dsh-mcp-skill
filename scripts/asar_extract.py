#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Minimal Electron ASAR reader: list and extract packages out of an `app.asar`.

Why you may need this: DSH's real plugin schemas live inside `app.asar`, not in
the docs. When a config field is undocumented, this is how you find the truth.

Usage
-----
    python asar_extract.py <path-to-app.asar> <substring> [-o OUTDIR] [--list]

Examples
--------
    # list every file whose path contains "dsh-mcp-client"
    python asar_extract.py "C:/Program Files/App/resources/app.asar" dsh-mcp-client --list

    # extract them to ./asar_unpack
    python asar_extract.py "C:/Program Files/App/resources/app.asar" dsh-mcp-client

Notes
-----
* ASAR layout: [u32 4][u32 pickle_size][u32 json_buf_size][u32 json_len][json][padding][files]
  The data area starts at 8 + pickle_size; each file entry has offset/size.
* Entries marked `unpacked` are NOT inside the archive (they live next to it in
  `app.asar.unpacked/`) and are reported but skipped.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def read_header(fh) -> tuple[dict, int]:
    fh.seek(0)
    _magic, pickle_size, _buf_size, json_len = struct.unpack("<IIII", fh.read(16))
    header = json.loads(fh.read(json_len))
    return header, 8 + pickle_size


def walk(node: dict, prefix: str = ""):
    for name, meta in node.get("files", {}).items():
        path = f"{prefix}/{name}" if prefix else name
        if "files" in meta:
            yield from walk(meta, path)
        else:
            yield path, meta


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="List/extract files from an Electron app.asar")
    ap.add_argument("asar", help="path to app.asar")
    ap.add_argument("target", help="substring to match against file paths")
    ap.add_argument("-o", "--outdir", default="asar_unpack", help="output directory")
    ap.add_argument("--list", action="store_true", help="only list matches, extract nothing")
    args = ap.parse_args(argv)

    asar = Path(args.asar)
    if not asar.is_file():
        print(f"not found: {asar}", file=sys.stderr)
        return 1

    with asar.open("rb") as fh:
        header, base = read_header(fh)
        entries = dict(walk(header))
        print(f"files in asar: {len(entries)}")

        wanted = {
            path: meta
            for path, meta in entries.items()
            if args.target.lower() in path.lower()
        }
        print(f"matched: {len(wanted)}")
        if not wanted:
            return 0

        for path in sorted(wanted):
            if args.list:
                print(path)

        if args.list:
            return 0

        out = Path(args.outdir)
        out.mkdir(parents=True, exist_ok=True)
        for path, meta in sorted(wanted.items()):
            if meta.get("unpacked"):
                print(f"SKIP (unpacked, look in app.asar.unpacked/): {path}")
                continue
            fh.seek(base + int(meta["offset"]))
            data = fh.read(int(meta["size"]))
            # flatten the path so nested node_modules trees stay browsable
            dest = out / path.replace("/", "__")
            dest.write_bytes(data)
            print(f"wrote {dest.name} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
