"""Check installed-file selection through the real assembly boundary."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from assemble_sdk import assemble
from installed_toolchain import resolve


class InstalledToolchainTest(unittest.TestCase):
    """An installed game may contain another version of a downloaded tools file."""

    def test_uses_verified_fallback_without_changing_steam_files(self) -> None:
        """Assemble the correct bytes, then refuse when no source matches."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam, depot = root / "steam", root / "depot"
            steam.mkdir()
            depot.mkdir()
            (steam / "tool.dll").write_bytes(b"other version")
            (depot / "tool.dll").write_bytes(b"pinned version")
            recipe, resolved = root / "pinned.json", root / "resolved.json"
            recipe.write_text(json.dumps({"profile": {"depots": []}, "files": [
                {"source": "valve-depot", "from": "tool.dll", "to": "tool.dll",
                 "sha256": hashlib.sha256(b"pinned version").hexdigest()}
            ]}))
            resolve(recipe, [steam, depot], resolved)
            assemble(resolved, root / "sdk")
            self.assertEqual((root / "sdk/tool.dll").read_bytes(), b"pinned version")
            self.assertEqual((steam / "tool.dll").read_bytes(), b"other version")
            (depot / "tool.dll").unlink()
            with self.assertRaisesRegex(ValueError, "Missing or changed pinned files"):
                resolve(recipe, [steam, depot], root / "invalid.json")
            self.assertFalse((root / "invalid.json").exists())


if __name__ == "__main__":
    unittest.main()
