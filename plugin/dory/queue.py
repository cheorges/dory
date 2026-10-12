"""Queue entries: one JSON file per ended (or saved) session."""

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

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
    _write(path, entry)
    if reason != "save":
        (state.sessions / f"{session_id}.json").unlink(missing_ok=True)
    return path


def pending(state: StateDir) -> list[Path]:
    return sorted(state.queue.glob("*.json"))


def load(path: Path) -> Entry:
    return Entry(**json.loads(path.read_text()))


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
    tmp.replace(target)
