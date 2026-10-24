"""Links that bring a library entry into the session start.

A project note links an entry in its text or in its `library` property; a topic file in `notes/`
only in the property, since the worker writes its text (`linked_by_property`). Only a link whose
target lies in `library/` counts. A target is a path from the vault root
(`library/Python/Package management`) or a bare name (`Package management`) that matches a file
under `library/`. Obsidian allows an embed (`![[...]]`), an alias (`|...`), a heading (`#...`)
and the `.md` suffix, and Markdown links with a percent-encoded or bracketed target; links inside
code are no links. Names match without case, as APFS and Obsidian match them. Every target is
resolved to its real path and kept only when that path lies inside `library/`, so neither `..`
nor a symlink leads out of it.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote

from dory.frontmatter import read_frontmatter
from dory.names import name_key
from dory.scopes import LIBRARY, LIBRARY_KEY

_FENCE = ("```", "~~~")
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK = re.compile(
    r"!?\[\[(?P<wiki>[^\]\n]*)\]\]"
    r"|!?\[[^\]\n]*\]\((?:<(?P<bracketed>[^>\n]+)>|(?P<plain>[^)\s]+))\)"
)


def library_entries(vault: Path, text: str) -> list[Path]:
    """Vault-relative paths of the library entries `text` links, in the order of the first link.

    A project note's whole text counts, its frontmatter and so its `library` property included.
    """
    library = (vault / LIBRARY).resolve()
    if not library.is_dir():
        return []
    found: list[Path] = []
    for target in _targets(INLINE_CODE.sub("", without_fenced_code(text))):
        path = _resolve(vault, library, target)
        if path is not None and path not in found:
            found.append(path)
    return found


def linked_by_property(vault: Path, path: Path) -> list[Path]:
    """The library entries the `library` property of `path` links; a bare path counts too."""
    value = read_frontmatter(path).get(LIBRARY_KEY)
    values = value if isinstance(value, list) else [value] if value else []
    text = "\n".join(
        item if "[[" in item or "](" in item else f"[[{item}]]" for item in map(str, values)
    )
    return library_entries(vault, text)


def without_fenced_code(text: str) -> str:
    """The lines outside fenced code; an indented fence counts, an unclosed one runs to the end."""
    kept, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
        elif not fenced:
            kept.append(line)
    return "\n".join(kept)


def wiki_names(text: str) -> list[str]:
    """The note names the wikilinks in `text` point to, outside code: `[[a/b.md#h|x]]` is `b`.
    A dot inside a name (`Node.js`) stays, a table's `\\|` and a `.md` suffix do not."""
    names = []
    for match in LINK.finditer(INLINE_CODE.sub("", without_fenced_code(text))):
        if match["wiki"] is None:
            continue
        target = match["wiki"].split("|", 1)[0].removesuffix("\\").split("#", 1)[0].strip()
        name = target.rsplit("/", 1)[-1]
        name = name[:-3] if name.lower().endswith(".md") else name
        if name:
            names.append(name)
    return names


def _targets(text: str) -> Iterator[str]:
    for match in LINK.finditer(text):
        if match["wiki"] is not None:
            target = match["wiki"].split("|", 1)[0].removesuffix("\\")  # `\|` in a table
        else:
            target = unquote(match["bracketed"] or match["plain"])
        target = target.split("#", 1)[0].strip()
        if target:
            yield target if target.lower().endswith(".md") else f"{target}.md"


def _resolve(vault: Path, library: Path, target: str) -> Path | None:
    if "/" in target:
        candidate = _walk(vault, target.split("/"))
    else:
        candidate = next(
            (
                path
                for path in sorted(library.rglob("*.md"))
                if name_key(path.name) == name_key(target)
            ),
            None,
        )
    if candidate is None:
        return None
    real = candidate.resolve()
    if not real.is_file() or not real.is_relative_to(library):
        return None
    return Path(LIBRARY) / real.relative_to(library)  # `library/` may itself be a link


def _walk(root: Path, parts: list[str]) -> Path | None:
    """The path the parts name below `root`, each part matched without case."""
    current = root
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            current = current / part
            continue
        current = next(
            (entry for entry in _entries(current) if name_key(entry.name) == name_key(part)), None
        )
        if current is None:
            return None
    return current


def _entries(folder: Path) -> list[Path]:
    try:
        return sorted(folder.iterdir())
    except OSError:
        return []
