"""The toolkit's layout: which Valve files it takes and the files it adds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from compiler_probe import JS, MESH, MODEL, XML

ROOT = Path(__file__).resolve().parents[1]
DEADLOCK = "1422450"
ASSETS = "game/citadel_assets/"
SAMPLE = "content/citadel_addons/modlock_sample/"
INSTALLER = "https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.ps1"

# Empty directories the editors expect to exist.
PROJECT_DIRS = ("content/citadel/", "content/citadel_assets/", "game/citadel/cfg/",
                "game/citadel_addons/modlock_sample/", "game/citadel_community_addons/")

MODELS = '@include "models_base.fgd"\n@include "models_base_breakables.fgd"\n'


@dataclass(frozen=True)
class Depot:
    """A Valve depot and the path prefixes the toolkit takes from it."""

    app: str
    depot: str
    include: tuple[str, ...]

    def target(self, path: str) -> str | None:
        """Return where a depot file goes in the toolkit, or None to leave it out.

        Deadlock contributes only its asset packages, mounted as citadel_assets;
        its game code stays with the game.
        """
        if not path.startswith(self.include):
            return None
        if self.app != DEADLOCK:
            return path
        if not path.endswith(".vpk"):
            return None
        return ASSETS + path.removeprefix("game/citadel/")


def depots(root: Path = ROOT) -> list[Depot]:
    """Read the depots in overlay order: a later depot's file replaces an earlier one's."""
    profile = json.loads((root / "profiles/toolkit.json").read_text(encoding="utf-8"))
    return [Depot(row["app"], row["depot"], tuple(row["include"])) for row in profile["depots"]]


def contained_path(root: Path, relative: str) -> Path:
    """Resolve a portable relative path inside root, rejecting traversal and symlink escape."""
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"Expected a relative portable path: {relative!r}")
    result = root.joinpath(*path.parts).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes its root: {relative!r}")
    return result


def authored(root: Path, launcher: Path) -> dict[str, bytes | Path]:
    """Return the project files the toolkit adds to Valve's, by toolkit path."""
    files = {
        "README.md": root / "bundle/README.md",
        "game/bin/win64/sdk-launcher.exe": launcher,
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
            'sdk-launcher.exe -tools -insecure -novid -console -condebug -playtest '
            f'-addon modlock_sample {options}\r\n'
            'if errorlevel 1 pause\r\n'
        ).encode()
    return files
