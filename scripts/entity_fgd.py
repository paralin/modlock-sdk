#!/usr/bin/env python3
"""Merge map-derived entity definitions with Valve's existing core FGDs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

INCLUDES = ("base.fgd", "lights.fgd", "lights2.fgd", "markup_volumes.fgd", "postprocessing.fgd", "ai_defaultnpc.fgd")
CLASS = re.compile(r'^@(Point|Solid)Class( base\(Targetname\))? = (\w+) : ""\n\[\n(.*?)^\]', re.MULTILINE | re.DOTALL)
PROPERTY = re.compile(r'^\s*(output )?(\w+)\((\w+)\) : ""\s*$', re.MULTILINE)


@dataclass
class Entity:
    """Merged observations for one entity class, without inferred defaults."""

    solid: bool = False
    targetname: bool = False
    fields: dict[str, set[str]] = field(default_factory=dict)
    outputs: set[str] = field(default_factory=set)


def declared_classes(text: str) -> set[str]:
    """Read class names after the header's top-level equals sign.

    Source 2 editor attributes contain nested assignments before the class name.
    Quoted strings and comments cannot introduce declarations or delimiters.
    """
    names = set()
    header = False
    depth = 0
    expect_name = False
    tokens = re.finditer(r'//[^\n]*|"(?:\\.|[^"\\])*"|@\w+|\w+|[{}\[\]()=]', text)
    for match in tokens:
        token = match.group()
        if token.startswith(('//', '"')):
            continue
        if token.startswith('@'):
            header = token.endswith('Class')
            depth = 0
            expect_name = False
        elif expect_name:
            names.add(token)
            header = expect_name = False
        elif header:
            if token in ('(', '{', '['):
                depth += 1
            elif token in (')', '}', ']'):
                depth -= 1
            elif token == '=' and depth == 0:
                expect_name = True
    return names


def merge(source: Path, core: Path, target: Path) -> int:
    """Write one FGD from exported lumps, preserving core definitions unchanged."""
    # Include Valve's recursive base definitions and avoid redeclaring their classes.
    known = set()
    visited = set()

    def read_base(name: str) -> None:
        """Collect the transitive declarations of an installed Valve FGD."""
        if name in visited:
            return
        visited.add(name)
        text = (core / name).read_text(encoding="utf-8-sig")
        known.update(declared_classes(text))
        for child in re.findall(r'@include\s+"([^"]+)"', text):
            read_base(child)

    for name in INCLUDES:
        read_base(name)

    # The extractor's receipt enumerates exactly which generated files belong here.
    entities: dict[str, Entity] = {}
    records = json.loads((source / "sources.json").read_text(encoding="utf-8"))
    for record in records:
        text = (source / (record["Sha256"] + ".fgd")).read_text(encoding="utf-8")
        for kind, base, name, body in CLASS.findall(text):
            if name in known:
                continue
            entity = entities.setdefault(name, Entity())
            entity.solid |= kind == "Solid"
            entity.targetname |= bool(base)
            for output, key, type_name in PROPERTY.findall(body):
                if output:
                    entity.outputs.add(key)
                else:
                    entity.fields.setdefault(key, set()).add(type_name)

    # Map serialization supplies observed keys, not editor defaults or full schemas.
    lines = ["// Generated from compiled Valve map entities; review inferred types.",
             "// Unobserved classes, inputs, defaults, choices and model events remain unknown."]
    lines.extend(f'@include "{name}"' for name in INCLUDES)
    for name, entity in sorted(entities.items()):
        kind = "Solid" if entity.solid else "Point"
        base = " base(Targetname)" if entity.targetname else ""
        lines.extend(["", f'@{kind}Class{base} = {name} : "Observed map entity"', "["])
        for key, types in sorted(entity.fields.items()):
            type_name = next(iter(types)) if len(types) == 1 else "string"
            if type_name not in {"string", "integer", "float", "boolean", "vector"}:
                type_name = "string"
            lines.append(f'    {key}({type_name}) : "Observed field"')
        lines.extend(f'    output {key}(void) : "Observed output"' for key in sorted(entity.outputs))
        lines.append("]")
    if not entities:
        raise ValueError("No additional entity classes were recovered")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(entities)


def main() -> int:
    """Create the merged FGD and report how many observed classes it adds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="EntityMetadata output directory")
    parser.add_argument("--core", type=Path, required=True, help="Verified game/core directory containing Valve FGDs")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        count = merge(args.source, args.core, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"entity_fgd: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {count} observed entity classes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
