#!/usr/bin/env python3
"""Inventory an SDK ZIP or source tree without executing or extracting binaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO


def fingerprint(stream: BinaryIO, path: str) -> dict:
    """Hash complete file bytes and report optional PE header metadata."""
    # SHA-1 permits comparisons with Steam manifests; SHA-256 identifies artifacts.
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    size = 0
    header = b""
    while block := stream.read(1024 * 1024):
        if not header:
            header = block[:4096]
        size += len(block)
        sha1.update(block)
        sha256.update(block)

    # PE timestamps are untrusted metadata, not an origin or signing check.
    result = {"path": path, "bytes": size, "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest()}
    if header.startswith(b"MZ") and len(header) >= 64:
        offset = struct.unpack_from("<I", header, 60)[0]
        if offset + 24 <= len(header) and header[offset:offset + 4] == b"PE\0\0":
            machine, _, timestamp = struct.unpack_from("<HHI", header, offset + 4)
            result["pe_machine"] = hex(machine)
            result["pe_timestamp"] = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    return result


def inventory_zip(path: Path, prefix: str) -> list[dict]:
    """Read regular ZIP entries in archive order; never extract their contents."""
    results = []
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            if not entry.filename.startswith(prefix):
                raise ValueError(f"Entry does not have prefix {prefix!r}: {entry.filename}")
            with archive.open(entry) as stream:
                results.append(fingerprint(stream, entry.filename.removeprefix(prefix)))
    return results


def inventory_directory(root: Path) -> list[dict]:
    """Hash regular files beneath a root, excluding Git metadata and symlinks."""
    results = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts or path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            results.append(fingerprint(stream, relative.as_posix()))
    return results


def compare(target: Path, candidates: list[Path]) -> list[dict]:
    """Find all byte-identical source candidates without assigning provenance."""
    # Preserve every possible source when several depots contain the same bytes.
    sources = defaultdict(list)
    for candidate in candidates:
        for row in json.loads(candidate.read_text(encoding="utf-8")):
            sources[(row["bytes"], row["sha256"])].append(
                {"inventory": str(candidate), "path": row["path"]}
            )

    # Empty candidate sets remain explicit unresolved entries.
    return [
        {**row, "candidates": sources[(row["bytes"], row["sha256"])]}
        for row in json.loads(target.read_text(encoding="utf-8"))
    ]


def main() -> int:
    """Write an inventory or comparison as JSON and report input errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    zip_parser = commands.add_parser("zip", help="Hash a ZIP without extraction")
    zip_parser.add_argument("archive", type=Path)
    zip_parser.add_argument("--strip-prefix", default="")
    tree_parser = commands.add_parser("directory", help="Hash an isolated downloaded tree")
    tree_parser.add_argument("root", type=Path)
    compare_parser = commands.add_parser("compare", help="Match target bytes against source inventories")
    compare_parser.add_argument("target", type=Path)
    compare_parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()

    # The caller chooses the output file; a failed input never produces a result.
    try:
        if args.command == "zip":
            rows = inventory_zip(args.archive, args.strip_prefix)
        elif args.command == "directory":
            if not args.root.is_dir():
                raise ValueError(f"Source directory does not exist: {args.root}")
            rows = inventory_directory(args.root)
        else:
            rows = compare(args.target, args.sources)
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(f"sdk_inventory: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
