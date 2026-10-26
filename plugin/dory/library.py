"""/dory:library: the context the skill needs, `dory library-write`, `dory link` and `dory guard`.

The library is the knowledge the user files deliberately. The skill proposes a folder, a title,
the content and the files to link it from, and writes only after the user's yes, and only
through these commands: code checks every path and writes the link form, and the guard of
`/dory:note`, which blocks Write and Edit under `library/` for the rest of a session, never meets
the skill. An entry loads at session start when a project note or a topic file in `notes/` links
it in its `library` property (`links`).
"""

import hashlib
import json
from datetime import date
from pathlib import Path

from dory import baseline, describe, links, names, scopes
from dory.config import Config
from dory.frontmatter import (
    Block,
    add_list_item,
    closing_line,
    join_blocks,
    read_frontmatter,
    split_blocks,
    strip_frontmatter,
)
from dory.project import Project, detect_project
from dory.state import StateDir
from dory.vault import snapshot

MAX_FOLDER_DEPTH = 2
MAX_OTHER_NOTES = 25  # per other project; the session's own project lists all its notes
CONTEXT_CHARS = 20_000  # other projects' notes stop here; the rest is counted
MAX_LISTED = 5  # aliases, tags or links named per line
_ENTRY_KEYS = ("type", "created", "updated")
_ALIASES = "aliases"
_SOURCE = "source"
GUARD_MESSAGE = (
    "{path} is in the user's library; /dory:note never writes there. "
    "To file knowledge in the library, the user runs /dory:library."
)


class LibraryError(Exception):
    """A library write that cannot happen; nothing was changed."""


def library_context(config: Config, cwd: Path) -> str:
    """What the dialog needs; takes the snapshot the later writes go back to."""
    state = StateDir(config.state_dir).ensure()
    taken = snapshot(config, state)
    project = detect_project(cwd, state.projects_file)
    vault = config.vault
    lines = [
        f"Vault: {vault}",
        f"Snapshot: {taken}",
        f"Today: {date.today():%Y-%m-%d}",
        f"Language: {config.language}",
        f"Project: {project.name} (repo {project.root})" if project else "Project: none",
        "",
        "The library (folder/title, aliases, the sha256 to extend it with):",
    ]
    library = vault / scopes.LIBRARY
    entries = sorted(path.relative_to(library) for path in library.rglob("*.md") if path.is_file())
    lines += [_entry_line(library / entry, entry) for entry in entries] or ["- empty"]
    topics = [
        path
        for path in scopes.notes_folder_files(vault)
        if scopes.file_type(vault / path) == "topic"
    ]
    topic_lines = [_linkable(vault, path) for path in topics] or ["- none"]
    used = sum(len(line) + 1 for line in [*lines, *topic_lines])
    skipped: list[int] = []  # note counts of the projects past the budget
    for name in scopes.visible_projects(vault, project):
        notes = scopes.project_notes(vault, Project(name, vault))
        own = project is not None and name == project.name
        if not own and used >= CONTEXT_CHARS:
            skipped.append(len(notes))
            continue
        header = f"The notes of {name} (a link loads the entry in its sessions):"
        lines += ["", header]
        used += len(header) + 2
        shown: list[str] = []
        for path in notes if own else notes[:MAX_OTHER_NOTES]:
            line = _linkable(vault, path)
            if not own and used + len(line) + 1 > CONTEXT_CHARS:
                break
            shown.append(line)
            used += len(line) + 1
        lines += shown or (["- none"] if not notes else [])
        if len(notes) > len(shown):
            lines.append(f"- {len(notes) - len(shown)} more notes of {name}")
            used += len(lines[-1]) + 1
    if skipped:
        lines += ["", f"- {sum(skipped)} more notes in {len(skipped)} more projects"]
    lines += ["", "The topic files in notes/ (a link loads the entry in every session):"]
    lines += topic_lines
    return "\n".join(lines)


def _entry_line(path: Path, entry: Path) -> str:
    """An entry with its aliases and the sha256 an extend sends; without the hash when the file
    cannot be read, so that the entry cannot be extended but the dialog still runs."""
    aliases = describe.values(read_frontmatter(path).get("aliases"))[:MAX_LISTED]
    details = [f"aliases: {', '.join(aliases)}"] if aliases else []
    try:
        details.append(f"sha256 {file_hash(path)}")
    except OSError:
        details.append("unreadable")
    return f"- {entry.with_suffix('').as_posix()} ({'; '.join(details)})"


