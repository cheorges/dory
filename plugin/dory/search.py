"""`dory search`: find vault notes by summary, when, tags, file name and text.

Every word of the query is matched as a substring (case-insensitive), so "deploy" finds
"Deployen". A hit in summary or when weighs most, then tags and file name, then the text.
Notes that match more words come first. The domain boundary of the recall applies, and
superseded notes are left out: their successor carries the knowledge.
"""

from pathlib import Path

from dory.config import Config
from dory.frontmatter import body
from dory.project import lookup_project
from dory.recall import Note, allowed, project_domain, scan
from dory.state import StateDir

MAX_HITS = 10
_WEIGHTS = (("summary", 3), ("when", 3), ("tags", 2), ("name", 2), ("text", 1))


def search(config: Config, cwd: Path, query: str) -> str:
    terms = [word for word in query.lower().split() if len(word) >= 2]
    project = lookup_project(cwd, StateDir(config.state_dir).projects_file)  # read-only
    notes = scan(config.vault)
    domain = project_domain(project, notes, config.vault)
    candidates = [n for n in notes if allowed(n, domain) and not n.superseded]
    scored = [(score, note) for note in candidates if (score := _score(note, terms))[0]]
    if not scored:
        return f'No hits for "{query}" in the vault {config.vault}.'
    scored.sort(key=lambda hit: (-hit[0][0], -hit[0][1], hit[1].path.name))
    shown = min(len(scored), MAX_HITS)
    lines = [f'Hits for "{query}" ({shown} of {len(scored)}), vault {config.vault}:']
    lines += [_line(note, config.vault) for _, note in scored[:MAX_HITS]]
    return "\n".join(lines)


def _score(note: Note, terms: list[str]) -> tuple[int, int]:
    """(number of matched words, summed weight of the best field per word)."""
    tags = note.meta.get("tags")
    fields = {
        "summary": str(note.meta.get("summary", "")),
        "when": str(note.meta.get("when", "")),
        "tags": " ".join(tags) if isinstance(tags, list) else str(tags or ""),
        "name": note.path.stem,
        "text": _text(note.path),
    }
    fields = {key: value.lower() for key, value in fields.items()}
    matched = weight = 0
    for term in terms:
        best = max((w for key, w in _WEIGHTS if term in fields[key]), default=0)
        matched += best > 0
        weight += best
    return matched, weight


def _text(path: Path) -> str:
    try:
        return body(path)
    except OSError:
        return ""  # the worker replaced or merged the note since the scan


def _line(note: Note, vault: Path) -> str:
    summary = note.meta.get("summary") or note.path.stem
    when = f" (when: {note.meta['when']})" if note.meta.get("when") else ""
    return f"- {summary}{when} → {note.path.relative_to(vault)}"
