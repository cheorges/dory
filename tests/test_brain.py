from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import brain
from conftest import assistant, user, write_note, write_transcript
from frontmatter import parse
from state import Config, enqueue, failed_count, load_anchors, queue_items, set_anchor

TODAY = date(2026, 10, 3)
BRAIN = Path(brain.__file__)


def cfg_for(tmp_path, **kw):
    v = tmp_path / "vault"
    v.mkdir(exist_ok=True)
    return Config(vault=v, data=tmp_path / "data", projects_dir=tmp_path / "projects", **kw)


def convo(n_user=3, entrypoint="cli", cwd="/w/dory"):
    es = []
    for i in range(n_user):
        es.append(user(f"u{i}", f"frage {i}", entrypoint=entrypoint, cwd=cwd))
        es.append(assistant(f"a{i}", {"type": "text", "text": f"antwort {i}"}))
    return es


def test_session_end_enqueues_and_spawns(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_CHILD", raising=False)
    cfg = cfg_for(tmp_path)
    spawned = []
    brain.session_end(cfg, {"session_id": "s1", "transcript_path": "/t", "cwd": "/w", "reason": "clear"},
                      spawn=spawned.append)
    assert [i["reason"] for _, i in queue_items(cfg)] == ["clear"]
    assert spawned == [cfg]


def test_session_end_guards(tmp_path, monkeypatch):
    cfg = cfg_for(tmp_path, exclude_paths=["/secret"])
    spawned = []
    monkeypatch.setenv("BRAIN_CHILD", "1")
    brain.session_end(cfg, {"session_id": "a", "cwd": "/w"}, spawn=spawned.append)
    monkeypatch.delenv("BRAIN_CHILD")
    brain.session_end(cfg, {"session_id": "b", "cwd": "/secret/x"}, spawn=spawned.append)
    cfg.auto_capture = False
    brain.session_end(cfg, {"session_id": "c", "cwd": "/w"}, spawn=spawned.append)
    cfg.auto_capture, cfg.vault = True, None
    brain.session_end(cfg, {"session_id": "d", "cwd": "/w"}, spawn=spawned.append)
    assert spawned == [] and queue_items(cfg) == []


def test_session_start_without_vault_path(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_CHILD", raising=False)
    cfg = cfg_for(tmp_path)
    cfg.vault = None
    assert "vault_path is not set" in brain.session_start(cfg, {}, spawn=lambda c: None)


def test_session_start_catches_up_and_notices(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_CHILD", raising=False)
    cfg = cfg_for(tmp_path)
    (cfg.data).mkdir(parents=True)
    (cfg.data / "installed_at").write_text(str(time.time() - 30 * 86400))
    t = write_transcript(cfg.projects_dir / "p" / "missed.jsonl", convo())
    old = time.time() - 3 * 3600
    os.utime(t, (old, old))
    spawned = []
    out = brain.session_start(cfg, {"session_id": "now", "cwd": str(tmp_path), "source": "clear"},
                              spawn=spawned.append, today=TODAY)
    assert [i["session_id"] for _, i in queue_items(cfg)] == ["missed"]
    assert spawned == [cfg]
    assert "previous session is being written" in out


def test_process_skips_short_and_headless_sessions(tmp_path):
    cfg = cfg_for(tmp_path)
    short = write_transcript(tmp_path / "short.jsonl", convo(n_user=2))
    headless = write_transcript(tmp_path / "headless.jsonl", convo(entrypoint="sdk-cli"))
    assert brain.process(cfg, {"session_id": "s", "transcript_path": str(short), "cwd": "/w"}, TODAY) == "skipped"
    assert brain.process(cfg, {"session_id": "h", "transcript_path": str(headless), "cwd": "/w"}, TODAY) == "skipped"
    assert load_anchors(cfg)["s"]["uuid"] == "a1"


def _fake_claude(tmp_path, monkeypatch, body):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "claude"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def test_worker_end_to_end_with_fake_writer(tmp_path, monkeypatch):
    cfg = cfg_for(tmp_path)
    t = write_transcript(cfg.projects_dir / "p" / "s1.jsonl", convo())
    enqueue(cfg, {"session_id": "s1", "transcript_path": str(t), "cwd": str(tmp_path), "reason": "other"})
    # fake writer: the vault is the argument after --add-dir; it writes one session note
    _fake_claude(tmp_path, monkeypatch, r'''
while [ "$1" != "--add-dir" ]; do shift; done; V="$2"
cat > /dev/null
mkdir -p "$V/sessions"
printf -- '---\nsummary: "fertig"\n---\n## Summary\nok\n' > "$V/sessions/2026-10-03 dory test.md"
echo done
''')
    brain.worker(cfg, today=TODAY)
    assert queue_items(cfg) == []
    note = cfg.vault / "sessions" / "2026-10-03 dory test.md"
    meta, _ = parse(note.read_text(encoding="utf-8"))
    assert meta["session_id"] == "s1" and meta["written_by"] == "background"
    assert (cfg.vault / "types.md").exists() and (cfg.vault / "templates" / "session.md").exists()
    assert "| background | session s1" in (cfg.vault / "log.md").read_text(encoding="utf-8")
    assert load_anchors(cfg)["s1"]["uuid"] == "a2"


def test_worker_records_failure_and_releases_lock(tmp_path, monkeypatch):
    cfg = cfg_for(tmp_path)
    t = write_transcript(cfg.projects_dir / "p" / "s1.jsonl", convo())
    enqueue(cfg, {"session_id": "s1", "transcript_path": str(t), "cwd": "/w"})
    _fake_claude(tmp_path, monkeypatch, "cat > /dev/null; exit 1\n")
    brain.worker(cfg, today=TODAY)
    assert queue_items(cfg)[0][1]["attempts"] == 1
    assert not (cfg.data / "lock").exists()


def test_worker_passes_and_reuses_existing_session_note(tmp_path, monkeypatch):
    cfg = cfg_for(tmp_path)
    t = write_transcript(cfg.projects_dir / "p" / "s1.jsonl", convo())
    write_note(cfg.vault / "sessions" / "earlier.md", "---\ntype: session\nsession_id: s1\n---\n")
    enqueue(cfg, {"session_id": "s1", "transcript_path": str(t), "cwd": "/w"})
    # the fake writer fails unless the prompt names the existing note
    _fake_claude(tmp_path, monkeypatch, 'grep -q "existing session note: sessions/earlier.md" || exit 1; echo SKIP\n')
    brain.worker(cfg, today=TODAY)
    assert queue_items(cfg) == []
    assert [p.name for p in (cfg.vault / "sessions").glob("*.md")] == ["earlier.md"]
    meta, _ = parse((cfg.vault / "sessions" / "earlier.md").read_text(encoding="utf-8"))
    assert meta["written_by"] == "background"


def _run_cli(args, stdin, env):
    return subprocess.run([sys.executable, str(BRAIN), *args], input=stdin, capture_output=True, text=True, env=env)


def test_cli_invalid_stdin_exits_zero_silently(tmp_path):
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "d")}
    for args in (["session-end"], ["session-start"]):
        r = _run_cli(args, "not json", env)
        assert r.returncode == 0
        assert "Traceback" not in r.stderr


def test_cli_session_start_prints_hook_json(tmp_path):
    v = tmp_path / "My Vault"
    v.mkdir()
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "d"), "CLAUDE_PLUGIN_OPTION_VAULT_PATH": str(v),
           "CLAUDE_PLUGIN_OPTION_AUTO_CAPTURE": "false"}
    env.pop("BRAIN_CHILD", None)
    r = _run_cli(["session-start"], json.dumps({"session_id": "x", "cwd": str(tmp_path), "source": "startup"}), env)
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "dory: second brain in" in out["hookSpecificOutput"]["additionalContext"]


