"""Check that the installer follows the current depots and keeps user work on rerun."""

import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install
import steam
from toolkit import Depot


def varint(value: int) -> bytes:
    """Encode a protobuf varint."""
    out = bytearray()
    while value >= 0x80:
        out.append(value & 0x7F | 0x80)
        value >>= 7
    return bytes(out + bytes([value]))


def depot_manifest(files: list[str], directories: list[str]) -> bytes:
    """Encode a Steam depot manifest listing files and directories."""
    payload = b""
    for name, flags in [(name, 0) for name in files] + [(name, 0x40) for name in directories]:
        encoded = name.replace("/", "\\").encode()
        mapping = b"\x0a" + varint(len(encoded)) + encoded + b"\x18" + varint(flags)
        payload += b"\x0a" + varint(len(mapping)) + mapping
    return struct.pack("<II", steam.MANIFEST_MAGIC, len(payload)) + payload


class InstallTest(unittest.TestCase):
    """Run the installer against a fake Steam library and a fake downloader."""

    def test_follows_depot_changes_and_keeps_user_work(self) -> None:
        """Installed depots are linked, the rest downloaded, and dropped files removed."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam_root, library = root / "Steam", root / "Library"
            (steam_root / "steamapps").mkdir(parents=True)
            (steam_root / "depotcache").mkdir()
            (steam_root / "steamapps/libraryfolders.vdf").write_text(
                f'"libraryfolders"\n{{\n "1"\n {{\n  "path"  "{library.as_posix()}"\n }}\n}}\n')
            (library / "steamapps").mkdir(parents=True)
            (library / "steamapps/appmanifest_1422450.acf").write_text(
                '"AppState"\n{\n "installdir"  "Deadlock"\n "InstalledDepots"\n {\n'
                '  "1422451"\n  {\n   "manifest"  "7"\n  }\n }\n}\n')
            game = library / "steamapps/common/Deadlock"
            (game / "game/citadel/bin").mkdir(parents=True)
            for name in ("pak01_dir.vpk", "pak01_000.vpk", "bin/client.dll"):
                (game / "game/citadel" / name).write_bytes(b"deadlock")
            (steam_root / "depotcache/1422451_7.manifest").write_bytes(depot_manifest(
                ["game/citadel/pak01_dir.vpk", "game/citadel/pak01_000.vpk",
                 "game/citadel/bin/client.dll"], ["game/citadel"]))

            profile = [Depot("730", "2347771", ("game/bin/",)),
                       Depot("1422450", "1422451", ("game/citadel/pak01_",))]
            depot_contents = {"game/bin/tools.dll": b"tool", "game/bin/old.dll": b"old"}
            downloads = []

            def download(program, app, depot, include, folder, account):
                downloads.append(depot)
                for name, data in depot_contents.items():
                    (folder / name).parent.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(data)
                (folder / ".DepotDownloader").mkdir(exist_ok=True)
                (folder / f".DepotDownloader/{depot}_9.manifest").write_bytes(b"")

            destination = root / "modlock-tools"
            with mock.patch.object(steam, "steam_roots", return_value=[steam_root]), \
                    mock.patch.object(install, "depots", return_value=profile), \
                    mock.patch.object(steam, "depot_downloader", return_value=Path("dd")), \
                    mock.patch.object(steam, "download", side_effect=download), \
                    mock.patch.object(install, "zig", return_value=Path("zig")), \
                    mock.patch.object(install, "build",
                                      side_effect=lambda zig, output: output.write_bytes(b"exe")):
                install.install(destination)
                sample = destination / "content/citadel_addons/modlock_sample/models/probe.vmdl"
                sample.write_text("my model")
                self.assertEqual((destination / "game/bin/old.dll").read_bytes(), b"old")

                # Valve drops old.dll in the next version.
                del depot_contents["game/bin/old.dll"]
                (root / "modlock-tools/.cache/depots/2347771/game/bin/old.dll").unlink()
                install.install(destination)

            package = destination / "game/citadel_assets/pak01_dir.vpk"
            self.assertTrue(os.path.samefile(package, game / "game/citadel/pak01_dir.vpk"))
            self.assertFalse((destination / "game/citadel_assets/bin").exists())
            self.assertEqual((destination / "game/bin/tools.dll").read_bytes(), b"tool")
            self.assertFalse((destination / "game/bin/old.dll").exists())
            self.assertEqual(downloads, ["2347771"] * 2)
            self.assertEqual(sample.read_text(), "my model")
            self.assertTrue((destination / "game/citadel/gameinfo.gi").is_file())
            self.assertTrue((destination / "Update.cmd").is_file())
            state = json.loads((destination / ".cache/installed.json").read_text())
            self.assertEqual(state["depots"], {"2347771": "9", "1422451": "7"})


if __name__ == "__main__":
    unittest.main()
