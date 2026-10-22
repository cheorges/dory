"""Before and after a worker run: the folders it needs, its baseline, and the checks.

The worker edits files with a model, so dory's code guards what the model must not change and
reports what it did change. The baseline copies the files a run may write, the project's
`knowledge.md` and every file in `notes/`, and hashes the files it must leave alone: every other
`.md` under `projects/`, the user's notes among them, and every `.md` under `private/`. After
the run, the checks restore the frontmatter keys that place a file and report every watched file
the run created, changed or deleted, and every entry it added, changed or removed in the
project's `knowledge.md` and in the topic files of `notes/`. Nothing the user may have written
is restored: the checks cannot tell the run's writes from the user's, and the snapshot is the
way back.

Each attempt of an entry takes its own baseline and reports its own changes, so edits the user
or other entries make between two attempts are neither undone nor counted. Only when an attempt
ended before its checks ran (a killed worker) does the next attempt keep that baseline, so the
killed run's changes are still checked. The baseline lives outside the bundle directory, which
the run itself can write.
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

from dory import entries, names
from dory.frontmatter import parse_frontmatter, read_frontmatter
from dory.project import Project
from dory.repodocs import SWEEP_GRACE_SECONDS
from dory.scopes import (
    KNOWLEDGE,
    NOTES_FOLDER,
    PRIVATE,
    file_type,
    knowledge_file,
    notes_folder_files,
    project_domain,
)
from dory.state import StateDir

KNOWLEDGE_KEYS = ("type", "domain", "paths")
_WATCHED = ("projects", PRIVATE)
_UNWATCHED = {".obsidian", ".trash"}  # Obsidian writes its workspace while the vault is open
_COMPLETE = "COMPLETE"
_CHECKED = "CHECKED"
_HASHES = "hashes.json"
_LAYOUT = "layout.json"  # missing in a baseline taken by an earlier version
_UNREADABLE = "unreadable"


def create_skeletons(vault: Path, project: Project | None, today: date) -> None:
    """The project's `knowledge.md` with its frontmatter, and an empty `private/` for the user."""
    (vault / PRIVATE).mkdir(parents=True, exist_ok=True)
    if project is None or not project.name:
        return
    path = vault / "projects" / project.name / KNOWLEDGE
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_skeleton(vault, project, today))


def baseline_dir(state: StateDir, entry_id: str) -> Path:
    return state.baselines / entry_id


def capture(vault: Path, target: Path, project: Project | None, *, topics_allowed: bool) -> bool:
    """Take the attempt's baseline, unless the last attempt ended before its checks ran.

    Returns True when that earlier, unchecked baseline is kept: its changes still need a check.
    A private project's run may not write topic files (`topics_allowed`), which every session
    lists.
    """
    with notes_lock(target.parent):  # add-note must not write between the hashes and the marker
        if _open(target) and (target / _LAYOUT).exists():
            return True
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        knowledge = knowledge_file(project)
        notes = notes_folder_files(vault)
        for relative in [*([knowledge] if knowledge else []), *notes]:
            source = vault / relative
            if source.is_file():
                copy = target / "files" / relative
                copy.parent.mkdir(parents=True, exist_ok=True)
                with contextlib.suppress(OSError):  # the checks report an unreadable file
                    shutil.copyfile(source, copy)
        hashes = {
            str(relative): _digest_or_mark(vault / relative)
            for relative in _watched_files(vault, knowledge)
        }
        (target / _HASHES).write_text(json.dumps(hashes, ensure_ascii=False))
        layout = {
            "knowledge": str(knowledge) if knowledge else None,
            "notes": [str(relative) for relative in notes],
            "topics": topics_allowed,
        }
        (target / _LAYOUT).write_text(json.dumps(layout))
        (target / _COMPLETE).touch()
        return False


def record_dory_write(state: StateDir, vault: Path, relative: Path) -> None:
    """A watched file dory writes for the user while entries wait: their checks take it as given.

    Call it under `notes_lock`, together with the write, so no check sees the file in between.
    """
    if relative.parts[0] not in _WATCHED:
        return
    queued = {path.stem for path in state.queue.glob("*.json")}
    digest = _digest_or_mark(vault / relative)
    for kept in sorted(state.baselines.glob("*")):
        if kept.name in queued and _open(kept) and (kept / _LAYOUT).exists():
            hashes = json.loads((kept / _HASHES).read_text())
            hashes[str(relative)] = digest
            (kept / _HASHES).write_text(json.dumps(hashes, ensure_ascii=False))


