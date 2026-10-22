"""File names from titles, and names compared the way the vault's file system compares them.

A note's or topic's file name is its title. The characters that break an Obsidian link or a
path go, and the name stays within what file systems accept. APFS ignores case by default and
Obsidian matches link targets without case, so two names are the same when their composed
(NFC) forms are equal after casefolding.
"""

import unicodedata

MAX_CHARACTERS = 80
MAX_BYTES = 200  # of UTF-8; file systems allow 255
_UNLINKABLE = frozenset("[]#^|\\/:")
# The skills pass titles and folders in double quotes on a command line, where these characters
# end the quotes or expand; a name that holds one did not arrive as the model wrote it.
NOT_IN_QUOTES = frozenset('"$`')


class TitleError(ValueError):
    """A title that leaves no file name."""


def file_stem(title: str) -> str:
    """The file name without `.md` for a title; raises TitleError when nothing is left."""
    text = "".join(_kept(char) for char in unicodedata.normalize("NFC", title))
    text = _trim(_cut(_trim(" ".join(text.split()))))
    if not text:
        raise TitleError(f"the title {title!r} leaves no file name")
    return text


def name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def is_clean(stem: str) -> bool:
    """Whether a name on disk is what `file_stem` makes of it."""
    try:
        return file_stem(stem) == unicodedata.normalize("NFC", stem)
    except TitleError:
        return False


def _kept(char: str) -> str:
    """Whitespace and the characters a name cannot hold leave a space ("a/b" is "a b")."""
    if char.isspace() or char in _UNLINKABLE:
        return " "
    return char if char.isprintable() else ""


def _trim(text: str) -> str:
    return text.lstrip(". ").rstrip(". ")


def _cut(text: str) -> str:
    text = text[:MAX_CHARACTERS]
    while len(text.encode()) > MAX_BYTES:
        text = text[:-1]
    return text