def test_cli_begin_and_finish_for_save(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    projects = tmp_path / "projects"
    write_transcript(projects / "p" / "s9.jsonl", convo(cwd=str(tmp_path)))
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("CLAUDE_PLUGIN_DATA", None)
    args = ["--vault", str(v), "--data", str(tmp_path / "d"), "--projects", str(projects)]
    assert _run_cli(["begin", "--session", "s9", *args], "", env).returncode == 0
    time.sleep(0.01)
    write_note(v / "sessions" / "2026-10-03 x save.md", '---\nsummary: "s"\n---\n## Summary\nx\n')
    r = _run_cli(["finish", "--session", "s9", "--written-by", "save", *args], "", env)
    assert r.returncode == 0, r.stderr
    meta, _ = parse((v / "sessions" / "2026-10-03 x save.md").read_text(encoding="utf-8"))
    assert meta["written_by"] == "save" and meta["session_id"] == "s9"
    anchors = json.loads((tmp_path / "d" / "processed.json").read_text())
    assert anchors["s9"]["uuid"] == "a2"
    assert not (tmp_path / "d" / "begin" / "s9.json").exists()


def test_worker_keeps_an_item_reenqueued_while_it_was_processed(tmp_path, monkeypatch):
    cfg = cfg_for(tmp_path)
    enqueue(cfg, {"session_id": "s1", "transcript_path": "/x", "cwd": "/w"})
    calls = []

    def fake_process(cfg_, item, today):
        calls.append(item["session_id"])
        if len(calls) == 1:
            time.sleep(0.01)
            enqueue(cfg_, {"session_id": "s1", "transcript_path": "/x", "cwd": "/w", "reason": "resume"})
        return "written"

    monkeypatch.setattr(brain, "process", fake_process)
    brain.worker(cfg, today=TODAY)
    assert calls == ["s1", "s1"]
    assert queue_items(cfg) == []


def test_process_sets_anchor_before_cleanup_can_fail(tmp_path, monkeypatch):
    cfg = cfg_for(tmp_path)
    t = write_transcript(cfg.projects_dir / "p" / "s1.jsonl", convo())
    monkeypatch.setattr(brain, "run_writer", lambda cfg_, prompt: "done")

    def broken_finish(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(brain, "finish", broken_finish)
    try:
        brain.process(cfg, {"session_id": "s1", "transcript_path": str(t), "cwd": "/w"}, TODAY)
    except OSError:
        pass
    assert load_anchors(cfg)["s1"]["uuid"] == "a2"


def test_hooks_write_one_event_line_each(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_CHILD", raising=False)
    cfg = cfg_for(tmp_path, auto_capture=False)
    brain.session_start(cfg, {"session_id": "s1", "source": "clear", "cwd": str(tmp_path)}, spawn=lambda c: None)
    brain.session_end(cfg, {"session_id": "s1", "reason": "prompt_input_exit", "cwd": "/w"}, spawn=lambda c: None)
    lines = (cfg.data / "events.log").read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("start session s1 source=clear")
    assert lines[1].endswith("end session s1 reason=prompt_input_exit")


def test_event_log_failure_never_stops_the_hook(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIN_CHILD", raising=False)
    cfg = cfg_for(tmp_path)
    cfg.data.mkdir(parents=True)
    (cfg.data / "events.log").mkdir()
    spawned = []
    brain.session_end(cfg, {"session_id": "s1", "cwd": "/w"}, spawn=spawned.append)
    assert spawned == [cfg]


def test_finish_keeps_the_begin_record_when_it_fails(tmp_path, monkeypatch):
    cfg = cfg_for(tmp_path)
    brain.begin(cfg, "s9")

    def broken_finish(*a, **kw):
        raise OSError("vault gone")

    monkeypatch.setattr(brain, "finish", broken_finish)
    try:
        brain.finish_cmd(cfg, "s9", "save", today=TODAY)
    except OSError:
        pass
    assert (cfg.data / "begin" / "s9.json").exists()
