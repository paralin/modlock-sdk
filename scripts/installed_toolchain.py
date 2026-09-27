#!/usr/bin/env python3
"""Resolve a pinned recipe against Steam installations and downloaded depot roots."""

import argparse
import json
import os
from pathlib import Path

from assemble_sdk import contained_path
from compiler_probe import digest


def resolve(recipe: Path, roots: list[Path], output: Path) -> None:
    """Select matching source bytes without changing the installed games."""
    original = json.loads(recipe.read_text(encoding="utf-8"))
    selected, missing = [], []
    for entry in original["files"]:
        for index, root in enumerate(roots):
            source = contained_path(root, entry["to"])
            if source.is_file() and digest(source) == entry["sha256"]:
                selected.append({**entry, "source": f"input-{index}", "from": entry["to"],
                                 "valve_source": entry["source"]})
                break
        else:
            missing.append(entry["to"])
    if missing:
        raise ValueError("Missing or changed pinned files:\n" + "\n".join(missing))
    result = {"pinned_recipe_sha256": digest(recipe), "profile": original["profile"],
              "sources": {f"input-{index}": {
                  "root": Path(os.path.relpath(root.resolve(), output.parent.resolve())).as_posix()
              } for index, root in enumerate(roots)}, "files": selected}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    """Produce a recipe consumable by assemble_sdk.py after all hashes match."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--source", type=Path, action="append", required=True,
                        help="Steam game or depot root; repeat in preference order")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        resolve(args.recipe, args.source, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"installed_toolchain: {error}\n")
    print(f"Verified installed sources; wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
