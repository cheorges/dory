"""Links in the user's project notes that bring a private note into the session start.

Only a link whose target lies in `private/` counts. A target is a path from the vault root
(`private/Employment contract`) or a bare name (`Employment contract`) that matches a file under
`private/`. Obsidian allows an embed (`![[...]]`), an alias (`|...`), a heading (`#...`) and the
`.md` suffix, and Markdown links with a percent-encoded or bracketed target; links inside code
are no links. Names match without case, as APFS and Obsidian match them. Every target is
resolved to its real path and kept only when that path lies inside `private/`, so neither `..`
nor a symlink leads out of it.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote

from dory.names import name_key
from dory.scopes import PRIVATE

_FENCE = ("```", "~~~")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK = re.compile(
    r"!?\[\[(?P<wiki>[^\]\n]*)\]\]"
    r"|!?\[[^\]\n]*\]\((?:<(?P<bracketed>[^>\n]+)>|(?P<plain>[^)\s]+))\)"
)


def private_notes(vault: Path, text: str) -> list[Path]:
    """Vault-relative paths of the private notes `text` links, in the order of the first link."""
    private = (vault / PRIVATE).resolve()
    if not private.is_dir():
        return []
    found: list[Path] = []
    for target in _targets(_INLINE_CODE.sub("", _without_fenced_code(text))):
        path = _resolve(vault, private, target)
        if path is not None and path not in found:
            found.append(path)
    return found


def _without_fenced_code(text: str) -> str:
    """The lines outside fenced code; an indented fence counts, an unclosed one runs to the end."""
    kept, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
        elif not fenced:
            kept.append(line)
    return "\n".join(kept)


def _targets(text: str) -> Iterator[str]:
    for match in _LINK.finditer(text):
        if match["wiki"] is not None:
            target = match["wiki"].split("|", 1)[0].removesuffix("\\")  # `\|` in a table
        else:
            target = unquote(match["bracketed"] or match["plain"])
        target = target.split("#", 1)[0].strip()
        if target:
            yield target if target.lower().endswith(".md") else f"{target}.md"


def _resolve(vault: Path, private: Path, target: str) -> Path | None:
    if "/" in target:
        candidate = _walk(vault, target.split("/"))
    else:
        candidate = next(
            (
                path
                for path in sorted(private.rglob("*.md"))
                if name_key(path.name) == name_key(target)
            ),
            None,
        )
    if candidate is None:
        return None
    real = candidate.resolve()
    if not real.is_file() or not real.is_relative_to(private):
        return None
    return Path(PRIVATE) / real.relative_to(private)  # `private/` may itself be a link


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
