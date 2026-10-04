from __future__ import annotations

from pathlib import Path

from frontmatter import parse

ROOT = Path(__file__).resolve().parent.parent


def skill(name):
    meta, body = parse((ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8"))
    return meta, body


def test_skills_have_name_and_description():
    for name in ("search", "save", "note"):
        meta, body = skill(name)
        assert meta["name"] == name
        assert len(meta["description"]) > 40
        assert body.strip()


def test_search_description_pushes_lookup():
    meta, _ = skill("search")
    assert "before saying you don't know" in meta["description"]


def test_save_and_note_call_begin_and_finish():
    for name, written_by in (("save", "save"), ("note", "note")):
        _, body = skill(name)
        assert "brain.py\" begin" in body
        assert f"--written-by {written_by}" in body
        assert "--session ${" not in body
        assert "rules/writer.md" in body


def test_save_checks_its_notes_before_finish():
    _, body = skill("save")
    assert body.index("Before step 4") < body.index("brain.py\" finish")
    for needle in ["## Summary", "decisions/", "only decided"]:
        assert needle in body, needle


def test_save_and_note_preapprove_brain_but_no_writes():
    # writes need the user's own Edit(<vault>/**) rule: placeholders are not replaced in allowed-tools
    for name in ("save", "note"):
        meta, body = skill(name)
        tools = [t.strip() for t in meta["allowed-tools"].split(",")]
        assert "Bash(python3 *scripts/brain.py*)" in tools
        assert not [t for t in tools if t.startswith(("Write", "Edit"))]
        assert "never with Bash" in body
