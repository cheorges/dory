"""/dory:note: the context the skill needs, and `dory add-note`, which writes the user's note.

The skill only chooses where a note belongs (Record 003): the project's `notes.md`,
`general/` or `private/`. Writing is deterministic: one dated bullet in the user's words, newest
last. Lists and registers under `notes/` are edited by the skill itself, after the snapshot
`prepare-note` takes.
"""

from datetime import date
from pathlib import Path

from dory import baseline, scopes, spawn, summary
from dory.config import Config
from dory.project import Project, detect_project
from dory.state import StateDir
from dory.vault import rules_text, snapshot

SCOPE_NAMES = ("project", "general", "private")
_HEADER = "---\ntype: notes\n---\n"


class NoteError(Exception):
    """A note that cannot be written; nothing was changed."""


def prepare_note(config: Config, cwd: Path) -> str:
    state = StateDir(config.state_dir).ensure()
    taken = snapshot(config, state)
    # A new repo becomes a project here, as in the worker.
    project = detect_project(cwd, state.projects_file)
    lines = [
        f"Vault: {config.vault}",
        f"Snapshot: {taken}",
        f"Today: {date.today():%Y-%m-%d}",
        f"Language: {config.language}",
    ]
    if project:
        lines += [
            f"Project: {project.name} (repo {project.root})",
            f"Domain: {scopes.project_domain(config.vault, project)}",
        ]
    else:
        lines.append("Project: none (outside a git repository)")
    lines.append("Scopes for `dory add-note --scope <scope>`, each writing one `notes.md`:")
    for name in SCOPE_NAMES if project else SCOPE_NAMES[1:]:
        lines.append(f"- {name}: {_notes_path(name, project).as_posix()}")
    lines += ["Lists and registers: notes/", "", rules_text().strip()]
    return "\n".join(lines)


def add_note(config: Config, cwd: Path, scope: str, text: str, today: date | None = None) -> Path:
    """Append the note to the scope's `notes.md`; return its vault-relative path."""
    if scope not in SCOPE_NAMES:
        raise NoteError(f"unknown scope {scope!r}: use project, general or private")
    words = " ".join(text.split())
    if not words:
        raise NoteError("empty note: nothing to write")
    state = StateDir(config.state_dir).ensure()
    project = detect_project(cwd, state.projects_file)
    if scope == "project" and project is None:
        raise NoteError("not in a git repository: use --scope general or --scope private")
    relative = _notes_path(scope, project)
    line = f"- {today or date.today():%Y-%m-%d}: {words}\n"
    path = config.vault / relative
    # A running worker restores the user's notes from its baseline after the run, so the line
    # goes into the baselines of queued entries too, under the lock their capture and restore
    # hold.
    with baseline.notes_lock(state.baselines):
        current = path.read_text(encoding="utf-8") if path.exists() else _HEADER
        for copy in baseline.notes_copies(state, relative):
            kept = copy.read_text(encoding="utf-8") if copy.exists() else current
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(_with_line(kept, line), encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_with_line(current, line), encoding="utf-8")
    # The session's context when it loads the file; a private note from a work project is
    # loaded outside a repository, whose context covers every scope but a project's.
    session = summary.context_for(config.vault, project)
    summary.mark(state, session.name if relative in session.files else summary.OUTSIDE)
    spawn.spawn_worker()
    return relative


def _notes_path(scope: str, project: Project | None) -> Path:
    if scope == "project" and project:
        return Path("projects") / project.name / scopes.NOTES
    return Path(scope) / scopes.NOTES


def _with_line(text: str, line: str) -> str:
    if text.endswith(line):
        return text
    separator = "" if text.endswith("\n") else "\n"
    return f"{text}{separator}{line}"
