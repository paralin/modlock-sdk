#!/usr/bin/env python3
"""Compile a Panorama or model addon twice and record reproducible output hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

XML = '<root><scripts><include src="file://{resources}/scripts/probe.js" /></scripts><Panel><Label text="SDK compiler probe" /></Panel></root>\n'
JS = '(function () { $.Msg("sdk_compiler_probe_loaded"); })();\n'
MODEL = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc28:version{fb63b6ca-f435-4aa0-a2c7-c66ddc651dca} -->
{
    rootNode = {
        _class = "RootNode"
        children = [
            { _class = "RenderMeshList" children = [
                { _class = "RenderMeshFile" name = "sdk_cube" filename = "models/probe.obj" }
            ] }
        ]
    }
}
'''
MESH = '''o sdk_cube
v -16 -16 -16
v 16 -16 -16
v 16 16 -16
v -16 16 -16
v -16 -16 16
v 16 -16 16
v 16 16 16
v -16 16 16
usemtl materials/dev/color_purple.vmat
f 1 4 3 2
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
'''


def digest(path: Path) -> str:
    """Hash the complete file without retaining its contents."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def windows_path(path: Path, wine: bool) -> str:
    """Quote an absolute path for cmd.exe, refusing shell expansion characters."""
    text = str(path.resolve())
    if any(character in text for character in '%!"\r\n'):
        raise ValueError("cmd.exe paths must not contain percent, exclamation, quote, or newline characters")
    if wine:
        text = "Z:" + text.replace("/", "\\")
    return '"' + text + '"'


