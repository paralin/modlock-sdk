#!/usr/bin/env python3
"""Verify a Valve VPK set, extract unchanged members, and build a matching recipe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from assemble_sdk import contained_path
from depot_match import ManifestFile, read_manifest
from sdk_inventory import fingerprint, inventory_directory


@dataclass(frozen=True)
class Member:
    """A raw VPK member described by the source-built extractor's directory dump."""

    path: str
    size: int
    archive_index: int


def read_directory(text: str) -> list[Member]:
    """Read ValvePak 6 directory records, requiring the complete declared count."""
    # Source2Viewer prints extension counts before ValvePak's entry records.
    expected = sum(int(value) for value in re.findall(r"^\t[^\r\n:]+: (\d+) files$", text, re.MULTILINE))
    members = []
    for line in text.splitlines():
        row = re.fullmatch(r"(.+) crc=0x[0-9a-f]+ metadatasz=(\d+) fnumber=(\d+) ofs=0x[0-9a-f]+ sz=(\d+)", line)
        if row:
            contained_path(Path("/"), row[1])
            members.append(Member(row[1], int(row[2]) + int(row[4]), int(row[3])))
    if not expected or len(members) != expected:
        raise ValueError(f"VPK directory declares {expected} members but contains {len(members)} records")
    return members


def verify_packages(packages: list[ManifestFile], root: Path) -> list[dict]:
    """Require each selected package to match Valve's size and SHA-1."""
    verified = []
    for entry in packages:
        with contained_path(root, entry.path).open("rb") as stream:
            actual = fingerprint(stream, entry.path)
        if (actual["bytes"], actual["sha1"]) != (entry.size, entry.sha1):
            raise ValueError(f"VPK bytes differ from Steam manifest: {entry.path}")
        verified.append(actual)
    return verified


def select_members(reference: Path, directory: Path, extractor: Path) -> list[Member]:
    """Shortlist members by mounted path and size; payload hashes decide matches.

    The caller verifies the directory package before invoking this operation.
    This bounded search can miss renamed members; full extraction remains available.
    """
    # A game mount prefix is absent from member paths inside its VPK.
    targets = json.loads(reference.read_text(encoding="utf-8"))
    candidates = {(row["path"].split("/", 2)[2], row["bytes"]) for row in targets
                  if row["path"].startswith("game/") and row["path"].count("/") >= 2}

    # The pinned extractor reads directory metadata without numbered packages.
    result = subprocess.run(["dotnet", str(extractor.resolve()), "-i", str(directory), "--vpk_dir"],
                            check=True, capture_output=True, text=True)
    selected = [member for member in read_directory(result.stdout)
                if (member.path, member.size) in candidates]
    if not selected:
        raise ValueError("No VPK members match reference paths and sizes")
    if any("," in member.path for member in selected):
        raise ValueError("The extractor's comma-separated path filter cannot represent this member name")
    return selected


def package_selection(reference: Path, manifest_path: Path, depot_root: Path,
                      archive: str, extractor: Path, matching_paths: bool) -> tuple[list[ManifestFile], list[Member]]:
    """Resolve a complete VPK set or packages containing candidate members."""
    # The directory and every numbered package must belong to the pinned manifest.
    manifest = read_manifest(manifest_path)
    if not archive.endswith("_dir.vpk"):
        raise ValueError("Archive must name a multipart VPK's _dir.vpk file")
    prefix = archive.removesuffix("dir.vpk")
    packages = [entry for entry in manifest.files
                if entry.path == archive or re.fullmatch(re.escape(prefix) + r"\d+\.vpk", entry.path)]
    directory = next((entry for entry in packages if entry.path == archive), None)
    if directory is None:
        raise ValueError("Requested VPK directory is absent from the manifest")
    if not matching_paths:
        return packages, []

    # Verify the small index before trusting it to select larger downloads.
    verify_packages([directory], depot_root)
    members = select_members(reference, contained_path(depot_root, archive), extractor)
    names = {archive} | {f"{prefix}{member.archive_index:03d}.vpk" for member in members
                        if member.archive_index != 0x7FFF}
    if names - {entry.path for entry in packages}:
        raise ValueError("VPK directory references packages absent from the Steam manifest")
    return [entry for entry in packages if entry.path in names], members


def extract_recipe(reference: Path, manifest_path: Path, app: str, depot_root: Path,
                   archive: str, extractor: Path, extracted: Path, output: Path,
                   matching_paths: bool = False) -> dict:
    """Extract one complete depot VPK set and match member bytes to a reference.

    Requires a new extraction directory and a source-built Source2Viewer CLI.
    Matching-path mode verifies only packages needed by its candidate members.
    The recipe records package hashes and member paths; no decompilation occurs.
    """
    # Resolve and verify packages before reading any member payload.
    manifest = read_manifest(manifest_path)
    if extracted.exists() or extracted.is_symlink():
        raise ValueError(f"Extraction directory already exists: {extracted}")
    packages, selected = package_selection(reference, manifest_path, depot_root, archive, extractor, matching_paths)
    verified = verify_packages(packages, depot_root)

    # Raw export preserves compiled member bytes; -d would transform them.
    command = ["dotnet", str(extractor.resolve()), "-i",
               str(contained_path(depot_root, archive)), "-o", str(extracted.resolve()) + os.sep]
    if selected:
        # Bounded arguments work on Windows too; each filter includes its extension.
        batch = []
        for member in selected:
            if batch and sum(len(name) + 1 for name in batch) + len(member.path) > 6000:
                subprocess.run(command + ["-f", ",".join(batch)], check=True)
                batch = []
            batch.append(member.path)
        if batch:
            subprocess.run(command + ["-f", ",".join(batch)], check=True)
        members = []
        for member in selected:
            with contained_path(extracted, member.path).open("rb") as stream:
                members.append(fingerprint(stream, member.path))
    else:
        subprocess.run(command, check=True)
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
        "selection": "mounted path and size" if matching_paths else "all package members",
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
    parser.add_argument("--matching-paths", action="store_true", help="Extract only members with reference paths and sizes")
    parser.add_argument("--select-packages", type=Path, help="Write a downloader file list for matching members, then exit")
    parser.add_argument("--extracted", type=Path, help="New directory for unchanged members")
    parser.add_argument("--output", type=Path, help="Verified subset recipe")
    args = parser.parse_args()
    if not args.select_packages and (args.extracted is None or args.output is None):
        parser.error("extraction requires --extracted and --output; use --select-packages to plan downloads")
    try:
        if args.select_packages:
            packages, members = package_selection(args.reference, args.manifest, args.depot_root,
                                                  args.archive, args.extractor, True)
            args.select_packages.parent.mkdir(parents=True, exist_ok=True)
            args.select_packages.write_text("".join(entry.path + "\n" for entry in packages), encoding="utf-8")
            print(f"Selected {len(packages)} packages ({sum(entry.size for entry in packages)} bytes) for {len(members)} candidate members")
            print(f"Wrote {args.select_packages}; download this list, then rerun with --matching-paths --extracted DIR --output RECIPE")
            return 0
        recipe = extract_recipe(args.reference, args.manifest, args.app, args.depot_root,
                                args.archive, args.extractor, args.extracted, args.output, args.matching_paths)
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
