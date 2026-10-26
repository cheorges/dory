"""Operations: `dory status` shows whether the worker keeps up, `dory retry` revives failures.

Costs come from runs.log, one JSON line per worker run (written by ingest). They are what
the runs would cost at API prices; the worker runs on the Claude subscription. Days and weeks
are counted in local time, the week starting on Monday.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from dory import queue, staleness, worker
from dory.state import StateDir


@dataclass(frozen=True)
class Run:
    at: datetime
    outcome: str
    cost: float
    error: str
    changes: tuple[dict, ...] = ()  # the vault changes the post-run checks reported


def status(state: StateDir, now: datetime | None = None, vault: Path | None = None) -> str:
    state.ensure()
    now = (now or datetime.now()).astimezone()
    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    runs = _runs(state.root / "runs.log")
    cost_today = sum(run.cost for run in runs if run.at.date() == today)
    cost_week = sum(run.cost for run in runs if week_start <= run.at.date() <= today)
    failed = sorted(state.failed.glob("*.json"))

    lines = [
        f"Queue: {len(queue.pending(state))}",
        f"Failed: {len(failed)}",
    ]
    for path in failed:
        lines.append(f"  - {path.stem}: {_last_error(path)}")
    # ingest logs skipped runs with a reason ("nothing new to condense"); that is no error.
    last = next((run for run in reversed(runs) if run.error and run.outcome != "skipped"), None)
    if last:
        lines.append(f"Last error ({last.at:%Y-%m-%d %H:%M}, {last.outcome}): {last.error}")
    lines.append(
        f"API equivalent: today {cost_today:.2f} USD, this week {cost_week:.2f} USD"
        " (runs on the subscription, not billed)"
    )
    if vault is not None:
        stale = staleness.counts(state, vault, now)
        lines.append(
            f"Stale entries: {stale['missing path']} with a missing path, "
            f"{stale['unchanged']} unchanged for over {staleness.STALE_DAYS} days"
        )
    knowledge = _knowledge_today(runs, today)
    if knowledge:
        lines.append(knowledge)
    if failed:
        lines.append("Try again: dory retry")
    return "\n".join(lines)


def retry(state: StateDir) -> int | None:
    """Move parked entries back into the queue with a fresh counter; unreadable ones stay.

    Returns None while a worker runs: its pass has already tried these entries and would
    skip them, so they would wait for the next session end.
    """
    state.ensure()
    with worker.lock(state) as held:
        if not held:
            return None
        moved = 0
        for path in sorted(state.failed.glob("*.json")):
            try:
                entry = queue.load(path)
            except (OSError, ValueError, TypeError):
                continue
            entry.attempts, entry.last_error = 0, ""
            queue.save(path, entry)
            path.replace(state.queue / path.name)
            moved += 1
        return moved


def _knowledge_today(runs: list[Run], today: date) -> str:
    """What the post-run checks reported today; every attempt reports only its own changes."""
    todays = [run for run in runs if run.at.date() == today]
    counts = {
        change: sum(_count(run, change) for run in todays)
        for change in ("removed", "rewritten", "restored", "unexpected", "failed")
    }
    if not any(counts.values()):
        return ""
    return (
        f"Knowledge today: {_plural(counts['removed'], 'entry', 'entries')} removed, "
        f"{_plural(counts['rewritten'], 'lead', 'leads')} rewritten, "
        f"{_plural(counts['restored'], 'file', 'files')} restored, "
        f"{_plural(counts['unexpected'], 'unexpected file', 'unexpected files')}, "
        f"{_plural(counts['failed'], 'failed check', 'failed checks')} (details in runs.log)"
    )


def _count(run: Run, change: str) -> int:
    """A changed entry with its old lead beside it counts as rewritten: a pairing to look at."""
    if change == "rewritten":
        return sum(1 for item in run.changes if item.get("change") == "changed" and item.get("was"))
    return sum(1 for item in run.changes if item.get("change") == change)


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _runs(log: Path) -> list[Run]:
    if not log.is_file():
        return []
    runs = []
    for line in log.read_text(errors="replace").splitlines():
        try:
            record = json.loads(line)
            at = datetime.fromisoformat(record["at"]).astimezone()
            changes = tuple(
                item for item in record.get("vault_changes") or [] if isinstance(item, dict)
            )
            runs.append(
                Run(
                    at,
                    str(record.get("outcome", "")),
                    float(record.get("cost_usd") or 0),
                    str(record.get("error") or ""),
                    changes,
                )
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            continue  # a torn or foreign line must not hide the rest
    return runs


def _last_error(path: Path) -> str:
    try:
        return queue.load(path).last_error or "(no error text)"
    except (OSError, ValueError, TypeError):
        return "(entry unreadable)"
