from __future__ import annotations

import pytest

from frontmatter import FrontmatterError, dump, open_items, parse, section, set_fields, wikilinks

NOTE = """---
type: project
status: active          # active | closed
pinned: false
summary: "Stand: SSO läuft, Quota offen (Stand 2026-10-03)"
aliases: []
topics: ["[[Obsidian]]", "[[Claude Code Plugins]]"]
supersedes:
---
# dory

## Current state
Schreibpfad steht.

## Open
- [ ] Vault-Aufbau
- [x] Name
- [ ] Spike

## History
- 2026-10-03 [[2026-10-03 dory plugin design]]: start
"""


def test_parse_scalars_bools_lists_and_comments():
    meta, body = parse(NOTE)
    assert meta["type"] == "project"
    assert meta["status"] == "active"
    assert meta["pinned"] is False
    assert meta["aliases"] == []
    assert meta["topics"] == ["[[Obsidian]]", "[[Claude Code Plugins]]"]
    assert meta["supersedes"] == ""
    assert body.startswith("# dory")


def test_umlauts_colons_and_quotes_round_trip():
    meta, _ = parse(NOTE)
    assert meta["summary"] == "Stand: SSO läuft, Quota offen (Stand 2026-10-03)"
    again, _ = parse(dump(meta))
    assert again == meta


def test_obsidian_block_lists_are_read():
    text = "---\ntype: topic\ntags:\n  - kunde\n  - werkzeug\naliases:\n- CC Plugins\n---\nbody"
    meta, body = parse(text)
    assert meta["tags"] == ["kunde", "werkzeug"]
    assert meta["aliases"] == ["CC Plugins"]
    assert body == "body"


def test_no_frontmatter_returns_empty_meta():
    assert parse("# just text") == ({}, "# just text")


def test_nested_yaml_is_rejected():
    with pytest.raises(FrontmatterError):
        parse("---\ntype: topic\nmeta:\n  nested: 1\n---\n")


def test_set_fields_updates_keeps_unknown_keys_and_orders():
    text = "---\nsummary: x\ncustom: keep\n---\nbody\n"
    out = set_fields(text, {"type": "session", "summary": "y"}, order=["type"])
    meta, body = parse(out)
    assert list(meta)[0] == "type"
    assert meta == {"type": "session", "summary": "y", "custom": "keep"}
    assert body == "body\n"


def test_section_and_open_items():
    _, body = parse(NOTE)
    assert section(body, "Current state") == "Schreibpfad steht."
    assert open_items(body) == ["Vault-Aufbau", "Spike"]


def test_wikilinks_strip_alias_heading_and_block():
    text = "see [[A|alias]], [[B#Heading]], [[C^block]] and [[folder/D]]"
    assert wikilinks(text) == ["A", "B", "C", "folder/D"]
