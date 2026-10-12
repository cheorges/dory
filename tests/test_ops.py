"""Story 7: `dory status`, `dory retry` and the run log."""

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from dory import queue, worker
from dory.ops import retry, status
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "tests" / "fixtures" / "transcripts" / "resume-compact.jsonl"
NOW = datetime(2026, 10, 14, 12, 0).astimezone()  # a Wednesday, local time


def park(state: StateDir, session_id: str, error: str) -> Path:
    path = queue.enqueue(
        state, session_id=session_id, transcript=TRANSCRIPT, cwd="/tmp", reason="clear"
    )
    entry = queue.load(path)
    entry.attempts, entry.last_error = 3, error
    queue.save(path, entry)
    return path.replace(state.failed / path.name)


def log_run(state: StateDir, at: datetime, outcome: str, cost: float, error: str = "") -> None:
    record = {
        "at": at.astimezone(UTC).isoformat(timespec="seconds"),
        "entry": f"e-{at:%d%H%M}",
        "outcome": outcome,
        "seconds": 12.5,
        "cost_usd": cost,
        "error": error,
    }
    with (state.root / "runs.log").open("a") as handle:
        handle.write(json.dumps(record) + "\n")


@pytest.fixture
def state(tmp_path):
    return StateDir(tmp_path / "state").ensure()


def test_status_shows_counts_last_error_and_costs_today_and_this_week(state):
    queue.enqueue(state, session_id="waiting-1", transcript=TRANSCRIPT, cwd="/tmp", reason="clear")
    park(state, "broken-1", "session note missing: sessions/x.md")
    log_run(state, NOW - timedelta(days=7), "done", 5.0)  # last week: counts nowhere
    log_run(state, NOW - timedelta(days=2), "done", 0.25)  # Monday: this week
    log_run(state, NOW - timedelta(hours=3), "failed", 0.05, "no json output (exit 1)")
    log_run(state, NOW - timedelta(hours=1), "done", 0.07)
    log_run(state, NOW - timedelta(minutes=30), "skipped", 0.0, "nothing new to condense")

    text = status(state, now=NOW)

    assert "Queue: 1" in text
    assert "nothing new to condense" not in text
    assert "Failed: 1" in text
    assert "no json output (exit 1)" in text
    assert "session note missing: sessions/x.md" in text  # why the parked entry is parked
    assert "API equivalent: today 0.12 USD" in text
    assert "this week 0.37 USD" in text


def test_status_of_an_empty_state_says_so(state):
    text = status(state, now=NOW)

    assert "Queue: 0" in text
    assert "Failed: 0" in text
    assert "today 0.00 USD" in text


def test_status_skips_broken_log_lines(state):
    (state.root / "runs.log").write_text('not json\n{"at": "x"}\n')
    log_run(state, NOW - timedelta(hours=1), "done", 0.07)

    assert "today 0.07 USD" in status(state, now=NOW)


def test_retry_moves_failed_entries_back_with_reset_counter(state):
    parked = [park(state, "broken-1", "boom"), park(state, "broken-2", "bang")]

    assert retry(state) == 2

    assert not list(state.failed.glob("*.json"))
    for path in parked:
        entry = queue.load(state.queue / path.name)
        assert entry.attempts == 0
        assert entry.last_error == ""


def test_retry_leaves_unreadable_entries_in_failed(state):
    (state.failed / "garbage.json").write_text("{not json")
    park(state, "broken-1", "boom")

    assert retry(state) == 1
    assert (state.failed / "garbage.json").exists()


def test_cli_status_and_retry(state):
    park(state, "broken-1", "boom")
    env = {**os.environ, "DORY_STATE_DIR": str(state.root), "DORY_NO_SPAWN": "1"}
    dory = str(ROOT / "plugin" / "bin" / "dory")

    shown = subprocess.run([dory, "status"], env=env, capture_output=True, text=True, check=True)
    retried = subprocess.run([dory, "retry"], env=env, capture_output=True, text=True, check=True)

    assert "Failed: 1" in shown.stdout
    assert "1 entry back in the queue" in retried.stdout
    assert len(queue.pending(state)) == 1


def test_retry_waits_while_a_worker_runs(state):
    parked = park(state, "broken-1", "boom")

    with worker.lock(state) as held:
        assert held
        assert retry(state) is None

    assert parked.exists()
    assert retry(state) == 1
