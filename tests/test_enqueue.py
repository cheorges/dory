import json
import os
import subprocess
import time
from pathlib import Path

from dory import queue
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]
DORY = ROOT / "plugin" / "bin" / "dory"
FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"


def run_hook(state_dir: Path, payload: dict, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DORY_STATE_DIR": str(state_dir), "DORY_NO_SPAWN": "1", **extra_env}
    return subprocess.run(
        [str(DORY), "enqueue"], input=json.dumps(payload), env=env, capture_output=True, text=True
    )


def hook_payload(transcript: Path, session_id: str = "abc123") -> dict:
    return {
        "session_id": session_id,
        "transcript_path": str(transcript),
        "cwd": str(ROOT),
        "hook_event_name": "SessionEnd",
        "reason": "clear",
    }


def test_session_end_hook_queues_entry_and_transcript_copy_within_a_second(tmp_path):
    transcript = tmp_path / "live.jsonl"
    transcript.write_bytes((FIXTURES / "resume-compact.jsonl").read_bytes())
    run_hook(tmp_path / "warmup", hook_payload(transcript))  # first uv start resolves the env

    started = time.monotonic()
    result = run_hook(tmp_path / "state", hook_payload(transcript))
    elapsed = time.monotonic() - started

    state = StateDir(tmp_path / "state")
    [entry_path] = queue.pending(state)
    entry = queue.load(entry_path)
    assert result.returncode == 0, result.stderr
    assert elapsed < 1.0
    assert entry.reason == "clear" and entry.session_id == "abc123"
    assert Path(entry.transcript_copy).read_bytes() == transcript.read_bytes()


def test_transcript_copy_survives_deletion_of_the_original(tmp_path):
    transcript = tmp_path / "live.jsonl"
    transcript.write_bytes((FIXTURES / "resume-compact.jsonl").read_bytes())
    run_hook(tmp_path / "state", hook_payload(transcript))
    transcript.unlink()

    entry = queue.load(queue.pending(StateDir(tmp_path / "state"))[0])

    assert Path(entry.transcript_copy).stat().st_size > 0


def test_worker_sessions_are_never_queued(tmp_path):
    transcript = tmp_path / "live.jsonl"
    transcript.write_bytes((FIXTURES / "resume-compact.jsonl").read_bytes())

    run_hook(tmp_path / "state", hook_payload(transcript), DORY_WORKER="1")

    assert not (tmp_path / "state" / "queue").exists()


def test_missing_transcript_exits_quietly(tmp_path):
    result = run_hook(tmp_path / "state", hook_payload(tmp_path / "missing.jsonl"))

    assert result.returncode == 0
    assert not (tmp_path / "state" / "queue").exists()


def test_session_file_is_removed_unless_the_session_is_only_saved(tmp_path):
    state = StateDir(tmp_path).ensure()
    (state.sessions / "s1.json").write_text("{}")
    (state.sessions / "s2.json").write_text("{}")
    source = FIXTURES / "resume-compact.jsonl"

    queue.enqueue(state, session_id="s1", transcript=source, cwd="/", reason="save")
    queue.enqueue(state, session_id="s2", transcript=source, cwd="/", reason="clear")

    assert (state.sessions / "s1.json").exists()
    assert not (state.sessions / "s2.json").exists()


def test_broken_config_never_fails_the_hook(tmp_path):
    transcript = tmp_path / "live.jsonl"
    transcript.write_bytes((FIXTURES / "resume-compact.jsonl").read_bytes())
    config = tmp_path / "config.toml"
    config.write_text("vault = [not toml")

    result = run_hook(tmp_path / "state", hook_payload(transcript), DORY_CONFIG=str(config))

    assert result.returncode == 0
    assert "TOMLDecodeError" in (tmp_path / "state" / "hook-errors.log").read_text()


def save(state_dir: Path, session_id: str, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DORY_STATE_DIR": str(state_dir), "DORY_NO_SPAWN": "1", **extra_env}
    return subprocess.run(
        [str(DORY), "enqueue", "--session", session_id], env=env, capture_output=True, text=True
    )


def remember(state: StateDir, session_id: str, transcript: Path) -> None:
    """What the SessionStart hook writes for every running session."""
    record = {"transcript_path": str(transcript), "cwd": str(ROOT)}
    (state.sessions / f"{session_id}.json").write_text(json.dumps(record))


def test_save_queues_exactly_this_session_among_parallel_ones(tmp_path):
    state = StateDir(tmp_path / "state").ensure()
    for session_id, fixture in (("left", "resume-compact"), ("right", "tool-error")):
        transcript = tmp_path / f"{session_id}.jsonl"
        transcript.write_bytes((FIXTURES / f"{fixture}.jsonl").read_bytes())
        remember(state, session_id, transcript)

    result = save(state.root, "right")

    assert result.returncode == 0, result.stderr
    [entry_path] = queue.pending(state)
    entry = queue.load(entry_path)
    assert (entry.session_id, entry.reason, entry.cwd) == ("right", "save", str(ROOT))
    assert Path(entry.transcript_copy).read_bytes() == (tmp_path / "right.jsonl").read_bytes()
    assert "queued" in result.stdout
    assert (state.sessions / "right.json").exists()  # a later save or the end still finds it


def test_save_returns_while_the_worker_still_runs(tmp_path):
    state = StateDir(tmp_path / "state").ensure()
    transcript = tmp_path / "live.jsonl"
    transcript.write_bytes((FIXTURES / "tool-output-secrets.jsonl").read_bytes())
    remember(state, "live", transcript)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    started_marker = tmp_path / "claude-started"
    fake = fake_bin / "claude"
    fake.write_text(f"#!/bin/sh\ntouch {started_marker}\nsleep 5\n")
    fake.chmod(0o755)
    config = tmp_path / "config.toml"
    config.write_text(f'vault = "{tmp_path / "vault"}"\nmin_user_messages = 1\n')
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}", "DORY_CONFIG": str(config)}
    save(tmp_path / "warmup", "none", **env)  # first uv start resolves the env

    started = time.monotonic()
    result = save(state.root, "live", DORY_NO_SPAWN="0", **env)
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    assert elapsed < 1.0
    deadline = time.monotonic() + 10
    while not started_marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert started_marker.exists()  # the worker was started and is still busy with claude


def test_save_without_a_known_session_says_why(tmp_path):
    result = save(tmp_path / "state", "unknown-session")

    assert result.returncode == 1
    assert "unknown-session" in result.stdout
    assert not queue.pending(StateDir(tmp_path / "state").ensure())


def test_save_with_an_empty_session_id_is_an_error(tmp_path):
    result = save(tmp_path / "state", "")

    assert result.returncode == 1
    assert "not found" in result.stdout
