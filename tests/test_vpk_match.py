"""Check the directory contract used to plan bounded VPK downloads."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from vpk_match import read_directory


class VpkDirectoryTest(unittest.TestCase):
    """Keep preload sizes and incomplete extractor output visible to callers."""

    def test_preloaded_bytes_count_toward_member_size(self) -> None:
        """Selection uses the complete member size, including inline bytes."""
        members = read_directory(
            "--- Files in package:\n\tvmat_c: 1 files\n"
            "materials/test material.vmat_c crc=0x12 metadatasz=8 fnumber=32767 ofs=0x00 sz=4\n"
        )
        self.assertEqual(members[0].path, "materials/test material.vmat_c")
        self.assertEqual(members[0].size, 12)
        self.assertEqual(members[0].archive_index, 0x7FFF)

    def test_truncated_directory_cannot_select_partial_downloads(self) -> None:
        """An extractor failure must not masquerade as a smaller package list."""
        with self.assertRaisesRegex(ValueError, "declares 2 members but contains 1"):
            read_directory(
                "\tvmat_c: 2 files\n"
                "materials/one.vmat_c crc=0x12 metadatasz=0 fnumber=1 ofs=0x00 sz=4\n"
            )


if __name__ == "__main__":
    unittest.main()
