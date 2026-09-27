#!/usr/bin/env python3
"""Select and verify a pinned Valve toolchain without a comparison archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from assemble_sdk import contained_path
from depot_match import read_manifest
from sdk_inventory import fingerprint


def build_profile(profile_path: Path, manifests: Path, inputs: Path | None, output: Path) -> dict:
    """Write download lists, or verify all selected files into an assembly recipe.

    A profile supplies pinned app/depot/manifest IDs and literal path prefixes.
    Payload verification preserves Valve paths and rejects conflicting inputs.
    """
    # Selection comes from Valve manifests, independently of a historical archive.
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    sources = {}
    files = {}
    selections = []
    for depot in profile["depots"]:
        manifest_path = manifests / f"manifest_{depot['depot']}_{depot['manifest']}.txt"
        manifest = read_manifest(manifest_path)
        if (manifest.depot, manifest.manifest) != (depot["depot"], depot["manifest"]):
            raise ValueError(f"Manifest identifiers differ from profile: {manifest_path}")
        selected = [entry for entry in manifest.files
                    if any(entry.path.startswith(prefix) for prefix in depot["include"])
                    and not any(entry.path.startswith(prefix) for prefix in depot.get("exclude", []))]
        if not selected:
            raise ValueError(f"Profile selects no files from depot {manifest.depot}")

        # Each depot has its own input directory; overlays must agree byte for byte.
        name = f"depot-{manifest.depot}-{manifest.manifest}"
        source = {
            "app": depot["app"], "depot": manifest.depot, "manifest": manifest.manifest,
            "manifest_text_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        }
        if inputs is not None:
            root = inputs / manifest.depot
            source["root"] = Path(os.path.relpath(root.resolve(), output.parent.resolve())).as_posix()
        sources[name] = source
        selections.append({**source, "files": len(selected), "bytes": sum(entry.size for entry in selected)})

        # Planning emits one exact file list per depot. Acquisition remains external.
        if inputs is None:
            output.mkdir(parents=True, exist_ok=True)
            listing = output / f"{manifest.depot}.files.txt"
            listing.write_text("".join(entry.path + "\n" for entry in selected), encoding="utf-8")
            continue

        # Match payloads to Valve's manifest, then pin assembly with SHA-256.
        for entry in selected:
            with contained_path(root, entry.path).open("rb") as stream:
                actual = fingerprint(stream, entry.path)
            if (actual["bytes"], actual["sha1"]) != (entry.size, entry.sha1):
                raise ValueError(f"Downloaded bytes differ from Steam manifest: {entry.path}")
            key = entry.path.casefold()
            if key in files and files[key]["sha256"] != actual["sha256"]:
                raise ValueError(f"Conflicting Valve depot files: {entry.path}")
            files.setdefault(key, {"source": name, "from": entry.path, "to": entry.path,
                                   "sha256": actual["sha256"]})
    return {
        "status": "download selection" if inputs is None else "verified toolchain files; runtime acceptance pending",
        "profile": profile,
        "profile_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "sources": sources,
        "selections": selections,
        "files": sorted(files.values(), key=lambda entry: entry["to"]),
    }


def main() -> int:
    """Plan downloads or publish a verified recipe for the selected profile."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("select", "recipe"))
    parser.add_argument("profile", type=Path)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, help="Depot directories, each named by its numeric ID")
    parser.add_argument("--output", type=Path, required=True, help="File-list directory for select; JSON recipe for recipe")
    args = parser.parse_args()
    if args.command == "recipe" and args.inputs is None:
        parser.error("recipe requires --inputs")
    if args.command == "select" and args.inputs is not None:
        parser.error("select does not read payloads; omit --inputs")
    try:
        result = build_profile(args.profile, args.manifests, args.inputs, args.output)
        target = args.output / "selection.json" if args.command == "select" else args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"current_toolchain: {error}", file=sys.stderr)
        return 1
    print(f"Selected {sum(row['files'] for row in result['selections'])} files, {sum(row['bytes'] for row in result['selections'])} bytes")
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
