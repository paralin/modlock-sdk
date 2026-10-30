#!/usr/bin/env python3
"""Install or update Modlock Tools from the current Valve depots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import durable
import steam
from build_programs import ZIG_VERSION, build
from toolkit import PROJECT_DIRS, ROOT, SAMPLE, authored, contained_path, depots

ZIG_INDEX = "https://ziglang.org/download/index.json"
VPK_MAGIC = 0x55AA1234
VPK_HEADER = struct.Struct("<7I")
VPK_ENTRY = struct.Struct("<IHHIIH")
# The archive index of an entry whose data sits in the package index itself.
VPK_IN_INDEX = 0x7FFF
# The empty signature section that ends an unsigned package.
UNSIGNED_VPK = struct.pack("<5I", VPK_MAGIC, 1, 0, 0, 0)
SHADER_ARCHIVE = re.compile(r"(.+/shaders_\w+)_\d{3}\.vpk")


def zig(cache: Path) -> Path:
    """Download the Zig compiler the program build requires once.

    Only the current version stays in the cache. Earlier installers unpacked
    Zig under its archive's own name without flushing it, so a power loss could
    leave a compiler whose headers are zeros; that folder is removed with the
    other old versions.
    """
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(platform.machine().lower(),
                                                       platform.machine().lower())
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[platform.system()]
    folder = cache / f"zig-{ZIG_VERSION}"
    for old in cache.glob("zig-*"):
        if old != folder:
            shutil.rmtree(old, ignore_errors=True)

    def download() -> bytes:
        print(f"Downloading Zig {ZIG_VERSION}", flush=True)
        return steam.fetch(json.loads(steam.fetch(ZIG_INDEX))[ZIG_VERSION][f"{arch}-{system}"]["tarball"])

    durable.unpack(folder, download)
    return folder / f"zig-{arch}-{system}-{ZIG_VERSION}" / ("zig.exe" if system == "windows" else "zig")


def depot_files(cache: Path, repair: bool) -> tuple[dict[str, Path], dict[str, str | None]]:
    """Find the current source of every Valve file the toolkit takes.

    An installed game supplies its depots directly, and Steam's manifest gives
    their exact file list. Every other depot is brought up to date by
    DepotDownloader in the cache, which checks every file it already has when
    repairing. Returns the source of each toolkit path and the manifest ID each
    depot came from.
    """
    installed = steam.installed_depots()
    sources, manifests, program = {}, {}, None
    for depot in depots():
        if depot.depot in installed:
            base, manifest = installed[depot.depot]
            print(f"Depot {depot.depot}: installed in {base}", flush=True)
            paths = steam.manifest_files(manifest)
            manifests[depot.depot] = manifest.stem.split("_")[1]
        else:
            print(f"Depot {depot.depot}: downloading", flush=True)
            base = cache / "depots" / depot.depot
            program = program or steam.depot_downloader(cache)
            steam.download(program, depot.app, depot.depot, depot.include, base,
                           cache / "steam-account", validate=repair)
            paths = [path.relative_to(base).as_posix() for path in base.rglob("*")
                     if path.is_file() and ".DepotDownloader" not in path.relative_to(base).parts]
            manifests[depot.depot] = steam.downloaded_manifest(base, depot.depot)

        # A later depot's copy of a path replaces an earlier one's.
        for path in paths:
            if (targets := depot.targets(path)) and (source := contained_path(base, path)).is_file():
                sources.update(dict.fromkeys(targets, source))
    return sources, manifests


def place(source: Path, target: Path, repair: bool) -> None:
    """Put a Valve file into the toolkit, sharing large packages with Steam.

    Packages are read only, so a hard link or symbolic link avoids copying tens
    of gigabytes. Other files are copied so editor writes never reach Steam. A
    link to the source is left alone, and so is a copy with the source's size
    and time unless repairing.
    """
    package = source.suffix == ".vpk"
    if target.exists() or target.is_symlink():
        if package and target.exists() and os.path.samefile(source, target):
            return
        if not repair and (target.stat().st_size, target.stat().st_mtime) == \
                (source.stat().st_size, source.stat().st_mtime):
            return
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    if package:
        for link in (os.link, os.symlink):
            try:
                link(source, target)
                return
            except OSError:
                pass
    durable.copy(source, target)


def single_file(index: bytes, archives: list[bytes]) -> bytes:
    """Rebuild a version 2 package split over archives as one unsigned file.

    The archives' data follows the index's own in its data section, in archive
    order, so an entry's offset grows by the size of the data before its
    archive. The chunk hashes describe the archives and are dropped; the section
    hashes are recomputed.
    """
    _, _, tree_size, own_size, *_ = VPK_HEADER.unpack_from(index)
    tree = bytearray(index[VPK_HEADER.size:VPK_HEADER.size + tree_size])
    own = index[VPK_HEADER.size + tree_size:VPK_HEADER.size + tree_size + own_size]
    bases = [len(own)]
    for archive in archives:
        bases.append(bases[-1] + len(archive))

    # The tree is extensions, then paths, then names, each list ending in an
    # empty string; each name is followed by its entry and preload bytes.
    position = 0

    def string() -> bytes:
        nonlocal position
        end = tree.index(0, position)
        value, position = tree[position:end], end + 1
        return value

    while string():
        while string():
            while string():
                crc, preload, archive, offset, size, end = VPK_ENTRY.unpack_from(tree, position)
                if archive != VPK_IN_INDEX:
                    VPK_ENTRY.pack_into(tree, position, crc, preload, VPK_IN_INDEX,
                                        bases[archive] + offset, size, end)
                position += VPK_ENTRY.size + preload

    data = own + b"".join(archives)
    header = VPK_HEADER.pack(VPK_MAGIC, 2, len(tree), len(data), 0, 48, len(UNSIGNED_VPK))
    hashes = hashlib.md5(tree).digest() + hashlib.md5(b"").digest()
    whole = hashlib.md5(header + tree + data + hashes).digest()
    return header + tree + data + hashes + whole + UNSIGNED_VPK


def shader_packages(sources: dict[str, Path]) -> dict[str, list[Path]]:
    """Take the shader packages' archives out of sources, keyed by their index.

    The editors' asset system reads every package in a game directory other
    than pak01 as a map, and reports a shader package's archive as a corrupt
    one, so the toolkit writes each shader package as one file. They are tens of
    megabytes.
    """
    packages: dict[str, list[Path]] = {}
    for name in sorted(sources):
        if match := SHADER_ARCHIVE.fullmatch(name):
            packages.setdefault(f"{match[1]}_dir.vpk", []).append(sources.pop(name))
    return packages


def install(destination: Path) -> None:
    """Bring the toolkit in destination up to the current Valve depots.

    The state file lists the Valve files the last run placed, so a file Valve
    has since removed is removed here too. Authored files are rewritten; the
    sample addon and other user work are kept.

    The state file is marked complete only once every file the run wrote is on
    disk. A run that finds it incomplete repairs: a power loss during the last
    run, or after one by an installer that did not flush its files, can leave
    files of the right size and time filled with zeros, so it checks every
    downloaded file and copies every placed one again.
    """
    destination = destination.absolute()
    cache = destination / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    state = cache / "installed.json"
    try:
        recorded = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A first run, or a state file an older installer left broken in a
        # crash: files Valve removed since then stay in place.
        recorded = {}
    previous = recorded.get("files", [])
    repair = not recorded.get("complete", False)
    save_state(state, recorded.get("depots", {}), previous, complete=False)
    if repair and previous:
        print("The last install did not finish; checking every file", flush=True)

    sources, manifests = depot_files(cache, repair)
    shaders = shader_packages(sources)
    removed = sorted(set(previous) - set(sources))
    print(f"Placing {len(sources)} Valve files; removing {len(removed)}", flush=True)
    for name in removed:
        target = contained_path(destination, name)
        target.unlink(missing_ok=True)
        # Prune the directories the removal emptied, such as a whole game
        # directory a profile no longer takes.
        for parent in target.parents:
            if parent == destination or not parent.is_dir() or any(parent.iterdir()):
                break
            parent.rmdir()
    for name, source in sources.items():
        target = contained_path(destination, name)
        if name not in shaders:
            place(source, target, repair)
            continue
        # Rewritten each run: a shader package is small, and its index alone
        # does not show whether an archive changed.
        target.parent.mkdir(parents=True, exist_ok=True)
        durable.write(target, single_file(source.read_bytes(),
                                          [archive.read_bytes() for archive in shaders[name]]))

    build(str(zig(cache)), cache)
    for name, content in authored(ROOT, cache).items():
        target = contained_path(destination, name)
        if name.startswith(SAMPLE) and target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        durable.write(target, content.read_bytes() if isinstance(content, Path) else content)
    for name in PROJECT_DIRS:
        contained_path(destination, name).mkdir(parents=True, exist_ok=True)

    save_state(state, manifests, sorted(sources), complete=True)


def save_state(state: Path, manifests: dict[str, str | None], files: list[str],
               complete: bool) -> None:
    """Record the depot manifests and placed files, and whether the run finished."""
    durable.write(state, (json.dumps({"complete": complete, "depots": manifests, "files": files},
                                     indent=2) + "\n").encode())


def main() -> int:
    """Install or update the toolkit and point at the editors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path.home() / "modlock-tools",
                        help="Toolkit directory; rerun to update it")
    args = parser.parse_args()
    try:
        install(args.destination)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"install: {error}", file=sys.stderr)
        return 1
    print(f"\nModlock Tools is ready in {args.destination.absolute()}.")
    print("Open Hammer.cmd, ModelDoc.cmd, or SFM.cmd there on Windows. Run Update.cmd to update.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
