"""Summaries of a context, made by the worker and loaded by the session start (Record 003).

A context is what one session start loads: a known project (`project-<name>`), `_general` for
a repository dory does not know yet, `_outside` for sessions outside a repository. A project's
name comes from its directory and can be anything, so the prefix keeps it apart from the two
reserved names. The summary lives in `<state>/summaries/<context>.md` with the hash of the text
it was made from and the domain in its header. A session start that needs a new one touches
`<context>.wanted`.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dory import scopes
from dory.config import Config
from dory.frontmatter import parse_frontmatter, strip_frontmatter
from dory.project import Project
from dory.state import StateDir

OUTSIDE = "_outside"
GENERAL = "_general"
_PROJECT = "project-"
CHARS_PER_TOKEN = 4
SHARE = 0.8  # of the limit; the rest stays for header, project line, queue lines and paths
_WANTED = ".wanted"


@dataclass(frozen=True)
class Context:
    name: str
    files: list[Path]

    @property
    def domain(self) -> str:
        """Private when the context loads `private/`; the summary must never cross it."""
        return "private" if any(path.parts[0] == "private" for path in self.files) else "work"


@dataclass(frozen=True)
class Summary:
    text: str
    hash: str
    domain: str


def context_name(project: Project | None) -> str:
    if project is None:
        return OUTSIDE
    return f"{_PROJECT}{project.name}" if project.name else GENERAL


def context_for(vault: Path, project: Project | None) -> Context:
    files = scopes.context_files(project, scopes.project_domain(vault, project))
    return Context(context_name(project), files)


def context_named(vault: Path, name: str) -> Context | None:
    """The context a mark names; None for a name dory does not give."""
    if name == OUTSIDE:
        return context_for(vault, None)
    if name == GENERAL:
        return context_for(vault, Project(name="", root=Path()))
    if name.startswith(_PROJECT) and len(name) > len(_PROJECT):
        # Only the name matters for the vault layout.
        return context_for(vault, Project(name=name.removeprefix(_PROJECT), root=Path()))
    return None


def limit_chars(config: Config) -> int:
    return config.recall_budget_tokens * CHARS_PER_TOKEN


def target_chars(config: Config) -> int:
    return int(limit_chars(config) * SHARE)


def needs_summary(text: str, config: Config) -> bool:
    """The one test the session start and the worker share."""
    return len(text) > target_chars(config)


def digest(text: str, domain: str, config: Config) -> str:
    """Changes with the text, the domain, the note language and the limit."""
    key = json.dumps([text, domain, config.language, config.recall_budget_tokens])
    return hashlib.sha256(key.encode()).hexdigest()


def load(state: StateDir, name: str) -> Summary | None:
    try:
        raw = _path(state, name).read_text(encoding="utf-8")
    except OSError:
        return None
    meta = parse_frontmatter(raw)
    if not meta.get("hash") or not meta.get("domain"):
        return None
    return Summary(strip_frontmatter(raw).strip("\n"), str(meta["hash"]), str(meta["domain"]))


def save(state: StateDir, name: str, summary: Summary) -> None:
    path = _path(state, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"---\nhash: {summary.hash}\ndomain: {summary.domain}\n---\n"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(header + summary.text + "\n", encoding="utf-8")
    tmp.replace(path)


def mark(state: StateDir, name: str) -> None:
    path = state.summaries / f"{name}{_WANTED}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def marked(state: StateDir) -> set[str]:
    return {path.name.removesuffix(_WANTED) for path in state.summaries.glob(f"*{_WANTED}")}


def unmark(state: StateDir, name: str) -> None:
    (state.summaries / f"{name}{_WANTED}").unlink(missing_ok=True)


def _path(state: StateDir, name: str) -> Path:
    return state.summaries / f"{name}.md"
