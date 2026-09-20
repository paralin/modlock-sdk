#!/usr/bin/env python3
"""Open SDK editors on a Windows desktop and record bounded startup evidence."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path


def owned_windows(pid: int) -> list[tuple[int, str]]:
    """Read visible window titles belonging only to the test process."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    windows = []

    def inspect(handle: int, _: int) -> bool:
        """Collect the test's visible top-level windows without interacting with them."""
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(handle):
            title = ctypes.create_unicode_buffer(2048)
            user32.GetWindowTextW(handle, title, len(title))
            windows.append((handle, title.value))
        return True

    user32.EnumWindows(callback_type(inspect), 0)
    return windows


def probe(sdk: Path, reports: Path, addon: str, tool: str) -> dict:
    """Observe one editor for 35 seconds, then close only its test process tree.

    Use a disposable SDK in an interactive desktop session. Window presence and
    loaded modules establish startup, not map authoring or successful rendering.
    ModelDoc opens the model fixture created by compiler_probe.py in the addon.
    """
    executable = sdk / "game/bin/win64/sdk-launcher.exe"
    console = sdk / "game/citadel/console.log"
    prefix = reports / tool
    if console.exists():
        console.replace(prefix.with_suffix(".prior-console.log"))
    command = [str(executable), "-tools", "-insecure", "-novid", "-console", "-condebug", "-playtest"]
    if tool == "modeldoc_editor":
        command += ["-addon", addon, "-asset", "models/probe.vmdl"]
    command += ["+show_tool", tool]
    result = {"command": command, "tool": tool, "observation": "Startup only; inspect windows, modules and console errors"}
    for name in ("sdk-launcher.exe", "engine2.dll"):
        with executable.with_name(name).open("rb") as stream:
            result[name + "_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    for name, field in (("gameinfo.gi", "gameinfo"), ("citadel.fgd", "entity_fgd"),
                        ("models_gamedata.fgd", "models_gamedata")):
        with (sdk / "game/citadel" / name).open("rb") as stream:
            result[field + "_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()

    # A compiler/engine error must become a report instead of a blocking OS dialog.
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    with prefix.with_suffix(".stdout.log").open("wb") as stream:
        process = subprocess.Popen(command, cwd=executable.parent, stdout=stream, stderr=subprocess.STDOUT)
        result["pid"] = process.pid
        try:
            try:
                result["exit_code"] = process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                result["alive_after_seconds"] = 35
                windows = owned_windows(process.pid)
                result["windows"] = [title for _, title in windows]
                for handle, title in windows:
                    if "Failed" not in title and "Error" not in title:
                        continue
                    details = subprocess.run([
                        "powershell", "-NoProfile", "-Command",
                        "Add-Type -AssemblyName UIAutomationClient; "
                        f"$dialog = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{handle}); "
                        "$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants, "
                        "[System.Windows.Automation.Condition]::TrueCondition) | "
                        "ForEach-Object { $_.Current.Name }",
                    ], capture_output=True, text=True, timeout=10, check=True)
                    result.setdefault("dialogs", {})[title] = details.stdout.strip()
                inspection = subprocess.run([
                    "powershell", "-NoProfile", "-Command",
                    f"(Get-Process -Id {process.pid}).Modules | Select-Object ModuleName,FileName | ConvertTo-Json",
                ], capture_output=True, text=True, timeout=10, check=True)
                modules = json.loads(inspection.stdout)
                result["modules"] = [entry for entry in modules
                                     if Path(entry["FileName"]).is_relative_to(sdk)]
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
                for handle, _ in windows:
                    user32.PostMessageW(handle, 0x0010, 0, 0)
                try:
                    result["close_exit_code"] = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    result["cleanup"] = "Stopped test process tree after close deadline"
        finally:
            # Failure during inspection must not leave an editor running unattended.
            if process.poll() is None:
                subprocess.run(["taskkill", "/pid", str(process.pid), "/t", "/f"],
                               capture_output=True, timeout=10, check=False)
                process.wait(timeout=10)
            prefix.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            if console.is_file():
                with console.open("rb") as log:
                    prefix.with_suffix(".console.log").write_bytes(log.read())
    return result


def main() -> int:
    """Run fresh editor observations; evidence needs review before acceptance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True, help="New report directory")
    parser.add_argument("--addon", required=True, help="Addon containing the compiled model probe")
    parser.add_argument("--tool", action="append", choices=("hammer", "modeldoc_editor", "sfm"), help="Selected tool; default all three")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Run in an interactive Windows desktop session")
    selected = args.tool or ("hammer", "modeldoc_editor", "sfm")
    if "modeldoc_editor" in selected:
        fixture = args.sdk / "content/citadel_addons" / args.addon / "models/probe.vmdl"
        if not fixture.is_file():
            parser.error("Compile the model probe first and pass its addon name with --addon")
    try:
        args.reports.mkdir(parents=True)
        for tool in selected:
            result = probe(args.sdk.resolve(), args.reports.resolve(), args.addon, tool)
            print(f"{tool}: {result.get('windows', [])}; inspect {args.reports / tool}", flush=True)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"editor_probe: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
