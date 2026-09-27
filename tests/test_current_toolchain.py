"""Exercise archive-independent selection and verification through real files."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from assemble_sdk import assemble
from current_toolchain import build_profile


class CurrentToolchainTest(unittest.TestCase):
    """A pinned profile must reproduce its selected Valve paths without a ZIP."""

    def setUp(self) -> None:
        """Create two depot manifests sharing an identical compiler dependency."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = b"current compiler dependency\n"
        self.profile = self.root / "profile.json"
        depots = []
        for depot in ("2", "3"):
            depots.append({"app": "1", "depot": depot, "manifest": "4", "include": ["game/bin/"]})
            (self.root / f"manifest_{depot}_4.txt").write_text(
                f"Content Manifest for Depot {depot}\nManifest ID / date : 4 / fixture\n"
                "Total number of files : 3\nSize Chunks File SHA Flags Name\n"
                f"{len(self.payload)} 1 {hashlib.sha1(self.payload).hexdigest()} 0 game/bin/tool.dll\n"
                f"0 0 {'0' * 40} 0 game/bin/__init__.py\n"
                f"4 1 {hashlib.sha1(b'map!').hexdigest()} 0 game/maps/unused.vpk\n",
                encoding="utf-8",
            )
            target = self.root / "inputs" / depot / "game/bin/tool.dll"
            target.parent.mkdir(parents=True)
            target.write_bytes(self.payload)
            (target.parent / "__init__.py").write_bytes(b"")
        self.profile.write_text(json.dumps({"depots": depots}), encoding="utf-8")

    def test_select_and_assemble_without_a_reference_archive(self) -> None:
        """Select native paths, preserve empty files, and combine identical overlaps."""
        build_profile(self.profile, self.root, None, self.root / "lists")
        self.assertEqual((self.root / "lists/2.files.txt").read_text(), "game/bin/tool.dll\ngame/bin/__init__.py\n")
        recipe_path = self.root / "recipe.json"
        recipe = build_profile(self.profile, self.root, self.root / "inputs", recipe_path)
        self.assertEqual(len(recipe["files"]), 2)
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        assemble(recipe_path, self.root / "output")
        self.assertEqual((self.root / "output/game/bin/tool.dll").read_bytes(), self.payload)
        self.assertEqual((self.root / "output/game/bin/__init__.py").read_bytes(), b"")

    def test_changed_download_is_rejected_before_recipe_publication(self) -> None:
        """A present but changed DLL cannot enter the current toolchain recipe."""
        (self.root / "inputs/2/game/bin/tool.dll").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "differ from Steam manifest"):
            build_profile(self.profile, self.root, self.root / "inputs", self.root / "recipe.json")

    def test_conflicting_depot_versions_cannot_share_an_output_path(self) -> None:
        """Individually valid downloads must agree before their trees are merged."""
        replacement = self.payload.replace(b"current", b"another")
        (self.root / "inputs/3/game/bin/tool.dll").write_bytes(replacement)
        manifest = self.root / "manifest_3_4.txt"
        manifest.write_text(manifest.read_text().replace(
            hashlib.sha1(self.payload).hexdigest(), hashlib.sha1(replacement).hexdigest()
        ), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Conflicting Valve depot files"):
            build_profile(self.profile, self.root, self.root / "inputs", self.root / "recipe.json")


if __name__ == "__main__":
    unittest.main()
