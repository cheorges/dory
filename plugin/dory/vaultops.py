"""Renames and deletions the worker marks but cannot carry out itself.

The worker run has no tool to rename or delete a file. When a knowledge note is corrected and
its core statement changes, the worker writes the new title into `rename_to`; when the
repository now documents a note, it sets `status: archived`. After a successful run,
`apply_marks` carries out the marks that run wrote and keeps every link in the vault pointing
at a file that exists. Only regular knowledge notes inside the vault are touched; the snapshot
taken before the run is the way back.

Which marks are carried out:
- A mark the run wrote: a rename always; a deletion only for a note of the session's project
  alone, because other projects' sessions never see this project's CLAUDE.md.
- A mark that was there before the run comes from a run that failed: it is reset, since
  nobody checked that run's work.

Each rename or deletion is all or nothing: every changed link is computed before a file is
written, and if a write, the rename or the deletion fails, the files already written are
restored and the mark is reset. Nothing is retried; the next session on the subject marks
the note again.
"""

import contextlib
import os
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from dory.frontmatter import read_frontmatter
from dory.recall import Note

RENAME_FIELD = "rename_to"
MAX_TITLE_CHARS = 100
_FORBIDDEN = re.compile(r'[\[\]#^|\\/:*"<>?]')
_SKIP_DIRS = {".obsidian", ".trash", ".git"}
# An Obsidian link: optional embed marker, folder, heading or block, and alias; inside tables
# Obsidian escapes the alias separator as `\|`.
_LINK = (
    r"(?P<embed>!?)\[\[(?P<folder>[^\[\]|#^\\]*/)?(?P<name>[^\[\]|#^\\/]+)"
    r"(?P<anchor>[#^][^\]|\\]*)?(?P<alias>\\?\|[^\]]*)?\]\]"
)
_ANY_LINK = re.compile(_LINK)
_LIST_ENTRY = re.compile(rf"^[ \t]*[-*][ \t]+{_LINK}[ \t]*$\n?", re.MULTILINE)

Mark = tuple[str, str]  # (path relative to the vault, "rename" or "delete")
Written = list[tuple[Path, str]]  # files written, with their text before the change


def current_marks(vault: Path) -> frozenset[Mark]:
    """The marks in the vault now; taken before a run to tell its own marks from older ones."""
    return frozenset(mark for note in _marked(vault) for mark in _marks_of(note, vault))


def apply_marks(
    vault: Path, project: str | None, earlier: frozenset[Mark] = frozenset()
) -> list[str]:
    """Carry out the run's marks; return one line per change, reset, skip or failure."""
    changes = [
        f"skipped {_relative(note.path, vault)}: {reason}"
        for note in _marked(vault)
        if (reason := _untouchable(note, vault))
    ]
    # Deletions first: an old deletion mark is reset before a rename moves its file.
    for kind in ("delete", "rename"):
        for note in _marked(vault):
            mark = (_relative(note.path, vault), kind)
            if mark not in _marks_of(note, vault) or _untouchable(note, vault):
                continue
            if line := _handle(vault, note, mark, project, earlier):
                changes.append(line)
    return changes


def rename_note(vault: Path, note: Note) -> list[str]:
    """Point every link in the vault at the new title, then move the note there."""
    title = _free_title(vault, note, clean_title(str(note.meta.get(RENAME_FIELD) or "")))
    if not title or title == note.path.stem:
        _rewrite(note.path, _set_field(_read(note.path), RENAME_FIELD, None))
        return [] if title else [f"skipped {_relative(note.path, vault)}: empty title"]
    old = _key(note.path.stem)

    def relink(match: re.Match[str]) -> str:
        if _key(match["name"]) != old:
            return match[0]
        parts = (match["folder"], title, match["anchor"], match["alias"])
        return f"{match['embed']}[[{''.join(part or '' for part in parts)}]]"

    target = note.path.with_name(f"{title}.md")
    written = _replace_everywhere(vault, lambda text: _ANY_LINK.sub(relink, text))
    _undo_on_failure(written, lambda: note.path.rename(target))
    _rewrite(target, _set_field(_read(target), RENAME_FIELD, None))
    return [f"renamed {_relative(note.path, vault)} to {title} ({len(written)} files relinked)"]


def delete_note(vault: Path, path: Path) -> str:
    """Drop list entries that only link the note, turn other links into text, delete it."""
    gone = _key(path.stem)

    def drop_entry(match: re.Match[str]) -> str:
        return "" if _key(match["name"]) == gone else match[0]

    def to_text(match: re.Match[str]) -> str:
        if _key(match["name"]) != gone:
            return match[0]
        alias = match["alias"]
        return alias.lstrip("\\")[1:] if alias else match["name"]

    def unlink(text: str) -> str:
        return _ANY_LINK.sub(to_text, _LIST_ENTRY.sub(drop_entry, text))

    written = _replace_everywhere(vault, unlink)
    _undo_on_failure(written, path.unlink)
    return f"deleted {_relative(path, vault)} ({len(written)} files unlinked)"


def clean_title(raw: str) -> str:
    """A file name Obsidian shows and links: no forbidden or control characters, no dot first."""
    title = " ".join(unicodedata.normalize("NFC", raw).split())
    title = "".join(char for char in _FORBIDDEN.sub("", title) if char.isprintable())
    return _cap(" ".join(title.split()), MAX_TITLE_CHARS)


