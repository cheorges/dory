import subprocess
from pathlib import Path

from dory.project import detect_project


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git("init", "-q", cwd=path)
    git(
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "i",
        cwd=path,
    )
    return path


def test_worktree_and_main_repo_are_the_same_project(tmp_path):
    repo = make_repo(tmp_path / "code" / "ai-assistant-hub")
    worktree = tmp_path / "worktrees" / "feature-x"
    git("worktree", "add", "-q", str(worktree), cwd=repo)
    projects = tmp_path / "state" / "projects.json"

    from_repo = detect_project(repo / ".", projects)
    from_worktree = detect_project(worktree, projects)

    assert from_repo.name == "ai-assistant-hub"
    assert from_worktree == from_repo


def test_subdirectory_resolves_to_its_repo(tmp_path):
    repo = make_repo(tmp_path / "ai-assistant-hub-infrastructure")
    (repo / "src").mkdir()

    project = detect_project(repo / "src", tmp_path / "projects.json")

    assert project.name == "ai-assistant-hub-infrastructure"


def test_directory_outside_a_repo_has_no_project(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    assert detect_project(downloads, tmp_path / "projects.json") is None


def test_same_repo_name_elsewhere_gets_a_prefix_and_the_first_keeps_its_name(tmp_path):
    projects = tmp_path / "projects.json"
    first = make_repo(tmp_path / "kolibee" / "website")
    second = make_repo(tmp_path / "cheorges" / "website")

    assert detect_project(first, projects).name == "website"
    assert detect_project(second, projects).name == "cheorges-website"
    assert detect_project(first, projects).name == "website"


def test_submodule_is_its_own_project(tmp_path):
    library = make_repo(tmp_path / "lib")
    parent = make_repo(tmp_path / "app")
    git(
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(library),
        "vendor/lib",
        cwd=parent,
    )

    project = detect_project(parent / "vendor" / "lib", tmp_path / "projects.json")

    assert project is not None
    assert project.root == (parent / "vendor" / "lib").resolve()
