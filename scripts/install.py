#!/usr/bin/env python3
"""Install or update Modlock Tools from the current Valve depots."""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import steam
from build_launcher import ZIG_VERSION, build
from toolkit import PROJECT_DIRS, ROOT, SAMPLE, authored, contained_path, depots

ZIG_INDEX = "https://ziglang.org/download/index.json"


def zig(cache: Path) -> Path:
    """Download the Zig compiler the launcher build requires once."""
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(platform.machine().lower(),
                                                       platform.machine().lower())
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[platform.system()]
    program = cache / f"zig-{arch}-{system}-{ZIG_VERSION}" / ("zig.exe" if system == "windows" else "zig")
    if not program.is_file():
        print(f"Downloading Zig {ZIG_VERSION}", flush=True)
        url = json.loads(steam.fetch(ZIG_INDEX))[ZIG_VERSION][f"{arch}-{system}"]["tarball"]
        archive = io.BytesIO(steam.fetch(url))
        if url.endswith(".zip"):
            zipfile.ZipFile(archive).extractall(cache)
        else:
            with tarfile.open(fileobj=archive) as tar:
                tar.extractall(cache, filter="tar")
    return program


def depot_files(cache: Path) -> tuple[dict[str, Path], dict[str, str | None]]:
    """Find the current source of every Valve file the toolkit takes.

    An installed game supplies its depots directly, and Steam's manifest gives
    their exact file list. Every other depot is brought up to date by
    DepotDownloader in the cache. Returns the source of each toolkit path and
    the manifest ID each depot came from.
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
                           cache / "steam-account")
            paths = [path.relative_to(base).as_posix() for path in base.rglob("*")
                     if path.is_file() and ".DepotDownloader" not in path.relative_to(base).parts]
            manifests[depot.depot] = steam.downloaded_manifest(base, depot.depot)

        # A later depot's copy of a path replaces an earlier one's.
        for path in paths:
            if (target := depot.target(path)) and (source := contained_path(base, path)).is_file():
                sources[target] = source
    return sources, manifests


def place(source: Path, target: Path) -> None:
    """Put a Valve file into the toolkit, sharing large packages with Steam.

    Packages are read only, so a hard link or symbolic link avoids copying tens
    of gigabytes. Other files are copied so editor writes never reach Steam. A
    file that already matches is left alone.
    """
    package = source.suffix == ".vpk"
    if target.exists() or target.is_symlink():
        if package and target.exists() and os.path.samefile(source, target):
            return
        if not package and (target.stat().st_size, target.stat().st_mtime) == \
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
    shutil.copy2(source, target)


def install(destination: Path) -> None:
    """Bring the toolkit in destination up to the current Valve depots.

    The state file lists the Valve files the last run placed, so a file Valve
    has since removed is removed here too. Authored files are rewritten; the
    sample addon and other user work are kept.
    """
    destination = destination.absolute()
    cache = destination / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    state = cache / "installed.json"
    previous = json.loads(state.read_text(encoding="utf-8"))["files"] if state.is_file() else []

    sources, manifests = depot_files(cache)
    removed = sorted(set(previous) - set(sources))
    print(f"Placing {len(sources)} Valve files; removing {len(removed)}", flush=True)
    for name in removed:
        contained_path(destination, name).unlink(missing_ok=True)
    for name, source in sources.items():
        place(source, contained_path(destination, name))

    launcher = cache / "sdk-launcher.exe"
    build(str(zig(cache)), launcher)
    for name, content in authored(ROOT, launcher).items():
        target = contained_path(destination, name)
        if name.startswith(SAMPLE) and target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, Path):
            shutil.copyfile(content, target)
        else:
            target.write_bytes(content)
    for name in PROJECT_DIRS:
        contained_path(destination, name).mkdir(parents=True, exist_ok=True)

    state.write_text(json.dumps({"depots": manifests, "files": sorted(sources)}, indent=2) + "\n",
                     encoding="utf-8")


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
