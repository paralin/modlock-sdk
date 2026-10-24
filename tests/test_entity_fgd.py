"""Exercise merging overlapping map observations without replacing Valve bases."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from entity_fgd import INCLUDES, merge


class EntityFgdTest(unittest.TestCase):
    """Keep inferred definitions separate from authoritative editor metadata."""

    def test_merges_observations_and_keeps_valve_base(self) -> None:
        """Merge brush evidence, outputs and earlier classes, while preserving a core class."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            core = root / "core"
            core.mkdir()
            for name in INCLUDES:
                (core / name).write_text('''// @PointClass = ignored_comment : "not a declaration"
@PointClass box_oriented { box_min = "mins" nested { value = "}" } }
    editor("quoted = value")
    = light_omni : "Valve definition" [ ]
''')
            lump = {"Map": "new.vpk", "MapSha256": "n", "Member": "m"}
            (root / "sources.json").write_text(json.dumps([{**lump, "Sha256": "a"}, {**lump, "Member": "n", "Sha256": "b"}]))
            (root / "a.fgd").write_text('''@PointClass = light_omni : ""
[
 bad(string) : ""
]
@PointClass base(Targetname) = citadel_probe : ""
[
 count(integer) : ""
 spawnflags(integer) : ""
 output OnReady(void) : ""
]
''')
            (root / "b.fgd").write_text('''@SolidClass = citadel_probe : ""
[
 count(string) : ""
 enabled(boolean) : ""
 spawnflags(uint32) : ""
]
''')
            # A class only an earlier build's map placed stays, as does its lump.
            output = root / "citadel.fgd"
            output.write_text('''@PointClass = citadel_removed : "Observed map entity"
[
    radius(float) : "Observed field"
]
''')
            receipt = root / "entity-sources.json"
            receipt.write_text(json.dumps([{"Map": "old.vpk", "MapSha256": "o", "Member": "m", "Sha256": "c"}]))
            self.assertEqual(merge(root, core, output, receipt), 2)
            text = output.read_text()
            self.assertIn('citadel_removed : "Observed map entity"\n[\n    radius(float)', text)
            self.assertEqual([row["Map"] for row in json.loads(receipt.read_text())], ["new.vpk", "new.vpk", "old.vpk"])
            self.assertIn('@SolidClass base(Targetname) = citadel_probe', text)
            self.assertIn('count(string)', text)
            self.assertIn('spawnflags(integer)', text)
            self.assertIn('output OnReady(void)', text)
            self.assertNotIn('light_omni', text)


if __name__ == "__main__":
    unittest.main()
