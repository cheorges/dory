"""Story 10: `dory search` over summary, when, tags, file names and text."""

import os
import subprocess
from pathlib import Path

import pytest

from dory import search as search_module
from dory.config import Config
from dory.project import project_for_root
from dory.search import search
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]


def write(vault: Path, relative: str, meta: dict[str, str], body: str = "Text.") -> None:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", *(f"{key}: {value}" for key, value in meta.items()), "---", body]
    path.write_text("\n".join(lines) + "\n")


def knowledge(
    vault: Path, relative: str, summary: str, when: str, body: str = "Text.", **extra: str
) -> None:
    meta = {"type": "gotcha", "projects": "[]", "domain": "work", "summary": summary}
    write(vault, relative, {**meta, "when": when, "status": "active", **extra}, body)


@pytest.fixture
def world(tmp_path):
    vault = tmp_path / "vault"
    config = Config(vault=vault, state_dir=tmp_path / "state")
    hub = tmp_path / "code" / "ai-assistant-hub"
    hub.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=hub, check=True)
    project_for_root(hub.resolve(), StateDir(config.state_dir).projects_file)
    write(
        vault,
        "projects/ai-assistant-hub/ai-assistant-hub.md",
        {"type": "project", "domain": "work"},
    )
    knowledge(
        vault,
        "projects/ai-assistant-hub/ai-assistant-hub-loki-uid-10001.md",
        "Loki only starts if the volume is owned by UID 10001.",
        "When deploying Loki",
        projects='["[[ai-assistant-hub]]"]',
        tags="[loki, docker]",
    )
    knowledge(
        vault, "general/uv-instead-of-pip.md", "Use uv instead of pip.", "When setting up Python"
    )
    knowledge(
        vault,
        "general/grafana-dashboards.md",
        "Grafana dashboards live in the repo under dashboards/.",
        "When changing Grafana",
        body="The Loki data source is already configured there.",
    )
    knowledge(
        vault,
        "general/deploy-fridays.md",
        "No deploys on Fridays.",
        "When planning any release",
        domain="private",
    )
    write(vault, "notes/shopping-list.md", {"type": "list", "domain": "private"}, "- [ ] Loki mug")
    home = tmp_path / "home"
    home.mkdir()
    return config, hub.resolve(), home


def test_note_matching_when_comes_first_with_summary_and_path(world):
    config, hub, _ = world

    text = search(config, hub, "loki deploy")

    first = text.splitlines()[1]
    assert "Loki only starts if the volume is owned by UID 10001." in first
    assert "projects/ai-assistant-hub/ai-assistant-hub-loki-uid-10001.md" in first
    assert "When deploying Loki" in first
    assert "grafana-dashboards.md" in text  # body hit, ranked lower


def test_private_notes_never_show_in_a_work_project(world):
    config, hub, _ = world

    text = search(config, hub, "deploy loki mug fridays")

    assert "deploy-fridays" not in text
    assert "shopping-list" not in text


def test_outside_a_repo_private_notes_are_found(world):
    config, _, home = world

    text = search(config, home, "fridays")

    assert "general/deploy-fridays.md" in text


def test_no_hits_are_said_explicitly(world):
    config, hub, _ = world

    text = search(config, hub, "kubernetes helm")

    assert text.startswith('No hits for "kubernetes helm"')


def test_superseded_notes_are_not_offered(world):
    config, hub, _ = world
    knowledge(
        config.vault,
        "general/loki-alt.md",
        "Loki runs as root.",
        "When deploying Loki",
        status="superseded",
        superseded_by='"[[ai-assistant-hub-loki-uid-10001]]"',
    )

    assert "loki-alt" not in search(config, hub, "loki deploy")


def test_archived_notes_are_not_offered(world):
    config, hub, _ = world
    knowledge(
        config.vault,
        "projects/ai-assistant-hub/ai-assistant-hub-loki-volume.md",
        "Loki needs its volume owned by UID 10001.",
        "When deploying Loki",
        projects='["[[ai-assistant-hub]]"]',
        status="archived",
    )

    assert "loki-volume" not in search(config, hub, "loki deploy")


def test_cli_search_runs_in_the_current_directory(world):
    config, hub, _ = world
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}

    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "search", "loki", "deploy"],
        cwd=hub,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "ai-assistant-hub-loki-uid-10001.md" in result.stdout.splitlines()[1]


def test_a_note_removed_during_the_search_is_skipped(world, monkeypatch):
    config, hub, _ = world
    real_body = search_module.body

    def vanishing(path):
        if path.name == "uv-instead-of-pip.md":
            raise FileNotFoundError(path)
        return real_body(path)

    monkeypatch.setattr(search_module, "body", vanishing)

    assert "ai-assistant-hub-loki-uid-10001.md" in search(config, hub, "loki deploy")
