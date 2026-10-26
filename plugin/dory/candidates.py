"""`dory library-candidates`: the files that should link a new library entry, and the entries
that may already cover its subject (Record 009).

Code finds and ranks the candidates, each with its reasons, and `/dory:library` chooses among
them. Signals, strongest first: a link `[[X]]` that no file answers yet, X being the draft's
title or an alias; a mention of the title, an alias or a phrase of a multi-word title outside
code and links; a file's own title or alias in the draft; BM25 over the linkable files with the
whole draft; and files that already link an entry the draft may duplicate. A library entry may
duplicate the draft when its title shares at least 75 % of its words, when the two share a
name, or when the entry's title or alias stands in the draft's title (`uv` in "uv sync").
Pure Python over the Markdown files; no index.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from dory import describe, links, names, scopes
from dory.frontmatter import body, read_frontmatter
from dory.project import Project

MAX_LINKS = 20
MAX_DUPLICATES = 5
MIN_PHRASE = 4  # a phrase of the title, or another file's name, of three characters or less
# counts as no mention; the draft's own title and aliases count at any length, as whole words
JACCARD = 0.75
_STEM = 6  # BM25 compares words by their first characters: Rechnung, Rechnungen
_K1, _B = 1.2, 0.75
_WORD = re.compile(r"\w+", re.UNICODE)
_WEIGHTS = {"unresolved": 10.0, "mention": 5.0, "phrase": 3.0, "title": 4.0, "neighbour": 2.0}
_BM25_WEIGHT = 4.0


@dataclass(frozen=True)
class Draft:
    title: str
    aliases: list[str]
    content: str

    @property
    def names(self) -> list[str]:
        return [self.title, *self.aliases]


@dataclass
class Candidate:
    path: Path
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def add(self, weight: float, reason: str) -> None:
        self.score += weight
        if reason not in self.reasons:
            self.reasons.append(reason)


def parse_draft(text: str) -> Draft:
    """`# <title>`, then an optional `aliases: a, b` line, then the content."""
    lines = text.strip().splitlines()
    if not lines or not lines[0].startswith("# ") or not lines[0][2:].strip():
        raise ValueError("the draft starts with a line `# <title>`")
    title, rest = lines[0][2:].strip(), lines[1:]
    aliases: list[str] = []
    if rest and rest[0].casefold().startswith("aliases:"):
        aliases = [a.strip() for a in rest[0].split(":", 1)[1].split(",") if a.strip()]
        rest = rest[1:]
    return Draft(title, aliases, "\n".join(rest).strip())


def candidates(
    vault: Path, project: Project | None, draft: Draft
) -> tuple[list[Candidate], list[Candidate]]:
    """The files to link from, best first, and the library entries that may cover the subject."""
    linkable = _linkable(vault, project)
    texts = {path: _plain(_read(vault / path)) for path in linkable}
    duplicates = _duplicates(vault, draft)
    found = {path: Candidate(path) for path in linkable}
    unanswered = _unanswered(vault, draft)
    draft_text = _plain(f"{draft.title}\n{draft.content}")  # _mentions ignores case; ß stays
    phrases = _phrases(draft.title, texts)
    for path in linkable:
        candidate, raw = found[path], _read(vault / path)
        for target in unanswered:
            if names.name_key(target) in {names.name_key(n) for n in links.wiki_names(raw)}:
                candidate.add(_WEIGHTS["unresolved"], f"links [[{target}]], which has no file yet")
        for name in draft.names:
            if _mentions(texts[path], name):
                candidate.add(_WEIGHTS["mention"], f'mentions "{name}"')
        if phrase := next((p for p in phrases if _mentions(texts[path], p)), None):
            candidate.add(_WEIGHTS["phrase"], f'mentions "{phrase}"')
        for own in _own_names(vault / path):
            if len(own) >= MIN_PHRASE and _mentions(draft_text, own):
                candidate.add(_WEIGHTS["title"], f'its name "{own}" occurs in the draft')
    _add_bm25(found, texts, f"{draft.title} {' '.join(draft.aliases)} {draft.content}")
    _add_neighbours(vault, found, duplicates, draft)
    ranked = sorted(
        (c for c in found.values() if c.score > 0), key=lambda c: (-c.score, c.path.as_posix())
    )
    return ranked[:MAX_LINKS], duplicates[:MAX_DUPLICATES]


def render(vault: Path, found: list[Candidate], duplicates: list[Candidate]) -> str:
    lines = ["Files to link from, best first:"]
    for candidate in found:
        about = describe.about(vault / candidate.path, read_frontmatter(vault / candidate.path))
        lines.append(
            f"- {candidate.path.as_posix()} ({_loads(candidate.path)}; score "
            f"{candidate.score:.1f}): {'; '.join(candidate.reasons)}"
            + (f' | "{about}"' if about else "")
        )
    lines += ["- none"] if not found else []
    lines += ["", "Library entries that may cover the same subject:"]
    lines += [f"- {c.path.as_posix()} ({'; '.join(c.reasons)})" for c in duplicates] or ["- none"]
    return "\n".join(lines)


def _linkable(vault: Path, project: Project | None) -> list[Path]:
    """The visible projects' notes and the topic files, the files `dory link` accepts."""
    found = [
        path
        for name in scopes.visible_projects(vault, project)
        for path in scopes.project_notes(vault, Project(name, vault))
    ]
    return found + [
        path
        for path in scopes.notes_folder_files(vault)
        if scopes.file_type(vault / path) == "topic"
    ]


