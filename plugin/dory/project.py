"""Map a working directory to a project: one project per git repository.

Worktrees belong to their main repository. The name is assigned once and stored in
projects.json, so a later repo with the same directory name never renames an existing
project.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    name: str
    root: Path


def repo_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return None
    common_dir = Path(result.stdout.strip())
    if common_dir.name == ".git":
        return common_dir.parent.resolve()
    # Submodule (common dir under .git/modules/) or bare repository (no working tree).
    toplevel = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return Path(toplevel.stdout.strip()).resolve() if toplevel.returncode == 0 else None


def detect_project(cwd: Path, projects_file: Path) -> Project | None:
    root = repo_root(cwd)
    return project_for_root(root, projects_file) if root else None


def lookup_project(cwd: Path, projects_file: Path) -> Project | None:
    """Read-only variant for hooks: an unknown repo gets an empty name, nothing is written."""
    root = repo_root(cwd)
    if root is None:
        return None
    return Project(name=_load(projects_file).get(str(root), ""), root=root)


def project_for_root(root: Path, projects_file: Path) -> Project:
    projects = _load(projects_file)
    name = projects.get(str(root))
    if name is None:
        name = _new_name(root, set(projects.values()))
        projects[str(root)] = name
        projects_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = projects_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(projects, indent=2, sort_keys=True))
        tmp.replace(projects_file)
    return Project(name=name, root=root)


def _load(projects_file: Path) -> dict[str, str]:
    if not projects_file.is_file():
        return {}
    return json.loads(projects_file.read_text())


def _new_name(root: Path, taken: set[str]) -> str:
    name = root.name
    if name not in taken:
        return name
    prefixed = f"{root.parent.name}-{root.name}"
    candidate, counter = prefixed, 2
    while candidate in taken:
        candidate = f"{prefixed}-{counter}"
        counter += 1
    return candidate
