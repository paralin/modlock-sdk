#!/usr/bin/env python3
"""Build the Windows launcher reproducibly with Zig 0.16.0."""

import argparse
import subprocess
from pathlib import Path

from compiler_probe import digest


def main() -> int:
    """Compile without host-dependent PDB identifiers and print the output hash."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", default="zig", help="Zig compiler executable")
    parser.add_argument("--output", type=Path, default=root / "output/authored/sdk-launcher.exe")
    args = parser.parse_args()
    version = subprocess.check_output([args.zig, "version"], text=True, timeout=10).strip()
    if version != "0.16.0":
        parser.error(f"Reproducible release builds require Zig 0.16.0; found {version}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.zig, "cc", "-target", "x86_64-windows-gnu", "-O2", "-s",
                    "-Wall", "-Wextra", "-Werror", "-Wl,--subsystem,windows",
                    str(root / "tools/sdk_launcher.c"), "-o", str(args.output)],
                   check=True, timeout=120)
    print(f"{digest(args.output)}  {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
