"""Queue entries: one JSON file per ended (or saved) session."""

import contextlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

from dory import repodocs
from dory.project import repo_root
from dory.state import StateDir


@dataclass
class Entry:
    session_id: str
    transcript_copy: str
    cwd: str
    reason: str
    ended_at: str
    repo_root: str = ""
    attempts: int = 0
    last_error: str = ""

    @property
    def id(self) -> str:
        return f"{self.ended_at.replace(':', '').replace('-', '')}-{self.session_id}"


def enqueue(state: StateDir, *, session_id: str, transcript: Path, cwd: str, reason: str) -> Path:
    state.ensure()
    entry = Entry(
        session_id=session_id,
        transcript_copy="",
        cwd=cwd,
        reason=reason,
        repo_root=str(repo_root(Path(cwd)) or "") if cwd else "",
        ended_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )
    # One copy per entry: a save still waiting when the session ends keeps its own cut.
    copy = state.transcripts / f"{entry.id}.jsonl"
    _clone(transcript, copy)
    entry.transcript_copy = str(copy)
    path = state.queue / f"{entry.id}.json"
    _write(path, entry)  # first: a hook killed while copying documents still queued its session
    _capture_docs(state, entry)
    if reason != "save":
        (state.sessions / f"{session_id}.json").unlink(missing_ok=True)
    return path


def _capture_docs(state: StateDir, entry: Entry) -> None:
    if not entry.repo_root:
        return
    try:
        repodocs.capture(Path(entry.cwd), Path(entry.repo_root), repodocs.docs_dir(state, entry.id))
    except Exception:  # the entry is queued already; it is processed without documents
        repodocs.discard(state, entry.id)


def discard_transcript(state: StateDir, entry_id: str) -> None:
    """Remove an entry's transcript copy; a parked entry keeps it for `dory retry`."""
    (state.transcripts / f"{entry_id}.jsonl").unlink(missing_ok=True)


def sweep(state: StateDir) -> None:
    """Remove transcript copies whose entry is neither queued nor parked (kill, crash)."""
    entries = (path for folder in (state.queue, state.failed) for path in folder.glob("*.json"))
    kept = {path.stem for path in entries}
    cutoff = time.time() - repodocs.SWEEP_GRACE_SECONDS
    for copy in state.transcripts.glob("*.jsonl"):
        with contextlib.suppress(FileNotFoundError):  # its run removed it meanwhile
            if copy.stem not in kept and copy.stat().st_mtime < cutoff:
                copy.unlink()


def pending(state: StateDir) -> list[Path]:
    return sorted(state.queue.glob("*.json"))


def load(path: Path) -> Entry:
    data = json.loads(path.read_text())
    known = {field.name for field in fields(Entry)}  # entries written by a newer version load
    return Entry(**{key: value for key, value in data.items() if key in known})


def save(path: Path, entry: Entry) -> None:
    _write(path, entry)


def _write(path: Path, entry: Entry) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(entry), indent=2))
    tmp.replace(path)


def _clone(source: Path, target: Path) -> None:
    # APFS clone: instant and nearly free; plain copy where cloning is unsupported.
    tmp = target.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    result = subprocess.run(["cp", "-c", str(source), str(tmp)], capture_output=True)
    if result.returncode != 0:
        shutil.copyfile(source, tmp)
    os.utime(tmp)  # a clone keeps the source's mtime; the sweep's grace counts from the copy
    tmp.replace(target)
