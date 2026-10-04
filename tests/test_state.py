from __future__ import annotations

import json
import os
import subprocess
import sys

import state
from state import (Config, acquire_lock, add_notice, enqueue, ensure_installed_at, failed_count, load_anchors,
                   drop_begin, load_begin, pop_notices, queue_items, record_failure, release_lock, save_begin, set_anchor)


def cfg_for(tmp_path, **kw):
    return Config(vault=tmp_path / "vault", data=tmp_path / "data", projects_dir=tmp_path / "projects", **kw)


def test_from_env_reads_plugin_options(tmp_path):
    env = {
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "d"),
        "CLAUDE_PLUGIN_OPTION_VAULT_PATH": str(tmp_path / "My Vault"),
        "CLAUDE_PLUGIN_OPTION_NOTE_LANGUAGE": "Deutsch",
        "CLAUDE_PLUGIN_OPTION_ACTIVE_DAYS": "7",
        "CLAUDE_PLUGIN_OPTION_WRITER_MODEL": "haiku",
        "CLAUDE_PLUGIN_OPTION_MIN_USER_MESSAGES": "5",
        "CLAUDE_PLUGIN_OPTION_AUTO_CAPTURE": "false",
        "CLAUDE_PLUGIN_OPTION_EXCLUDE_PATHS": '["~/secret", "/tmp/x"]',
    }
    cfg = Config.from_env(env)
    assert cfg.vault == tmp_path / "My Vault"
    assert cfg.data == tmp_path / "d"
    assert (cfg.language, cfg.active_days, cfg.model, cfg.min_user_messages) == ("Deutsch", 7, "haiku", 5)
    assert cfg.auto_capture is False
    assert cfg.exclude_paths == ["~/secret", "/tmp/x"]


def test_from_env_defaults_and_comma_list(tmp_path):
    cfg = Config.from_env({"CLAUDE_PLUGIN_OPTION_EXCLUDE_PATHS": "/a, /b"})
    assert cfg.vault is None
    assert cfg.active_days == 14 and cfg.auto_capture is True
    assert cfg.exclude_paths == ["/a", "/b"]


def test_excluded(tmp_path):
    cfg = cfg_for(tmp_path, exclude_paths=[str(tmp_path / "kunde")])
    assert cfg.excluded(str(tmp_path / "kunde" / "repo"))
    assert not cfg.excluded(str(tmp_path / "kundeX"))
    assert not cfg.excluded("")


def test_enqueue_is_idempotent_per_session(tmp_path):
    cfg = cfg_for(tmp_path)
    enqueue(cfg, {"session_id": "s1", "transcript_path": "/t1", "cwd": "/w", "reason": "other"})
    p, item = queue_items(cfg)[0]
    record_failure(cfg, p, item, "boom")
    enqueue(cfg, {"session_id": "s1", "transcript_path": "/t1", "cwd": "/w", "reason": "catch-up"})
    items = queue_items(cfg)
    assert len(items) == 1
    assert items[0][1]["attempts"] == 1
    assert items[0][1]["reason"] == "catch-up"


def test_failure_moves_to_failed_after_three_attempts(tmp_path):
    cfg = cfg_for(tmp_path)
    enqueue(cfg, {"session_id": "s1"})
    for _ in range(3):
        p, item = queue_items(cfg)[0]
        record_failure(cfg, p, item, "boom")
    assert queue_items(cfg) == []
    assert failed_count(cfg) == 1
    assert "boom" in (cfg.data / "errors.log").read_text()


def test_anchors(tmp_path):
    cfg = cfg_for(tmp_path)
    assert load_anchors(cfg) == {}
    set_anchor(cfg, "s1", "u9")
    a = load_anchors(cfg)["s1"]
    assert a["uuid"] == "u9" and a["at"] > 0


def test_lock_blocks_second_holder_and_recovers_dead_pid(tmp_path):
    cfg = cfg_for(tmp_path)
    assert acquire_lock(cfg)
    assert not acquire_lock(cfg)
    release_lock(cfg)
    dead = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    (cfg.data / "lock").mkdir(parents=True)
    (cfg.data / "lock" / "pid").write_text(dead.stdout.strip())
    assert acquire_lock(cfg)
    assert (cfg.data / "lock" / "pid").read_text() == str(os.getpid())
    release_lock(cfg)


def test_notices_are_popped_once(tmp_path):
    cfg = cfg_for(tmp_path)
    add_notice(cfg, "new folder people/")
    add_notice(cfg, "second")
    assert pop_notices(cfg) == ["new folder people/", "second"]
    assert pop_notices(cfg) == []


def test_installed_at_is_stable(tmp_path):
    cfg = cfg_for(tmp_path)
    first = ensure_installed_at(cfg)
    assert ensure_installed_at(cfg) == first


def test_begin_round_trip(tmp_path):
    cfg = cfg_for(tmp_path)
    assert load_begin(cfg, "s1") is None
    save_begin(cfg, "s1", 123.0, ["a.md", "dir/"])
    assert load_begin(cfg, "s1") == (123.0, {"a.md", "dir/"})
    drop_begin(cfg, "s1")
    assert load_begin(cfg, "s1") is None
