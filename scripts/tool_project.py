#!/usr/bin/env python3
"""Mount verified Deadlock VPKs in a separate CS2 content-authoring project."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from assemble_sdk import contained_path

GAMEINFO = '''"GameInfo"
{
    game "Citadel asset tools"
    title "Citadel asset tools"
    GameData "citadel.fgd"
    LayeredOnMod core
    Engine2 { HasModAppSystems 0 }
    FileSystem
    {
        SteamAppId 1422450
        SearchPaths
        {
            Mod citadel
            Write citadel
            Game citadel
            Game core
            Mod core
            Game citadel_assets
            AddonRoot citadel_addons
            OfficialAddonRoot citadel_community_addons
        }
    }
    Hammer
    {
        fgd "citadel.fgd"
        GameFeatureSet CounterStrike
    }
    ModelDoc
    {
        models_gamedata "models_gamedata.fgd"
        features "animgraph;modelconfig"
    }
}
'''
MODELS = '@include "models_base.fgd"\n@include "models_base_breakables.fgd"\n'


def asset_path(path: str) -> str | None:
    """Map a Deadlock asset package to its tools-tree path; other files map to None."""
    if path.startswith(("game/citadel/pak01_", "game/citadel/maps/")) and path.endswith(".vpk"):
        return "game/citadel_assets/" + path.removeprefix("game/citadel/")
    return None


def create(tools: Path, runtime: Path, recipe: Path, fgd: Path) -> dict:
    """Add fresh project directories; preserve tool binaries and existing projects.

    Only manifest-selected asset VPKs enter the content mount. Every copied VPK
    must match the runtime recipe SHA-256. Failed creation removes its own files.
    Native game code, localization and shaders remain with their original build.
    """
    # Reserve distinct game/content mounts before copying any large payloads.
    tools, runtime = tools.resolve(), runtime.resolve()
    project = tools / "game/citadel"
    project_content = tools / "content/citadel"
    assets = tools / "game/citadel_assets"
    content = tools / "content/citadel_assets"
    for target in (project, project_content, assets, content):
        if target.exists() or target.is_symlink():
            raise ValueError(f"Project path exists; use a fresh tools assembly: {target}")
    if not (tools / "game/core/models_base.fgd").is_file():
        raise ValueError("Tools assembly is missing Valve's core ModelDoc definitions")
    fgd_bytes = fgd.read_bytes()
    original = json.loads(recipe.read_text(encoding="utf-8"))
    selected = [entry for entry in original["files"] if asset_path(entry["to"])]
    if not any(entry["to"] == "game/citadel/pak01_dir.vpk" for entry in selected):
        raise ValueError("Runtime recipe has no Citadel VPK directory")
    created = []
    try:
        # Copy compiled assets into a normal relative mount with a content counterpart.
        for target in (project, project_content, assets, content):
            target.mkdir(parents=True)
            created.append(target)
        for entry in selected:
            target = contained_path(tools, asset_path(entry["to"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(contained_path(runtime, entry["to"]), target)
            with target.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != entry["sha256"]:
                raise ValueError(f"Runtime resource differs from recipe: {entry['to']}")

        # Author explicit generic tools configuration; no game DLL is mounted.
        (project / "cfg").mkdir()
        (project / "gameinfo.gi").write_text(GAMEINFO, encoding="utf-8", newline="\n")
        (project / "citadel.fgd").write_bytes(fgd_bytes)
        (project / "models_gamedata.fgd").write_text(MODELS, encoding="utf-8", newline="\n")
        result = {"runtime_recipe_sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
                  "entity_fgd_sha256": hashlib.sha256(fgd_bytes).hexdigest(),
                  "gameinfo_sha256": hashlib.sha256(GAMEINFO.encode()).hexdigest(),
                  "models_gamedata_sha256": hashlib.sha256(MODELS.encode()).hexdigest(),
                  "asset_packages": len(selected), "status": "content project; editor and game acceptance pending"}
        (project / "assembly.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    except BaseException:
        # These directories were exclusively created by this operation.
        for target in reversed(created):
            shutil.rmtree(target)
        raise


def main() -> int:
    """Create the isolated content project and explain its acceptance boundary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--fgd", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = create(args.tools, args.runtime, args.recipe, args.fgd)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"tool_project: {error}", file=sys.stderr)
        return 1
    print(f"Mounted {result['asset_packages']} verified VPKs in {args.tools / 'game/citadel_assets'}")
    print("Ready for compiler probes; game loading, Hammer, ModelDoc, and S2FM remain separate checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