def library_write(
    config: Config,
    folder: str,
    title: str,
    text: str,
    today: date | None = None,
    *,
    expect: str | None = None,
    aliases: list[str] | None = None,
    source: str | None = None,
) -> tuple[Path, bool]:
    """Create an entry, or replace the existing one when `expect` is the sha256 of the file as it
    was read; return its vault-relative path and whether it is new. `aliases` and `source` set
    those properties; left out on a replace, the entry keeps its own."""
    content = strip_frontmatter(text).strip() if text.startswith("---") else text.strip()
    if not content:
        raise LibraryError("empty entry: nothing to write")
    vault = config.vault
    if bad := sorted(set(title + folder) & names.NOT_IN_QUOTES):
        raise LibraryError(f"a folder or title holds no {' '.join(bad)}")
    properties = _properties(aliases, source)
    try:
        stem = names.file_stem(title)
    except names.TitleError as error:
        raise LibraryError(str(error)) from error
    parts = _folder_parts(vault, folder)
    relative = Path(scopes.LIBRARY, *parts) / f"{stem}.md"
    day = f"{today or date.today():%Y-%m-%d}"
    state = StateDir(config.state_dir).ensure()
    with baseline.notes_lock(state.baselines):
        existing = _existing(vault, relative)
        if existing is None and expect is not None:
            raise LibraryError(f"{relative.as_posix()} is no entry yet: write it without --replace")
        if existing is not None:
            current = file_hash(vault / existing)
            if expect is None:
                raise LibraryError(
                    f"{existing.as_posix()} exists (sha256 {current}); nothing was written. "
                    f"Replacing it takes --replace --expect {current}, only to extend that entry"
                )
            if expect != current:
                raise LibraryError(
                    f"{existing.as_posix()} changed since it was read (sha256 now {current}); "
                    "read it again"
                )
        relative = existing or relative
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = _entry_text(path if existing else None, content, day, properties)
        path.write_text(entry, encoding="utf-8")
        baseline.record_dory_write(state, vault, relative)
    return relative, existing is None


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _properties(aliases: list[str] | None, source: str | None) -> list[Block]:
    """The `aliases` and `source` blocks to write, quoted; each value checked first."""
    values = [*(aliases or []), *([source] if source is not None else [])]
    for value in values:
        # A backslash would start an escape in a quoted YAML value, which dory's reader keeps.
        if not value.strip() or "\n" in value or set(value) & {*names.NOT_IN_QUOTES, "\\"}:
            forbidden = " ".join(sorted({*names.NOT_IN_QUOTES, "\\"}))
            raise LibraryError(f"alias or source {value!r}: one line, not blank, no {forbidden}")
    blocks: list[Block] = []
    if aliases:
        blocks.append(
            (_ALIASES, [f"{_ALIASES}:", *(f'  - "{alias.strip()}"' for alias in aliases)])
        )
    if source is not None:
        blocks.append((_SOURCE, [f'{_SOURCE}: "{source.strip()}"']))
    return blocks


def _entry_text(existing: Path | None, content: str, day: str, properties: list[Block]) -> str:
    """The entry with `type`, `created` and `updated` first, then the given properties; an
    existing entry keeps its other properties (tags, and aliases or source when none are given)
    and its `created`."""
    own: list[Block] = []
    created = day
    given = {key for key, _ in properties}
    if existing is not None:
        blocks, _ = split_blocks(existing.read_text(encoding="utf-8"))
        created = str(read_frontmatter(existing).get("created") or day)
        own = [block for block in blocks if block[0] not in (*_ENTRY_KEYS, *given)]
    fixed: list[Block] = [
        ("type", ["type: library"]),
        ("created", [f"created: {created}"]),
        ("updated", [f"updated: {day}"]),
    ]
    return join_blocks([*fixed, *properties, *own], f"{content}\n")


def link(config: Config, entry: str, files: list[str]) -> list[tuple[Path, bool]]:
    """Add the entry to the `library` property of each file; return each file and whether it
    changed. Every file is checked before any is written."""
    vault = config.vault
    target = _entry(vault, entry)
    linking = [_linking_file(vault, name) for name in files]
    if not linking:
        raise LibraryError("no file to link from")
    item = f"[[{target.with_suffix('').as_posix()}|{target.stem}]]"
    state = StateDir(config.state_dir).ensure()
    done = []
    with baseline.notes_lock(state.baselines):
        for relative in linking:
            path = vault / relative
            if target in links.linked_by_property(vault, path):
                done.append((relative, False))
                continue
            text = path.read_text(encoding="utf-8")
            path.write_text(add_list_item(text, scopes.LIBRARY_KEY, item), encoding="utf-8")
            baseline.record_dory_write(state, vault, relative)
            done.append((relative, True))
    return done


