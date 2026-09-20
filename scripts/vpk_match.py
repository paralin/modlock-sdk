#!/usr/bin/env python3
"""Verify a Valve VPK set, extract unchanged members, and build a matching recipe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from assemble_sdk import contained_path
from depot_match import read_manifest
from sdk_inventory import fingerprint, inventory_directory


def extract_recipe(reference: Path, manifest_path: Path, app: str, depot_root: Path,
                   archive: str, extractor: Path, extracted: Path, output: Path) -> dict:
    """Extract one complete depot VPK set and match member bytes to a reference.

    Requires a new extraction directory and a source-built Source2Viewer CLI.
    The recipe records package hashes and member paths; no decompilation occurs.
    """
    # Identify every numbered package and directory file in the pinned manifest.
    manifest = read_manifest(manifest_path)
    if not archive.endswith("_dir.vpk"):
        raise ValueError("Archive must name a multipart VPK's _dir.vpk file")
    prefix = archive.removesuffix("dir.vpk")
    packages = [entry for entry in manifest.files
                if entry.path.startswith(prefix) and entry.path.endswith(".vpk")]
    if not any(entry.path == archive for entry in packages):
        raise ValueError("Requested VPK directory is absent from the manifest")
    if extracted.exists() or extracted.is_symlink():
        raise ValueError(f"Extraction directory already exists: {extracted}")

    # Establish the complete package bytes before interpreting any member data.
    verified = []
    for entry in packages:
        with contained_path(depot_root, entry.path).open("rb") as stream:
            actual = fingerprint(stream, entry.path)
        if (actual["bytes"], actual["sha1"]) != (entry.size, entry.sha1):
            raise ValueError(f"VPK bytes differ from Steam manifest: {entry.path}")
        verified.append(actual)

    # Raw export preserves compiled member bytes; -d would transform them.
    subprocess.run(["dotnet", str(extractor.resolve()), "-i",
                    str(contained_path(depot_root, archive)), "-o", str(extracted.resolve())], check=True)
    members = inventory_directory(extracted)
    index = defaultdict(list)
    for member in members:
        index[(member["bytes"], member["sha256"])].append(member)

    # Match all reference paths by content, including members mounted elsewhere.
    targets = json.loads(reference.read_text(encoding="utf-8"))
    source_name = f"vpk-{manifest.depot}-{manifest.manifest}-{archive}"
    files = []
    alternatives = {}
    for target in targets:
        candidates = index.get((target["bytes"], target["sha256"]), [])
        if candidates:
            files.append({"source": source_name, "from": candidates[0]["path"],
                          "to": target["path"], "sha256": target["sha256"]})
            alternatives[target["path"]] = [entry["path"] for entry in candidates]
    if not files:
        raise ValueError("No extracted members match the reference; no recipe was produced")
    return {
        "status": "verified subset; not a runnable SDK",
        "reference_files": len(targets),
        "reference_inventory_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "sources": {source_name: {
            "root": Path(os.path.relpath(extracted.resolve(), output.parent.resolve())).as_posix(),
            "kind": "vpk-members", "app": app, "depot": manifest.depot,
            "manifest": manifest.manifest, "vpk": archive,
            "manifest_text_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "packages": verified,
            "extractor_sha256": hashlib.sha256(extractor.read_bytes()).hexdigest(),
        }},
        "extracted_files": len(members),
        "member_candidates": alternatives,
        "files": files,
    }


def main() -> int:
    """Run package verification and raw extraction, then write matching provenance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--app", required=True)
    parser.add_argument("--depot-root", type=Path, required=True)
    parser.add_argument("--archive", required=True, help="Depot-relative _dir.vpk path")
    parser.add_argument("--extractor", type=Path, required=True, help="Source-built Source2Viewer-CLI.dll")
    parser.add_argument("--extracted", type=Path, required=True, help="New directory for unchanged members")
    parser.add_argument("--output", type=Path, required=True, help="Verified subset recipe")
    args = parser.parse_args()
    try:
        recipe = extract_recipe(args.reference, args.manifest, args.app, args.depot_root,
                                args.archive, args.extractor, args.extracted, args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"vpk_match: {error}", file=sys.stderr)
        return 1
    print(f"Matched {len(recipe['files'])}/{recipe['reference_files']} reference paths from {recipe['extracted_files']} VPK members")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
