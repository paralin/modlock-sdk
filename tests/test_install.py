"""Check that the installer reuses Steam games and keeps user work on rerun."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install
from install import CS2, DEADLOCK, File


class InstallTest(unittest.TestCase):
    """Run the installer against a fake Steam library and a fake downloader."""

    def test_links_packages_copies_binaries_and_downloads_the_rest(self) -> None:
        """Installed files are reused, missing ones downloaded, and edits survive."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam = root / "Steam"
            library = root / "Library"
            (steam / "steamapps").mkdir(parents=True)
            (steam / "steamapps/libraryfolders.vdf").write_text(
                f'"libraryfolders"\n{{\n "1"\n {{\n  "path"  "{library.as_posix()}"\n }}\n}}\n')
            (library / "steamapps").mkdir(parents=True)
            (library / "steamapps/appmanifest_1422450.acf").write_text(
                '"AppState"\n{\n "installdir"  "Deadlock"\n}\n')
            game = library / "steamapps/common/Deadlock"
            (game / "game/citadel").mkdir(parents=True)
            (game / "game/citadel/pak01_dir.vpk").write_bytes(b"assets")

            files = [File(DEADLOCK, "1422451", "game/citadel/pak01_dir.vpk",
                          "game/citadel_assets/pak01_dir.vpk"),
                     File(CS2, "2347771", "game/bin/win64/tools.dll", "game/bin/win64/tools.dll")]
            downloads = []

            def download(program, app, wanted, folder):
                downloads.append((app, [file.path for file in wanted]))
                for file in wanted:
                    (folder / file.path).parent.mkdir(parents=True, exist_ok=True)
                    (folder / file.path).write_bytes(b"tool")

            def build(zig, output):
                output.write_bytes(b"launcher")

            destination = root / "modlock-tools"
            with mock.patch.object(install, "steam_roots", return_value=[steam]), \
                    mock.patch.object(install, "toolkit_files", return_value=files), \
                    mock.patch.object(install, "depot_downloader", return_value=Path("dd")), \
                    mock.patch.object(install, "download", side_effect=download), \
                    mock.patch.object(install, "zig", return_value=Path("zig")), \
                    mock.patch.object(install, "build", side_effect=build):
                install.install(destination)
                sample = destination / "content/citadel_addons/modlock_sample/models/probe.vmdl"
                sample.write_text("my model")
                install.install(destination)

            package = destination / "game/citadel_assets/pak01_dir.vpk"
            self.assertTrue(os.path.samefile(package, game / "game/citadel/pak01_dir.vpk"))
            self.assertEqual((destination / "game/bin/win64/tools.dll").read_bytes(), b"tool")
            self.assertEqual(downloads, [(CS2, ["game/bin/win64/tools.dll"])] * 2)
            self.assertEqual((destination / "game/bin/win64/sdk-launcher.exe").read_bytes(),
                             b"launcher")
            self.assertEqual(sample.read_text(), "my model")
            self.assertTrue((destination / "game/citadel/gameinfo.gi").is_file())


if __name__ == "__main__":
    unittest.main()
