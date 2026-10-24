"""What a vault file is about, for the commands that list files to choose from.

`library-context` lists each file with this line, and `library-candidates` ranks the same files.
"""

import re
from pathlib import Path

from dory.frontmatter import body
from dory.links import without_fenced_code

ABOUT_CHARS = 100
# The sections of knowledge and topic files say nothing about what a file is about.
SECTIONS = frozenset({"Pitfalls", "Decisions", "Facts", "How-to", "Preferences"})
_HEADING = re.compile(r"^#{1,6}\s+(.+)$")  # a tag line such as `#release` is none


def about(path: Path, meta: dict[str, object]) -> str:
    """The file's `description`, else its first heading outside code, cut to one short line;
    empty when the file cannot be read."""
    text = str(meta.get("description") or "").strip()
    if not text:
        try:
            lines = without_fenced_code(body(path)).splitlines()
        except OSError:
            return ""
        headings = (m for line in lines if (m := _HEADING.match(line)))
        heading = next((m for m in headings if m.group(1).strip() not in SECTIONS), None)
        text = heading.group(1).strip() if heading else ""
    return text if len(text) <= ABOUT_CHARS else f"{text[: ABOUT_CHARS - 1]}…"


def values(value: object) -> list[str]:
    """A property's values as a list of non-empty strings, a scalar included."""
    items = value if isinstance(value, list) else [value] if value else []
    return [str(item).strip() for item in items if str(item).strip()]
