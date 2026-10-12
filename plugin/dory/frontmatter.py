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
    text = path.read_text(encoding="utf-8-sig", errors="replace")
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
