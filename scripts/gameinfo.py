"""Build the toolkit's gameinfo.gi from the game's current one.

The game's file carries Valve's renderer, editor and compiler settings, which
change with each update, so the toolkit starts from it and changes only what the
toolkit's layout needs. The changes live in an overlay file in the same KeyValues
format: each of its sections merges into the game's section of the same name key
by key, and each value inside a section, a block or a single value, replaces the
game's whole. A search path list therefore replaces the game's list, including
any search paths another program added to the game's file.
"""

from __future__ import annotations

import re

# A KeyValues token: a quoted string, a brace, or a bare word. Comments start
# with // and run to the end of the line.
TOKEN = re.compile(r'\s+|//[^\n]*|"((?:[^"\\]|\\.)*)"|([{}])|([^\s{}"]+)')

Block = list[tuple[str, "str | Block"]]


def parse(text: str) -> Block:
    """Read KeyValues text into ordered (key, value) pairs; keys may repeat."""
    tokens = []
    position = 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if match is None:
            raise ValueError(f"Unreadable KeyValues at offset {position}")
        position = match.end()
        if match[1] is not None:
            tokens.append(("word", match[1]))
        elif match[2] is not None:
            tokens.append((match[2], match[2]))
        elif match[3] is not None:
            tokens.append(("word", match[3]))

    def block(index: int, closed: bool) -> tuple[Block, int]:
        pairs: Block = []
        while index < len(tokens):
            kind, key = tokens[index]
            if kind == "}" and closed:
                return pairs, index + 1
            if kind != "word" or index + 1 >= len(tokens):
                raise ValueError(f"Expected a key, found {key!r}")
            kind, value = tokens[index + 1]
            if kind == "{":
                child, index = block(index + 2, True)
                pairs.append((key, child))
            elif kind == "word":
                pairs.append((key, value))
                index += 2
            else:
                raise ValueError(f"Expected a value for {key!r}")
        if closed:
            raise ValueError("Unclosed block")
        return pairs, index

    return block(0, False)[0]


def format_block(pairs: Block, depth: int = 0) -> str:
    """Write pairs as KeyValues text, one pair per line, indented by tabs."""
    indent = "\t" * depth
    lines = []
    for key, value in pairs:
        if isinstance(value, str):
            lines.append(f'{indent}"{key}"\t"{value}"\n')
        else:
            lines.append(f'{indent}"{key}"\n{indent}{{\n{format_block(value, depth + 1)}{indent}}}\n')
    return "".join(lines)


def overlay(game: Block, changes: Block, levels: int) -> Block:
    """Apply changes to a copy of game; blocks merge for levels more levels.

    A key matches the game's first pair of that name, ignoring case, as the
    engine reads it; a key the game lacks is added at the end.
    """
    result = list(game)
    for key, value in changes:
        index = next((i for i, (name, _) in enumerate(result) if name.lower() == key.lower()), None)
        if index is None:
            result.append((key, value))
            continue
        current = result[index][1]
        if levels > 0 and not isinstance(value, str) and not isinstance(current, str):
            value = overlay(current, value, levels - 1)
        result[index] = (result[index][0], value)
    return result


def tools(game: bytes, changes: bytes) -> bytes:
    """Return the toolkit's gameinfo.gi: the game's file with changes applied.

    Both files hold one root block, GameInfo; its sections merge one level
    deep.
    """
    (root, game_info), = parse(game.decode("utf-8-sig"))
    (_, change_info), = parse(changes.decode("utf-8-sig"))
    if isinstance(game_info, str) or isinstance(change_info, str):
        raise ValueError("gameinfo.gi must hold one GameInfo block")
    return format_block([(root, overlay(game_info, change_info, 1))]).encode()
