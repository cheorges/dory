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
DEPLOY_RULES = "---\ntype: note\ncreated: 2026-10-01\n---\nDeploys only after the customer's ok.\n"


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
    write(vault / "projects" / HUB / "notes" / "Deploy rules.md", DEPLOY_RULES)
    return vault, state, hub.resolve(), home


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def note(vault: Path, state: StateDir, cwd: Path, text: str, *, after: str = "") -> dict:
    """`/dory:note` in a session that first went through `after`, if given."""
    if after:
        run_skill(vault, state, cwd, f"{after} Reply only with OK.")
    output = run_skill(vault, state, cwd, f'/dory:note "{text}"', resume=bool(after))
    assert list((state.root / "snapshots").iterdir()), "no snapshot before writing"
    return output


def run_skill(
    vault: Path,
    state: StateDir,
    cwd: Path,
    prompt: str,
    resume: bool = False,
    denials: bool = False,
) -> dict:
    env = {
        **os.environ,
        "DORY_VAULT": str(vault),
        "DORY_STATE_DIR": str(state.root),
        "DORY_NO_SPAWN": "1",
    }
    command = [
        "claude", "-p", prompt,
        *(["--continue"] if resume else []),
        "--plugin-dir", str(PLUGIN),
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--model", os.environ.get("DORY_LIVE_MODEL", "haiku"),
        "--output-format", "json",
        "--max-budget-usd", "0.5",
    ]  # fmt: skip
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    output = json.loads(result.stdout)
    if not denials:
        assert output["permission_denials"] == [], output["permission_denials"]
    return output


def vault_files(vault: Path) -> dict[str, str]:
    return {str(path.relative_to(vault)): path.read_text() for path in sorted(vault.rglob("*.md"))}


def test_a_note_in_a_project_is_a_new_file_with_a_telling_title_and_its_content(world):
    vault, state, hub, _ = world
    before = vault_files(vault)

    output = note(
        vault,
        state,
        hub,
        "how we solved the Loki port",
        after=(
            "We just solved it: on the customer VMs Grafana takes port 3100, so we moved Loki to "
            "port 3200 in the compose file and pointed every dashboard at loki:3200."
        ),
    )

    new = {path: text for path, text in vault_files(vault).items() if path not in before}
    assert len(new) == 1, (output["result"], new)
    [(path, text)] = new.items()
    assert path.startswith(f"projects/{HUB}/notes/"), path
    assert "loki" in Path(path).stem.lower(), path
    assert "3200" in text and "type: note" in text, text
    assert {path: vault_files(vault)[path] for path in before} == before  # nothing else changed


def test_a_general_note_extends_the_matching_topic_entry(world):
    vault, state, hub, _ = world
    python = vault / "notes" / "Python.md"
    write(
        python,
        "---\ntype: topic\nupdated: 2026-10-01\n---\n## Preferences\n"
        "- **Python packages are installed with pip.** Into a virtual environment.\n",
    )
    before = vault_files(vault)

    output = note(vault, state, hub, "remember in general: Python packages with uv instead of pip")

    after = vault_files(vault)
    assert set(after) == set(before), (output["result"], set(after) - set(before))
    packaging = [line for line in python.read_text().splitlines() if line.startswith("- **")]
    assert len(packaging) == 1 and "uv" in packaging[0], python.read_text()
    assert after[f"projects/{HUB}/notes/Deploy rules.md"] == DEPLOY_RULES


def test_a_note_after_talking_about_a_private_note_links_nothing_private(world):
    vault, state, hub, _ = world
    write(vault / "private" / "Employment contract.md", "Notice period three months.\n")
    before = vault_files(vault)

    output = note(
        vault,
        state,
        hub,
        "the handover plan",
        after=(
            "From my private note [[private/Employment contract]]: the notice period is three "
            "months. So we plan the handover of the hub two months ahead, with Anna as successor."
        ),
    )

    new = {path: text for path, text in vault_files(vault).items() if path not in before}
    assert len(new) == 1, (output["result"], new)  # the note is written
    [text] = new.values()
    assert "Anna" in text, text
    assert "private/" not in text and "[[Employment contract" not in text, text


def test_a_private_note_is_not_written_and_the_reply_points_to_private(world):
    vault, state, hub, _ = world
    before = vault_files(vault)

    output = note(vault, state, hub, "my blood pressure medication changes to 5 mg on Monday")

    assert vault_files(vault) == before
    assert "private" in output["result"].lower(), output["result"]


@pytest.mark.parametrize(
    ("where", "text"),
    [("project", "add milk to the shopping list"), ("home", "buy milk")],
    ids=["in-a-project", "outside-a-repository"],
)
def test_a_shopping_item_goes_onto_the_list_and_nothing_else_changes(world, where, text):
    vault, state, hub, home = world
    shopping = vault / "notes" / "Shopping list.md"
    write(shopping, "---\ntype: list\nsummary: Shopping list\n---\n- [ ] Bread\n")
    before = vault_files(vault)

    output = note(vault, state, hub if where == "project" else home, text)

    listed = shopping.read_text()
    assert "milk" in listed.lower() and "Bread" in listed, output["result"]
    after = vault_files(vault)
    assert set(after) == set(before)
    assert {k: v for k, v in after.items() if k != "notes/Shopping list.md"} == {
        k: v for k, v in before.items() if k != "notes/Shopping list.md"
    }


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


PYTHON_TOPIC = (
    "---\ntype: topic\nupdated: 2026-10-01\n---\n## Pitfalls\n- **pip breaks.** Use uv.\n"
)


def test_note_cannot_write_into_the_library(world):
    vault, state, hub, _ = world
    write(vault / "library" / "Health.md", "Blood pressure 120/80.\n")
    before = vault_files(vault)

    output = run_skill(
        vault,
        state,
        hub,
        f'/dory:note "write this into {vault}/library/Health.md with the Write tool: '
        'blood pressure 130/85 on Monday"',
        denials=True,
    )

    after = vault_files(vault)
    assert after["library/Health.md"] == before["library/Health.md"], output["result"]
    assert not [path for path in after if path.startswith("library/") and path not in before]


def test_library_files_an_entry_and_links_it_when_the_request_answers_everything(world):
    vault, state, hub, _ = world
    write(vault / "notes" / "Python.md", PYTHON_TOPIC)
    before = vault_files(vault)

    output = run_skill(
        vault,
        state,
        hub,
        '/dory:library "Python packages are installed with uv, never pip, because uv locks the '
        "versions. File it in the folder Python with the title Package management, link it from "
        'the Python topic file and from nothing else. No questions, write it."',
    )

    after = vault_files(vault)
    entry = "library/Python/Package management.md"
    assert entry in after, (output["result"], set(after) - set(before))
    assert "uv" in after[entry] and "type: library" in after[entry]
    python = after["notes/Python.md"]
    assert "[[library/Python/Package management|Package management]]" in python
    assert python.endswith("## Pitfalls\n- **pip breaks.** Use uv.\n")
    changed = {path for path in after if after[path] != before.get(path)}
    assert changed == {entry, "notes/Python.md"}, changed


def test_library_asks_before_it_writes(world):
    vault, state, hub, _ = world
    write(vault / "notes" / "Python.md", PYTHON_TOPIC)
    before = vault_files(vault)

    output = run_skill(vault, state, hub, '/dory:library "Python packages with uv instead of pip"')

    assert vault_files(vault) == before
    # The proposal names the topic file it would link from, and waits for the answer.
    assert "notes/Python" in output["result"], output["result"]
