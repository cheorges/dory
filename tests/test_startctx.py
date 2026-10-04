from __future__ import annotations

import os
import time
from datetime import date

from conftest import user, write_note, write_transcript
from startctx import find_missed, render
from state import Config, enqueue, load_anchors, set_anchor

TODAY = date(2026, 10, 3)


def cfg_for(tmp_path, **kw):
    return Config(vault=tmp_path / "vault", data=tmp_path / "data", projects_dir=tmp_path / "projects", **kw)


def topic(i, pinned="false"):
    return (f"---\ntype: topic\nstatus: active\npinned: {pinned}\nlast_active: 2026-10-{(i % 3) + 1:02d}\n"
            f"summary: \"summary {i} {'x' * 80}\"\n---\n")


def test_render_current_project_active_and_notices(tmp_path):
    cfg = cfg_for(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    write_note(cfg.vault / "projects" / "dory" / "dory.md",
               f"---\ntype: project\nstatus: active\nlast_active: 2026-10-03\nsummary: Schreibpfad steht\n"
               f"path: {work}\n---\n# dory\n\n## Open\n- [ ] Spike\n- [ ] Plan\n")
    write_note(cfg.vault / "topics" / "Obsidian.md", topic(1))
    out = render(cfg, str(work), ["new folder people/"], TODAY)
    assert out.startswith("dory: second brain in ")
    assert "## Current project: [[dory]] (2026-10-03)\nSchreibpfad steht\nOpen: Spike; Plan" in out
    assert "- [[Obsidian]] (topic," in out
    assert "[[dory]] (project" not in out
    assert "## Notices\n- new folder people/" in out


def test_render_without_project_or_notices_has_no_empty_sections(tmp_path):
    cfg = cfg_for(tmp_path)
    cfg.vault.mkdir()
    out = render(cfg, str(tmp_path), [], TODAY)
    assert "Current project" not in out and "## Notices" not in out


def test_render_budget_drops_oldest_unpinned_keeps_pinned(tmp_path):
    cfg = cfg_for(tmp_path)
    for i in range(80):
        write_note(cfg.vault / "topics" / f"T{i:02d}.md", topic(i))
    write_note(cfg.vault / "topics" / "Pin.md", topic(99, pinned="true").replace("2026-10-01", "2020-01-01"))
    out = render(cfg, str(tmp_path), [], TODAY, target=4000, hard=9000)
    assert len(out) <= 4000
    assert "[[Pin]]" in out
    assert "more in hot.md" in out


def test_render_hard_limit(tmp_path):
    cfg = cfg_for(tmp_path)
    for i in range(5):
        write_note(cfg.vault / "topics" / f"P{i}.md", topic(i, pinned="true").replace("x" * 80, "x" * 3000))
    out = render(cfg, str(tmp_path), [], TODAY, target=4000, hard=9000)
    assert len(out) <= 9000


def _transcript(cfg, sid, age, entrypoint="cli", cwd="/w/p"):
    p = write_transcript(cfg.projects_dir / "proj" / f"{sid}.jsonl",
                         [user(f"{sid}-1", "hi", entrypoint=entrypoint, cwd=cwd)])
    t = time.time() - age
    os.utime(p, (t, t))
    return p


def test_find_missed_filters(tmp_path):
    cfg = cfg_for(tmp_path, exclude_paths=["/secret"])
    now = time.time()
    _transcript(cfg, "ok", 3 * 3600)
    _transcript(cfg, "current", 3 * 3600)
    _transcript(cfg, "running", 600)
    _transcript(cfg, "old", 8 * 86400)
    _transcript(cfg, "headless", 3 * 3600, entrypoint="sdk-cli")
    _transcript(cfg, "excluded", 3 * 3600, cwd="/secret/repo")
    _transcript(cfg, "done", 3 * 3600)
    set_anchor(cfg, "done", "done-1")
    _transcript(cfg, "queued", 3 * 3600)
    enqueue(cfg, {"session_id": "queued"})
    got = find_missed(cfg, "current", now, installed_at=now - 30 * 86400)
    assert [g["session_id"] for g in got] == ["ok"]
    assert got[0]["reason"] == "catch-up" and got[0]["cwd"] == "/w/p"
    assert {"headless", "excluded"} <= set(load_anchors(cfg))


def test_find_missed_respects_install_time(tmp_path):
    cfg = cfg_for(tmp_path)
    now = time.time()
    _transcript(cfg, "before", 5 * 3600)
    assert find_missed(cfg, None, now, installed_at=now - 4 * 3600) == []


def test_find_missed_skips_sessions_that_failed_for_good(tmp_path):
    cfg = cfg_for(tmp_path)
    now = time.time()
    _transcript(cfg, "broken", 3 * 3600)
    write_note(cfg.data / "queue" / "failed" / "broken.json", '{"session_id": "broken", "attempts": 3}')
    assert find_missed(cfg, None, now, installed_at=now - 30 * 86400) == []
