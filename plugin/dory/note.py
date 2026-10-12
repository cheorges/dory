"""Context for /dory:note: snapshot the vault, then tell the skill where and how to write.

The note is written inline by the session itself (record 001, decision 4). This only does
what must happen before: the snapshot, the project of the working directory and the rules.
"""

from datetime import date
from pathlib import Path

from dory.config import Config
from dory.frontmatter import read_frontmatter
from dory.project import detect_project
from dory.state import StateDir
from dory.vault import rules_text, snapshot


def prepare_note(config: Config, cwd: Path) -> str:
    state = StateDir(config.state_dir).ensure()
    taken = snapshot(config, state)
    # A new repo becomes a project here, as in the worker, and counts as known right away.
    project = detect_project(cwd, state.projects_file)
    folders = {p.name for p in (config.vault / "projects").glob("*") if p.is_dir()}
    known = sorted(folders | ({project.name} if project else set()))
    lines = [
        f"Vault: {config.vault}",
        f"Snapshot: {taken}",
        f"Today: {date.today():%Y-%m-%d}",
        f"Language: {config.language}",
    ]
    if project:
        overview = Path("projects") / project.name / f"{project.name}.md"
        domain = read_frontmatter(config.vault / overview).get("domain") or "work"
        missing = (
            ""
            if (config.vault / overview).is_file()
            else " (missing, create it according to the rules)"
        )
        lines += [
            f"Project: {project.name} (repo {project.root})",
            f"Domain: {domain}",
            f"Project overview: {overview}{missing}",
        ]
    else:
        lines.append("Project: none (outside a git repository)")
    lines += [f"Known projects: {', '.join(known) or '(none)'}", "", rules_text().strip()]
    return "\n".join(lines)