def _duplicates(vault: Path, draft: Draft) -> list[Candidate]:
    library = vault / scopes.LIBRARY
    draft_names = {names.name_key(n) for n in draft.names}
    title_words = set(_words(draft.title))
    found = []
    for path in sorted(library.rglob("*.md")):
        relative = path.relative_to(vault)
        candidate = Candidate(relative)
        words = set(_words(path.stem))
        if title_words and words:
            overlap = len(title_words & words) / len(title_words | words)
            if overlap >= JACCARD:
                candidate.add(overlap, f'its title "{path.stem}" shares the words of the draft\'s')
        own_names = _own_names(path)
        own = {names.name_key(n) for n in own_names}
        for shared in sorted(own & draft_names):
            candidate.add(1.0, f'shares the name "{shared}"')
        for name in own_names:
            if names.name_key(name) not in draft_names and _mentions(draft.title, name):
                candidate.add(0.8, f'its name "{name}" is in the draft\'s title')
        if candidate.score:
            found.append(candidate)
    return sorted(found, key=lambda c: (-c.score, c.path.as_posix()))


def _unanswered(vault: Path, draft: Draft) -> list[str]:
    """The draft's title and aliases that no file in the vault is named after."""
    stems = {names.name_key(path.stem) for path in vault.rglob("*.md")}
    return [name for name in draft.names if names.name_key(name) not in stems]


def _plain(text: str) -> str:
    """The text without code and links, which count as no mention."""
    text = links.INLINE_CODE.sub(" ", links.without_fenced_code(text))
    return links.LINK.sub(" ", text)


def _mentions(text: str, phrase: str) -> bool:
    pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, phrase.split())) + r"(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _phrases(title: str, texts: dict[Path, str]) -> list[str]:
    """The phrases of a multi-word title, longest first, without the whole title. Each starts
    and ends with a word of at least four characters, so that "the working" is none, and a
    single word counts only when at most a tenth of the linkable files hold it, so that "with"
    or "eine" is none."""
    words = title.split()
    spans = [
        words[start:end]
        for start in range(len(words))
        for end in range(start + 1, len(words) + 1)
        if end - start < len(words)
    ]
    kept = [w for w in spans if len(w[0]) >= MIN_PHRASE and len(w[-1]) >= MIN_PHRASE]
    rare = max(1, len(texts) // 10)
    kept = [
        w for w in kept if len(w) > 1 or sum(_mentions(t, w[0]) for t in texts.values()) <= rare
    ]
    return [" ".join(w) for w in sorted(kept, key=len, reverse=True)]


def _own_names(path: Path) -> list[str]:
    return [path.stem, *describe.values(read_frontmatter(path).get("aliases"))]


def _words(text: str) -> list[str]:
    return [word.casefold() for word in _WORD.findall(text) if len(word) > 2]


def _stems(text: str) -> list[str]:
    """The words BM25 compares: four characters or more, so that "the" and "mit" do not."""
    return [word[:_STEM] for word in _words(text) if len(word) >= MIN_PHRASE]


def _add_bm25(found: dict[Path, Candidate], texts: dict[Path, str], query: str) -> None:
    documents = {path: Counter(_stems(f"{path.stem} {text}")) for path, text in texts.items()}
    if not documents:
        return
    average = sum(sum(d.values()) for d in documents.values()) / len(documents)
    terms = set(_stems(query))
    frequency = {t: sum(1 for d in documents.values() if t in d) for t in terms}
    scores: dict[Path, tuple[float, list[str]]] = {}
    for path, counts in documents.items():
        length, total, shared = sum(counts.values()), 0.0, []
        for term in terms:
            if not counts[term]:
                continue
            idf = math.log(1 + (len(documents) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            tf = counts[term] * (_K1 + 1) / (counts[term] + _K1 * (1 - _B + _B * length / average))
            total += idf * tf
            shared.append((idf, term))
        if total:
            scores[path] = (total, [term for _, term in sorted(shared, reverse=True)[:3]])
    best = max(score for score, _ in scores.values()) if scores else 0
    for path, (score, shared) in scores.items():
        found[path].add(_BM25_WEIGHT * score / best, f"shares words: {', '.join(shared)}")


def _add_neighbours(
    vault: Path, found: dict[Path, Candidate], duplicates: list[Candidate], draft: Draft
) -> None:
    """Files that already link an entry the draft may duplicate, or that the draft links."""
    entries = [c.path for c in duplicates[:MAX_DUPLICATES]]
    linked = {names.name_key(name) for name in links.wiki_names(draft.content)}
    for path, candidate in found.items():
        # A project note links an entry in its text too, a topic file only in its property.
        linking = (
            links.library_entries(vault, _read_all(vault / path))
            if path.parts[0] == "projects"
            else links.linked_by_property(vault, vault / path)
        )
        for entry in linking:
            if entry in entries:
                candidate.add(_WEIGHTS["neighbour"], f"links {entry.with_suffix('').as_posix()}")
        if names.name_key(path.stem) in linked:
            candidate.add(_WEIGHTS["neighbour"], "the draft links it")


def _loads(path: Path) -> str:
    parts = path.parts
    return f"loads in {parts[1]}'s sessions" if parts[0] == "projects" else "loads in every session"


def _read(path: Path) -> str:
    try:
        return body(path)
    except OSError:
        return ""


def _read_all(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
