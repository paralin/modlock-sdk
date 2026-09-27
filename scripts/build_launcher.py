#!/usr/bin/env python3
"""Build the Windows launcher reproducibly with Zig 0.16.0."""

import argparse
import subprocess
from pathlib import Path

from compiler_probe import digest

ROOT = Path(__file__).resolve().parents[1]
ZIG_VERSION = "0.16.0"


def build(zig: str, output: Path) -> str:
    """Compile without host-dependent PDB identifiers and return the output SHA-256."""
    version = subprocess.check_output([zig, "version"], text=True, timeout=10).strip()
    if version != ZIG_VERSION:
        raise ValueError(f"Reproducible launcher builds require Zig {ZIG_VERSION}; found {version}")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([zig, "cc", "-target", "x86_64-windows-gnu", "-O2", "-s",
                    "-Wall", "-Wextra", "-Werror", "-Wl,--subsystem,windows",
                    str(ROOT / "tools/sdk_launcher.c"), "-o", str(output)],
                   check=True, timeout=120)
    return digest(output)


def main() -> int:
    """Build the launcher and print its hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", default="zig", help="Zig compiler executable")
    parser.add_argument("--output", type=Path, default=ROOT / "output/authored/sdk-launcher.exe")
    args = parser.parse_args()
    try:
        print(f"{build(args.zig, args.output)}  {args.output}")
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
