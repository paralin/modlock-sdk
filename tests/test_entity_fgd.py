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
        """Merge brush evidence and outputs, while preserving a core class."""
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
            (root / "sources.json").write_text(json.dumps([{"Sha256": "a"}, {"Sha256": "b"}]))
            (root / "a.fgd").write_text('''@PointClass = light_omni : ""
[
 bad(string) : ""
]
@PointClass base(Targetname) = citadel_probe : ""
[
 count(integer) : ""
 output OnReady(void) : ""
]
''')
            (root / "b.fgd").write_text('''@SolidClass = citadel_probe : ""
[
 count(string) : ""
 enabled(boolean) : ""
]
''')
            output = root / "citadel.fgd"
            self.assertEqual(merge(root, core, output), 1)
            text = output.read_text()
            self.assertIn('@SolidClass base(Targetname) = citadel_probe', text)
            self.assertIn('count(string)', text)
            self.assertIn('output OnReady(void)', text)
            self.assertNotIn('light_omni', text)


if __name__ == "__main__":
    unittest.main()
