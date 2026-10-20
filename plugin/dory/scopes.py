"""Where knowledge lives in the vault: one knowledge file and one notes file per scope.

A scope is a project (`projects/<name>/`), `general/` for knowledge without a project in the
work domain, or `private/` for the private domain. The worker writes `knowledge.md`; the user
writes `notes.md` through /dory:note. Any other file in these folders is from an earlier
version of dory and is neither read nor written.
"""

from pathlib import Path

from dory.frontmatter import read_frontmatter
from dory.project import Project

KNOWLEDGE = "knowledge.md"
NOTES = "notes.md"
SCOPES = ("projects", "general", "private")


def knowledge_files(project: Project | None, domain: str = "work") -> list[Path]:
    """Vault-relative paths of the knowledge files a worker run may write.

    A private project's session never writes `general/`, which every work session loads.
    """
    files = [Path("general") / KNOWLEDGE, Path("private") / KNOWLEDGE]
    if domain == "private":
        files.remove(Path("general") / KNOWLEDGE)
    if project and project.name:
        files.insert(0, Path("projects") / project.name / KNOWLEDGE)
    return files


def context_files(project: Project | None, domain: str = "work") -> list[Path]:
    """Vault-relative paths a session start loads, in load order: notes before knowledge.

    A project loads its own folder and `general/`, a private one `private/` as well. Outside
    a repository `general/` and `private/` load; a repository dory does not know yet loads
    `general/`.
    """
    folders = [Path("general")]
    if project is None or domain == "private":
        folders.append(Path("private"))
    if project and project.name:
        folders.insert(0, Path("projects") / project.name)
    return [folder / name for folder in folders for name in (NOTES, KNOWLEDGE)]


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


def notes_files(vault: Path, project: Project | None) -> list[Path]:
    """Vault-relative paths of the existing notes files a run reads for its scopes."""
    scopes = [Path("general"), Path("private")]
    if project and project.name:
        scopes.insert(0, Path("projects") / project.name)
    return [scope / NOTES for scope in scopes if (vault / scope / NOTES).is_file()]
