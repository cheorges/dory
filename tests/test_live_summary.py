"""Live checks of the summary run (Record 003, Story S4).

They count against the usage limit and depend on the model, so they are skipped by default:
    DORY_LIVE=1 uv run pytest -m live tests/test_live_summary.py   # DORY_LIVE_MODEL, default haiku
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from dory import summary
from dory.config import Config
from dory.ingest import _worker_env
from dory.state import StateDir
from dory.summarize import SETTINGS, build_command, make_summarize, stdin_text

pytestmark = pytest.mark.live

TEXT = """## projects/hub/notes.md
- 2026-10-19: Loki port 3100 clashes with Grafana

## projects/hub/knowledge.md
### Pitfalls
- **Loki only starts if UID 10001 owns the data directory.** The container exits at start on a
  root-owned directory. Run `chown -R 10001` on it before deploying.
"""


@pytest.fixture
def world(tmp_path):
    if os.environ.get("DORY_LIVE") != "1":
        pytest.skip("live test: set DORY_LIVE=1")
    state = tmp_path / "state"
    state.mkdir()
    cwd = tmp_path / "run"
    cwd.mkdir()
    config = Config(vault=tmp_path / "vault", state_dir=state, model=_model())
    return config, cwd


def _model() -> str:
    return os.environ.get("DORY_LIVE_MODEL", "haiku")


def _run(command: list[str], cwd: Path, env: dict[str, str]) -> dict:
    result = subprocess.run(
        command,
        input=stdin_text(TEXT),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return json.loads(result.stdout)


def _dory_files(state: Path) -> list[Path]:
    return [*state.glob("sessions/*.json"), *state.glob("queue/*.json")]


def test_summary_command_returns_the_summary_and_leaves_no_trace_of_dory(world):
    config, cwd = world
    # Without the worker's marker, so only the disabled hooks keep dory's hooks quiet.
    env = {**_worker_env(), "DORY_STATE_DIR": str(config.state_dir)}
    env.pop("DORY_WORKER")

    data = _run(build_command(config, target=600), cwd, env)

    assert not data.get("is_error"), data
    assert "10001" in data["result"], data["result"]
    assert len(data["result"]) <= 900, data["result"]
    assert not data["result"].lstrip().startswith("```"), data["result"]
    assert data.get("num_turns", 1) == 1, data
    assert _dory_files(config.state_dir) == []


def test_control_without_disabled_hooks_the_session_start_hook_writes_its_file(world):
    """Positive control: the observation above can see a hook of the installed dory plugin."""
    config, cwd = world
    env = {**_worker_env(), "DORY_STATE_DIR": str(config.state_dir)}
    env.pop("DORY_WORKER")
    command = build_command(config, target=600)
    del command[command.index("--settings") : command.index("--settings") + 2]
    del command[command.index("--restricted")]
    assert SETTINGS not in command

    _run(command, cwd, env)

    assert list(config.state_dir.glob("sessions/*.json"))


def test_a_full_project_is_summarized_within_the_target_in_the_note_language(tmp_path):
    if os.environ.get("DORY_LIVE") != "1":
        pytest.skip("live test: set DORY_LIVE=1")
    from test_live_rules import german_words, realistic_knowledge

    config = Config(
        vault=tmp_path / "vault", state_dir=tmp_path / "state", model=_model(), language="German"
    )
    state = StateDir(config.state_dir).ensure()
    body, _ = realistic_knowledge()
    project = config.vault / "projects" / "hub"
    project.mkdir(parents=True)
    (project / "knowledge.md").write_text(f"---\ntype: knowledge\ndomain: work\n---\n{body}")
    notes = "---\ntype: notes\n---\n- 2026-10-19: Ask before Friday deploys\n"
    (project / "notes.md").write_text(notes)

    assert make_summarize(config, state)({"project-hub"}) is False

    saved = summary.load(state, "project-hub")
    [line] = [json.loads(row) for row in (state.root / "runs.log").read_text().splitlines()]
    assert saved is not None, line
    assert len(saved.text) <= summary.target_chars(config)
    assert german_words(saved.text) >= 2, saved.text
    assert "### Pitfalls" in saved.text, saved.text
    assert "10001" in saved.text or "chown" in saved.text, saved.text
    assert line["outcome"] == "done"
    assert line["cost_usd"] > 0
    print(f"\n{line['cost_usd']} USD, {line['seconds']} s, {len(saved.text)} characters")
