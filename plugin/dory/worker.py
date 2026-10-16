"""Drain the queue one entry at a time under a lock.

Only one worker runs at a time (flock; the kernel drops the lock when the process dies).
After releasing the lock the queue is checked again, so an entry that arrives while the
lock is being released is not left lying until the next session ends.
"""

import fcntl
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path

from dory import queue, repodocs
from dory.bundle import build_bundle, write_bundle
from dory.condense import condense
from dory.config import Config
from dory.project import project_for_root
from dory.state import StateDir

MAX_ATTEMPTS = 3


class Outcome(Enum):
    DONE = "done"
    SKIPPED = "skipped"
    TRANSIENT = "transient"
    FAILED = "failed"
    TIMEOUT = "timeout"  # counts as a failure, then ends the pass: offline runs all hang


Process = Callable[[Path, queue.Entry], Outcome]


def run(state: StateDir, process: Process) -> str:
    state.ensure()
    tried: set[str] = set()
    while True:
        with lock(state) as held:
            if not held:
                return "busy"
            repodocs.sweep(state)
            stopped = _drain(state, process, tried)
        if stopped:
            return "stopped"
        if not _untried(state, tried):
            return "done"


def prepare(entry: queue.Entry, config: Config, state: StateDir):
    condensed = condense(
        Path(entry.transcript_copy),
        min_user_messages=config.min_user_messages,
        seen=state.load_seen(),
        max_tokens=config.condense_max_tokens,
    )
    if condensed.skipped or not condensed.text:
        return None, condensed
    root = Path(entry.repo_root) if entry.repo_root else None
    project = project_for_root(root, state.projects_file) if root else None
    docs = repodocs.docs_dir(state, entry.id)
    bundle = write_bundle(state.work, entry.id, build_bundle(entry, project, condensed, docs))
    return bundle, condensed


def dry_run(config: Config) -> list[Path]:
    state = StateDir(config.state_dir).ensure()
    bundles = []
    for path in queue.pending(state):
        bundle, _ = prepare(queue.load(path), config, state)
        if bundle:
            bundles.append(bundle)
    return bundles


@contextmanager
def lock(state: StateDir) -> Iterator[bool]:
    """Yield whether the worker lock was taken; never waits."""
    with state.lock_file.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _untried(state: StateDir, tried: set[str]) -> list[Path]:
    return [path for path in queue.pending(state) if path.name not in tried]


def _drain(state: StateDir, process: Process, tried: set[str]) -> bool:
    while candidates := _untried(state, tried):
        for path in candidates:
            tried.add(path.name)
            if _handle(state, path, process):
                return True
    return False


def _handle(state: StateDir, path: Path, process: Process) -> bool:
    try:
        return _handle_entry(state, path, process)
    finally:
        if not path.exists():  # the entry left the queue: its documents are no longer needed
            repodocs.discard(state, path.stem)


def _handle_entry(state: StateDir, path: Path, process: Process) -> bool:
    try:
        entry = queue.load(path)
    except (OSError, ValueError, TypeError):
        path.replace(state.failed / path.name)
        return False
    try:
        outcome = process(path, entry)
    except Exception as error:  # a broken entry must not stop the queue
        outcome, entry.last_error = Outcome.FAILED, repr(error)
    if outcome is Outcome.TRANSIENT:
        return True
    if outcome is Outcome.DONE:
        path.replace(state.done / path.name)
        return False
    if outcome is Outcome.SKIPPED:
        # Its own suffix keeps it out of the part numbering of the session's notes.
        path.replace(state.done / f"{path.stem}.skipped.json")
        return False
    entry.attempts += 1
    queue.save(path, entry)
    if entry.attempts >= MAX_ATTEMPTS:
        path.replace(state.failed / path.name)
    return outcome is Outcome.TIMEOUT
