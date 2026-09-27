"""Check that a release unpacks to the installed toolkit and rebuilds identically."""

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release_bundle import build
from toolkit import ROOT


class ReleaseBundleTest(unittest.TestCase):
    """Pack a fake installed toolkit with real ZIP files."""

    def test_parts_reconstruct_toolkit_and_ignore_input_timestamps(self) -> None:
        """Several archives unpack to one toolkit, and a rebuild gives the same ZIPs."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            toolkit = root / "toolkit"
            files = {"game/bin/win64/engine2.dll": b"tools",
                     "game/citadel_assets/pak01_dir.vpk": b"directory",
                     "game/citadel_assets/pak01_000.vpk": b"chunk data"}
            for name, data in files.items():
                (toolkit / name).parent.mkdir(parents=True, exist_ok=True)
                (toolkit / name).write_bytes(data)
            (toolkit / ".cache").mkdir()
            (toolkit / ".cache/sdk-launcher.exe").write_bytes(b"launcher")
            (toolkit / ".cache/installed.json").write_text(
                json.dumps({"depots": {"1422451": "7"}, "files": sorted(files)}))

            first = build(ROOT, toolkit, root / "first", "fixture", 10)
            os.utime(toolkit / "game/citadel_assets/pak01_dir.vpk", (100000, 100000))
            second = build(ROOT, toolkit, root / "second", "fixture", 10)
            self.assertEqual(first, second)
            self.assertEqual(first["depots"], {"1422451": "7"})
            self.assertEqual(len(first["archives"]), 3)
            for archive in first["archives"]:
                with zipfile.ZipFile(root / "first" / archive["name"]) as zipped:
                    zipped.extractall(root / "installed")
            installed = root / "installed"
            self.assertEqual((installed / "game/citadel_assets/pak01_dir.vpk").read_bytes(),
                             b"directory")
            self.assertEqual((installed / "game/bin/win64/sdk-launcher.exe").read_bytes(),
                             b"launcher")
            self.assertTrue((installed / "game/citadel_addons/modlock_sample").is_dir())
            with self.assertRaisesRegex(ValueError, "destination exists"):
                build(ROOT, toolkit, root / "first", "fixture", 10)


if __name__ == "__main__":
    unittest.main()
