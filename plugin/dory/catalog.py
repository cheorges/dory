"""The catalog a worker run reads: every entry's lead in the vault, grouped by file.

The run reads the session project's `knowledge.md` in full and greps the topic files, but
never sees what other projects already hold. The catalog lists the leads of every knowledge
and topic file, so an insight extends the entry it matches instead of becoming a second one.
The user's notes, `library/`, lists and registers stay out, and so does every private
project except the session's own.
"""

from pathlib import Path

from dory import scopes
from dory.entries import parse
from dory.project import Project

LEAD_CHARS = 100  # 100 entries stay near 12,000 characters, about 3,000 tokens


def build(
    vault: Path,
    project: Project | None,
    *,
    private: bool,
    flags: dict[str, dict[str, list[str]]] | None = None,
) -> str:
    """`flags` holds per file and entry key the signals of `staleness.flags`."""
    flags = flags or {}
    sections = [
        _section(vault, path, flags.get(path.as_posix(), {}))
        for path in _files(vault, project, private=private)
    ]
    sections = [section for section in sections if section]
    lines = [
        "# Catalog of the entries in the vault",
        "",
        "Every entry of the knowledge and topic files, by file: its section and its bold lead, "
        f"cut at {LEAD_CHARS} characters, with its flags in brackets. Check each insight against "
        "it before you write.",
        "",
    ]
    return "\n".join(lines + (sections or ["No entries yet."])) + "\n"


def _files(vault: Path, project: Project | None, *, private: bool) -> list[Path]:
    own = scopes.knowledge_file(project)
    files = [own] if own and (vault / own).is_file() else []
    if not private:
        others = [
            Path("projects") / name / scopes.KNOWLEDGE
            for name in scopes.visible_projects(vault, project)
        ]
        files += [path for path in others if path != own and (vault / path).is_file()]
    files += [
        path
        for path in scopes.notes_folder_files(vault)
        if scopes.file_type(vault / path) == "topic"
    ]
    return files


def _section(vault: Path, relative: Path, flags: dict[str, list[str]]) -> str:
    path = vault / relative
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # one unreadable file must not fail every run; the checks report it
        return ""
    entries = parse(text)
    if not entries:
        return ""
    lines = [f"## {relative.as_posix()}"]
    for entry in entries:
        lead = entry.lead if len(entry.lead) <= LEAD_CHARS else entry.lead[: LEAD_CHARS - 1] + "…"
        line = f"- {entry.section}: {lead}" if entry.section else f"- {lead}"
        labels = flags.get(entry.key)
        lines.append(f"{line} [{'; '.join(labels)}]" if labels else line)
    return "\n".join(lines) + "\n"
