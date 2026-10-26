"""The trace of a run: the previous text of every entry it changed or removed.

Entries always describe the current state, so a run rewrites them in place. The trace keeps
what they said before in the run's session note, which the session start never loads, so the
user can see and restore an earlier version in Obsidian without paying for it at every start.
"""

import contextlib
import json
import re
import time
from pathlib import Path

from dory.repodocs import SWEEP_GRACE_SECONDS
from dory.state import StateDir

HEADING = "## Replaced"
_PENDING = "traces"  # in the state directory: traces of attempts that did not finish
_SECTION = re.compile(r"\n*^## Replaced\n.*?(?=^## |\Z)", re.M | re.S)
_LEAD = re.compile(r"^[-*+]\s+\*\*(.+?)\*\*")  # on the first line, like `entries`


def section(replaced: list[tuple[str, str, str]]) -> str:
    """`replaced` holds (file, change, previous text) per entry."""
    blocks = [HEADING, ""]
    for relative, change, text in replaced:
        lead = _LEAD.match(text)
        title = lead.group(1) if lead else " ".join(text.split())[:80]
        blocks.append(f"> [!quote]- {_link(relative)} ({change}): {title}")
        blocks += [f"> {line}".rstrip() for line in text.splitlines()]
        blocks.append("")
    return "\n".join(blocks)


def append(note: Path, replaced: list[tuple[str, str, str]]) -> None:
    """Put the trace at the end of the session note, replacing one a repeated check wrote."""
    if not replaced or not note.is_file():
        return
    text = _SECTION.sub("", note.read_text(encoding="utf-8")).rstrip("\n")
    note.write_text(f"{text}\n\n{section(replaced)}", encoding="utf-8")


def keep(state: StateDir, entry_id: str, replaced: list[tuple[str, str, str]]) -> None:
    """Hold an attempt's trace that did not finish, for the attempt that does."""
    if not replaced:
        return
    path = _pending(state, entry_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([*take(state, entry_id), *map(list, replaced)]))


def take(state: StateDir, entry_id: str) -> list[tuple[str, str, str]]:
    """The trace earlier attempts kept, removed from the store."""
    path = _pending(state, entry_id)
    try:
        held = [tuple(item) for item in json.loads(path.read_text())]
    except (OSError, ValueError):
        return []
    path.unlink(missing_ok=True)
    return held


def discard(state: StateDir, entry_id: str) -> None:
    _pending(state, entry_id).unlink(missing_ok=True)


def sweep(state: StateDir) -> None:
    """Remove held traces whose entry is neither queued nor parked (kill, crash)."""
    entries = (path for folder in (state.queue, state.failed) for path in folder.glob("*.json"))
    kept = {path.stem for path in entries}
    cutoff = time.time() - SWEEP_GRACE_SECONDS
    for held in (state.root / _PENDING).glob("*.json"):
        with contextlib.suppress(FileNotFoundError):
            if held.stem not in kept and held.stat().st_mtime < cutoff:
                held.unlink()


def _pending(state: StateDir, entry_id: str) -> Path:
    return state.root / _PENDING / f"{entry_id}.json"


def _link(relative: str) -> str:
    path = Path(relative)
    label = path.parent.name if path.name == "knowledge.md" else path.stem
    return f"[[{path.with_suffix('').as_posix()}|{label}]]"
