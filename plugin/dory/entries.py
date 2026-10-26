"""Entries of a knowledge or notes file: the units that the post-run diff and search work on.

An entry is a bullet at column 0 up to the next such bullet or heading. Text between a heading
and its first bullet is an entry too, so that losing it shows. An entry is known by its bold
lead; one without a bold lead by the start of its text. A run that corrects an entry often
rewrites its lead as well, so the diff pairs a vanished entry with a similar new one and counts
the pair as one change instead of a removal.
"""

import difflib
import re
from dataclasses import dataclass, field

from dory.frontmatter import strip_frontmatter

_HEADING = re.compile(r"^#{1,6}\s")
_BULLET = re.compile(r"^[-*+]\s+")
_BOLD_LEAD = re.compile(r"^\*\*(.+?)\*\*")
_UNLED_LEAD_CHARS = 80
_SIMILAR = 0.5  # difflib ratio from which a vanished and a new entry count as one change


@dataclass(frozen=True)
class Entry:
    key: str
    lead: str
    section: str
    text: str


@dataclass(frozen=True)
class Change:
    change: str  # "added", "changed" or "removed"
    lead: str
    was: str = ""  # the old lead, when a corrected entry got a new one
    before: str = field(default="", compare=False)  # the old text of a changed or removed entry


def parse(text: str) -> list[Entry]:
    entries: list[Entry] = []
    section = ""
    lines: list[str] = []

    def close() -> None:
        content = "\n".join(lines).strip()
        if content:
            entries.append(_entry(content, section))
        lines.clear()

    for line in strip_frontmatter(text).splitlines():
        if _HEADING.match(line):
            close()
            section = line.lstrip("#").strip()
            continue
        if _BULLET.match(line):
            close()
        lines.append(line)
    close()
    return _number_duplicates(entries)


def diff(before: list[Entry], after: list[Entry]) -> list[Change]:
    old = {entry.key: entry for entry in before}
    new = {entry.key: entry for entry in after}
    changes = [
        Change("changed", entry.lead, before=old[entry.key].text)
        for entry in after
        if entry.key in old
        and (entry.text, entry.section) != (old[entry.key].text, old[entry.key].section)
    ]
    gone = [entry for entry in before if entry.key not in new]
    fresh = [entry for entry in after if entry.key not in old]
    paired_gone, paired_fresh = _pair_similar(gone, fresh)
    changes += [
        Change("changed", fresh[j].lead, was=gone[i].lead, before=gone[i].text)
        for i, j in zip(paired_gone, paired_fresh, strict=True)
    ]
    changes += [
        Change("added", entry.lead) for j, entry in enumerate(fresh) if j not in paired_fresh
    ]
    changes += [
        Change("removed", entry.lead, before=entry.text)
        for i, entry in enumerate(gone)
        if i not in paired_gone
    ]
    return changes


def _entry(content: str, section: str) -> Entry:
    text = _BULLET.sub("", content, count=1)
    bold = _BOLD_LEAD.match(text)
    lead = bold.group(1).strip() if bold else " ".join(text.split())[:_UNLED_LEAD_CHARS]
    return Entry(key=_normalize(lead), lead=lead, section=section, text=content)


def key(lead: str) -> str:
    """The key an entry with this lead gets (without the numbering of duplicate leads)."""
    return _normalize(lead)


def _normalize(text: str) -> str:
    return " ".join(text.replace("**", "").split()).casefold().rstrip(".:;,!? ")


def _number_duplicates(entries: list[Entry]) -> list[Entry]:
    seen: dict[str, int] = {}
    numbered = []
    for entry in entries:
        seen[entry.key] = seen.get(entry.key, 0) + 1
        count = seen[entry.key]
        key = entry.key if count == 1 else f"{entry.key} #{count}"
        numbered.append(Entry(key, entry.lead, entry.section, entry.text))
    return numbered


def _similarity(old: Entry, new: Entry) -> float:
    """How alike two entries are; the leads count only when the new one keeps the old one's words.

    A short entry corrected into a longer one differs in length more than in what it says, so
    its lead decides. Leads built on the same pattern ("Loki runs on port 3100", "Redis runs on
    port 6379") are alike as well, so a lead counts only when every word of the old one except
    its numbers is still there: a corrected value, not another subject.
    """
    text = _ratio(old.text, new.text)
    if not _words(old.lead) <= _words(new.lead):
        return text
    return max(text, _ratio(old.lead, new.lead))


def _words(text: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]+", _normalize(text)))


def _ratio(old: str, new: str) -> float:
    # Without autojunk: from 200 characters on, difflib would ignore every frequent letter.
    return difflib.SequenceMatcher(None, _normalize(old), _normalize(new), autojunk=False).ratio()


def _pair_similar(gone: list[Entry], fresh: list[Entry]) -> tuple[list[int], list[int]]:
    """Most similar pairs first; each entry pairs at most once."""
    scored = sorted(
        ((_similarity(a, b), i, j) for i, a in enumerate(gone) for j, b in enumerate(fresh)),
        key=lambda pair: (-pair[0], pair[1], pair[2]),
    )
    paired_gone: list[int] = []
    paired_fresh: list[int] = []
    for score, i, j in scored:
        if score < _SIMILAR:
            break
        if i not in paired_gone and j not in paired_fresh:
            paired_gone.append(i)
            paired_fresh.append(j)
    return paired_gone, paired_fresh
