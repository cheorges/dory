"""Where things live in the vault.

A project keeps its knowledge in `projects/<name>/knowledge.md`, which the worker writes, and
the user's notes in `projects/<name>/notes/`, one file each. Everything without a project lives
in `notes/`: topic files the worker maintains, lists and registers. `library/` holds the knowledge
the user files deliberately, by hand or through `/dory:library`; a project note or a topic file
links an entry there to load it. Any other file in a project folder is from an earlier version
of dory and is neither read nor written.
"""

from pathlib import Path

from dory.frontmatter import read_frontmatter
from dory.project import Project

KNOWLEDGE = "knowledge.md"
NOTES_FOLDER = "notes"  # in the vault for everything without a project, in a project for its notes
LIBRARY = "library"
LIBRARY_KEY = "library"  # the property of a project note or topic file that links entries
OLD_PRIVATE = "private"  # the folder before 0.7.0; the user renames it in Obsidian
LIST_TYPES = frozenset({"list", "register"})


def knowledge_file(project: Project | None) -> Path | None:
    """The project's `knowledge.md`, the one file in its folder the worker writes."""
    if project is None or not project.name:
        return None
    return Path("projects") / project.name / KNOWLEDGE


def notes_folder_files(root: Path) -> list[Path]:
    """The files of `notes/` under `root` that count: the `.md` files at its top level."""
    folder = root / NOTES_FOLDER
    return sorted(path.relative_to(root) for path in folder.glob("*.md") if path.is_file())


def project_notes(vault: Path, project: Project | None) -> list[Path]:
    """The user's notes for a project: the `.md` files at the top level of its `notes/`."""
    if project is None or not project.name:
        return []
    folder = vault / "projects" / project.name / NOTES_FOLDER
    return sorted(path.relative_to(vault) for path in folder.glob("*.md") if path.is_file())


def file_type(path: Path) -> str:
    """The kind of a file in `notes/`: a list, a register, or else a topic."""
    kind = str(read_frontmatter(path).get("type", ""))
    return kind if kind in LIST_TYPES else "topic"


def project_domain(vault: Path, project: Project | None) -> str:
    """A project is work unless the user set `domain: private` in its knowledge file.

    Before that file exists, a project overview of an earlier version decides, so a project the
    user had marked private stays private.
    """
    if project is None or not project.name:
        return "work"
    folder = vault / "projects" / project.name
    source = folder / KNOWLEDGE
    if not source.exists():
        source = folder / f"{project.name}.md"
    return "private" if read_frontmatter(source).get("domain") == "private" else "work"


def visible_projects(vault: Path, project: Project | None) -> list[str]:
    """The projects whose files a session may list, its own first: a private project's session
    sees only its own project, and no other session sees a private project."""
    own = project.name if project and project.name else None
    if own and project_domain(vault, project) == "private":
        return [own]
    others = sorted(
        path.name
        for path in (vault / "projects").glob("*")
        if path.is_dir()
        and path.name != own
        and project_domain(vault, Project(path.name, path)) != "private"
    )
    return [own, *others] if own else others
