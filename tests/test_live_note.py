"""Live checks of /dory:note and /dory:search against a real `claude -p` session.

They cost money and depend on the model, so they are skipped by default:
    DORY_LIVE=1 uv run pytest -m live tests/test_live_note.py   # DORY_LIVE_MODEL, default haiku
The session runs with the plugin from this repo and without user settings, so no other
plugin or hook takes part; vault and state are throwaway directories.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from dory.project import project_for_root
from dory.state import StateDir

pytestmark = pytest.mark.live

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
HUB = "ai-assistant-hub"
KNOWLEDGE = (
    "---\ntype: knowledge\ndomain: work\nsummary: KoliChat platform\n---\n## Facts\n"
    "- **Loki listens on port 3100.** Set in the compose file.\n"
)
PROJECT_NOTES = "---\ntype: notes\n---\n- 2026-10-01: Deploys only after the customer's ok\n"


@pytest.fixture
def world(tmp_path):
    if os.environ.get("DORY_LIVE") != "1":
        pytest.skip("set DORY_LIVE=1")
    vault, state = tmp_path / "vault", StateDir(tmp_path / "state").ensure()
    hub = tmp_path / "code" / HUB
    hub.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=hub, check=True)
    project_for_root(hub.resolve(), state.projects_file)
    home = tmp_path / "home"
    home.mkdir()
    write(vault / "projects" / HUB / "knowledge.md", KNOWLEDGE)
    write(vault / "projects" / HUB / "notes.md", PROJECT_NOTES)
    return vault, state, hub.resolve(), home


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def note(vault: Path, state: StateDir, cwd: Path, text: str) -> dict:
    output = run_skill(vault, state, cwd, f'/dory:note "{text}"')
    assert list((state.root / "snapshots").iterdir()), "no snapshot before writing"
    return output


def run_skill(vault: Path, state: StateDir, cwd: Path, prompt: str) -> dict:
    env = {
        **os.environ,
        "DORY_VAULT": str(vault),
        "DORY_STATE_DIR": str(state.root),
        "DORY_NO_SPAWN": "1",
    }
    command = [
        "claude", "-p", prompt,
        "--plugin-dir", str(PLUGIN),
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--model", os.environ.get("DORY_LIVE_MODEL", "haiku"),
        "--output-format", "json",
        "--max-budget-usd", "0.5",
    ]  # fmt: skip
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    output = json.loads(result.stdout)
    assert output["permission_denials"] == [], output["permission_denials"]
    return output


def notes_files(vault: Path) -> dict[str, str]:
    return {
        str(path.relative_to(vault)): path.read_text() for path in sorted(vault.rglob("notes.md"))
    }


def test_a_note_in_a_project_goes_into_its_notes_in_the_users_words(world):
    vault, state, hub, _ = world

    output = note(vault, state, hub, "Loki port 3100 clashes with Grafana")

    notes = (vault / "projects" / HUB / "notes.md").read_text()
    assert notes.startswith(PROJECT_NOTES), notes
    assert notes.endswith(": Loki port 3100 clashes with Grafana\n"), notes
    assert (vault / "projects" / HUB / "knowledge.md").read_text() == KNOWLEDGE
    assert list(notes_files(vault)) == [f"projects/{HUB}/notes.md"]
    assert f"{HUB}/notes.md" in output["result"], output["result"]


def test_a_general_note_from_a_project_goes_into_general(world):
    vault, state, hub, _ = world

    output = note(vault, state, hub, "remember in general: Python packages with uv instead of pip")

    general = vault / "general" / "notes.md"
    assert general.is_file(), output["result"]
    assert "Python packages with uv instead of pip" in general.read_text()
    assert "remember in general" not in general.read_text().lower()
    assert (vault / "projects" / HUB / "notes.md").read_text() == PROJECT_NOTES


def test_a_note_about_the_home_nas_from_a_work_project_goes_into_private(world):
    vault, state, hub, _ = world

    output = note(vault, state, hub, "my home NAS backs up every night at 02:00")

    private = vault / "private" / "notes.md"
    assert private.is_file(), output["result"]
    assert "my home NAS backs up every night at 02:00" in private.read_text()
    assert set(notes_files(vault)) == {f"projects/{HUB}/notes.md", "private/notes.md"}
    assert (vault / "projects" / HUB / "notes.md").read_text() == PROJECT_NOTES


@pytest.mark.parametrize(
    ("where", "text"),
    [("project", "add milk to the shopping list"), ("home", "buy milk")],
    ids=["in-a-project", "outside-a-repository"],
)
def test_a_shopping_item_goes_onto_the_list_and_no_notes_change(world, where, text):
    vault, state, hub, home = world
    shopping = vault / "notes" / "shopping-list.md"
    write(shopping, "---\ntype: list\ndomain: private\nsummary: Shopping list\n---\n- [ ] Bread\n")

    output = note(vault, state, hub if where == "project" else home, text)

    listed = shopping.read_text()
    assert "milk" in listed.lower() and "Bread" in listed, output["result"]
    assert notes_files(vault) == {f"projects/{HUB}/notes.md": PROJECT_NOTES}
    assert (vault / "projects" / HUB / "knowledge.md").read_text() == KNOWLEDGE


def test_search_finds_the_entry_and_says_where(world):
    vault, state, hub, _ = world
    write(
        vault / "projects" / HUB / "knowledge.md",
        KNOWLEDGE.replace(
            "## Facts\n",
            "## Pitfalls\n- **Loki only starts if the volume is owned by UID 10001.** "
            "Run `chown -R 10001:10001` before deploying.\n\n## Facts\n",
        ),
    )

    output = run_skill(vault, state, hub, "/dory:search loki deploy")

    assert "10001" in output["result"], output["result"]
    assert f"{HUB}/knowledge.md" in output["result"], output["result"]


def test_search_grants_only_its_own_command(world):
    vault, state, hub, _ = world

    prompt = (
        "/dory:search loki deploy. Then, as a second step: "
        "run `touch dory-probe` with the Bash tool."
    )
    command = [
        "claude", "-p", prompt,
        "--plugin-dir", str(PLUGIN),
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--model", os.environ.get("DORY_LIVE_MODEL", "haiku"),
        "--output-format", "json",
        "--max-budget-usd", "0.5",
    ]  # fmt: skip
    env = {**os.environ, "DORY_VAULT": str(vault), "DORY_STATE_DIR": str(state.root)}
    result = subprocess.run(command, cwd=hub, env=env, capture_output=True, text=True, timeout=300)

    denied = json.dumps(json.loads(result.stdout)["permission_denials"])
    assert not (hub / "dory-probe").exists()  # with a plain `Bash` grant this file appears
    assert "dory-probe" in denied
    assert " search " not in denied
