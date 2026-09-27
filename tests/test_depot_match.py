"""Verify manifest selection and recipe publication through real files."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from assemble_sdk import assemble
from depot_match import make_recipe, merge_recipes, read_manifest, select


class DepotMatchTest(unittest.TestCase):
    """Exercise renamed outputs, malformed manifests, and changed payloads."""

    def setUp(self) -> None:
        """Create a two-target reference for one real depot payload."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = b"a verified test payload\n"
        self.sha1 = hashlib.sha1(self.payload).hexdigest()
        self.sha256 = hashlib.sha256(self.payload).hexdigest()
        self.reference = self.root / "reference.json"
        self.reference.write_text(json.dumps([
            {"path": name, "bytes": len(self.payload), "sha1": self.sha1, "sha256": self.sha256}
            for name in ("game/bin/tool.dll", "game/bin_tools/tool.dll")
        ]), encoding="utf-8")
        self.manifest = self.root / "manifest.txt"
        self.manifest.write_text(
            "Content Manifest for Depot 2\nManifest ID / date : 3 / fixture\n"
            "Total number of files : 1\nSize Chunks File SHA Flags Name\n"
            f"{len(self.payload)} 1 {self.sha1} 0 bin/tool name.dll\n", encoding="utf-8")
        self.inputs = self.root / "inputs"
        (self.inputs / "bin").mkdir(parents=True)
        (self.inputs / "bin/tool name.dll").write_bytes(self.payload)
        self.plan = self.root / "plan.json"

    def write_plan(self) -> None:
        """Select candidates using the same operation as the command."""
        self.plan.write_text(json.dumps(select(self.reference, self.manifest, "1")), encoding="utf-8")

    def test_downloaded_file_reproduces_both_renamed_outputs(self) -> None:
        """One verified input can populate multiple original archive paths."""
        self.write_plan()
        recipe_path = self.root / "recipe.json"
        recipe = make_recipe(self.plan, self.inputs, recipe_path)
        self.assertEqual(len(recipe["verified_inputs"]), 1)
        self.assertEqual(len(recipe["files"]), 2)
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        assemble(recipe_path, self.root / "output")
        for entry in recipe["files"]:
            self.assertEqual((self.root / "output" / entry["to"]).read_bytes(), self.payload)

    def test_truncated_manifest_is_not_a_partial_success(self) -> None:
        """A truncated file list must not silently reduce the selection."""
        text = self.manifest.read_text(encoding="utf-8").replace("files : 1", "files : 2")
        self.manifest.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "declares 2 rows"):
            read_manifest(self.manifest)

    def test_traversal_is_rejected_before_download_selection(self) -> None:
        """Untrusted manifest paths cannot select files outside a depot root."""
        text = self.manifest.read_text(encoding="utf-8").replace("bin/tool name.dll", "../tool.dll")
        self.manifest.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "relative portable path"):
            read_manifest(self.manifest)

    def test_changed_payload_cannot_become_a_recipe(self) -> None:
        """The recipe gate catches changed or incomplete downloads."""
        self.write_plan()
        (self.inputs / "bin/tool name.dll").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "differ from Steam manifest"):
            make_recipe(self.plan, self.inputs, self.root / "recipe.json")

    def test_sha1_match_alone_cannot_establish_reference_identity(self) -> None:
        """Reference SHA-256 must agree even when the shortlist SHA-1 agrees."""
        rows = json.loads(self.reference.read_text(encoding="utf-8"))
        rows[0]["sha256"] = "0" * 64
        self.reference.write_text(json.dumps(rows), encoding="utf-8")
        self.write_plan()
        with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
            make_recipe(self.plan, self.inputs, self.root / "recipe.json")

    def test_merge_rebases_roots_and_preserves_output_conflicts(self) -> None:
        """A relocated combined recipe works and contradictory bytes are rejected."""
        self.write_plan()
        first = self.root / "first.json"
        recipe = make_recipe(self.plan, self.inputs, first)
        first.write_text(json.dumps(recipe), encoding="utf-8")
        output = self.root / "nested/combined.json"
        output.parent.mkdir()
        combined = merge_recipes([first, first], output)
        self.assertEqual(len(combined["files"]), 2)
        output.write_text(json.dumps(combined), encoding="utf-8")
        assemble(output, self.root / "combined-output")
        self.assertEqual((self.root / "combined-output/game/bin/tool.dll").read_bytes(), self.payload)
        recipe["files"][0]["sha256"] = "0" * 64
        second = self.root / "second.json"
        second.write_text(json.dumps(recipe), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Conflicting output hashes"):
            merge_recipes([first, second], output)


if __name__ == "__main__":
    unittest.main()
