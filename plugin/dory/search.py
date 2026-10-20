"""`dory search`: find entries of the knowledge and notes files, session notes and lists.

Each entry of a `knowledge.md` or `notes.md` is scored on its own (with the parser of the
post-run checks), so a hit shows the statement, not a file that holds twenty. Every word of the
query is matched as a substring (case-insensitive), so "deploy" finds "Deployen". A hit in an
entry's lead or a note's summary weighs most, then tags and file name, then the text; hits that
match more words come first. Other files in the scope folders are from an earlier version of
dory and are neither shown nor searched (Record 003, decision 5).

The domain boundary of the session start applies: `general/` is work and `private/` private by
folder, a project's folder follows the project's domain, session notes and lists their own. In
a work project nothing private is shown; outside a repository and in a private project
everything is.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from dory import entries, scopes
from dory.config import Config
from dory.frontmatter import parse_frontmatter, strip_frontmatter
from dory.project import Project, lookup_project
from dory.state import StateDir

MAX_HITS = 10
_WEIGHTS = {"title": 3, "tags": 2, "name": 2, "text": 1}
_CATALOG_TYPES = {"list", "register"}
_BULLET = re.compile(r"^[-*+]\s+")


@dataclass(frozen=True)
class Candidate:
    path: Path  # vault-relative
    title: str  # an entry's lead, a note's summary
    label: str  # an entry's section, or the kind of note
    domain: str
    fields: dict[str, str]  # lower-case text per weight key


def search(config: Config, cwd: Path, query: str) -> str:
    terms = [word for word in query.lower().split() if len(word) >= 2]
    project = lookup_project(cwd, StateDir(config.state_dir).projects_file)  # read-only
    everything = project is None or scopes.project_domain(config.vault, project) == "private"
    candidates = [
        candidate
        for candidate in _candidates(config.vault)
        if everything or candidate.domain != "private"
    ]
    scored = [
        (score, index, c) for index, c in enumerate(candidates) if (score := _score(c, terms))[0]
    ]
    if not scored:
        return f'No hits for "{query}" in the vault {config.vault}.'
    scored.sort(key=lambda hit: (-hit[0][0], -hit[0][1], hit[2].path.as_posix(), hit[1]))
    shown = min(len(scored), MAX_HITS)
    lines = [f'Hits for "{query}" ({shown} of {len(scored)}), vault {config.vault}:']
    lines += [_line(candidate) for _, _, candidate in scored[:MAX_HITS]]
    return "\n".join(lines)


def _candidates(vault: Path) -> list[Candidate]:
    found: list[Candidate] = []
    for folder, domain in _scope_folders(vault):
        for name in (scopes.NOTES, scopes.KNOWLEDGE):
            found += _entries(vault, folder / name, domain)
    for path in sorted((vault / "sessions").rglob("*.md")):
        found += _note(vault, path, "session", default_domain="work")
    for path in sorted((vault / "notes").glob("*.md")):
        found += _note(vault, path, "list", default_domain="private")
    return found


def _scope_folders(vault: Path) -> list[tuple[Path, str]]:
    folders = [(Path("general"), "work"), (Path("private"), "private")]
    for folder in sorted((vault / "projects").glob("*")):
        if folder.is_dir():
            project = Project(name=folder.name, root=Path())  # only the name matters here
            folders.append((folder.relative_to(vault), scopes.project_domain(vault, project)))
    return folders


def _entries(vault: Path, relative: Path, domain: str) -> list[Candidate]:
    return [
        Candidate(
            path=relative,
            title=_statement(entry),
            label=entry.section,
            domain=domain,
            fields={"title": entry.lead.lower(), "text": entry.text.lower()},
        )
        for entry in entries.parse(_read(vault / relative))
    ]


def _statement(entry: entries.Entry) -> str:
    """The bold lead of a knowledge entry; a note of the user's has none and shows whole."""
    text = " ".join(_BULLET.sub("", entry.text, count=1).split())
    return entry.lead if text.startswith("**") else text


def _note(vault: Path, path: Path, kind: str, default_domain: str) -> list[Candidate]:
    """A session note or a list as one candidate; lists and registers only under `notes/`."""
    raw = _read(path)
    meta = parse_frontmatter(raw)
    if not meta:
        return []
    if kind == "list" and str(meta.get("type", "")) not in _CATALOG_TYPES:
        return []
    tags = meta.get("tags")
    summary = str(meta.get("summary") or path.stem)
    fields = {
        "title": summary,
        "tags": " ".join(map(str, tags)) if isinstance(tags, list) else str(tags or ""),
        "name": path.stem,
        "text": strip_frontmatter(raw),
    }
    return [
        Candidate(
            path=path.relative_to(vault),
            title=summary,
            label=str(meta.get("type", kind)),
            domain=str(meta.get("domain") or default_domain),
            fields={key: value.lower() for key, value in fields.items()},
        )
    ]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""  # missing, or replaced by a worker run in this moment


def _score(candidate: Candidate, terms: list[str]) -> tuple[int, int]:
    """(number of matched words, summed weight of the best field per word)."""
    matched = weight = 0
    for term in terms:
        best = max(
            (_WEIGHTS[key] for key, value in candidate.fields.items() if term in value),
            default=0,
        )
        matched += best > 0
        weight += best
    return matched, weight


def _line(candidate: Candidate) -> str:
    label = f" ({candidate.label})" if candidate.label else ""
    return f"- {candidate.title}{label} → {candidate.path.as_posix()}"
