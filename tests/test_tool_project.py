"""Check that the authoring mount verifies assets and preserves existing data."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from tool_project import create


class ToolProjectTest(unittest.TestCase):
    """Exercise mount selection and failure cleanup with real files."""

    def test_mounts_only_verified_assets_and_preserves_existing_project(self) -> None:
        """Game DLLs stay outside the content mount and a rerun cannot replace it."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools, runtime, recipe, fgd = self.fixture(root)
            result = create(tools, runtime, recipe, fgd)
            self.assertEqual(result["asset_packages"], 1)
            self.assertEqual((tools / "game/citadel_assets/pak01_dir.vpk").read_bytes(), b"verified")
            self.assertFalse((tools / "game/citadel_assets/bin/win64/client.dll").exists())
            config = tools / "game/citadel/gameinfo.gi"
            config.write_text("user configuration")
            with self.assertRaisesRegex(ValueError, "Project path exists"):
                create(tools, runtime, recipe, fgd)
            self.assertEqual(config.read_text(), "user configuration")

    def test_changed_package_does_not_publish_a_project(self) -> None:
        """A mismatch removes the new mount and leaves source inputs intact."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools, runtime, recipe, fgd = self.fixture(root)
            source = runtime / "game/citadel/pak01_dir.vpk"
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "differs from recipe"):
                create(tools, runtime, recipe, fgd)
            self.assertFalse((tools / "game/citadel").exists())
            self.assertFalse((tools / "game/citadel_assets").exists())
            self.assertEqual(source.read_bytes(), b"changed")

    def fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        """Create the real manifest/file boundary needed by each acceptance check."""
        tools, runtime = root / "tools", root / "runtime"
        (tools / "game/core").mkdir(parents=True)
        (tools / "game/core/models_base.fgd").write_text("// Valve base fixture")
        (runtime / "game/citadel").mkdir(parents=True)
        (runtime / "game/citadel/pak01_dir.vpk").write_bytes(b"verified")
        recipe, fgd = root / "recipe.json", root / "citadel.fgd"
        recipe.write_text(json.dumps({"files": [
            {"to": "game/citadel/pak01_dir.vpk", "sha256": hashlib.sha256(b"verified").hexdigest()},
            {"to": "game/citadel/bin/win64/client.dll", "sha256": "unused"},
        ]}))
        fgd.write_text('// Inferred fixture\n')
        return tools, runtime, recipe, fgd


if __name__ == "__main__":
    unittest.main()
