"""`dory search`: find entries and notes anywhere in the vault.

Each entry of a project's `knowledge.md` and of a topic file in `notes/` is scored on its own
(with the parser of the post-run checks), so a hit shows the statement, not a file that holds
twenty. The user's project notes, private notes, lists, registers and session notes count as one
document each. Every word of the query is matched as a substring (case-insensitive), so "deploy"
finds "Deployen". A hit in an entry's lead or a note's title weighs most, then tags and file
name, then the text; hits that match more words come first. Files an earlier version of dory
wrote (`general/`, a project's `notes.md`, single notes in a project folder) are neither shown
nor searched.

A search is the user's own request, so it covers the whole vault in every session, `private/`
included.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from dory import entries, scopes
from dory.config import Config
from dory.frontmatter import parse_frontmatter, strip_frontmatter

MAX_HITS = 10
_WEIGHTS = {"title": 3, "tags": 2, "name": 2, "text": 1}
_BULLET = re.compile(r"^[-*+]\s+")


@dataclass(frozen=True)
class Candidate:
    path: Path  # vault-relative
    title: str  # an entry's lead, a note's summary or name
    label: str  # an entry's section, or the kind of note
    fields: dict[str, str]  # lower-case text per weight key


def search(config: Config, cwd: Path, query: str) -> str:
    """Hits for `query`; `cwd` is where the user searches, and the whole vault is searched."""
    terms = [word for word in query.lower().split() if len(word) >= 2]
    candidates = _candidates(config.vault)
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
    for path in sorted((vault / "projects").glob(f"*/{scopes.KNOWLEDGE}")):
        found += _entries(vault, path.relative_to(vault))
    for relative in scopes.notes_folder_files(vault):
        kind = scopes.file_type(vault / relative)
        if kind == "topic":
            found += _entries(vault, relative)
        else:
            found += _document(vault, vault / relative, kind)
    for path in sorted((vault / "projects").glob(f"*/{scopes.NOTES_FOLDER}/*.md")):
        found += _document(vault, path, "note")
    for path in sorted((vault / scopes.PRIVATE).rglob("*.md")):
        found += _document(vault, path, "private note")
    for path in sorted((vault / "sessions").rglob("*.md")):
        found += _document(vault, path, "session")
    return found


def _entries(vault: Path, relative: Path) -> list[Candidate]:
    return [
        Candidate(
            path=relative,
            title=_statement(entry),
            label=entry.section,
            fields={"title": entry.lead.lower(), "text": entry.text.lower()},
        )
        for entry in entries.parse(_read(vault / relative))
    ]


def _statement(entry: entries.Entry) -> str:
    """The bold lead of an entry; a bullet without one shows whole."""
    text = " ".join(_BULLET.sub("", entry.text, count=1).split())
    return entry.lead if text.startswith("**") else text


def _document(vault: Path, path: Path, kind: str) -> list[Candidate]:
    """A note, list or session note as one candidate, titled by its summary or its name."""
    if not path.is_file():
        return []
    raw = _read(path)
    meta = parse_frontmatter(raw)
    tags = meta.get("tags")
    title = str(meta.get("summary") or path.stem)
    fields = {
        "title": title,
        "tags": " ".join(map(str, tags)) if isinstance(tags, list) else str(tags or ""),
        "name": path.stem,
        "text": strip_frontmatter(raw),
    }
    return [
        Candidate(
            path=path.relative_to(vault),
            title=title,
            label=str(meta.get("type") or kind),
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
