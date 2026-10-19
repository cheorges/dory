"""Before and after a worker run: the files it may write, its baseline, and the checks.

The worker edits knowledge files with a model, so dory's code guards what the model must not
change: the frontmatter keys that place a file (type, domain, paths) and the user's notes. It
also reports every other file the run touched in the scope folders, and every entry it added,
changed or removed. Each attempt of an entry takes its own baseline and reports its own changes,
so edits the user or other entries make between two attempts are neither undone nor counted.
Only when an attempt ended before its checks ran (a killed worker) does the next attempt keep
that baseline, so the killed run's changes are still checked. The baseline lives outside the
bundle directory, which the run itself can write.
"""

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from dory import entries
from dory.frontmatter import parse_frontmatter
from dory.project import Project
from dory.repodocs import SWEEP_GRACE_SECONDS
from dory.scopes import NOTES, SCOPES, knowledge_files, project_domain
from dory.state import StateDir

PROTECTED_KEYS = ("type", "domain", "paths")
_UNWATCHED = {".obsidian", ".trash"}  # Obsidian writes its workspace while the vault is open
_COMPLETE = "COMPLETE"
_CHECKED = "CHECKED"
_HASHES = "hashes.json"
_FILES = "knowledge-files.json"
_UNREADABLE = "unreadable"


def create_skeletons(vault: Path, project: Project | None, today: date) -> None:
    for relative in knowledge_files(project):
        path = vault / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_skeleton(vault, relative, project, today))


def baseline_dir(state: StateDir, entry_id: str) -> Path:
    return state.baselines / entry_id


def capture(vault: Path, target: Path, knowledge: list[Path]) -> bool:
    """Take the attempt's baseline, unless the last attempt ended before its checks ran.

    Returns True when that earlier, unchecked baseline is kept: its changes still need a check.
    """
    with notes_lock(target.parent):  # add-note must not write between copy and marker
        if (target / _COMPLETE).exists() and not (target / _CHECKED).exists():
            return True
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        for relative in [*knowledge, *_notes_files(vault)]:
            source = vault / relative
            if source.is_file():
                copy = target / "files" / relative
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, copy)
        hashes = {
            str(relative): _digest_or_mark(vault / relative)
            for relative in _other_files(vault, knowledge)
        }
        (target / _HASHES).write_text(json.dumps(hashes, ensure_ascii=False))
        (target / _FILES).write_text(json.dumps([str(relative) for relative in knowledge]))
        (target / _COMPLETE).touch()
        return False


def notes_copies(state: StateDir, relative: Path) -> list[Path]:
    """Where the baselines of queued entries keep a `notes.md`, whether they hold it yet or not.

    `dory add-note` writes its line there as well, so the checks of a running worker keep it.
    """
    queued = {path.stem for path in state.queue.glob("*.json")}
    return [
        kept / "files" / relative
        for kept in sorted(state.baselines.glob("*"))
        if kept.name in queued and (kept / _COMPLETE).exists() and not (kept / _CHECKED).exists()
    ]


