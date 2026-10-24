"""The toolkit's layout: which Valve files it takes and the files it adds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from compiler_probe import JS, MESH, MODEL, XML

ROOT = Path(__file__).resolve().parents[1]
ASSETS = "game/citadel_assets/"
SAMPLE = "content/citadel_addons/modlock_sample/"
INSTALLER = "https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.ps1"
# The editors are Dota's and the compiler Deadlock's, and their animation
# libraries disagree on one class, CNmSoundEvent, so the engine's schema check
# would abort the editors. The engine looks a switch up by the MurmurHash2 of its
# lowercase name; this name hashes, as the switch that turns the abort into a
# warning does, to 0xd96c98b0.
SCHEMA_MISMATCH_WARNS = "-ignaaw0gjr0"
EDITOR_ARGS = ("-tools", "-insecure", "-novid", "-console", "-condebug", "-playtest",
               SCHEMA_MISMATCH_WARNS)

# Empty directories the editors expect to exist.
PROJECT_DIRS = ("content/citadel/", "content/citadel_assets/", "content/core_deadlock/",
                "game/citadel/cfg/", "game/citadel_addons/modlock_sample/",
                "game/citadel_community_addons/")

MODELS = '@include "models_base.fgd"\n@include "models_base_breakables.fgd"\n'


@dataclass(frozen=True)
class Depot:
    """A Valve depot and where the toolkit puts the files it takes from it.

    paths maps a depot path prefix to a toolkit path prefix, or to a list of
    them for a file needed under several names. A file goes where its longest
    matching prefix sends it, so one file can be renamed inside a directory the
    depot otherwise contributes as is.
    """

    app: str
    depot: str
    paths: dict[str, str | list[str]]

    @property
    def include(self) -> tuple[str, ...]:
        """The depot path prefixes the toolkit takes."""
        return tuple(self.paths)

    def targets(self, path: str) -> list[str]:
        """Return where a depot file goes in the toolkit; empty to leave it out."""
        prefixes = [prefix for prefix in self.paths if path.startswith(prefix)]
        if not prefixes:
            return []
        prefix = max(prefixes, key=len)
        targets = self.paths[prefix]
        return [target + path.removeprefix(prefix)
                for target in ([targets] if isinstance(targets, str) else targets)]


def depots(root: Path = ROOT) -> list[Depot]:
    """Read the depots in overlay order: a later depot's file replaces an earlier one's."""
    profile = json.loads((root / "profiles/toolkit.json").read_text(encoding="utf-8"))
    return [Depot(row["app"], row["depot"], row["paths"]) for row in profile["depots"]]


def contained_path(root: Path, relative: str) -> Path:
    """Resolve a portable relative path inside root, rejecting traversal and symlink escape.

    Only the directories are resolved: the file itself may be a symbolic link
    the installer placed to a package in the Steam library.
    """
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Expected a relative portable path: {relative!r}")
    root = root.resolve()
    result = root.joinpath(*path.parts)
    if not result.parent.resolve().is_relative_to(root):
        raise ValueError(f"Path escapes its root: {relative!r}")
    return result


def authored(root: Path, programs: Path) -> dict[str, bytes | Path]:
    """Return the project files the toolkit adds to Valve's, by toolkit path.

    programs is the directory build_programs wrote the Windows programs to.
    """
    files = {
        "README.md": root / "bundle/README.md",
        "game/bin/win64/sdk-launcher.exe": programs / "sdk-launcher.exe",
        "game/bin/win64/vrad3.exe": programs / "vrad3.exe",
        "game/citadel/gameinfo.gi": root / "metadata/citadel-tools-gameinfo.gi",
        "game/citadel/models_gamedata.fgd": MODELS.encode(),
        "game/citadel/citadel.fgd": root / "metadata/citadel.fgd",
        SAMPLE + "models/probe.vmdl": MODEL.encode(),
        SAMPLE + "models/probe.obj": MESH.encode(),
        SAMPLE + "panorama/layout/probe.xml": XML.encode(),
        SAMPLE + "panorama/scripts/probe.js": JS.encode(),
        "Update.cmd": (
            '@echo off\r\nset "MODLOCK_TOOLS_DIR=%~dp0."\r\n'
            'powershell -NoProfile -ExecutionPolicy Bypass -Command '
            f'"irm {INSTALLER} | iex"\r\npause\r\n'
        ).encode(),
    }
    for name, options in {
        "Hammer": "+show_tool hammer",
        "ModelDoc": "-asset models/probe.vmdl +show_tool modeldoc_editor",
        "SFM": "+show_tool sfm",
    }.items():
        files[f"{name}.cmd"] = (
            '@echo off\r\nsetlocal\r\ncd /d "%~dp0game\\bin\\win64"\r\n'
            f'sdk-launcher.exe {" ".join(EDITOR_ARGS)} -addon modlock_sample {options}\r\n'
            'if errorlevel 1 pause\r\n'
        ).encode()
    return files
