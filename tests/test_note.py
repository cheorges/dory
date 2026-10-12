"""Story 9: what `dory prepare-note` gives the /dory:note skill before it writes."""

import os
import subprocess
from pathlib import Path

from dory.config import Config
from dory.note import prepare_note
from dory.project import project_for_root
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path.resolve()


def world(tmp_path: Path) -> tuple[Config, Path]:
    vault = tmp_path / "vault"
    overview = vault / "projects" / "ai-assistant-hub" / "ai-assistant-hub.md"
    overview.parent.mkdir(parents=True)
    overview.write_text("---\ntype: project\ndomain: work\nsummary: KoliChat\n---\n")
    config = Config(vault=vault, state_dir=tmp_path / "state")
    hub = make_repo(tmp_path / "code" / "ai-assistant-hub")
    project_for_root(hub, StateDir(config.state_dir).projects_file)
    return config, hub


def test_snapshot_exists_before_anything_is_written(tmp_path):
    config, hub = world(tmp_path)

    text = prepare_note(config, hub)

    snapshots = list((config.state_dir / "snapshots").iterdir())
    assert len(snapshots) == 1
    assert (snapshots[0] / "projects" / "ai-assistant-hub" / "ai-assistant-hub.md").is_file()
    assert f"Snapshot: {snapshots[0]}" in text


def test_context_names_vault_project_domain_date_and_rules(tmp_path):
    config, hub = world(tmp_path)

    (hub / "src").mkdir()

    text = prepare_note(config, hub / "src")  # a subdirectory still belongs to the repo

    assert f"Vault: {config.vault}" in text
    assert "Project: ai-assistant-hub" in text
    assert "Domain: work" in text
    assert "projects/ai-assistant-hub/ai-assistant-hub.md" in text
    assert "Today: " in text
    assert "Language: English" in text
    assert "# Writing rules for the dory-brain vault" in text  # the rules, verbatim


def test_outside_a_repo_there_is_no_project(tmp_path):
    config, _ = world(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    text = prepare_note(config, home)

    assert "Project: none" in text
    assert "Known projects: ai-assistant-hub" in text


def test_cli_prepare_note_uses_the_current_directory(tmp_path):
    config, hub = world(tmp_path)
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}

    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "prepare-note"],
        cwd=hub,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Project: ai-assistant-hub" in result.stdout


def test_a_repo_without_vault_folder_is_known_and_its_overview_marked_missing(tmp_path):
    config, _ = world(tmp_path)
    fresh = make_repo(tmp_path / "code" / "teko")

    text = prepare_note(config, fresh)

    assert "Project: teko" in text
    assert "Known projects: ai-assistant-hub, teko" in text
    assert "projects/teko/teko.md (missing, create it according to the rules)" in text
