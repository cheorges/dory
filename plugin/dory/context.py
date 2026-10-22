"""The text of a context: what a session start loads in full and the worker summarizes.

A known project's context is its notes, by name, each followed by the private notes it links
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
        files += [linked for linked in links.private_notes(vault, text) if linked not in files]
    return [*files, knowledge]


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
