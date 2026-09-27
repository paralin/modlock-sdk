"""Exercise release reproducibility and pinned-input failure with real ZIP files."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release_bundle import build


class ReleaseBundleTest(unittest.TestCase):
    """Verify the delivery boundary rather than compression implementation details."""

    def fixture(self, root: Path) -> tuple[Path, Path, Path]:
        """Create pinned inputs with one excluded gameplay DLL and two asset parts."""
        for directory in ("recipes", "metadata", "bundle", "tools", "runtime"):
            (root / directory).mkdir()
        for name in ("bundle/README.md", "REPRODUCING.md", "metadata/citadel.fgd", "bundle/Install.ps1"):
            (root / name).write_text(name)
        (root / "VERSION").write_text("0.0.1\n")
        launcher = root / "launcher.exe"
        launcher.write_bytes(b"authored launcher")
        for profile, base, files in (
            ("current-cs2-tools", "tools", {"game/bin/win64/engine2.dll": b"tools"}),
            ("current-deadlock", "runtime", {"game/citadel/pak01_dir.vpk": b"directory",
                                             "game/citadel/pak01_000.vpk": b"chunk data",
                                             "game/citadel/bin/win64/client.dll": b"excluded"}),
        ):
            rows = []
            for name, data in files.items():
                path = root / base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                rows.append({"to": name, "sha256": hashlib.sha256(data).hexdigest()})
            (root / "recipes" / f"{profile}.json").write_text(json.dumps({"files": rows}))
        return root / "tools", root / "runtime", launcher

    def test_parts_reconstruct_sdk_and_ignore_input_timestamps(self) -> None:
        """Multiple archives install one complete tree and rebuild byte-identically."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools, runtime, launcher = self.fixture(root)
            first = build(root, tools, runtime, launcher, root / "first", "fixture", 10)
            os.utime(runtime / "game/citadel/pak01_dir.vpk", (100000, 100000))
            second = build(root, tools, runtime, launcher, root / "second", "fixture", 10)
            self.assertEqual(first, second)
            self.assertEqual(len(first["archives"]), 3)
            for archive in first["archives"]:
                with zipfile.ZipFile(root / "first" / archive["name"]) as zipped:
                    zipped.extractall(root / "installed")
            self.assertEqual((root / "installed/game/citadel_assets/pak01_dir.vpk").read_bytes(), b"directory")
            self.assertTrue((root / "installed/game/citadel_addons/modlock_sample").is_dir())
            self.assertFalse((root / "installed/game/citadel/bin").exists())
            with self.assertRaisesRegex(ValueError, "destination exists"):
                build(root, tools, runtime, launcher, root / "first", "fixture", 10)

    def test_changed_input_does_not_publish_release(self) -> None:
        """A changed asset fails packaging and preserves the original input."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools, runtime, launcher = self.fixture(root)
            source = runtime / "game/citadel/pak01_dir.vpk"
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "differs from pinned recipe"):
                build(root, tools, runtime, launcher, root / "release", "fixture", 10)
            self.assertFalse((root / "release").exists())
            self.assertEqual(source.read_bytes(), b"changed")
            self.assertEqual(list(root.glob(".release-*")), [])


if __name__ == "__main__":
    unittest.main()
