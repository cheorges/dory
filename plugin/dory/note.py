"""/dory:note: the context the skill needs, and `dory add-note`, which creates a note file.

The skill decides where a note belongs and writes its title and content: a new file in the
project's `notes/`, or, for what applies in general, a new topic file in `notes/`. An
existing topic file, a list or a register the skill changes itself with Edit, after the snapshot
`prepare-note` takes. `dory add-note` only ever creates a file, named by its title and with its
frontmatter, and never overwrites one, a name in other case included.
"""

from datetime import date
from pathlib import Path

from dory import baseline, names, scopes, spawn, summary
from dory.config import Config
from dory.project import Project, detect_project
from dory.state import StateDir
from dory.vault import rules_text, snapshot

SCOPE_NAMES = ("project", "general")


class NoteError(Exception):
    """A note that cannot be written; nothing was changed."""


def prepare_note(config: Config, cwd: Path) -> str:
    state = StateDir(config.state_dir).ensure()
    taken = snapshot(config, state)
    # A new repo becomes a project here, as in the worker.
    project = detect_project(cwd, state.projects_file)
    vault = config.vault
    lines = [
        f"Vault: {vault}",
        f"Snapshot: {taken}",
        f"Today: {date.today():%Y-%m-%d}",
        f"Language: {config.language}",
    ]
    if project:
        lines += [
            f"Project: {project.name} (repo {project.root})",
            f"Domain: {scopes.project_domain(vault, project)}",
        ]
    else:
        lines.append("Project: none (outside a git repository)")
    lines.append(
        "Scopes for `dory add-note --scope <scope> --title <title>`, each creating a file:"
    )
    if project:
        lines.append(f"- project: {_folder('project', project).as_posix()}/")
    lines.append("- general: notes/ (a new topic file)")
    if project:
        lines.append("The project's notes:")
        lines += [f"- {path.stem}" for path in scopes.project_notes(vault, project)] or ["- none"]
    lines.append("The files in notes/, for everything without a project:")
    lines += [
        f"- {path.stem} ({scopes.file_type(vault / path)})"
        for path in scopes.notes_folder_files(vault)
    ] or ["- none"]
    lines += ["", rules_text().strip()]
    return "\n".join(lines)


def add_note(
    config: Config, cwd: Path, scope: str, title: str, text: str, today: date | None = None
) -> Path:
    """Create the note file; return its vault-relative path."""
    if scope not in SCOPE_NAMES:
        raise NoteError(f"unknown scope {scope!r}: use project or general")
    content = text.strip()
    if not content:
        raise NoteError("empty note: nothing to write")
    try:
        stem = names.file_stem(title)
    except names.TitleError as error:
        raise NoteError(str(error)) from error
    state = StateDir(config.state_dir).ensure()
    project = detect_project(cwd, state.projects_file)
    if scope == "project" and project is None:
        raise NoteError("not in a git repository: use --scope general")
    folder = _folder(scope, project)
    relative = folder / f"{stem}.md"
    day = f"{today or date.today():%Y-%m-%d}"
    head = (
        f"---\ntype: note\ncreated: {day}\n---\n"
        if scope == "project"
        else f"---\ntype: topic\nupdated: {day}\n---\n"
    )
    # A running worker reports every new file among the user's notes after its run, so the
    # queued entries' baselines take this one as given, under the lock their capture and checks
    # hold.
    with baseline.notes_lock(state.baselines):
        _refuse_existing(config.vault, folder, stem, scope)
        path = config.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(f"{head}{content}\n")
        except FileExistsError as error:
            raise NoteError(f"{relative.as_posix()} exists: choose another title") from error
        baseline.record_dory_write(state, config.vault, relative)
    if scope == "project":
        summary.mark(state, summary.context_name(project))
        spawn.spawn_worker()
    return relative


def _folder(scope: str, project: Project | None) -> Path:
    if scope == "project" and project:
        return Path("projects") / project.name / scopes.NOTES_FOLDER
    return Path(scopes.NOTES_FOLDER)


def _refuse_existing(vault: Path, folder: Path, stem: str, scope: str) -> None:
    """A file of the same name, in any case, is never overwritten."""
    key = names.name_key(stem)
    for path in sorted((vault / folder).glob("*.md")):
        if names.name_key(path.stem) != key:
            continue
        existing = (folder / path.name).as_posix()
        if scope == "project":
            raise NoteError(f"{existing} exists: choose another title")
        kind = scopes.file_type(path)
        raise NoteError(f"{existing} exists ({kind}): change that file with Edit instead")
