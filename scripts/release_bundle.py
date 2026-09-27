#!/usr/bin/env python3
"""Pack an installed toolkit into deterministic Windows ZIPs for a release."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import shutil
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

from compiler_probe import digest
from toolkit import ASSETS, PROJECT_DIRS, ROOT, authored, contained_path

PART_BYTES = 2 * 1024**3


def write_archive(path: Path, entries: list[dict]) -> dict:
    """Stream, hash, and compress each member into a ZIP with fixed metadata."""
    members = []
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        for entry in sorted(entries, key=lambda row: row["path"]):
            name, source = entry["path"], entry["input"]
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o40755 if name.endswith("/") else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.compress_level = 1
            info.file_size = source.stat().st_size if isinstance(source, Path) else len(source)
            checksum, size = hashlib.sha256(), 0
            with (source.open("rb") if isinstance(source, Path) else io.BytesIO(source)) as stream:
                with archive.open(info, "w", force_zip64=True) as output:
                    while block := stream.read(1024 * 1024):
                        output.write(block)
                        checksum.update(block)
                        size += len(block)
            members.append({"path": name, "bytes": size, "sha256": checksum.hexdigest()})
    return {"name": path.name, "bytes": path.stat().st_size,
            "sha256": digest(path), "members": members}


def build(root: Path, toolkit: Path, output: Path, revision: str,
          part_bytes: int = PART_BYTES) -> dict:
    """Pack the Valve files an install placed in toolkit, plus the authored files.

    Asset packages go into separate archives of at most part_bytes each, so no
    download is too large; the rest goes into the tools archive. release.json
    records the depot manifests the files came from and each member's SHA-256.
    """
    if part_bytes <= 0:
        raise ValueError("Part size must be positive")
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"Release destination exists: {output}")
    version = (root / "VERSION").read_text().strip()
    if not version or any(c not in "0123456789." for c in version):
        raise ValueError("VERSION must contain a numeric dotted version")
    state = json.loads((toolkit / ".cache/installed.json").read_text(encoding="utf-8"))
    manifest = {"version": version, "source_revision": revision,
                "packager": {"python": platform.python_version(),
                             "zlib": zlib.ZLIB_RUNTIME_VERSION,
                             "compression": "deflate-1", "part_bytes": part_bytes},
                "depots": state["depots"], "archives": []}

    tools, assets = [], []
    for name in state["files"]:
        entry = {"path": name, "input": contained_path(toolkit, name)}
        (assets if name.startswith(ASSETS) else tools).append(entry)
    for name, source in authored(root, toolkit / ".cache/sdk-launcher.exe").items():
        tools.append({"path": name, "input": source})
    for name in PROJECT_DIRS:
        tools.append({"path": name, "input": b""})

    # Bound each asset archive by uncompressed bytes; never split a VPK member.
    archives = [(f"modlock-tools-{version}-windows-x64.zip", tools)]
    part, size = [], 0
    for entry in sorted(assets, key=lambda row: row["path"]):
        length = entry["input"].stat().st_size
        if part and size + length > part_bytes:
            archives.append((f"modlock-assets-{version}-{len(archives):03d}.zip", part))
            part, size = [], 0
        part.append(entry)
        size += length
    if part:
        archives.append((f"modlock-assets-{version}-{len(archives):03d}.zip", part))

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".release-", dir=output.parent) as temporary:
        stage = Path(temporary) / "bundle"
        stage.mkdir()
        for index, (name, entries) in enumerate(archives, 1):
            print(f"[{index}/{len(archives)}] Building {name} ({len(entries)} entries)", flush=True)
            manifest["archives"].append(write_archive(stage / name, entries))
        for name, source in (("README.md", root / "bundle/README.md"),
                             ("Install.ps1", root / "bundle/Install.ps1")):
            shutil.copyfile(source, stage / name)
        (stage / "release.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        sums = [f"{digest(path)}  {path.name}" for path in sorted(stage.iterdir())]
        (stage / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")
        if output.exists():
            raise ValueError(f"Release destination appeared during build: {output}")
        stage.rename(output)
    return manifest


def main() -> int:
    """Build a versioned release from an installed toolkit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolkit", type=Path, required=True, help="Toolkit made by install.py")
    parser.add_argument("--output", type=Path, required=True, help="New release directory")
    parser.add_argument("--revision", required=True, help="Source Git commit used for this build")
    args = parser.parse_args()
    try:
        result = build(ROOT, args.toolkit, args.output, args.revision)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"release_bundle: {error}", file=sys.stderr)
        return 1
    print(f"Ready: {len(result['archives'])} ZIPs, README.md, Install.ps1, release.json, SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
