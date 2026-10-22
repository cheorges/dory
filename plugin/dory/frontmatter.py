"""Read the YAML frontmatter of vault notes without a YAML library.

The notes follow the fixed schema in dory:rules: flat keys, scalars, inline lists
(`["[[a]]", "[[b]]"]`, `[loki, docker]`) and block lists (`- item`). Anything richer is
not needed, and a stdlib parser keeps the SessionStart hook free of dependencies.
"""

import json
from pathlib import Path

_MAX_HEADER_BYTES = 8_192
_BLOCK_INDICATORS = {">", ">-", ">+", "|", "|-", "|+"}


def read_frontmatter(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as handle:
            head = handle.read(_MAX_HEADER_BYTES)
    except OSError:
        return {}
    return parse_frontmatter(head)


def parse_frontmatter(text: str) -> dict[str, object]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, object] = {}
    key = None
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        stripped = line.strip()
        if key and stripped.startswith("- ") and line[:1] in (" ", "-"):
            current = data.get(key)
            data[key] = (
                [*current, _scalar(stripped[2:])]
                if isinstance(current, list)
                else [_scalar(stripped[2:])]
            )
            continue
        if key and line[:1] == " " and stripped and data.get(key) in ("", []):
            data[key] = stripped  # value on the line after the key, or after `>` / `|`
            continue
        if key and line[:1] == " " and isinstance(data.get(key), str):
            data[key] = f"{data[key]} {stripped}".strip()  # folded continuation line
            continue
        if ":" not in line or line[:1] == " ":
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        data[key] = _value(value.strip())
    return {}  # no closing marker: not a frontmatter block


def body(path: Path) -> str:
    return strip_frontmatter(path.read_text(encoding="utf-8-sig", errors="replace"))


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    _, _, rest = text.partition("\n---")
    return rest.partition("\n")[2]


def _value(raw: str) -> object:
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        inner = raw[1:-1].strip()
        return [_scalar(part) for part in inner.split(",")] if inner else []
    if raw == "":
        return []  # a key followed by a block list, or an empty value
    if raw in _BLOCK_INDICATORS:
        return ""  # block scalar: the indented lines that follow are the value
    return _scalar(raw)


def _scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def add_list_item(text: str, key: str, item: str) -> str:
    """`text` with `item` appended to the list property `key`, written as a block list.

    An inline list or a scalar under `key` becomes a block list with its values kept; a file
    without frontmatter gets one. The other keys and the body stay as they are.
    """
    lines = text.splitlines(keepends=True)
    end = closing_line(lines)
    if end is None:
        head, rest = [], text
    else:
        head, rest = [line.rstrip("\n") for line in lines[1:end]], "".join(lines[end + 1 :])
    blocks = _key_blocks(head)
    found = next((index for index, (name, _) in enumerate(blocks) if name == key), None)
    values: list[str] = []
    if found is not None:
        current = parse_frontmatter("\n".join(["---", *blocks[found][1], "---"])).get(key)
        values = [str(value) for value in current] if isinstance(current, list) else []
        if isinstance(current, str) and current:
            values = [current]
    items = [*values, item]
    block = [f"{key}:", *(f"  - {json.dumps(value, ensure_ascii=False)}" for value in items)]
    if found is None:
        blocks.append((key, block))
    else:
        blocks[found] = (key, block)
    head = [line for _, block_lines in blocks for line in block_lines]
    return "\n".join(["---", *head, "---", ""]) + rest


def closing_line(lines: list[str]) -> int | None:
    """The index of the line that closes the frontmatter; None without a complete one."""
    if not lines or lines[0].strip() != "---":
        return None
    return next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)


def _key_blocks(head: list[str]) -> list[tuple[str, list[str]]]:
    """Frontmatter lines grouped by key; indented and list lines belong to the key above."""
    blocks: list[tuple[str, list[str]]] = []
    for line in head:
        if (line[:1] not in (" ", "-", "") and ":" in line) or not blocks:
            blocks.append((line.partition(":")[0].strip(), [line]))
        else:
            blocks[-1][1].append(line)
    return blocks
