#!/usr/bin/env python3
"""Build the toolkit's Windows programs reproducibly with Zig 0.16.0."""

import argparse
import subprocess
from pathlib import Path

from compiler_probe import digest

ROOT = Path(__file__).resolve().parents[1]
ZIG_VERSION = "0.16.0"

# Each program's source and the linker options it needs. The launcher is a GUI
# program so no console opens behind the editors; the vrad3 shim runs under the
# compiler, which reads its console output.
PROGRAMS = {
    "sdk-launcher.exe": ("tools/sdk_launcher.c", ["-Wl,--subsystem,windows"]),
    "vrad3.exe": ("tools/vrad3_shim.c", ["-lshell32"]),
}


def build(zig: str, directory: Path) -> dict[str, str]:
    """Compile every program into directory without host-dependent PDB identifiers.

    Returns the SHA-256 of each program by file name.
    """
    version = subprocess.check_output([zig, "version"], text=True, timeout=10).strip()
    if version != ZIG_VERSION:
        raise ValueError(f"Reproducible builds require Zig {ZIG_VERSION}; found {version}")
    directory.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, (source, options) in PROGRAMS.items():
        output = directory / name
        subprocess.run([zig, "cc", "-target", "x86_64-windows-gnu", "-O2", "-s",
                        "-Wall", "-Wextra", "-Werror", *options,
                        str(ROOT / source), "-o", str(output)],
                       check=True)
        hashes[name] = digest(output)
    return hashes


def main() -> int:
    """Build the programs and print their hashes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", default="zig", help="Zig compiler executable")
    parser.add_argument("--output", type=Path, default=ROOT / "output/authored")
    args = parser.parse_args()
    try:
        for name, sha in build(args.zig, args.output).items():
            print(f"{sha}  {args.output / name}")
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
