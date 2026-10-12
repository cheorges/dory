from dory.frontmatter import parse_frontmatter


def test_schema_shapes_are_parsed():
    text = """---
type: gotcha
projects: ["[[ai-assistant-hub]]", "[[ai-assistant-hub-infrastructure]]"]
tags: [loki, docker]
summary: "Loki only starts with UID 10001."
related:
  - "[[teko]]"
  - anella
superseded_by:
pinned: false
---
Text
"""
    data = parse_frontmatter(text)

    assert data["projects"] == ["[[ai-assistant-hub]]", "[[ai-assistant-hub-infrastructure]]"]
    assert data["tags"] == ["loki", "docker"]
    assert data["summary"] == "Loki only starts with UID 10001."
    assert data["related"] == ["[[teko]]", "anella"]
    assert not data["superseded_by"]
    assert data["pinned"] == "false"


def test_folded_summary_is_joined():
    data = parse_frontmatter("---\nsummary: Erste Zeile\n  zweite Zeile\n---\n")

    assert data["summary"] == "Erste Zeile zweite Zeile"


def test_missing_or_unclosed_frontmatter_gives_nothing():
    assert parse_frontmatter("# Titel\n") == {}
    assert parse_frontmatter("---\ntype: session\n") == {}


def test_block_scalar_and_value_on_next_line_are_read():
    folded = parse_frontmatter("---\nsummary: >-\n  Phase B\n  geplant\n---\n")
    next_line = parse_frontmatter("---\nsummary:\n  Phase B geplant\n---\n")

    assert folded["summary"] == "Phase B geplant"
    assert next_line["summary"] == "Phase B geplant"


def test_byte_order_mark_is_tolerated(tmp_path):
    from dory.frontmatter import read_frontmatter

    note = tmp_path / "bom.md"
    note.write_text("﻿---\ntype: project\n---\n", encoding="utf-8")

    assert read_frontmatter(note) == {"type": "project"}