@contextmanager
def notes_lock(baselines: Path) -> Iterator[None]:
    """Keep `dory add-note` apart from a run's baseline capture and its checks.

    Held for milliseconds, unlike the worker lock, which lasts the whole run.
    """
    baselines.mkdir(parents=True, exist_ok=True)
    with (baselines.parent / "notes.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def mark_checked(target: Path) -> None:
    """The attempt's changes are checked; the next attempt takes a fresh baseline."""
    (target / _CHECKED).touch()


def check(vault: Path, target: Path) -> list[dict]:
    """Restore the keys that place a file, then report what the run changed against the baseline."""
    layout = json.loads((target / _LAYOUT).read_text())
    knowledge = Path(layout["knowledge"]) if layout["knowledge"] else None
    captured = [Path(name) for name in layout["notes"]]
    uncopied = {relative for relative in captured if not (target / "files" / relative).exists()}
    kept_notes = notes_folder_files(target / "files")
    new_notes = sorted(set(notes_folder_files(vault)) - set(captured))
    changes: list[dict] = []
    if knowledge:
        changes += _guarded(
            knowledge, lambda: _restore_keys(vault, target, knowledge, KNOWLEDGE_KEYS)
        )
    for relative in kept_notes:
        changes += _guarded(relative, lambda r=relative: _restore_type(vault, target, r))
    changes += [
        {"change": "failed", "file": str(r), "lead": "not readable when the baseline was taken"}
        for r in sorted(uncopied)
    ]
    for relative in new_notes:
        changes += _guarded(relative, lambda r=relative: _new_note(vault, r))
    with notes_lock(target.parent):
        changes += _guarded("watched files", lambda: _unexpected(vault, target, knowledge))
    if not layout["topics"]:
        changes += _guarded(
            NOTES_FOLDER, lambda: _topics_written(vault, target, new_notes, uncopied)
        )
    for relative in [*([knowledge] if knowledge else []), *_topics(vault, target, uncopied)]:
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


def _open(target: Path) -> bool:
    """Taken completely and not checked yet: an attempt ended before its checks ran."""
    return (target / _COMPLETE).exists() and not (target / _CHECKED).exists()


def _skeleton(vault: Path, project: Project, today: date) -> str:
    lines = [
        "---",
        "type: knowledge",
        f"domain: {project_domain(vault, project)}",
        f"paths: {json.dumps([str(project.root)], ensure_ascii=False)}",
        f"updated: {today:%Y-%m-%d}",
        "---",
        "",
    ]
    return "\n".join(lines)


def _watched_files(vault: Path, knowledge: Path | None) -> list[Path]:
    """Markdown files the run has no business writing: the user's, other projects', old ones."""
    found = (
        path.relative_to(vault)
        for folder in _WATCHED
        for path in (vault / folder).rglob("*.md")
        if path.is_file()
    )
    return sorted(relative for relative in found if relative != knowledge)


def _topics(vault: Path, target: Path, uncopied: set[Path]) -> list[Path]:
    """Files of `notes/` before or after the run that are no list or register.

    A file the baseline could not copy has no state to compare with; it is reported once.
    """
    candidates = (
        set(notes_folder_files(vault)) | set(notes_folder_files(target / "files"))
    ) - uncopied
    return sorted(relative for relative in candidates if _is_topic(vault, target, relative))


def _is_topic(vault: Path, target: Path, relative: Path) -> bool:
    """A file without a type, or with one the user made up, is a topic; the baseline decides."""
    kept = target / "files" / relative
    source = kept if kept.exists() else vault / relative
    return file_type(source) == "topic"


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


def _restore_keys(vault: Path, target: Path, relative: Path, keys: tuple[str, ...]) -> list[dict]:
    kept = (target / "files" / relative).read_text()
    path = vault / relative
    text = path.read_text() if path.exists() else ""
    expected, actual = parse_frontmatter(kept), parse_frontmatter(text)
    wrong = sorted(key for key in keys if expected.get(key) != actual.get(key))
    if not wrong:
        return []
    head, rest = _split(text)
    own = [block for block in _blocks(head or []) if block[0] not in keys]
    protected = [block for block in _blocks(_split(kept)[0] or []) if block[0] in keys]
    lines = [line for _, block in [*protected, *own] for line in block]
    path.parent.mkdir(parents=True, exist_ok=True)
    head_text = "\n".join(["---", *lines, "---", ""]) if lines else ""
    path.write_text(head_text + rest)
    return [
        {"change": "restored", "file": str(relative), "lead": f"frontmatter: {', '.join(wrong)}"}
    ]


def _restore_type(vault: Path, target: Path, relative: Path) -> list[dict]:
    """The type the file had before the run; a file the run deleted stays gone.

    A file without a type is a topic, so a type the run added is taken back only when it makes
    the file a list or register.
    """
    path = vault / relative
    if not path.exists():
        return []
    if "type" not in read_frontmatter(target / "files" / relative) and file_type(path) == "topic":
        return []
    return _restore_keys(vault, target, relative, ("type",))


def _new_note(vault: Path, relative: Path) -> list[dict]:
    """A file the run created in `notes/`: a topic unless it says otherwise, named by the rules."""
    changes = []
    path = vault / relative
    if "type" not in read_frontmatter(path):
        text = path.read_text()
        head, rest = _split(text)
        lines = ["type: topic", *(head or [])]
        path.write_text("\n".join(["---", *lines, "---", ""]) + rest)
        changes.append({"change": "restored", "file": str(relative), "lead": "frontmatter: type"})
    if not names.is_clean(relative.stem):
        changes.append(
            {"change": "unexpected", "file": str(relative), "lead": "name breaks the naming rules"}
        )
    return changes


def _unexpected(vault: Path, target: Path, knowledge: Path | None) -> list[dict]:
    before: dict[str, str] = json.loads((target / _HASHES).read_text())
    current = _watched_files(vault, knowledge)
    changes = []
    for relative in current:
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
    names_now = {str(relative) for relative in current}
    changes += [
        {"change": "unexpected", "file": name, "lead": "deleted"}
        for name in before
        if name not in names_now
    ]
    return changes


def _topics_written(
    vault: Path, target: Path, new_notes: list[Path], uncopied: set[Path]
) -> list[dict]:
    """A private project's run must not write a topic file: every session lists them."""
    changes = []
    for relative in _topics(vault, target, uncopied):
        path, kept = vault / relative, target / "files" / relative
        if relative in new_notes:
            lead = "created by a private project's run"
        elif path.exists() and kept.exists() and path.read_bytes() != kept.read_bytes():
            lead = "changed by a private project's run"
        else:
            continue
        changes.append({"change": "unexpected", "file": str(relative), "lead": lead})
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
