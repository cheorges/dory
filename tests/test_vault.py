from __future__ import annotations

import os
import subprocess
import time
from datetime import date
from pathlib import Path

from conftest import write_note
from vault import (active_notes, append_log, build_hot, changed_since, conflict_files, dead_links, find_project_note,
                   find_session_note, hot_line, is_active, iter_notes, project_name, project_root, seed, snapshot,
                   writable)

TODAY = date(2026, 10, 3)


def note(type_, last_active="2026-10-01", **extra):
    fields = {"type": type_, "status": "active", "pinned": "false", "last_active": last_active,
              "summary": f'"{type_} summary"', **extra}
    fm = "\n".join(f"{k}: {v}" for k, v in fields.items())
    return f"---\n{fm}\n---\n# x\n\n## Open\n- [ ] one\n- [ ] two\n"


def test_seed_copies_missing_and_never_overwrites(tmp_path, vault):
    src = tmp_path / "seed"
    write_note(src / "types.md", "seed types")
    write_note(src / "templates" / "topic.md", "seed topic")
    write_note(vault / "types.md", "user edited")
    copied = seed(vault, src)
    assert (vault / "types.md").read_text() == "user edited"
    assert (vault / "templates" / "topic.md").read_text() == "seed topic"
    assert copied == [vault / "templates" / "topic.md"]


def test_iter_notes_skips_reserved_templates_dotdirs_and_reports_errors(vault):
    write_note(vault / "topics" / "A.md", note("topic"))
    write_note(vault / "hot.md", "x")
    write_note(vault / "templates" / "topic.md", note("topic"))
    write_note(vault / ".obsidian" / "x.md", note("topic"))
    write_note(vault / "topics" / "Broken.md", "---\ntype: topic\nmeta:\n  nested: 1\n---\n")
    errors = []
    names = [p.name for p, _, _ in iter_notes(vault, errors)]
    assert names == ["A.md"]
    assert errors and errors[0][0].name == "Broken.md"


def test_project_root_for_repo_worktree_and_plain_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "init"], check=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})
    (repo / "sub").mkdir()
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(wt)], check=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    assert project_root(str(repo / "sub")) == repo.resolve()
    assert project_root(str(wt)) == repo.resolve()
    assert project_root(str(plain)) == plain.resolve()


def test_project_name_prefers_note_with_matching_path(tmp_path, vault):
    work = tmp_path / "work" / "dory-repo"
    work.mkdir(parents=True)
    write_note(vault / "projects" / "dory" / "dory.md", note("project", path=str(work)))
    assert find_project_note(vault, work.resolve()) == vault / "projects" / "dory" / "dory.md"
    assert project_name(vault, str(work)) == ("dory", work.resolve())
    other = tmp_path / "other"
    other.mkdir()
    assert project_name(vault, str(other)) == ("other", other.resolve())


def test_find_session_note(vault):
    write_note(vault / "sessions" / "2026-10-03 x.md", "---\ntype: session\nsession_id: abc\n---\n")
    assert find_session_note(vault, "abc").name == "2026-10-03 x.md"
    assert find_session_note(vault, "nope") is None


def test_is_active_rules():
    assert is_active({"last_active": "2026-09-20"}, TODAY, 14)
    assert not is_active({"last_active": "2026-09-18"}, TODAY, 14)
    assert is_active({"last_active": "2020-01-01", "pinned": True}, TODAY, 14)
    assert not is_active({"last_active": "2026-10-03", "status": "closed"}, TODAY, 14)
    assert not is_active({}, TODAY, 14)


def test_active_notes_order_and_sessions_excluded(vault):
    write_note(vault / "topics" / "Old.md", note("topic", "2026-09-25"))
    write_note(vault / "topics" / "New.md", note("topic", "2026-10-02"))
    write_note(vault / "topics" / "Pinned.md", note("topic", "2025-01-01", pinned="true"))
    write_note(vault / "sessions" / "S.md", note("session", "2026-10-03"))
    assert [p.stem for p, _, _ in active_notes(vault, TODAY, 14)] == ["Pinned", "New", "Old"]


def test_hot_line_and_build_hot(vault):
    p = write_note(vault / "projects" / "dory" / "dory.md", note("project", "2026-10-02"))
    write_note(vault / "topics" / "Gone.md", note("topic", "2026-01-01"))
    meta = {"type": "project", "last_active": "2026-10-02", "summary": "Stand X"}
    assert hot_line(p, meta, "## Open\n- [ ] a\n") == "- [[dory]] (project, 2026-10-02): Stand X · 1 open"
    hot = build_hot(vault, TODAY, 14).read_text(encoding="utf-8")
    assert "[[dory]]" in hot and "Gone" not in hot


def test_snapshot_changed_dead_links_conflicts_log(vault):
    write_note(vault / "topics" / "A.md", "---\ntype: topic\n---\n[[B]] [[A]] [[img.png]] [[folder/A]]")
    before = snapshot(vault)
    assert "topics/" in before and "topics/A.md" in before
    t = time.time()
    time.sleep(0.01)
    b = write_note(vault / "topics" / "C.md", "---\ntype: topic\n---\n")
    write_note(vault / "log.md", "x")
    assert changed_since(vault, t) == [b]
    assert dead_links(vault, [vault / "topics" / "A.md"]) == [(vault / "topics" / "A.md", "B")]
    write_note(vault / "topics" / "A (conflicted copy).md", "x")
    assert [p.name for p in conflict_files(vault)] == ["A (conflicted copy).md"]
    append_log(vault, "line one")
    assert (vault / "log.md").read_text().endswith("line one\n")


def test_writable(tmp_path, vault):
    assert writable(vault)
    assert not writable(tmp_path / "missing")
    assert not writable(None)


def test_find_session_note_skips_non_utf8_files(vault):
    (vault / "sessions").mkdir()
    (vault / "sessions" / "a latin1.md").write_bytes("---\ntype: session\nsummary: Gr\xfcn\n---\n".encode("latin-1"))
    write_note(vault / "sessions" / "b.md", "---\ntype: session\nsession_id: abc\n---\n")
    assert find_session_note(vault, "abc").name == "b.md"
