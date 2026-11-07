"""Check that the installer follows the current depots and keeps user work on rerun."""

import io
import json
import os
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import convars
import gameinfo
import install
import steam
from toolkit import Depot


def varint(value: int) -> bytes:
    """Encode a protobuf varint."""
    out = bytearray()
    while value >= 0x80:
        out.append(value & 0x7F | 0x80)
        value >>= 7
    return bytes(out + bytes([value]))


def depot_manifest(files: list[str], directories: list[str]) -> bytes:
    """Encode a Steam depot manifest listing files and directories."""
    payload = b""
    for name, flags in [(name, 0) for name in files] + [(name, 0x40) for name in directories]:
        encoded = name.replace("/", "\\").encode()
        mapping = b"\x0a" + varint(len(encoded)) + encoded + b"\x18" + varint(flags)
        payload += b"\x0a" + varint(len(mapping)) + mapping
    return struct.pack("<II", steam.MANIFEST_MAGIC, len(payload)) + payload


CODE_RVA, DATA_RVA, TABLE_RVA, BLOCKS_RVA = 0x1000, 0x2000, 0x2100, 0x3000
CODE_OFFSET, DATA_OFFSET, IMAGE_BASE = 0x200, 0x1200, 0x180000000
# Code a real module holds beside its registration routines. Each constant
# equals a type number, and the load is a read of the same field that never
# indexes the table; none of them may change.
INITIALIZER = (b"\x41\xb8\x03\x00\x00\x00"  # mov r8d, 3
               b"\xbb\x03\x00\x00\x00"  # mov ebx, 3
               b"\x66\xc7\x44\x24\x60\x03\x00"  # mov word ptr [rsp + 0x60], 3
               b"\x66\x89\x5c\x24\x60"  # mov word ptr [rsp + 0x60], bx
               b"\x48\x0f\xbf\x48\x28\x48\x8b\xc1")  # movsx rcx, word ptr [rax + 0x28]; mov rax, rcx


