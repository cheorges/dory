"""Live checks of /dory:note and /dory:search against a real `claude -p` session (Stories 9, 10).

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

from dory.frontmatter import read_frontmatter
from dory.project import project_for_root
from dory.state import StateDir

pytestmark = pytest.mark.live

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
HUB = "ai-assistant-hub"


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
    write(
        vault / "projects" / HUB / f"{HUB}.md",
        "---\ntype: project\ndomain: work\nsummary: KoliChat-Plattform\n---\n"
        "## Open\n\n## Knowledge\n",
    )
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


def test_note_in_a_project_becomes_knowledge_of_that_project(world):
    vault, state, hub, _ = world

    output = note(vault, state, hub, "Loki port 3100 clashes with Grafana")

    notes = [
        path
        for path in (vault / "projects" / HUB).glob("*.md")
        if read_frontmatter(path).get("type") not in ("project", None)
    ]
    assert len(notes) == 1, output["result"]
    meta = read_frontmatter(notes[0])
    assert meta["projects"] == [f"[[{HUB}]]"]
    assert meta["domain"] == "work"
    assert meta["summary"] and meta["when"]
    assert meta.get("sources") == []
    assert "3100" in notes[0].read_text()


def test_note_at_home_extends_the_shopping_list(world):
    vault, state, _, home = world
    shopping = vault / "notes" / "shopping-list.md"
    write(shopping, "---\ntype: list\ndomain: private\nsummary: Shopping list\n---\n- [ ] Bread\n")

    output = note(vault, state, home, "buy milk")

    text = shopping.read_text()
    assert "milk" in text.lower() and "Bread" in text, output["result"]
    assert read_frontmatter(shopping)["type"] == "list"
    assert len(list(vault.rglob("*.md"))) == 2  # overview and the list, nothing new


def test_note_on_a_known_topic_extends_the_existing_note(world):
    vault, state, hub, _ = world
    existing = vault / "projects" / HUB / f"{HUB}-loki-port-3100.md"
    write(
        existing,
        f'---\ntype: fact\nprojects: ["[[{HUB}]]"]\ndomain: work\n'
        "summary: Loki listens on port 3100.\nwhen: When configuring Loki\n"
        "pinned: false\nstatus: active\nsuperseded_by:\ncreated: 2026-10-01\n"
        'updated: 2026-10-01\nsources: ["[[alt]]"]\n---\nLoki listens on port 3100.\n',
    )

    output = note(vault, state, hub, "Loki port 3100 clashes with Grafana")

    knowledge = [p for p in (vault / "projects" / HUB).glob("*.md") if p.name != f"{HUB}.md"]
    assert knowledge == [existing], output["result"]
    assert "Grafana" in existing.read_text()
    assert read_frontmatter(existing)["updated"] != "2026-10-01"


def test_note_in_a_repo_the_worker_never_saw_lands_in_that_project(world, tmp_path):
    vault, state, _, _ = world
    fresh = tmp_path / "code" / "teko"
    fresh.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=fresh, check=True)

    output = note(vault, state, fresh, "Teko backups run every night at 02:00 on the NAS")

    notes = [p for p in (vault / "projects" / "teko").glob("*.md") if p.name != "teko.md"]
    assert len(notes) == 1, output["result"]
    assert read_frontmatter(notes[0])["projects"] == ["[[teko]]"]
    assert (vault / "projects" / "teko" / "teko.md").is_file()


def test_search_finds_the_note_and_says_where(world):
    vault, state, hub, _ = world
    write(
        vault / "projects" / HUB / f"{HUB}-loki-uid-10001.md",
        f'---\ntype: gotcha\nprojects: ["[[{HUB}]]"]\ndomain: work\n'
        "summary: Loki only starts if the volume is owned by UID 10001.\n"
        "when: When deploying Loki\nstatus: active\n---\nchown -R 10001:10001\n",
    )

    output = run_skill(vault, state, hub, "/dory:search loki deploy")

    assert f"{HUB}-loki-uid-10001" in output["result"]


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
