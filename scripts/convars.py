"""Make a module built for one console variable numbering run on an engine with another.

Each module that declares console variables links its own copy of the
registration code and its own table of types, one row per type. tier0 holds the
variables themselves, and a variable's type is a number both sides read. Deadlock's
engine added int8 and uint8 after bool, so every later type moved up by two: a
module with the 16 row table and a tier0 with the 18 row table disagree on every
number but bool's. tier0 refuses a shared name declared under another number,
and binds a private name to the wrong type without a word.

The rewrite keeps the module's table and its old numbers. Two kinds of code meet
tier0's numbering, and each gets a translation:

- The declare routine, which both registration paths pass through: it copies the
  value block into the definition that reaches tier0, queued or at once. Its
  value block leaves the routine with the engine's number. Its own table lookup
  still uses the old number. A value block serves one declaration: each variable
  has its own initializer, which fills the block on its own stack.
- Every load of the type field of tier0's entry that goes on to index the table,
  including the type traits helper, whose callers all pass that field. The load
  yields the module's number, so the table sees only its own rows and a later
  comparison with a compiled number still holds.

A compiled type number is never touched, so a constant that only happens to equal
a type number stays as it is. Each rewritten instruction becomes a call to a short
routine placed in the padding between functions, so the file keeps its size and
its layout: no section, relocation or import changes. The routines are leaves
with no frame, which is what code without unwind records must be.

A module whose code does not match what is described here raises Unsupported and
stays as Valve shipped it.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import PurePosixPath

# Every module with registration code holds this string; the others declare nothing.
MARKER = b"RegisterConVar: Unknown error registering convar"
OLD_ROWS, NEW_ROWS = 16, 18
ROW_SIZE = 0x58
# The table's row pointers sit at the end of each row, this far from its start.
ROW_POINTER = 0x50
# The offset of the type in a variable's default data and in tier0's entry.
ENTRY_TYPE = 0x28

SCN_EXECUTE = 0x20000000
PE32_PLUS = 0x20B

RET, CALL = b"\xc3", b"\xe8"
JNS = 0x79
# The start of cmp r16, imm8, which the read back uses to test for the invalid type.
CMP_WORD = b"\x66\x83"
# A run of padding, at least as long as the shortest routine. Functions are
# aligned to 16 bytes, so a run seldom passes 15 and no routine here does.
PADDING = re.compile(b"\xcc{13,}")

# imul r64, r64, 0x58, the only way the modules scale a type number to a row.
IMUL_ROW = re.compile(rb"[\x48\x49\x4c\x4d]\x6b[\xc0-\xff]\x58")
# That, followed within a few bytes by lea r64, [rip + disp32].
IMUL_LEA = re.compile(rb"[\x48\x49\x4c\x4d]\x6b[\xc0-\xff]\x58.{0,12}?[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]",
                      re.S)
# movsx r64, word ptr [base + 0x28], then a table index from that register.
ENTRY_LOAD = re.compile(rb"(?=([\x48\x49\x4c\x4d])\x0f\xbf([\x40-\x7f])\x28.{0,16}?"
                        rb"([\x48\x49\x4c\x4d])\x6b([\xc0-\xff])\x58)", re.S)
# The setup routine's lookup, by the type it was passed: compiled numbers, kept.
SETUP = re.compile(rb"\x66\x83\xfe\xff\x74\x11\x48\x6b\xce\x58\x48\x8d\x05(....)", re.S)
SETUP_INDEX = 6
# The declare routine's lookup, by the type in the value block in rdi.
DECLARE = re.compile(rb"\x48\x0f\xbf\x47\x60\x66\x83\xf8\xff\x74\x11\x4c\x6b\xd0\x58\x48\x8d\x05(....)", re.S)
DECLARE_INDEX = 11
# The type traits helper: movsx rax, cx; lea rcx, [rows]; imul rax, rax, 0x58;
# add rax, rcx; ret. Its own padding holds the longer version.
TRAITS = re.compile(rb"\x48\x0f\xbf\xc1\x48\x8d\x0d(....)\x48\x6b\xc0\x58\x48\x03\xc1\xc3\xcc{7}", re.S)
TRAITS_INDEX = 11
# The value block's type in rdi moves up by two unless it is bool or invalid.
RAISE_VALUE_BLOCK = b"\x85\xc0\x7e\x05\x66\x83\x47\x60\x02"
# The most code the registration routines span; the largest stock span is 0x1500.
REGISTRATION_SPAN = 0x4000
# What a person loses with a module, by file name. A module not named here is
# shared code, and costs whatever loads it.
FEATURES = {
    "hammer": "Hammer",
    "met": "The Material Editor",
    "modeldoc_editor": "ModelDoc",
    "pet": "The Particle Editor",
    "sfm": "Source Filmmaker",
    "workshopmanager": "The Workshop Manager",
    "resourceinfo": "resourceinfo.exe",
    "vrad3": "Baked lighting",
    "vrad3_base": "Baked lighting",
}


class Unsupported(ValueError):
    """The module's code does not match the structure this rewrite understands."""


