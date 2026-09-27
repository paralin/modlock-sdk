#!/usr/bin/env python3
"""Install Modlock Tools from the local Steam games, downloading what is missing."""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from assemble_sdk import contained_path
from build_launcher import ZIG_VERSION, build
from release_bundle import PROJECT_DIRS, authored
from tool_project import asset_path

ROOT = Path(__file__).resolve().parents[1]
CS2, DEADLOCK = "730", "1422450"
DEPOT_DOWNLOADER = "https://github.com/SteamRE/DepotDownloader/releases/latest/download"
ZIG_INDEX = "https://ziglang.org/download/index.json"
SAMPLE = "content/citadel_addons/"


@dataclass
class File:
    """One toolkit file: its Steam app, depot, depot path, and destination."""

    app: str
    depot: str
    path: str
    target: str


def default_destination() -> Path:
    """Use a short ASCII path on Windows, where the tools reject some characters."""
    if os.name == "nt":
        return Path("C:/modlock-tools")
    return Path.home() / "modlock-tools"


def steam_roots() -> list[Path]:
    """Return the Steam installations this machine may have, most likely first."""
    roots = []
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                roots.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
        except OSError:
            pass
        roots.append(Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Steam")
    else:
        home = Path.home()
        roots += [home / ".steam/steam", home / ".local/share/Steam",
                  home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
                  home / "Library/Application Support/Steam"]
    return [root for root in roots if (root / "steamapps").is_dir()]


def installed_games() -> dict[str, Path]:
    """Find CS2 and Deadlock in every Steam library listed by libraryfolders.vdf."""
    libraries = []
    for root in steam_roots():
        libraries.append(root)
        folders = root / "steamapps/libraryfolders.vdf"
        if folders.is_file():
            text = folders.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                libraries.append(Path(match.group(1).replace("\\\\", "\\")))
    games = {}
    for library in libraries:
        for app in (CS2, DEADLOCK):
            manifest = library / f"steamapps/appmanifest_{app}.acf"
            if app in games or not manifest.is_file():
                continue
            text = manifest.read_text(encoding="utf-8", errors="replace")
            match = re.search(r'"installdir"\s+"([^"]+)"', text)
            if match and (game := library / "steamapps/common" / match.group(1)).is_dir():
                games[app] = game
    return games


def toolkit_files() -> list[File]:
    """List the CS2 tools and the Deadlock asset packages the toolkit needs."""
    files = []
    for app, profile in ((CS2, "current-cs2-tools"), (DEADLOCK, "current-deadlock")):
        recipe = json.loads((ROOT / "recipes" / f"{profile}.json").read_text(encoding="utf-8"))
        for row in recipe["files"]:
            target = row["to"] if app == CS2 else asset_path(row["to"])
            if target:
                depot = row["source"].split("-")[1]
                files.append(File(app, depot, row["from"], target))
    return files


def fetch(url: str) -> bytes:
    """Download a small file into memory."""
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def depot_downloader(cache: Path) -> Path:
    """Download the latest prebuilt DepotDownloader for this machine once."""
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[platform.system()]
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    folder = cache / f"depotdownloader-{system}-{arch}"
    program = folder / ("DepotDownloader.exe" if system == "windows" else "DepotDownloader")
    if not program.is_file():
        print("Downloading DepotDownloader", flush=True)
        archive = fetch(f"{DEPOT_DOWNLOADER}/DepotDownloader-{system}-{arch}.zip")
        zipfile.ZipFile(io.BytesIO(archive)).extractall(folder)
        program.chmod(0o755)
    return program


def zig(cache: Path) -> Path:
    """Download the Zig compiler the reproducible launcher build requires once."""
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(platform.machine().lower(),
                                                       platform.machine().lower())
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[platform.system()]
    folder = cache / f"zig-{arch}-{system}-{ZIG_VERSION}"
    program = folder / ("zig.exe" if system == "windows" else "zig")
    if not program.is_file():
        print(f"Downloading Zig {ZIG_VERSION}", flush=True)
        url = json.loads(fetch(ZIG_INDEX))[ZIG_VERSION][f"{arch}-{system}"]["tarball"]
        archive = io.BytesIO(fetch(url))
        if url.endswith(".zip"):
            zipfile.ZipFile(archive).extractall(cache)
        else:
            with tarfile.open(fileobj=archive) as tar:
                tar.extractall(cache, filter="tar")
    return program


def download(program: Path, app: str, files: list[File], folder: Path) -> None:
    """Fetch the current Windows files for one app after a Steam QR login.

    Steam denies anonymous sessions access to these depots. DepotDownloader
    shows a QR code for the Steam mobile app and keeps no login afterward.
    Files already in the folder are checked and skipped by DepotDownloader.
    """
    folder.mkdir(parents=True, exist_ok=True)
    filelist = folder / "files.txt"
    filelist.write_text("".join(f"{file.path}\n" for file in files), encoding="utf-8")
    depots = sorted({file.depot for file in files})
    name = "Counter-Strike 2 Workshop Tools" if app == CS2 else "Deadlock"
    print(f"\nDownloading {len(files)} {name} files. Scan the QR code with the Steam app.",
          flush=True)
    subprocess.run([str(program), "-app", app, "-depot", *depots, "-os", "windows",
                    "-osarch", "64", "-qr", "-filelist", str(filelist), "-dir", str(folder)],
                   check=True)


def place(source: Path, target: Path) -> None:
    """Put a Valve file into the toolkit, sharing large packages with Steam.

    Packages are read only, so a hard link or symbolic link avoids copying tens
    of gigabytes. Other files are copied so editor writes never reach Steam.
    """
    if target.exists() or target.is_symlink():
        same = source.stat()
        if source.suffix != ".vpk" and target.stat().st_size == same.st_size \
                and target.stat().st_mtime == same.st_mtime:
            return
        if source.suffix == ".vpk" and target.exists() and os.path.samefile(source, target):
            return
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix == ".vpk":
        for link in (os.link, os.symlink):
            try:
                link(source, target)
                return
            except OSError:
                pass
    shutil.copy2(source, target)


def install(destination: Path) -> None:
    """Assemble the toolkit in place; rerunning updates Valve files and keeps user work."""
    destination = destination.absolute()
    cache = destination / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    games = installed_games()
    for app, name in ((CS2, "Counter-Strike 2"), (DEADLOCK, "Deadlock")):
        found = games.get(app)
        print(f"{name}: {found or 'not installed; downloading from Steam'}")

    # Prefer the installed games; download everything else from the current depots.
    sources, missing = {}, {}
    for file in toolkit_files():
        game = games.get(file.app)
        if game and (local := contained_path(game, file.path)).is_file():
            sources[file.target] = local
        else:
            missing.setdefault(file.app, []).append(file)
    if missing:
        program = depot_downloader(cache)
        for app, files in missing.items():
            folder = cache / "depots" / app
            download(program, app, files, folder)
            for file in files:
                if (local := contained_path(folder, file.path)).is_file():
                    sources[file.target] = local
                else:
                    print(f"Skipped {file.path}: not in the current {file.app} depots")

    print(f"Placing {len(sources)} Valve files in {destination}", flush=True)
    for target, source in sources.items():
        place(source, contained_path(destination, target))

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


def main() -> int:
    """Install or update the toolkit and point at the editors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=default_destination(),
                        help="Toolkit directory; rerun to update it")
    args = parser.parse_args()
    try:
        install(args.destination)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"install: {error}", file=sys.stderr)
        return 1
    print(f"\nModlock Tools is ready in {args.destination.absolute()}.")
    print("Open Hammer.cmd, ModelDoc.cmd, or SFM.cmd there on Windows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
