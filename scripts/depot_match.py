#!/usr/bin/env python3
"""Select Steam manifest matches, then verify downloaded bytes into a recipe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from assemble_sdk import contained_path
from sdk_inventory import fingerprint


class Target(TypedDict):
    """Reference destination and required SHA-256 content hash."""

    path: str
    sha256: str


class Selection(TypedDict):
    """One downloaded input that can satisfy several reference paths."""

    path: str
    bytes: int
    sha1: str
    targets: list[Target]


class DownloadPlan(TypedDict):
    """Pinned manifest selection, before payload verification."""

    app: str
    depot: str
    manifest: str
    manifest_text_sha256: str
    reference_inventory_sha256: str
    reference_files: int
    files: list[Selection]


@dataclass(frozen=True)
class ManifestFile:
    """One regular depot file with its Steam content hash."""

    path: str
    size: int
    sha1: str


@dataclass(frozen=True)
class Manifest:
    """Identifiers and regular files decoded from a DepotDownloader text dump."""

    depot: str
    manifest: str
    files: tuple[ManifestFile, ...]


def read_manifest(path: Path) -> Manifest:
    """Parse a complete manifest dump; reject malformed rows and unsafe paths."""
    # Read identifiers and the declared row count before accepting file records.
    text = path.read_text(encoding="utf-8-sig")
    depot = re.search(r"^Content Manifest for Depot (\d+)\s*$", text, re.MULTILINE)
    manifest = re.search(r"^Manifest ID / date\s*:\s*(\d+) /", text, re.MULTILINE)
    count = re.search(r"^Total number of files\s*:\s*(\d+)\s*$", text, re.MULTILINE)
    header = re.search(r"^\s*Size Chunks File SHA\s+Flags Name\s*$", text, re.MULTILINE)
    if not all((depot, manifest, count, header)):
        raise ValueError(f"Incomplete manifest header: {path}")

    # Validate every row, including directories omitted from the returned files.
    files = []
    names = set()
    rows = 0
    for line in text[header.end():].splitlines():
        if not line.strip():
            continue
        row = re.fullmatch(r"\s*(\d+)\s+(\d+)\s+([0-9a-f]{40}|)\s+([0-9a-f]+)\s+(.+)", line)
        if row is None:
            raise ValueError(f"Malformed manifest row: {line!r}")
        rows += 1
        flags = int(row[4], 16)
        name = row[5].replace("\\", "/")
        contained_path(Path("/"), name)
        if name.casefold() in names:
            raise ValueError(f"Duplicate Windows manifest path: {name}")
        names.add(name.casefold())
        if flags & (64 | 512):  # Steam directory and symlink flags.
            continue
        if not row[3]:
            raise ValueError(f"Missing regular-file SHA-1: {name}")
        files.append(ManifestFile(name, int(row[1]), row[3]))
    if rows != int(count[1]):
        raise ValueError(f"Manifest declares {count[1]} rows but contains {rows}")
    return Manifest(depot[1], manifest[1], tuple(files))


def select(reference: Path, manifest_path: Path, app: str) -> DownloadPlan:
    """Return candidate matches by size/SHA-1, preserving every target path."""
    # Index reference hashes without reading or executing archive payloads.
    targets = json.loads(reference.read_text(encoding="utf-8"))
    index = defaultdict(list)
    for target in targets:
        contained_path(Path("/"), target["path"])
        index[(target["bytes"], target["sha1"])].append(target)

    # SHA-1 only shortlists candidates; recipe creation checks SHA-256 as well.
    manifest = read_manifest(manifest_path)
    selected: list[Selection] = []
    for entry in manifest.files:
        matches = index.get((entry.size, entry.sha1), [])
        if matches:
            selected.append({
                "path": entry.path,
                "bytes": entry.size,
                "sha1": entry.sha1,
                "targets": [{"path": row["path"], "sha256": row["sha256"]} for row in matches],
            })
    return {
        "app": app,
        "depot": manifest.depot,
        "manifest": manifest.manifest,
        "manifest_text_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "reference_inventory_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "reference_files": len(targets),
        "files": selected,
    }


def make_recipe(plan_path: Path, root: Path, recipe_path: Path) -> dict:
    """Verify all candidates against both hashes and return an assembly recipe."""
    # Keep Steam IDs and input roots independent of the workstation directory.
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not plan["files"]:
        raise ValueError("No manifest matches; no recipe was produced")
    name = f"depot-{plan['depot']}-{plan['manifest']}"
    source = {key: plan[key] for key in ("app", "depot", "manifest", "manifest_text_sha256")}
    source["root"] = Path(os.path.relpath(root.resolve(), recipe_path.parent.resolve())).as_posix()

    # A successful download exit alone cannot establish file completeness.
    outputs = {}
    verified = []
    for entry in plan["files"]:
        path = contained_path(root, entry["path"])
        with path.open("rb") as stream:
            actual = fingerprint(stream, entry["path"])
        if (actual["bytes"], actual["sha1"]) != (entry["bytes"], entry["sha1"]):
            raise ValueError(f"Downloaded bytes differ from Steam manifest: {entry['path']}")
        for target in entry["targets"]:
            contained_path(Path("/"), target["path"])
            if actual["sha256"] != target["sha256"]:
                raise ValueError(f"Downloaded SHA-256 differs from reference: {target['path']}")
            outputs.setdefault(target["path"], {
                "source": name, "from": entry["path"], "to": target["path"],
                "sha256": actual["sha256"],
            })
        verified.append(actual)
    return {
        "status": "verified subset; not a runnable SDK",
        "sources": {name: source},
        "reference_files": plan["reference_files"],
        "reference_inventory_sha256": plan["reference_inventory_sha256"],
        "verified_inputs": verified,
        "files": sorted(outputs.values(), key=lambda entry: entry["to"]),
    }


def merge_recipes(paths: list[Path], output: Path) -> dict:
    """Combine verified subsets, rejecting contradictory hashes or source roots.

    This combines recorded verification results; the assembler rechecks input
    bytes when publishing. Identical candidates use the first recipe's source.
    """
    # Require one reference inventory so coverage counts retain their meaning.
    recipes = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in paths]
    reference_hash = recipes[0][1]["reference_inventory_sha256"]
    reference_files = recipes[0][1]["reference_files"]
    sources = {}
    outputs = {}
    for path, recipe in recipes:
        if (recipe["reference_inventory_sha256"], recipe["reference_files"]) != (reference_hash, reference_files):
            raise ValueError("Cannot merge recipes for different reference inventories")

        # Rebase each input root from its original recipe to the combined recipe.
        for name, original in recipe["sources"].items():
            root = (path.parent / original["root"]).resolve()
            source = {**original, "root": Path(os.path.relpath(root, output.parent.resolve())).as_posix()}
            if name in sources and sources[name] != source:
                raise ValueError(f"Conflicting source declaration: {name}")
            sources[name] = source

        # Multiple depots may carry identical content; differing bytes are a conflict.
        for entry in recipe["files"]:
            key = entry["to"].casefold()
            if key in outputs and outputs[key]["sha256"] != entry["sha256"]:
                raise ValueError(f"Conflicting output hashes: {entry['to']}")
            outputs.setdefault(key, entry)
    return {
        "status": "verified subset; not a runnable SDK",
        "sources": sources,
        "reference_files": reference_files,
        "reference_inventory_sha256": reference_hash,
        "files": sorted(outputs.values(), key=lambda entry: entry["to"]),
    }


def main() -> int:
    """Select a download list or publish a recipe after successful verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    selection = commands.add_parser("select", help="Find candidate matches without downloading payloads")
    selection.add_argument("reference", type=Path)
    selection.add_argument("manifest", type=Path)
    selection.add_argument("--app", required=True)
    selection.add_argument("--output", required=True, type=Path, help="Plan JSON; also writes <plan>.files.txt")
    recipe = commands.add_parser("recipe", help="Verify every downloaded match and write an assembly recipe")
    recipe.add_argument("plan", type=Path)
    recipe.add_argument("root", type=Path)
    recipe.add_argument("--output", required=True, type=Path)
    merge = commands.add_parser("merge", help="Combine verified subsets for the same reference")
    merge.add_argument("recipes", nargs="+", type=Path)
    merge.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    # Construct the complete result before writing a usable recipe.
    try:
        if args.command == "select":
            result = select(args.reference, args.manifest, args.app)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            selection_path = args.output.with_suffix(".files.txt")
            selection_path.write_text("".join(row["path"] + "\n" for row in result["files"]), encoding="utf-8")
            print(f"Selected {len(result['files'])} depot files ({sum(row['bytes'] for row in result['files'])} bytes)")
            print(f"File list: {selection_path}")
        elif args.command == "recipe":
            result = make_recipe(args.plan, args.root, args.output)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            print(f"Verified {len(result['verified_inputs'])} inputs for {len(result['files'])}/{result['reference_files']} reference paths")
        else:
            result = merge_recipes(args.recipes, args.output)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            print(f"Combined {len(result['sources'])} sources for {len(result['files'])}/{result['reference_files']} reference paths")
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"depot_match: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
