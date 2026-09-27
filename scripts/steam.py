"""Read depot files from local Steam games and download the rest with DepotDownloader."""

from __future__ import annotations

import io
import os
import platform
import re
import struct
import subprocess
import urllib.request
import zipfile
from pathlib import Path

DEPOT_DOWNLOADER = "https://github.com/SteamRE/DepotDownloader/releases/latest/download"
MANIFEST_MAGIC = 0x71F617D0
DIRECTORY_FLAG = 0x40


def fetch(url: str) -> bytes:
    """Download a small file into memory."""
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def steam_roots() -> list[Path]:
    """Return the Steam installations on this machine, most likely first."""
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


def keyvalues(path: Path) -> dict:
    """Parse a Steam KeyValues text file such as an app manifest into nested dicts."""
    text = path.read_text(encoding="utf-8", errors="replace")
    stack, key = [{}], None
    for quoted, brace in re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text):
        if brace == "{":
            stack[-1][key] = {}
            stack.append(stack[-1][key])
            key = None
        elif brace == "}":
            stack.pop()
        elif key is None:
            key = quoted
        else:
            stack[-1][key] = quoted.replace("\\\\", "\\")
            key = None
    return stack[0]


def installed_depots() -> dict[str, tuple[Path, Path]]:
    """Map each installed depot to its game directory and Steam's manifest of it.

    Steam lists a game's installed depots and their manifest IDs in
    appmanifest_<app>.acf, and keeps each manifest in depotcache.
    """
    found = {}
    for root in steam_roots():
        libraries = [root]
        folders = root / "steamapps/libraryfolders.vdf"
        if folders.is_file():
            listed = keyvalues(folders).get("libraryfolders", {})
            libraries += [Path(entry["path"]) for entry in listed.values()
                          if isinstance(entry, dict) and "path" in entry]
        for library in libraries:
            for manifest in sorted(library.glob("steamapps/appmanifest_*.acf")):
                state = keyvalues(manifest).get("AppState", {})
                game = library / "steamapps/common" / state.get("installdir", "")
                for depot, info in state.get("InstalledDepots", {}).items():
                    cached = root / "depotcache" / f"{depot}_{info.get('manifest')}.manifest"
                    if state.get("installdir") and game.is_dir() and cached.is_file():
                        found.setdefault(depot, (game, cached))
    return found


def fields(data: bytes):
    """Yield (field number, value) from a protobuf message; bytes for length fields."""
    position = 0
    while position < len(data):
        key, position = varint(data, position)
        number, kind = key >> 3, key & 7
        if kind == 0:
            value, position = varint(data, position)
        elif kind == 1:
            value, position = data[position:position + 8], position + 8
        elif kind == 2:
            length, position = varint(data, position)
            value, position = data[position:position + length], position + length
        elif kind == 5:
            value, position = data[position:position + 4], position + 4
        else:
            raise ValueError(f"Unsupported protobuf wire type {kind}")
        yield number, value


def varint(data: bytes, position: int) -> tuple[int, int]:
    """Decode a protobuf varint at position; return it and the next position."""
    result = shift = 0
    while True:
        byte = data[position]
        position += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, position
        shift += 7


def manifest_files(path: Path) -> list[str]:
    """List the file paths in a Steam depot manifest, with forward slashes.

    The file starts with Steam's ContentManifestPayload: a magic number, a
    length, then one FileMapping message (field 1) per file or directory.
    """
    data = path.read_bytes()
    magic, length = struct.unpack_from("<II", data)
    if magic != MANIFEST_MAGIC:
        raise ValueError(f"Not a Steam depot manifest: {path.name}")
    files = []
    for number, mapping in fields(data[8:8 + length]):
        if number != 1:
            continue
        values = dict(fields(mapping))
        if not values.get(3, 0) & DIRECTORY_FLAG:
            files.append(values[1].decode("utf-8").replace("\\", "/"))
    return files


def depot_downloader(cache: Path) -> Path:
    """Download the latest prebuilt DepotDownloader for this machine once."""
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[platform.system()]
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    folder = cache / f"depotdownloader-{system}-{arch}"
    program = folder / ("DepotDownloader.exe" if system == "windows" else "DepotDownloader")
    if not program.is_file():
        print("Downloading DepotDownloader", flush=True)
        zipfile.ZipFile(io.BytesIO(fetch(f"{DEPOT_DOWNLOADER}/DepotDownloader-{system}-{arch}.zip"))
                        ).extractall(folder)
        program.chmod(0o755)
    return program


def download(program: Path, app: str, depot: str, include: tuple[str, ...],
             folder: Path, account: Path) -> None:
    """Bring a depot's included files in folder up to the current Windows version.

    Steam denies anonymous sessions these depots. The first run shows a QR code
    for the Steam mobile app and saves a login token in DepotDownloader's own
    storage; account records the account name so later runs reuse it. When the
    saved login fails, the next attempt asks for a new QR scan. DepotDownloader
    downloads only changed files and deletes files the new version drops.
    """
    folder.mkdir(parents=True, exist_ok=True)
    filelist = folder.parent / f"{depot}.files.txt"
    filelist.write_text("".join(f"regex:^{re.escape(prefix)}\n" for prefix in include),
                        encoding="utf-8")
    command = [str(program), "-app", app, "-depot", depot, "-os", "windows", "-osarch", "64",
               "-filelist", str(filelist), "-dir", str(folder), "-remember-password"]
    for attempt in range(2):
        name = account.read_text(encoding="utf-8").strip() if account.is_file() else ""
        login = ["-username", name] if name else ["-qr"]
        if not name:
            print("Scan the QR code with the Steam mobile app to log in.", flush=True)
        with subprocess.Popen(command + login, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
                              text=True, errors="replace") as process:
            for line in process.stdout:
                print(line, end="", flush=True)
                if match := re.search(r"login with -username (\S+) -remember-password", line):
                    account.write_text(match.group(1), encoding="utf-8")
        if process.returncode == 0:
            return
        if not name:
            break
        account.unlink(missing_ok=True)
    raise subprocess.CalledProcessError(process.returncode, command)


def downloaded_manifest(folder: Path, depot: str) -> str | None:
    """Return the manifest ID DepotDownloader last saved for a depot folder."""
    saved = sorted((folder / ".DepotDownloader").glob(f"{depot}_*.manifest"),
                   key=lambda path: path.stat().st_mtime)
    return saved[-1].stem.split("_")[1] if saved else None