@dataclass(frozen=True)
class Section:
    """A section's place in memory and in the file."""

    rva: int
    offset: int
    size: int
    characteristics: int


class Image:
    """A 64 bit PE file's sections, enough to read data by its address."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        try:
            header, = struct.unpack_from("<I", data, 0x3C)
            if data[:2] != b"MZ" or data[header:header + 4] != b"PE\0\0":
                raise Unsupported("it is not a Windows module")
            count, = struct.unpack_from("<H", data, header + 6)
            optional, = struct.unpack_from("<H", data, header + 20)
            magic, = struct.unpack_from("<H", data, header + 24)
            if magic != PE32_PLUS:
                raise Unsupported("it is not a 64 bit module")
            self.base, = struct.unpack_from("<Q", data, header + 48)
            self.sections = []
            for index in range(count):
                row = header + 24 + optional + index * 40
                _, rva, size, offset = struct.unpack_from("<4I", data, row + 8)
                characteristics, = struct.unpack_from("<I", data, row + 36)
                self.sections.append(Section(rva, offset, size, characteristics))
        except struct.error as error:
            raise Unsupported("its header is damaged") from error
        code = [section for section in self.sections if section.characteristics & SCN_EXECUTE]
        if not code or code[0].offset + code[0].size > len(data):
            raise Unsupported("its code section is damaged")
        self.code = code[0]

    @property
    def code_range(self) -> tuple[int, int]:
        """The file offsets the code section starts and ends at."""
        return self.code.offset, self.code.offset + self.code.size

    def offset(self, rva: int) -> int | None:
        """Return the file offset of an address, or None when the file has no bytes for it."""
        for section in self.sections:
            if section.rva <= rva < section.rva + section.size:
                return section.offset + rva - section.rva
        return None

    def rva(self, offset: int) -> int:
        """Return the address of a file offset in the code section."""
        return self.code.rva + offset - self.code.offset

    def target(self, field: int) -> int:
        """Return the address an instruction ending in a 32 bit displacement at field refers to."""
        return self.rva(field) + 4 + struct.unpack_from("<i", self.data, field)[0]


@dataclass(frozen=True)
class EntryLoad:
    """A load of the type field of tier0's entry that goes on to index the table."""

    offset: int
    register: int
    index: int


def feature(name: str) -> str:
    """Name what stops working when the module at a toolkit path cannot be used."""
    path = PurePosixPath(name)
    return FEATURES.get(path.stem, f"Any tool that loads {path.name}")


def table_rows(image: Image, table: int) -> int:
    """Count the rows from table whose default data carries the row's own number."""
    rows = 0
    while (row := image.offset(table + rows * ROW_SIZE)) is not None and row + 8 <= len(image.data):
        block = image.offset(struct.unpack_from("<Q", image.data, row)[0] - image.base + ENTRY_TYPE)
        if block is None or block + 2 > len(image.data) \
                or struct.unpack_from("<H", image.data, block)[0] != rows:
            break
        rows += 1
    return rows


def find_table(image: Image) -> tuple[int, int] | None:
    """Return the address and row count of the module's table of types, if it has one.

    The module's lookups multiply by the row size and then load the table's
    address, at least three times, which sets it apart from another array of
    that stride; the row walk rejects the rest.
    """
    uses: dict[int, int] = {}
    for match in IMUL_LEA.finditer(image.data, *image.code_range):
        table = image.target(match.end())
        uses[table] = uses.get(table, 0) + 1
    rows, table = max(((table_rows(image, table), table) for table, count in uses.items() if count >= 3),
                      default=(0, 0))
    return (table, rows) if rows else None


def numbering(data: bytes) -> int | None:
    """Return the number of types a module's table has, or None if it declares no variables."""
    if MARKER not in data:
        return None
    found = find_table(Image(data))
    return found[1] if found else None


def entry_loads(image: Image) -> list[EntryLoad]:
    """Find every load of the type field that indexes a row with the loaded register.

    A load through the stack pointer has another encoding and is not one.
    """
    loads = []
    for match in ENTRY_LOAD.finditer(image.data, *image.code_range):
        rex, modrm, index_rex, index_modrm = (match.group(number)[0] for number in (1, 2, 3, 4))
        register = (modrm >> 3 & 7) | (rex & 4) << 1
        if modrm & 7 != 4 and (index_modrm & 7) | (index_rex & 1) << 3 == register:
            loads.append(EntryLoad(match.start(), register, match.start(3)))
    return loads


