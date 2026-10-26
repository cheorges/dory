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


def log_changes(state: StateDir, at: datetime, entry: str, changes: list) -> None:
    record = {
        "at": at.astimezone(UTC).isoformat(timespec="seconds"),
        "entry": entry,
        "outcome": "done",
        "seconds": 20.0,
        "cost_usd": 0.1,
        "error": "",
        "vault_changes": changes,
    }
    with (state.root / "runs.log").open("a") as handle:
        handle.write(json.dumps(record) + "\n")


def removed(lead: str) -> dict:
    return {"change": "removed", "file": "projects/hub/knowledge.md", "lead": lead}


def test_status_sums_what_each_attempt_reported_today(state):
    log_changes(state, NOW - timedelta(days=1), "yesterday", [removed("Old entry.")])
    log_changes(state, NOW - timedelta(hours=3), "retried", [removed("First attempt.")])
    log_changes(state, NOW - timedelta(hours=2), "retried", [removed("Second attempt.")])
    restored = {"change": "restored", "file": "projects/hub/notes.md", "lead": "the user's notes"}
    failed = {"change": "failed", "file": "general/knowledge.md", "lead": "PermissionError"}
    rewritten = {"change": "changed", "file": "x", "lead": "Redis on 6379.", "was": "Loki on 3100."}
    edited = {"change": "changed", "file": "x", "lead": "Same lead."}
    log_changes(
        state,
        NOW - timedelta(hours=1),
        "other",
        [removed("Third."), restored, failed, rewritten, edited],
    )

    text = status(state, now=NOW)

    assert (
        "Knowledge today: 3 entries removed, 1 lead rewritten, 1 file restored, "
        "0 unexpected files, 1 failed check" in text
    )


def test_status_says_nothing_about_knowledge_on_a_quiet_day(state):
    log_run(state, NOW - timedelta(hours=1), "done", 0.07)

    assert "Knowledge today" not in status(state, now=NOW)


def test_status_counts_stale_entries_when_it_knows_the_vault(state, tmp_path):
    from dory import staleness

    vault = tmp_path / "vault"
    topic = vault / "notes" / "Old.md"
    topic.parent.mkdir(parents=True)
    topic.write_text("---\ntype: topic\n---\n- **Old.** x\n")
    staleness.observe(state, vault, datetime.now(UTC) - timedelta(days=100))

    text = status(state, vault=vault)

    assert "Stale entries: 0 with a missing path, 1 unchanged for over 90 days" in text