def guard(config: Config, raw: str) -> str | None:
    """The message that blocks a Write or Edit under `library/`; None lets it through."""
    hook = json.loads(raw or "{}")
    tool_input = hook.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return None
    path = Path(target).expanduser()
    if not path.is_absolute():
        path = Path(hook.get("cwd") or ".") / path
    library = (config.vault / scopes.LIBRARY).resolve()
    resolved = path.resolve()
    # APFS and Obsidian ignore case, so `Library/x.md` is the same file.
    inside = names.name_key(resolved.as_posix()).startswith(
        names.name_key(library.as_posix()) + "/"
    ) or names.name_key(resolved.as_posix()) == names.name_key(library.as_posix())
    return GUARD_MESSAGE.format(path=target) if inside else None


def _linkable(vault: Path, relative: Path) -> str:
    """A file that can link an entry: its path, what it is about, its aliases, tags and links."""
    path = vault / relative
    meta = read_frontmatter(path)
    about = describe.about(path, meta)
    details = [
        f"{key}: {', '.join(values[:MAX_LISTED])}"
        for key in ("aliases", "tags")
        if (values := describe.values(meta.get(key)))
    ]
    if linked := links.linked_by_property(vault, path):
        named = ", ".join(p.with_suffix("").as_posix() for p in linked[:MAX_LISTED])
        details.append(f"links {named}")
    line = f"- {relative.as_posix()}" + (f': "{about}"' if about else "")
    return line + (f" ({'; '.join(details)})" if details else "")


def _folder_parts(vault: Path, folder: str) -> list[str]:
    """The folder below `library/`, each part a clean name and spelled as an existing folder."""
    raw = [part for part in folder.strip().strip("/").split("/") if part.strip()]
    if len(raw) > MAX_FOLDER_DEPTH:
        raise LibraryError(f"folder {folder!r} is deeper than {MAX_FOLDER_DEPTH} levels")
    parts: list[str] = []
    current = vault / scopes.LIBRARY
    for part in raw:
        if not names.is_clean(part.strip()):
            raise LibraryError(f"folder name {part!r} breaks the naming rules")
        clean = part.strip()
        existing = next(
            (
                child.name
                for child in _children(current)
                if child.is_dir() and names.name_key(child.name) == names.name_key(clean)
            ),
            clean,
        )
        parts.append(existing)
        current = current / existing
    return parts


def _existing(vault: Path, relative: Path) -> Path | None:
    """The entry of that name in that folder, in any case."""
    folder = vault / relative.parent
    key = names.name_key(relative.name)
    for child in _children(folder):
        if child.is_file() and names.name_key(child.name) == key:
            return relative.parent / child.name
    return None


def _entry(vault: Path, entry: str) -> Path:
    name = entry.strip().removesuffix(".md")
    if not name.casefold().startswith(f"{scopes.LIBRARY}/"):
        name = f"{scopes.LIBRARY}/{name}"
    found = links.library_entries(vault, f"[[{name}]]")
    if not found:
        raise LibraryError(f"{entry!r} is no entry in library/")
    return found[0]


def _linking_file(vault: Path, name: str) -> Path:
    """A project note or a topic file in `notes/`, nothing else."""
    relative = Path(name.strip())
    if relative.is_absolute():
        try:
            relative = relative.resolve().relative_to(vault.resolve())
        except ValueError as error:
            raise LibraryError(f"{name} is not in the vault") from error
    path = vault / relative
    if ".." in relative.parts or not path.is_file():
        raise LibraryError(f"{relative.as_posix()} is no file in the vault")
    parts = relative.parts
    note = len(parts) == 4 and parts[0] == "projects" and parts[2] == scopes.NOTES_FOLDER
    topic = len(parts) == 2 and parts[0] == scopes.NOTES_FOLDER
    if not (note or topic) or relative.suffix != ".md":
        raise LibraryError(
            f"{relative.as_posix()}: only a project note or a topic file in notes/ links entries"
        )
    if topic and scopes.file_type(path) != "topic":
        raise LibraryError(f"{relative.as_posix()} is a {scopes.file_type(path)}, no topic file")
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---" and closing_line(lines) is None:
        raise LibraryError(f"{relative.as_posix()}: its frontmatter has no closing line")
    return relative


def _children(folder: Path) -> list[Path]:
    try:
        return sorted(folder.iterdir())
    except OSError:
        return []
