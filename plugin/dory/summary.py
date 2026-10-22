"""Summaries of a context, made by the worker and loaded by the session start.

A context is what one session start loads in full: a known project's notes, the private notes
they link and its `knowledge.md` (`context.loaded_files`). Its name is `project-<name>`; the
names `_general` and `_outside` of earlier versions name no context any more, since nothing
loads in full outside a known project. The summary lives in `<state>/summaries/<context>.md`
with the hash of the text it was made from, the domain and the linked private notes in its
header; it is used only for the same domain and the same linked notes, so a private note's
content never outlives its link. A session start that needs a new one touches
`<context>.wanted`.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dory import context, scopes
from dory.config import Config
from dory.frontmatter import parse_frontmatter, strip_frontmatter
from dory.project import Project
from dory.state import StateDir

OUTSIDE = "_outside"
GENERAL = "_general"
_PROJECT = "project-"
CHARS_PER_TOKEN = 4
SHARE = 0.8  # of the limit; the rest stays for header, project line, queue lines and paths
LEVELS = {"lean": 0.05, "balanced": 0.10, "rich": 0.15}  # of the context window
SUMMARY_MAX_TOKENS = 10_000  # one run writes no more; the lean limit of a 200k window
_WANTED = ".wanted"


@dataclass(frozen=True)
class Context:
    name: str
    files: list[Path]
    private_project: bool = False

    @property
    def domain(self) -> str:
        """Private for a private project or one that loads a private note; never crossed."""
        return "private" if self.private_project or self.linked else "work"

    @property
    def linked(self) -> tuple[str, ...]:
        """The private notes the context loads, as their paths."""
        return tuple(sorted(path.as_posix() for path in self.files if path.parts[0] == "private"))


@dataclass(frozen=True)
class Summary:
    text: str
    hash: str
    domain: str
    linked: tuple[str, ...] = ()

    def fits(self, ctx: Context) -> bool:
        """Made for the context's domain and the private notes it loads now."""
        return self.domain == ctx.domain and self.linked == ctx.linked


def context_name(project: Project | None) -> str:
    if project is None:
        return OUTSIDE
    return f"{_PROJECT}{project.name}" if project.name else GENERAL


def context_for(vault: Path, project: Project | None) -> Context:
    private = scopes.project_domain(vault, project) == "private"
    return Context(context_name(project), context.loaded_files(vault, project), private)


def context_named(vault: Path, name: str) -> Context | None:
    """The context a mark names; None for a name dory does not give, `_general` and `_outside`
    of earlier versions included."""
    if name.startswith(_PROJECT) and len(name) > len(_PROJECT):
        # Only the name matters for the vault layout.
        return context_for(vault, Project(name=name.removeprefix(_PROJECT), root=Path()))
    return None


def limit_tokens(config: Config) -> int:
    """What the session start may inject: the level's share of the window, or an exact limit."""
    if config.recall_budget_tokens:
        return config.recall_budget_tokens
    return int(config.context_window * LEVELS.get(config.context, LEVELS["lean"]))


def limit_chars(config: Config) -> int:
    return limit_tokens(config) * CHARS_PER_TOKEN


def threshold_chars(config: Config) -> int:
    """A project's files longer than this get a summary."""
    return int(limit_chars(config) * SHARE)


def target_chars(config: Config) -> int:
    """The longest summary: the threshold, but never more than one run writes."""
    return min(threshold_chars(config), SUMMARY_MAX_TOKENS * CHARS_PER_TOKEN)


def needs_summary(text: str, config: Config) -> bool:
    """The one test the session start and the worker share."""
    return len(text) > threshold_chars(config)


def digest(text: str, domain: str, config: Config) -> str:
    """Changes with the text, the domain, the note language and the limit."""
    key = json.dumps([text, domain, config.language, limit_tokens(config)])
    return hashlib.sha256(key.encode()).hexdigest()


def load(state: StateDir, name: str) -> Summary | None:
    try:
        raw = _path(state, name).read_text(encoding="utf-8")
    except OSError:
        return None
    meta = parse_frontmatter(raw)
    if not meta.get("hash") or not meta.get("domain"):
        return None
    linked = meta.get("linked")
    return Summary(
        strip_frontmatter(raw).strip("\n"),
        str(meta["hash"]),
        str(meta["domain"]),
        tuple(map(str, linked)) if isinstance(linked, list) else (),
    )


def save(state: StateDir, name: str, summary: Summary) -> None:
    path = _path(state, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    linked = json.dumps(list(summary.linked), ensure_ascii=False)
    header = f"---\nhash: {summary.hash}\ndomain: {summary.domain}\nlinked: {linked}\n---\n"
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