def probe(sdk: Path, compiler: Path, mod: str, addon: str, report: Path, proton: Path | None, steam: Path | None, kind: str = "panorama") -> dict:
    """Create a fresh addon, compile twice, and retain logs and verified artifacts.

    The SDK must be a disposable copy. Proton uses a new prefix beside the report;
    only that prefix's server is stopped. A graphical DISPLAY must be provided
    on Linux, including for this console compiler. Each run has a 90s deadline.
    """
    # Refuse an existing addon so acceptance cannot overwrite user-authored assets.
    if not re.fullmatch(r"[a-z][a-z0-9_]*", addon):
        raise ValueError("Addon name must contain lowercase letters, digits, and underscores")
    sdk, compiler, report = sdk.resolve(), compiler.resolve(), report.resolve()
    folder = "panorama" if kind == "panorama" else "models"
    content = sdk / "content" / f"{mod}_addons" / addon / folder
    output = sdk / "game" / f"{mod}_addons" / addon / folder
    gameinfo = sdk / "game" / mod / "gameinfo.gi"
    if content.parent.exists() or output.parent.exists() or report.exists():
        raise ValueError("Probe addon or report exists; choose a new --addon and --report")
    if compiler.name != "resourcecompiler.exe":
        raise ValueError("--compiler must identify Valve's resourcecompiler.exe")
    if not compiler.is_file() or not gameinfo.is_file():
        raise ValueError("Compiler or gameinfo.gi is absent; assemble the selected profile first")
    report.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    prefix = report.with_suffix(".compatdata")
    wine = proton.resolve().parent / "files/bin/wine" if proton else None
    command = ["cmd.exe", "/d", "/v:off", "/c"]
    if wine is not None:
        if steam is None:
            raise ValueError("--proton requires --steam pointing to the Steam client installation")
        prefix.mkdir()
        environment.update(WINEPREFIX=str(prefix / "pfx"), WINEDEBUG="-all",
                           STEAM_COMPAT_DATA_PATH=str(prefix),
                           STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam.resolve()),
                           SteamAppId="730", SteamGameId="730", PROTON_USE_WINED3D="1",
                           PROTON_LOG="1", PROTON_LOG_DIR=str(prefix))
        command = [str(wine.resolve()), "cmd", "/d", "/v:off", "/c"]
    elif os.name != "nt":
        raise ValueError("Use Windows, or provide --proton and --steam on Linux with DISPLAY set")

    # Exercise a source dependency and preserve identical fixture bytes on each OS.
    if kind == "panorama":
        fixtures = {"layout/probe.xml": XML, "scripts/probe.js": JS}
        input_name = "layout/probe.xml"
        outputs = ("layout/probe.vxml_c", "scripts/probe.vjs_c")
    else:
        fixtures = {"probe.vmdl": MODEL, "probe.obj": MESH}
        input_name = "probe.vmdl"
        outputs = ("probe.vmdl_c",)
    for name, text in fixtures.items():
        path = content / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    result = {
        "status": "failed", "runtime": "Valve Proton Wine with WineD3D" if wine else "Windows",
        "compiler_sha256": digest(compiler),
        "compiler_dll_sha256": digest(compiler.with_suffix(".dll")),
        "gameinfo_sha256": digest(gameinfo),
        "mod": mod, "addon": addon, "kind": kind,
        "sources": {name: {"bytes": (content / name).stat().st_size, "sha256": digest(content / name)}
                    for name in fixtures},
        "runs": [],
    }
    try:
        # Proton installs the Windows runtime libraries missing from a bare prefix.
        if proton is not None:
            with report.with_suffix(".bootstrap.log").open("wb") as bootstrap:
                subprocess.run([str(proton.resolve()), "run", "cmd", "/c", "exit"],
                               env=environment, stdout=bootstrap, stderr=subprocess.STDOUT,
                               timeout=90, check=True)
            result["proton_version"] = (proton.resolve().parent / "version").read_text().strip()

        # cmd.exe redirection captures the binlaunch executable's child output.
        for iteration in range(2):
            log = report.with_suffix(f".run{iteration + 1}.log")
            invocation = (
                'resourcecompiler.exe -game '
                f'{windows_path(gameinfo.parent, wine is not None)} -i '
                f'{windows_path(content / input_name, wine is not None)} '
                f'-nop4 -f > {windows_path(log, wine is not None)} 2>&1'
            )
            batch = report.with_suffix(f".run{iteration + 1}.cmd")
            batch.write_bytes(("@echo off\r\n" + invocation + "\r\nexit /b %errorlevel%\r\n").encode("utf-8"))
            completed = subprocess.run(
                command + [windows_path(batch, wine is not None)[1:-1]], cwd=compiler.parent, env=environment,
                capture_output=True, timeout=90, check=False,
            )
            if not log.exists():
                log.write_bytes(completed.stdout + completed.stderr)
            row = {"exit_code": completed.returncode, "log": log.name, "artifacts": {}}
            result["runs"].append(row)
            if completed.returncode:
                raise RuntimeError(f"Compiler exited {completed.returncode}; inspect {log}")
            for relative in outputs:
                artifact = output / relative
                if not artifact.is_file() or artifact.stat().st_size == 0:
                    raise RuntimeError(f"Compiler produced no resource: {artifact}; inspect {log}")
                row["artifacts"][relative] = {"bytes": artifact.stat().st_size, "sha256": digest(artifact)}
        if result["runs"][0]["artifacts"] != result["runs"][1]["artifacts"]:
            raise RuntimeError("Forced recompilation changed the resource hashes")
        result["status"] = f"passed: repeated {kind} compilation"
        return result
    finally:
        # Preserve failure evidence and release only the Wine server created here.
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if wine is not None:
            subprocess.run([str(wine.resolve().with_name("wineserver")), "-k"], env=environment, timeout=10, check=False)
            subprocess.run([str(wine.resolve().with_name("wineserver")), "-w"], env=environment, timeout=10, check=True)
            shutil.rmtree(prefix)


def main() -> int:
    """Run the probe and report the artifact and failure-log locations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True, help="Isolated assembled SDK root")
    parser.add_argument("--compiler", type=Path, help="Compiler executable, default SDK/game/bin/win64/resourcecompiler.exe")
    parser.add_argument("--mod", choices=("csgo", "citadel", "dota"), required=True)
    parser.add_argument("--addon", default="modlock_sdk_probe")
    parser.add_argument("--kind", choices=("panorama", "model"), default="panorama")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--proton", type=Path, help="Valve Proton's proton script on Linux")
    parser.add_argument("--steam", type=Path, help="Steam client installation used by Proton")
    args = parser.parse_args()
    try:
        result = probe(args.sdk, args.compiler or args.sdk / "game/bin/win64/resourcecompiler.exe",
                       args.mod, args.addon, args.report, args.proton, args.steam, args.kind)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"compiler_probe: {error}", file=sys.stderr)
        return 1
    print(f"{result['status']}; report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
