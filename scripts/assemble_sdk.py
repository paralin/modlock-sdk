#!/usr/bin/env python3
"""Assemble an explicit file recipe from verified local sources into a new tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath


def contained_path(root: Path, relative: str) -> Path:
    """Resolve a recipe path inside its root, rejecting traversal and symlink escape."""
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Recipe requires a relative portable path: {relative!r}")
    result = root.joinpath(*path.parts).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Recipe path escapes its source: {relative!r}")
    return result


def assemble(recipe_path: Path, destination: Path) -> None:
    """Publish a new directory only after all selected file hashes match the recipe."""
    # Resolve sources relative to the recipe, keeping every source root explicit.
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    sources = {
        name: (recipe_path.parent / source["root"]).resolve()
        for name, source in recipe["sources"].items()
    }
    if not recipe["files"]:
        raise ValueError("Recipe has no files; no SDK was assembled")
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Build in a sibling directory so failed copies never publish a partial SDK.
    with tempfile.TemporaryDirectory(prefix=".sdk-assembly-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "sdk"
        stage.mkdir()
        selected = set()
        for entry in recipe["files"]:
            target = contained_path(stage, entry["to"])
            key = target.relative_to(stage).as_posix().casefold()
            if key in selected:
                raise ValueError(f"Duplicate Windows destination: {entry['to']}")
            selected.add(key)
            source = contained_path(sources[entry["source"]], entry["from"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            with target.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != entry["sha256"]:
                raise ValueError(f"Source bytes do not match recipe: {entry['from']}")

        # Refuse a concurrently created target; callers choose isolated output paths.
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Destination appeared during assembly: {destination}")
        stage.rename(destination)


def main() -> int:
    """Assemble the requested recipe and return a nonzero status for a failed build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        assemble(args.recipe, args.destination)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"assemble_sdk: {error}", file=sys.stderr)
        return 1
    print(f"Assembled {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