def aligned(data: bytes, engine: int) -> bytes:
    """Return a module as it must be to run on an engine with this many types.

    A module that declares no variables, or agrees with the engine, comes back
    as it is, so the same code does nothing once the vendors match. Raises
    Unsupported for a pairing this rewrite does not know.
    """
    rows = numbering(data)
    if rows is None or rows == engine:
        return data
    if (rows, engine) != (OLD_ROWS, NEW_ROWS):
        raise Unsupported(f"it has {rows} console variable types and the engine has {engine}")
    return adapt(data)


def adapt(data: bytes) -> bytes:
    """Return a module with the 16 row table rewritten to run on the 18 row engine.

    Raises Unsupported, naming what did not match, unless every lookup of the
    table is accounted for.
    """
    image = Image(data)
    found = find_table(image)
    if found is None or found[1] != OLD_ROWS:
        raise Unsupported("its table of types was not found")
    table = found[0]

    def lookups(pattern: re.Pattern[bytes], target: int) -> list[re.Match[bytes]]:
        """Return the matches of a pattern whose displacement selects target."""
        return [match for match in pattern.finditer(data, *image.code_range)
                if image.target(match.start(1)) == target]

    setup, declare = lookups(SETUP, table), lookups(DECLARE, table)
    traits = lookups(TRAITS, table - ROW_POINTER)
    loads = entry_loads(image)
    if len(setup) != 1 or len(declare) != 1 or len(traits) > 1:
        raise Unsupported("its registration routines were not found")
    if not any(data[load.offset + 5:load.offset + 7] == CMP_WORD for load in loads):
        raise Unsupported("its read back of the type was not found")

    # The registration code is one object file. A load of this shape outside it,
    # or a table lookup inside it left unexplained, means the code has changed.
    anchors = [setup[0].start(), declare[0].start(), *(match.start() for match in traits),
               *(load.offset for load in loads)]
    if max(anchors) - min(anchors) > REGISTRATION_SPAN:
        raise Unsupported("a load of the type sits outside the registration code")
    known = {setup[0].start() + SETUP_INDEX, declare[0].start() + DECLARE_INDEX,
             *(match.start() + TRAITS_INDEX for match in traits), *(load.index for load in loads)}
    if any(match.start() not in known for match in IMUL_ROW.finditer(data, min(anchors), max(anchors) + 0x20)):
        raise Unsupported("its table is indexed in a way this rewrite does not understand")

    # The traits helper grows into its own padding, so it goes first.
    result = bytearray(data)
    for match in traits:
        result[match.start():match.end()] = lowered_traits(image, match)
    padding = Padding(result, image.code_range)
    for load in loads:
        padding.reroute(load.offset, data[load.offset:load.offset + 5] + lower_number(load.register) + RET)
    site = declare[0].start()
    padding.reroute(site, data[site:site + 5] + RAISE_VALUE_BLOCK + RET)
    return bytes(result)


def lowered_traits(image: Image, match: re.Match[bytes]) -> bytes:
    """Return the traits helper with its number lowered, in the same place.

    The address load moves back by the added code, so its displacement shrinks.
    """
    code = lower_number(0)
    field = match.start(1) + len(code)
    head, tail = match[0][:4], match[0][11:-7]
    displacement = image.target(match.start(1)) - image.rva(field) - 4
    return head + code + match[0][4:7] + struct.pack("<i", displacement) + tail


def lower_number(register: int) -> bytes:
    """Return code that turns an engine number in a register into the module's.

    Numbers from int16 up move down by two. bool, the two types the module
    lacks, and the invalid type, which only an unbound entry holds, read as
    row 0: always a row of the module's table.
    """
    low = register & 7
    subtract = (b"\x41" if register >= 8 else b"") + bytes((0x83, 0xE8 | low, 2))
    clear = (b"\x45" if register >= 8 else b"") + bytes((0x31, 0xC0 | low << 3 | low))
    return subtract + bytes((JNS, len(clear))) + clear


class Padding:
    """Place routines in the padding between a module's functions.

    Compilers fill those gaps with int3, which no path reaches.
    """

    def __init__(self, result: bytearray, code_range: tuple[int, int]) -> None:
        self.result = result
        self.runs = [[match.start(), match.end()] for match in PADDING.finditer(result, *code_range)]
        self.placed: dict[bytes, int] = {}

    def reroute(self, site: int, routine: bytes) -> None:
        """Replace the 5 byte instruction at site with a call to a routine holding it."""
        position = self.placed.get(routine)
        if position is None:
            position = self.place(routine)
            self.placed[routine] = position
        self.result[site:site + 5] = CALL + struct.pack("<i", position - site - 5)

    def place(self, routine: bytes) -> int:
        """Return the file offset of a new copy of a routine."""
        for run in self.runs:
            if run[1] - run[0] >= len(routine):
                position = run[0]
                self.result[position:position + len(routine)] = routine
                run[0] += len(routine)
                return position
        raise Unsupported("it has no room for the rewrite")
