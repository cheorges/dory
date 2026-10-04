from __future__ import annotations

from pathlib import Path

from frontmatter import parse

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = {
    "project": ["## Current state", "## Open", "## History"],
    "topic": ["## Current state", "## Open", "## History"],
    "decision": ["## Context", "## Decision", "## Alternatives", "## Source"],
    "session": ["## Summary", "## Decisions", "## Open", "## Touched"],
}
COMMON = ["type", "status", "pinned", "created", "last_active", "summary", "aliases", "tags"]


def test_templates_have_frontmatter_and_sections():
    for type_, sections in SECTIONS.items():
        text = (ROOT / "vault-seed" / "templates" / f"{type_}.md").read_text(encoding="utf-8")
        meta, body = parse(text)
        assert meta["type"] == type_
        if type_ != "session":
            assert all(k in meta for k in COMMON), type_
        for s in sections:
            assert s in body, (type_, s)


def test_types_md_lists_types_and_limits():
    text = (ROOT / "vault-seed" / "types.md").read_text(encoding="utf-8")
    for needle in ["sessions/", "projects/", "topics/", "decisions/", "min_notes_for_new_type: 3",
                   "max_types: 8", "min_notes_for_subfolder: 5", "max_subfolder_depth: 1"]:
        assert needle in text


def test_rules_cover_every_spec_rule():
    text = (ROOT / "rules" / "writer.md").read_text(encoding="utf-8")
    for needle in ["Search before creating", "## Current state", "## History", "supersedes", "SKIP", "aliases",
                   "[REDACTED]", "types.md", "(as of", "last_active", "summary", "note language",
                   "keep its `# ` title", "## Touched", "only decided", "names an alternative"]:
        assert needle in text, needle
