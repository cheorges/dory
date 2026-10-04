"""Flat YAML frontmatter and Markdown section helpers.

ponytail: no PyYAML. Supports exactly what dory writes and what Obsidian's
property editor produces: scalars, booleans, inline lists, block lists.
Nested mappings raise FrontmatterError.
"""
from __future__ import annotations

import json
import re

_FM = re.compile(r"\A---\n(?:(.*?)\n)?---[ \t]*(?:\n|\Z)", re.S)
_KEY = re.compile(r"([A-Za-z_][\w-]*):(?:[ \t]+(.*))?$")
_ITEM = re.compile(r"\s*-\s+(.*)$")
_LIST_ITEM = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|\'([^\']*)\'|([^,]+?))\s*(?:,|$)')
_LINK = re.compile(r"\[\[([^\]|#^]+)")


class FrontmatterError(ValueError):
    pass


def _strip_comment(value: str) -> str:
    value = value.strip()
    if value[:1] in ('"', "'"):
        return value
    return value.split(" #", 1)[0].strip()


def _scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return json.loads(value)
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1]
    if value in ("true", "false"):
        return value == "true"
    return value


def _inline_list(value: str) -> list:
    inner = value.strip()[1:-1]
    items = []
    for dq, sq, bare in _LIST_ITEM.findall(inner):
        if dq or sq:
            items.append(json.loads(f'"{dq}"') if dq else sq)
        elif bare.strip():
            items.append(bare.strip())
    return items


def parse(text: str) -> tuple:
    m = _FM.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    key = None
    open_keys: set = set()
    for line in (m.group(1) or "").split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = _ITEM.match(line)
        if item and key in open_keys:
            meta[key].append(_scalar(item.group(1)))
            continue
        kv = _KEY.match(line)
        if not kv:
            raise FrontmatterError(f"unsupported frontmatter line: {line!r}")
        key, raw = kv.group(1), _strip_comment(kv.group(2) or "")
        open_keys.discard(key)
        if raw == "":
            meta[key] = []
            open_keys.add(key)
        elif raw.startswith("[") and raw.endswith("]"):
            meta[key] = _inline_list(raw)
        else:
            meta[key] = _scalar(raw)
    for k in open_keys:
        if meta[k] == []:
            meta[k] = ""  # ponytail: "key:" without items is an empty scalar, like Obsidian's empty text property
    return meta, text[m.end():]


def _needs_quotes(value: str) -> bool:
    return (value == "" or value != value.strip() or value in ("true", "false")
            or any(c in value for c in ':#[]{},"\'') or value[:1] in "-?!&*|>%@`")


def _dump_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(str(v), ensure_ascii=False) for v in value) + "]"
    value = str(value)
    return json.dumps(value, ensure_ascii=False) if _needs_quotes(value) else value


def dump(meta: dict) -> str:
    lines = [f"{k}: {_dump_value(v)}" for k, v in meta.items()]
    return "---\n" + "\n".join(lines) + "\n---\n"


def set_fields(text: str, updates: dict, order: list = None) -> str:
    meta, body = parse(text)
    meta.update(updates)
    if order:
        meta = {**{k: meta[k] for k in order if k in meta}, **{k: v for k, v in meta.items() if k not in order}}
    return dump(meta) + body


def section(body: str, name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}[ \t]*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""


def open_items(body: str) -> list:
    return re.findall(r"^\s*- \[ \] (.+?)\s*$", section(body, "Open"), re.M)


def wikilinks(text: str) -> list:
    return [t.strip() for t in _LINK.findall(text)]