def fake_module(rows: int, extra: bytes = b"", marker: bytes = convars.MARKER) -> bytes:
    """Build a PE file with a table of types and the code that uses it.

    extra is code placed after the registration routines.
    """
    code = bytearray()

    def with_address(instruction: bytes, target: int) -> None:
        """Append an instruction ending in a displacement selecting target."""
        code.extend(instruction)
        code.extend(struct.pack("<i", target - CODE_RVA - len(code) - 4))

    with_address(b"\x66\x83\xfe\xff\x74\x11\x48\x6b\xce\x58\x48\x8d\x05", TABLE_RVA)  # Setup.
    code.extend(INITIALIZER)
    with_address(b"\x48\x0f\xbf\x47\x60\x66\x83\xf8\xff\x74\x11\x4c\x6b\xd0\x58\x48\x8d\x05",
                 TABLE_RVA)  # Declare.
    with_address(b"\x48\x0f\xbf\x48\x28\x66\x83\xf9\xff\x74\x21\x48\x6b\xc9\x58\x48\x8d\x05",
                 TABLE_RVA)  # Read back.
    code.extend(b"\x4d\x0f\xbf\x7e\x28\x49\x8b\xd3\x4d\x6b\xe7\x58")  # movsx r15; mov rdx; imul r12, r15.
    with_address(b"\x48\x0f\xbf\xc1\x48\x8d\x0d", TABLE_RVA - convars.ROW_POINTER)  # Traits.
    code.extend(b"\x48\x6b\xc0\x58\x48\x03\xc1\xc3" + b"\xcc" * 13)
    code.extend(extra + b"\x90" * 64 + (b"\xcc" * 15 + b"\x90") * 8)

    data = bytearray(0x2000)
    for row in range(rows):
        block = BLOCKS_RVA + row * 0x40
        struct.pack_into("<Q", data, TABLE_RVA - DATA_RVA + row * convars.ROW_SIZE, IMAGE_BASE + block)
        struct.pack_into("<H", data, block - DATA_RVA + convars.ENTRY_TYPE, row)
    data[0x1800:0x1800 + len(marker)] = marker

    header = bytearray(CODE_OFFSET)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 0x40)
    header[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<H", header, 0x46, 2)
    struct.pack_into("<H", header, 0x54, 0xF0)
    struct.pack_into("<HxxxxxxxxxxxxxxxxxxxxxxQ", header, 0x58, convars.PE32_PLUS, IMAGE_BASE)
    for index, (rva, size, offset, flags) in enumerate(((CODE_RVA, 0x1000, CODE_OFFSET, convars.SCN_EXECUTE),
                                                        (DATA_RVA, len(data), DATA_OFFSET, 0))):
        struct.pack_into("<4I", header, 0x148 + index * 40 + 8, size, rva, size, offset)
        struct.pack_into("<I", header, 0x148 + index * 40 + 36, flags)
    return bytes(header) + bytes(code).ljust(0x1000, b"\x90") + bytes(data)


class ConvarsTest(unittest.TestCase):
    """Rewrite small modules that have the structure of Valve's."""

    def test_translates_only_code_that_meets_the_engine(self) -> None:
        """Each number crossing to tier0 is translated, and no other byte of code changes.

        The compiled type numbers and their look-alikes stay; the value block
        and every load gain a routine in the padding; the file keeps its size.
        """
        stock = fake_module(16)
        rewritten = convars.aligned(stock, 18)
        self.assertEqual(len(rewritten), len(stock))
        self.assertEqual(convars.numbering(rewritten), 16)

        # Find the sites from the stock code, then read each routine it now calls.
        image = convars.Image(stock)
        at = stock.index
        declare = at(b"\x48\x0f\xbf\x47\x60")
        readback = at(b"\x48\x0f\xbf\x48\x28\x66")
        extended = at(b"\x4d\x0f\xbf\x7e\x28")

        def routine(site: int, length: int) -> bytes:
            """Return the routine the call at site reaches."""
            self.assertEqual(rewritten[site], 0xE8)
            position = site + 5 + struct.unpack_from("<i", rewritten, site + 1)[0]
            return rewritten[position:position + length]

        self.assertEqual(routine(declare, 15), stock[declare:declare + 5] + convars.RAISE_VALUE_BLOCK + b"\xc3")
        self.assertEqual(routine(readback, 13), stock[readback:readback + 5] + b"\x83\xe9\x02\x79\x02\x31\xc9\xc3")
        # r15 needs the extended encodings.
        self.assertEqual(routine(extended, 15),
                         stock[extended:extended + 5] + b"\x41\x83\xef\x02\x79\x03\x45\x31\xff\xc3")

        # The traits helper keeps its place and still loads the same address.
        traits = at(b"\x48\x0f\xbf\xc1")
        self.assertEqual(rewritten[traits + 4:traits + 11], b"\x83\xe8\x02\x79\x02\x31\xc0")
        self.assertEqual(convars.Image(rewritten).target(traits + 14), image.target(traits + 7))

        # Outside those sites and the padding nothing moved, the constants above all.
        self.assertEqual(rewritten[at(INITIALIZER):at(INITIALIZER) + len(INITIALIZER)], INITIALIZER)
        sites = [*range(declare, declare + 5), *range(readback, readback + 5), *range(extended, extended + 5),
                 *range(traits, traits + 26)]
        changed = [offset for offset in range(len(stock)) if stock[offset] != rewritten[offset]]
        self.assertTrue(all(offset in sites or stock[offset] == 0xCC for offset in changed))

    def test_acts_only_on_a_pairing_it_knows(self) -> None:
        """Agreeing numberings do nothing; anything else leaves the module and says why."""
        stock = fake_module(16)
        self.assertEqual(convars.numbering(fake_module(18)), 18)
        self.assertIs(convars.aligned(stock, 16), stock)
        self.assertIsNone(convars.numbering(fake_module(16, marker=b"none")))
        with self.assertRaisesRegex(convars.Unsupported, "17 console variable types"):
            convars.aligned(fake_module(17), 18)
        with self.assertRaisesRegex(convars.Unsupported, "20"):
            convars.aligned(stock, 20)
        # An index of the table nothing explains, in the registration code.
        with self.assertRaisesRegex(convars.Unsupported, "does not understand"):
            convars.aligned(fake_module(16, extra=b"\x48\x6b\xc1\x58\x90\x48\x0f\xbf\x48\x28\x48\x6b\xc1\x58"), 18)
        with self.assertRaises(convars.Unsupported):
            convars.aligned(b"MZ" + bytes(0x40) + convars.MARKER, 18)

    def test_aligns_private_copies_on_each_run(self) -> None:
        """Copies follow their sources and tier0; a rerun writes nothing and Steam's files stay.

        A module that cannot be handled stays stock and is reported, and the
        run goes on. When tier0 moves back, the copy returns to stock.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam_root, destination = root / "steam", root / "toolkit"
            names = {"game/bin/win64/tier0.dll": fake_module(18),
                     "game/bin/win64/tools/hammer.dll": fake_module(16),
                     "game/bin/win64/tools/pet.dll": fake_module(17),
                     "game/bin/win64/deadlock.dll": fake_module(18)}
            sources = {}
            for name, data in names.items():
                source = steam_root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(data)
                os.utime(source, ns=(10**18, 10**18))
                sources[name] = source

            def run() -> str:
                """Place the files and align them, as a run of the installer does."""
                for name, source in sources.items():
                    install.place(source, destination / name, False)
                with mock.patch("sys.stdout", io.StringIO()) as output:
                    install.align_modules(sources, destination)
                return output.getvalue()

            report = run()
            hammer = destination / "game/bin/win64/tools/hammer.dll"
            self.assertIn("updated game/bin/win64/tools/hammer.dll\n", report)
            self.assertIn("The Particle Editor will not work", report)
            self.assertNotEqual(hammer.read_bytes(), names["game/bin/win64/tools/hammer.dll"])
            self.assertEqual(hammer.stat().st_size, sources["game/bin/win64/tools/hammer.dll"].stat().st_size)
            self.assertEqual(hammer.stat().st_mtime_ns, 10**18)
            for name, data in names.items():
                self.assertEqual(sources[name].read_bytes(), data)

            before = {path: path.stat().st_mtime_ns for path in destination.rglob("*") if path.is_file()}
            with mock.patch.object(install.durable.os, "replace", side_effect=AssertionError("wrote")):
                report = run()
            self.assertNotIn("updated", report)
            self.assertEqual(before, {path: path.stat().st_mtime_ns for path in destination.rglob("*") if path.is_file()})

            sources["game/bin/win64/tier0.dll"].write_bytes(fake_module(16))
            os.utime(sources["game/bin/win64/tier0.dll"], ns=(10**18, 10**18))
            sources["game/bin/win64/tools/pet.dll"].write_bytes(fake_module(16))
            os.utime(sources["game/bin/win64/tools/pet.dll"], ns=(10**18, 10**18))
            del sources["game/bin/win64/deadlock.dll"]
            run()
            self.assertEqual(hammer.read_bytes(), names["game/bin/win64/tools/hammer.dll"])


class InstallTest(unittest.TestCase):
    """Run the installer against a fake Steam library and a fake downloader."""

    def test_follows_depot_changes_and_keeps_user_work(self) -> None:
        """Installed depots are linked, the rest downloaded, and dropped files removed.

        A run after one that did not finish validates the downloads and copies
        every file again, replacing a copy a power loss zeroed. A shader package
        is written as one file. Other packages are symbolic links, as when the
        toolkit and the Steam library sit on different disks, so a rerun
        replaces links it placed itself.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam_root, library = root / "Steam", root / "Library"
            (steam_root / "steamapps").mkdir(parents=True)
            (steam_root / "depotcache").mkdir()
            (steam_root / "steamapps/libraryfolders.vdf").write_text(
                f'"libraryfolders"\n{{\n "1"\n {{\n  "path"  "{library.as_posix()}"\n }}\n}}\n')
            (library / "steamapps").mkdir(parents=True)
            (library / "steamapps/appmanifest_1422450.acf").write_text(
                '"AppState"\n{\n "installdir"  "Deadlock"\n "InstalledDepots"\n {\n'
                '  "1422451"\n  {\n   "manifest"  "7"\n  }\n }\n}\n')
            game = library / "steamapps/common/Deadlock"
            (game / "game/citadel/bin").mkdir(parents=True)
            for name in ("pak01_dir.vpk", "pak01_000.vpk", "bin/client.dll"):
                (game / "game/citadel" / name).write_bytes(b"deadlock")
            # The game's own file, with a search path another program added.
            (game / "game/citadel/gameinfo.gi").write_text(
                '"GameInfo"\n{\n\tgame "citadel"\n\tFileSystem\n\t{\n\t\tSearchPaths\n\t\t{\n'
                '\t\t\tGame citadel/other_program // added by another program\n'
                '\t\t\tGame citadel\n\t\t}\n\t\t"UserSettingsPathID" "USRLOCAL"\n\t}\n'
                '\tHammer { RenderMode ToolsVis }\n'
                '\tEngine2 { HasModAppSystems 1 Capable64Bit 1 }\n}\n')
            # A shader package with one file, "abc" at offset 2 of archive 000.
            shader_tree = b"txt\0shaders\0a\0" + struct.pack("<IHHIIH", 0, 0, 0, 2, 3, 0xFFFF) + b"\0\0\0"
            (game / "game/citadel/shaders_pc_dir.vpk").write_bytes(
                struct.pack("<7I", install.VPK_MAGIC, 2, len(shader_tree), 0, 28, 48, 20) + shader_tree)
            (game / "game/citadel/shaders_pc_000.vpk").write_bytes(b"xxabcyy")
            (steam_root / "depotcache/1422451_7.manifest").write_bytes(depot_manifest(
                ["game/citadel/pak01_dir.vpk", "game/citadel/pak01_000.vpk",
                 "game/citadel/bin/client.dll", "game/citadel/shaders_pc_dir.vpk",
                 "game/citadel/shaders_pc_000.vpk", "game/citadel/gameinfo.gi"], ["game/citadel"]))

            profile = [Depot("730", "2347771", {"game/bin/": "game/bin/"}),
                       Depot("1422450", "1422451",
                             {"game/citadel/gameinfo.gi": "game/citadel/gameinfo.gi",
                              "game/citadel/pak01_": "game/citadel_assets/pak01_",
                              "game/citadel/shaders_": "game/citadel_assets/shaders_"})]
            depot_contents = {"game/bin/tools.dll": b"tool", "game/bin/old/old.dll": b"old"}
            downloads = []

            def download(program, app, depot, include, folder, account, validate):
                downloads.append((depot, validate))
                for name, data in depot_contents.items():
                    (folder / name).parent.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(data)
                (folder / ".DepotDownloader").mkdir(exist_ok=True)
                (folder / f".DepotDownloader/{depot}_9.manifest").write_bytes(b"")

            destination = root / "modlock-tools"
            with mock.patch.object(steam, "steam_roots", return_value=[steam_root]), \
                    mock.patch.object(install, "depots", return_value=profile), \
                    mock.patch.object(steam, "depot_downloader", return_value=Path("dd")), \
                    mock.patch.object(steam, "download", side_effect=download), \
                    mock.patch.object(install, "zig", return_value=Path("zig")), \
                    mock.patch.object(install.os, "link", side_effect=OSError("cross-device")), \
                    mock.patch.object(install, "build",
                                      side_effect=lambda zig, directory: [
                                          (directory / name).write_bytes(b"exe")
                                          for name in ("sdk-launcher.exe", "vrad3.exe")]):
                install.install(destination)
                sample = destination / "content/citadel_addons/modlock_sample/models/probe.vmdl"
                sample.write_text("my model")
                self.assertEqual((destination / "game/bin/old/old.dll").read_bytes(), b"old")

                # Valve drops old/ in the next version.
                del depot_contents["game/bin/old/old.dll"]
                (root / "modlock-tools/.cache/depots/2347771/game/bin/old/old.dll").unlink()
                install.install(destination)

                # A power loss during a run zeroes a copy but keeps its size
                # and time, and leaves the state incomplete.
                tools = destination / "game/bin/tools.dll"
                times = tools.stat()
                tools.write_bytes(bytes(4))
                os.utime(tools, ns=(times.st_atime_ns, times.st_mtime_ns))
                state_file = destination / ".cache/installed.json"
                state_file.write_text(state_file.read_text().replace('"complete": true',
                                                                     '"complete": false'))
                install.install(destination)

            package = destination / "game/citadel_assets/pak01_dir.vpk"
            self.assertTrue(package.is_symlink())
            self.assertTrue(os.path.samefile(package, game / "game/citadel/pak01_dir.vpk"))
            shaders = (destination / "game/citadel_assets/shaders_pc_dir.vpk").read_bytes()
            _, _, tree, data, chunks, _, _ = struct.unpack_from("<7I", shaders)
            entry = struct.unpack_from("<IHHIIH", shaders, 28 + shader_tree.index(b"a\0") + 2)
            self.assertEqual((data, chunks, entry[2:5]), (7, 0, (0x7FFF, 2, 3)))
            self.assertEqual(shaders[28 + tree + 2:28 + tree + 5], b"abc")
            self.assertFalse((destination / "game/citadel_assets/shaders_pc_000.vpk").exists())
            self.assertFalse((destination / "game/citadel_assets/bin").exists())
            self.assertEqual((destination / "game/bin/tools.dll").read_bytes(), b"tool")
            self.assertFalse((destination / "game/bin/old").exists())
            self.assertEqual(downloads, [("2347771", True), ("2347771", False), ("2347771", True)])
            self.assertEqual(sample.read_text(), "my model")
            # The game's gameinfo.gi with the toolkit's changes: sections merge
            # key by key, and the search path list is the toolkit's alone.
            (_, info), = gameinfo.parse((destination / "game/citadel/gameinfo.gi").read_text())
            info = dict(info)
            paths = dict(info["FileSystem"])["SearchPaths"]
            self.assertEqual(paths[0], ("Mod", "citadel"))
            self.assertNotIn(("Game", "citadel/other_program"), paths)
            self.assertEqual(dict(info["FileSystem"])["UserSettingsPathID"], "MOD")
            self.assertEqual(info["Hammer"], [("RenderMode", "ToolsVis")])
            self.assertEqual(info["Engine2"], [("HasModAppSystems", "0"), ("Capable64Bit", "1")])
            self.assertTrue((destination / "Update.cmd").is_file())
            state = json.loads((destination / ".cache/installed.json").read_text())
            self.assertEqual(state["depots"], {"2347771": "9", "1422451": "7"})
            self.assertTrue(state["complete"])

    def test_zig_recovers_from_a_crash(self) -> None:
        """A Zig folder a crash left zeroed or half unpacked is replaced; a complete one is kept."""
        top = "zig-x86_64-windows-" + install.ZIG_VERSION
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.writestr(f"{top}/lib/internal.h", "#define _PGLOBAL\n")
            zip_file.writestr(f"{top}/zig.exe", "zig")
        index = json.dumps({install.ZIG_VERSION: {"x86_64-windows": {"tarball": "zig.zip"}}})
        fetched = []

        def fetch(url: str) -> bytes:
            fetched.append(url)
            return archive.getvalue() if url == "zig.zip" else index.encode()

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            # Earlier installers' folder, whose header a power loss zeroed.
            legacy = cache / top
            (legacy / "lib").mkdir(parents=True)
            (legacy / "lib/internal.h").write_bytes(bytes(17))
            (legacy / "zig.exe").write_text("zig")
            # The current folder, cut short before its last file.
            (cache / f"zig-{install.ZIG_VERSION}/{top}/lib").mkdir(parents=True)
            with mock.patch.object(install.platform, "machine", return_value="AMD64"), \
                    mock.patch.object(install.platform, "system", return_value="Windows"), \
                    mock.patch.object(steam, "fetch", side_effect=fetch):
                program = install.zig(cache)
                self.assertEqual(install.zig(cache), program)

            self.assertEqual(program.read_text(), "zig")
            self.assertEqual((program.parent / "lib/internal.h").read_text(), "#define _PGLOBAL\n")
            self.assertFalse(legacy.exists())
            self.assertEqual(fetched, [install.ZIG_INDEX, "zig.zip"])


if __name__ == "__main__":
    unittest.main()