@contextmanager
def notes_lock(baselines: Path) -> Iterator[None]:
    """Keep `dory add-note` apart from a run's baseline capture and its notes restore.

    Held for milliseconds, unlike the worker lock, which lasts the whole run.
    """
    baselines.mkdir(parents=True, exist_ok=True)
    with (baselines.parent / "notes.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def unchecked_files(target: Path) -> list[Path] | None:
    """The knowledge files of a baseline that the next attempt keeps, or None.

    The files a run may write depend on the project's domain, which can change between two
    attempts; a kept baseline is checked against the files it captured.
    """
    if not (target / _COMPLETE).exists() or (target / _CHECKED).exists():
        return None
    try:
        return [Path(name) for name in json.loads((target / _FILES).read_text())]
    except (OSError, ValueError):
        return None


def mark_checked(target: Path) -> None:
    """The attempt's changes are checked; the next attempt takes a fresh baseline."""
    (target / _CHECKED).touch()


def check(vault: Path, target: Path, knowledge: list[Path]) -> list[dict]:
    """Restore what the run must not change, then report what it changed against the baseline."""
    changes: list[dict] = []
    for relative in knowledge:
        changes += _guarded(relative, lambda r=relative: _restore_frontmatter(vault, target, r))
    with notes_lock(target.parent):
        for relative in _notes_files(target / "files"):
            changes += _guarded(relative, lambda r=relative: _restore_notes(vault, target, r))
    changes += _guarded("scope folders", lambda: _unexpected(vault, target, knowledge))
    for relative in knowledge:
        changes += _guarded(relative, lambda r=relative: _entry_changes(vault, target, r))
    return changes


def vault_state(vault: Path) -> dict[str, tuple[int, int]]:
    """Modification time and size of every file, to tell whether a run changed the vault."""
    found: dict[str, tuple[int, int]] = {}
    for root, dirs, files in os.walk(vault):
        if Path(root) == vault:
            dirs[:] = [name for name in dirs if name not in _UNWATCHED]
        for name in files:
            with contextlib.suppress(FileNotFoundError):
                stat = (Path(root) / name).stat()
                found[str(Path(root, name).relative_to(vault))] = (stat.st_mtime_ns, stat.st_size)
    return found


def discard(state: StateDir, entry_id: str) -> None:
    shutil.rmtree(baseline_dir(state, entry_id), ignore_errors=True)


def sweep(state: StateDir) -> None:
    """Remove baselines whose entry left the queue without its run cleaning up (kill, crash)."""
    queued = {path.stem for path in state.queue.glob("*.json")}
    cutoff = time.time() - SWEEP_GRACE_SECONDS
    for kept in state.baselines.glob("*"):
        with contextlib.suppress(FileNotFoundError):
            if kept.name not in queued and kept.stat().st_mtime < cutoff:
                shutil.rmtree(kept, ignore_errors=True)


def _skeleton(vault: Path, relative: Path, project: Project | None, today: date) -> str:
    scope = relative.parts[0]
    private = scope == "private" or (
        scope == "projects" and project_domain(vault, project) == "private"
    )
    lines = ["---", "type: knowledge", f"domain: {'private' if private else 'work'}"]
    if scope == "projects" and project:
        lines.append(f"paths: {json.dumps([str(project.root)], ensure_ascii=False)}")
    lines += [f"updated: {today:%Y-%m-%d}", "---", ""]
    return "\n".join(lines)


def _notes_files(root: Path) -> list[Path]:
    found = [path for path in (root / "projects").glob(f"*/{NOTES}") if path.is_file()]
    found += [
        root / scope / NOTES for scope in ("general", "private") if (root / scope / NOTES).is_file()
    ]
    return sorted(path.relative_to(root) for path in found)


def _other_files(vault: Path, knowledge: list[Path]) -> list[Path]:
    """Markdown files in the scope folders that the run has no business writing."""
    own = {*knowledge, *_notes_files(vault)}
    return sorted(
        path.relative_to(vault)
        for scope in SCOPES
        for path in (vault / scope).rglob("*.md")
        if path.is_file() and path.relative_to(vault) not in own
    )


def _guarded(relative: Path | str, step: Callable[[], list[dict]]) -> list[dict]:
    try:
        return step()
    except (OSError, ValueError) as error:
        return [
            {
                "change": "failed",
                "file": str(relative),
                "lead": f"{type(error).__name__}: {error}"[:200],
            }
        ]


def _restore_frontmatter(vault: Path, target: Path, relative: Path) -> list[dict]:
    kept = (target / "files" / relative).read_text()
    path = vault / relative
    text = path.read_text() if path.exists() else ""
    expected, actual = parse_frontmatter(kept), parse_frontmatter(text)
    wrong = sorted(key for key in PROTECTED_KEYS if expected.get(key) != actual.get(key))
    if not wrong:
        return []
    head, rest = _split(text)
    own = [block for block in _blocks(head or []) if block[0] not in PROTECTED_KEYS]
    protected = [block for block in _blocks(_split(kept)[0] or []) if block[0] in PROTECTED_KEYS]
    lines = [line for _, block in [*protected, *own] for line in block]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *lines, "---", ""]) + rest)
    return [
        {"change": "restored", "file": str(relative), "lead": f"frontmatter: {', '.join(wrong)}"}
    ]


def _restore_notes(vault: Path, target: Path, relative: Path) -> list[dict]:
    kept = (target / "files" / relative).read_bytes()
    path = vault / relative
    if path.is_file() and path.read_bytes() == kept:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(kept)
    return [{"change": "restored", "file": str(relative), "lead": "the user's notes"}]


def _unexpected(vault: Path, target: Path, knowledge: list[Path]) -> list[dict]:
    before: dict[str, str] = json.loads((target / _HASHES).read_text())
    changes = []
    for relative in _other_files(vault, knowledge):
        name = str(relative)
        try:
            digest = _digest(vault / relative)
        except OSError as error:
            changes.append(
                {"change": "failed", "file": name, "lead": f"{type(error).__name__}: {error}"[:200]}
            )
            continue
        if name not in before:
            changes.append({"change": "unexpected", "file": name, "lead": "created"})
        elif before[name] != digest:
            changes.append({"change": "unexpected", "file": name, "lead": "changed"})
    current = {str(relative) for relative in _other_files(vault, knowledge)}
    changes += [
        {"change": "unexpected", "file": name, "lead": "deleted"}
        for name in before
        if name not in current
    ]
    kept_notes = set(_notes_files(target / "files"))
    changes += [
        {"change": "unexpected", "file": str(relative), "lead": "created"}
        for relative in _notes_files(vault)
        if relative not in kept_notes
    ]
    return changes


def _entry_changes(vault: Path, target: Path, relative: Path) -> list[dict]:
    kept = target / "files" / relative
    path = vault / relative
    before = entries.parse(kept.read_text() if kept.exists() else "")
    after = entries.parse(path.read_text() if path.exists() else "")
    return [
        {
            "change": change.change,
            "file": str(relative),
            "lead": change.lead,
            **({"was": change.was} if change.was else {}),
        }
        for change in entries.diff(before, after)
    ]


def _split(text: str) -> tuple[list[str] | None, str]:
    """Frontmatter lines without the markers, and the rest; None when there is no frontmatter."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return [raw.rstrip("\n") for raw in lines[1:index]], "".join(lines[index + 1 :])
    return None, text


def _blocks(head: list[str]) -> list[tuple[str, list[str]]]:
    """Frontmatter lines grouped by key; indented and list lines belong to the key above."""
    blocks: list[tuple[str, list[str]]] = []
    for line in head:
        starts_key = line[:1] not in (" ", "-", "") and ":" in line
        if starts_key or not blocks:
            blocks.append((line.partition(":")[0].strip(), [line]))
        else:
            blocks[-1][1].append(line)
    return blocks


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_or_mark(path: Path) -> str:
    """An unreadable file must not stop the baseline; it is compared as such afterwards."""
    try:
        return _digest(path)
    except OSError:
        return _UNREADABLE
