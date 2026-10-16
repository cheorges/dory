"""Redacted copies of the documents a worker run checks its notes against.

They are captured when the session is queued, so a retry hours later still sees the checkout
as it was when the session ended, including a worktree that is gone by then. The worker
reads these copies, never the repository itself.
"""

import contextlib
import shutil
import subprocess
import time
from pathlib import Path

from dory.project import repo_root
from dory.secrets import redact
from dory.state import StateDir

RECORDS = Path("docs") / "records"
MAX_CHARS = 200_000
CUT_MARKER = f"\n\n[... cut at {MAX_CHARS:,} characters ...]\n"
_SOURCE = "SOURCE"
_READ_MARGIN = 4_096  # read past the cut, so redaction sees a secret that crosses it
SWEEP_GRACE_SECONDS = 600  # a hook captures the documents just before it writes the entry


def docs_dir(state: StateDir, entry_id: str) -> Path:
    return state.work / entry_id / "repo"


def capture(cwd: Path, project_root: Path, target: Path) -> Path:
    """Copy CLAUDE.md and the records into target; return the checkout they came from.

    The checkout is the one the session ran in, a worktree on its own branch included.
    Records that only the main repository has are added, so a branch cut before a record
    was merged still sees it. `SOURCE` is written last: without it the copy is incomplete.
    """
    checkout = _checkout(cwd, project_root)
    target.mkdir(parents=True, exist_ok=True)
    _copy(checkout / "CLAUDE.md", target / "CLAUDE.md", checkout)
    for source_root in dict.fromkeys([checkout, project_root]):
        for record in sorted((source_root / RECORDS).glob("*.md")):
            copy = target / "records" / record.name
            if not copy.exists():
                _copy(record, copy, source_root)
    (target / _SOURCE).write_text(str(checkout))
    return checkout


def source(docs: Path) -> Path | None:
    """The checkout a complete capture came from; None if there is no complete capture."""
    marker = docs / _SOURCE
    return Path(marker.read_text().strip()) if marker.is_file() else None


def discard(state: StateDir, entry_id: str) -> None:
    shutil.rmtree(docs_dir(state, entry_id), ignore_errors=True)


def sweep(state: StateDir) -> None:
    """Remove copies whose entry left the queue without its run cleaning up (kill, crash)."""
    queued = {path.stem for path in state.queue.glob("*.json")}
    cutoff = time.time() - SWEEP_GRACE_SECONDS
    for docs in state.work.glob("*/repo"):
        with contextlib.suppress(FileNotFoundError):  # a failed capture removed it meanwhile
            if docs.parent.name not in queued and docs.stat().st_mtime < cutoff:
                shutil.rmtree(docs, ignore_errors=True)


def _checkout(cwd: Path, project_root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if result.returncode == 0:
        toplevel = Path(result.stdout.strip()).resolve()
        if repo_root(toplevel) == project_root:
            return toplevel
    return project_root


def _copy(source: Path, target: Path, boundary: Path) -> None:
    real = source.resolve()
    if not real.is_file() or not real.is_relative_to(boundary):
        return  # a missing file, a folder, or a symlink that leaves the checkout
    with real.open(encoding="utf-8", errors="replace") as handle:
        text = handle.read(MAX_CHARS + _READ_MARGIN)
    # Redact before cutting, so a secret across the cut is caught whole.
    cut = len(text) > MAX_CHARS
    text = redact(text)[:MAX_CHARS] + (CUT_MARKER if cut else "")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
