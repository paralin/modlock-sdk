#!/usr/bin/env python3
"""Build deterministic Windows ZIPs from pinned tools, assets, and authored files."""

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

from assemble_sdk import contained_path
from compiler_probe import JS, MESH, MODEL, XML, digest
from tool_project import GAMEINFO, MODELS

ROOT = Path(__file__).resolve().parents[1]
PART_BYTES = 2 * 1024**3


def authored(root: Path, launcher: Path) -> dict[str, bytes | Path]:
    """Supply the standalone project and an editable example without game DLLs."""
    files = {
        "README.md": root / "bundle/README.md",
        "REPRODUCING.md": root / "REPRODUCING.md",
        "game/bin/win64/sdk-launcher.exe": launcher,
        "game/citadel/gameinfo.gi": GAMEINFO.encode(),
        "game/citadel/models_gamedata.fgd": MODELS.encode(),
        "game/citadel/citadel.fgd": root / "metadata/citadel.fgd",
        "content/citadel_addons/modlock_sample/models/probe.vmdl": MODEL.encode(),
        "content/citadel_addons/modlock_sample/models/probe.obj": MESH.encode(),
        "content/citadel_addons/modlock_sample/panorama/layout/probe.xml": XML.encode(),
        "content/citadel_addons/modlock_sample/panorama/scripts/probe.js": JS.encode(),
    }
    for name, options in {
        "Hammer": "+show_tool hammer",
        "ModelDoc": "-asset models/probe.vmdl +show_tool modeldoc_editor",
        "SFM": "+show_tool sfm",
    }.items():
        files[f"{name}.cmd"] = (
            '@echo off\r\nsetlocal\r\ncd /d "%~dp0game\\bin\\win64"\r\n'
            'sdk-launcher.exe -tools -insecure -novid -console -condebug -playtest '
            f'-addon modlock_sample {options}\r\n'
            'if errorlevel 1 pause\r\n'
        ).encode()
    return files


def write_archive(path: Path, entries: list[dict]) -> dict:
    """Stream, hash, and compress each member; reject changed pinned inputs."""
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
            actual = checksum.hexdigest()
            if entry.get("sha256", actual) != actual:
                raise ValueError(f"Source differs from pinned recipe: {name}")
            members.append({"path": name, "bytes": size, "sha256": actual,
                            "source": entry["source"]})
    return {"name": path.name, "bytes": path.stat().st_size,
            "sha256": digest(path), "members": members}


def build(root: Path, tools: Path, runtime: Path, launcher: Path,
          output: Path, revision: str, part_bytes: int = PART_BYTES) -> dict:
    """Publish a new release only after every packaged input passes its hash check."""
    if part_bytes <= 0:
        raise ValueError("Part size must be positive")
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"Release destination exists: {output}")
    version = (root / "VERSION").read_text().strip()
    if not version or any(c not in "0123456789." for c in version):
        raise ValueError("VERSION must contain a numeric dotted version")
    manifest = {"version": version, "source_revision": revision,
                "packager": {"python": platform.python_version(),
                             "zlib": zlib.ZLIB_RUNTIME_VERSION,
                             "compression": "deflate-1", "part_bytes": part_bytes},
                "recipes": {}, "archives": []}
    groups, seen = [], set()
    for profile, base in (("current-cs2-tools", tools), ("current-deadlock", runtime)):
        recipe = root / "recipes" / f"{profile}.json"
        manifest["recipes"][profile] = digest(recipe)
        rows = json.loads(recipe.read_text())["files"]
        selected = []
        for row in rows:
            name = row["to"]
            if profile == "current-deadlock":
                if not (name.startswith(("game/citadel/pak01_", "game/citadel/maps/"))
                        and name.endswith(".vpk")):
                    continue
                name = name.replace("game/citadel/", "game/citadel_assets/", 1)
            contained_path(output, name)
            if name.casefold() in seen:
                raise ValueError(f"Duplicate Windows destination: {name}")
            seen.add(name.casefold())
            selected.append({"path": name, "input": contained_path(base, row["to"]),
                             "sha256": row["sha256"],
                             "source": {"recipe": profile, "path": row["to"]}})
        if not selected:
            raise ValueError(f"No selected files in {profile}")
        groups.append(sorted(selected, key=lambda row: row["path"]))

    for name, source in authored(root, launcher).items():
        if name.casefold() in seen:
            raise ValueError(f"Authored file would replace a Valve file: {name}")
        seen.add(name.casefold())
        groups[0].append({"path": name, "input": source, "source": "authored"})
    for name in ("content/citadel/", "content/citadel_assets/", "game/citadel/cfg/",
                 "game/citadel_addons/modlock_sample/", "game/citadel_community_addons/"):
        groups[0].append({"path": name, "input": b"", "source": "authored"})

    # Bound each asset archive by uncompressed bytes; never split a VPK member.
    archives = [(f"modlock-tools-{version}-windows-x64.zip", groups[0])]
    part, size = [], 0
    for entry in groups[1]:
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
    """Build a versioned release from previously assembled, pinned source trees."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, required=True, help="Verified CS2 tools assembly")
    parser.add_argument("--runtime", type=Path, required=True, help="Verified Deadlock assembly")
    parser.add_argument("--launcher", type=Path, required=True, help="Source-built sdk-launcher.exe")
    parser.add_argument("--output", type=Path, required=True, help="New release directory")
    parser.add_argument("--revision", required=True, help="Source Git commit used for this build")
    args = parser.parse_args()
    try:
        result = build(ROOT, args.tools, args.runtime, args.launcher, args.output, args.revision)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"release_bundle: {error}", file=sys.stderr)
        return 1
    print(f"Ready: {len(result['archives'])} ZIPs, README.md, Install.ps1, release.json, SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