def _handle(
    vault: Path, note: Note, mark: Mark, project: str | None, earlier: frozenset[Mark]
) -> str:
    kind = mark[1]
    if mark in earlier:
        return _reset(note, kind, "mark from a run that failed", vault)
    if kind == "delete" and not (project and note.projects == [project]):
        return _reset(note, kind, "not a note of this project alone", vault)
    try:
        done = rename_note(vault, note) if kind == "rename" else [delete_note(vault, note.path)]
    except (OSError, ValueError) as error:
        reset = _reset(note, kind, "carrying it out failed", vault)
        return f"failed {mark[0]}: {error}; {reset}"
    return "; ".join(done)


def _reset(note: Note, kind: str, reason: str, vault: Path) -> str:
    """Undo a mark that is not carried out; a reset that fails is never retried as a mark."""
    where = _relative(note.path, vault)
    field, value = (RENAME_FIELD, None) if kind == "rename" else ("status", "active")
    try:
        _rewrite(note.path, _set_field(_read(note.path), field, value))
    except (OSError, ValueError) as error:
        return f"failed {where}: could not reset the mark ({reason}): {error}"
    return f"reset {where}: {reason}"


def _free_title(vault: Path, note: Note, title: str) -> str:
    """The title, or with the project in brackets when another file already has it."""
    if not title:
        return ""
    taken = {_key(path.stem) for path in _files(vault, symlinks=True) if path != note.path}

    def free(candidate: str) -> bool:
        target = note.path.with_name(f"{candidate}.md")
        occupied = os.path.lexists(target) and not _same_file(target, note.path)
        return _key(candidate) not in taken and not occupied

    if free(title):
        return title
    folder = note.path.relative_to(vault).parts
    owner = clean_title(folder[1] if folder[0] == "projects" and len(folder) > 2 else folder[0])
    for counter in range(1, 100):
        suffix = f" ({owner})" if counter == 1 else f" ({owner} {counter})"
        candidate = _cap(title, MAX_TITLE_CHARS - len(suffix)) + suffix
        if free(candidate):
            return candidate
    return ""


def _marked(vault: Path) -> list[Note]:
    notes = (Note(path, read_frontmatter(path)) for path in _files(vault, symlinks=True))
    return [
        note for note in notes if RENAME_FIELD in note.meta or note.meta.get("status") == "archived"
    ]


def _marks_of(note: Note, vault: Path) -> set[Mark]:
    where = _relative(note.path, vault)
    marks = {(where, "rename")} if RENAME_FIELD in note.meta else set()
    return marks | ({(where, "delete")} if note.meta.get("status") == "archived" else set())


def _untouchable(note: Note, vault: Path) -> str:
    if note.path.is_symlink() or not note.path.resolve().is_relative_to(vault.resolve()):
        return "not a regular file in the vault"
    if not note.holds_knowledge:
        return f"not a knowledge note (type {note.type or 'missing'})"
    names = [_key(path.stem) for path in _files(vault, symlinks=True)]
    if names.count(_key(note.path.stem)) > 1:
        return "another note has the same name"
    return ""


def _files(vault: Path, symlinks: bool = False) -> list[Path]:
    """Notes in the vault; symlinks only when asked, so they can be reported, never written."""

    def wanted(path: Path) -> bool:
        if _SKIP_DIRS.intersection(path.relative_to(vault).parts):
            return False
        return symlinks if path.is_symlink() else path.is_file()

    return sorted(path for path in vault.rglob("*.md") if wanted(path))


def _replace_everywhere(vault: Path, change: Callable[[str], str]) -> Written:
    """Change every note or none: all new texts are computed before the first write."""
    planned = []
    for path in _files(vault):
        try:
            text = _read(path)
        except FileNotFoundError:
            continue  # removed since the scan: nothing left to relink there
        if (new := change(text)) != text:
            planned.append((path, text, new))
    written: Written = []
    _undo_on_failure(written, lambda: [_write_and_keep(written, *plan) for plan in planned])
    return written


def _write_and_keep(written: Written, path: Path, text: str, new: str) -> None:
    written.append((path, text))  # first: a write that breaks off midway is put back too
    _write(path, new)


def _undo_on_failure(written: Written, step: Callable[[], object]) -> None:
    """Run the step; if it fails, put back the files already written and re-raise."""
    try:
        step()
    except BaseException:
        for path, text in reversed(written):
            with contextlib.suppress(OSError):  # the snapshot before the run still has it
                _write(path, text)
        raise


def _set_field(text: str, key: str, value: str | None) -> str:
    """Replace or (with None) remove a top-level frontmatter field with all of its lines."""
    lines = text.split("\n")
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    kept, dropping = [], False
    for index, line in enumerate(lines):
        if dropping and index < end and (line[:1].isspace() or line.startswith("- ")):
            continue  # the rest of a value on the following lines (`>-`, `|`, `- item`)
        dropping = (
            0 < index < end and not line[:1].isspace() and line.partition(":")[0].strip() == key
        )
        if dropping:
            if value is not None:
                kept.append(f"{key}: {value}")
            continue
        kept.append(line)
    return "\n".join(kept)


def _read(path: Path) -> str:
    # surrogateescape keeps bytes that are not UTF-8 exactly as they were when written back
    return path.read_text(encoding="utf-8", errors="surrogateescape")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", errors="surrogateescape")


def _rewrite(path: Path, text: str) -> None:
    if _read(path) != text:
        _write(path, text)


def _same_file(first: Path, second: Path) -> bool:
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def _cap(title: str, limit: int) -> str:
    if len(title) <= limit:
        return title.strip(" .")
    return (title[:limit].rsplit(" ", 1)[0] or title[:limit]).strip(" .")


def _key(stem: str) -> str:
    return unicodedata.normalize("NFC", stem).casefold()


def _relative(path: Path, vault: Path) -> str:
    return str(path.relative_to(vault))
