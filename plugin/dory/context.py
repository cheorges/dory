"""The text of a context: what a session start loads in full and the worker summarizes.

A known project's context is its notes, by name, each followed by the library entries it links
first, then its `knowledge.md`; outside a known project nothing loads in full. Both sides build
the text here, so a summary's hash and the session start's check describe the same text: the
file bodies without frontmatter, in load order, each under its vault path with its own headings
one level down.
"""

import re
from pathlib import Path

from dory import links, scopes
from dory.frontmatter import body
from dory.project import Project

_HEADING = re.compile(r"^#{1,5} ")
_FENCE = ("```", "~~~")


def loaded_files(vault: Path, project: Project | None) -> list[Path]:
    """Vault-relative paths a session start loads in full, in load order."""
    knowledge = scopes.knowledge_file(project)
    if knowledge is None:
        return []
    files: list[Path] = []
    for note in scopes.project_notes(vault, project):
        files.append(note)
        try:
            text = (vault / note).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # the session start reports nothing it cannot read
        files += [linked for linked in links.library_entries(vault, text) if linked not in files]
    return [*files, knowledge]


def topic_entries(vault: Path, topic: Path) -> list[Path]:
    """The library entries a topic file in `notes/` links in its `library` property."""
    return links.linked_by_property(vault, vault / topic)


def library_files(vault: Path, project: Project | None) -> list[Path]:
    """Every library entry a session start in `project` may load: from its notes and topics."""
    found = [path for path in loaded_files(vault, project) if path.parts[0] == scopes.LIBRARY]
    for topic in scopes.notes_folder_files(vault):
        if scopes.file_type(vault / topic) == "topic":
            found += [path for path in topic_entries(vault, topic) if path not in found]
    return found


def file_texts(vault: Path, files: list[Path]) -> dict[Path, str]:
    """The non-empty files among `files` (vault-relative), in their order."""
    texts = {}
    for path in files:
        if text := _file_text(vault, path):
            texts[path] = text
    return texts


def heading(path: Path) -> str:
    return f"## {path.as_posix()}"


def text(texts: dict[Path, str]) -> str:
    return "\n\n".join(f"{heading(path)}\n{content}" for path, content in texts.items())


def _file_text(vault: Path, path: Path) -> str:
    try:
        content = body(vault / path)
    except OSError:
        return ""  # missing, or replaced by a worker run in this moment
    lines, fenced = [], False
    for line in content.strip("\n").rstrip().splitlines():
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
        elif not fenced and _HEADING.match(line):
            line = f"#{line}"
        lines.append(line)
    return "\n".join(lines)
