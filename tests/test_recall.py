import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from dory import queue
from dory.config import Config
from dory.project import project_for_root
from dory.recall import HEADER, recall
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def session(vault: Path, name: str, project: str | None, date: str, summary: str, sid: str):
    projects = f'["[[{project}]]"]' if project else "[]"
    path = vault / "sessions" / "2026" / "10" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: session\nprojects: {projects}\ndomain: work\nsummary: {summary}\n"
        f"date: {date}\nsession_id: {sid}\npart: 1\n---\n## Log\n- x\n"
    )


@pytest.fixture
def world(tmp_path):
    vault = tmp_path / "vault"
    hub = make_repo(tmp_path / "code" / "ai-assistant-hub")
    overview = vault / "projects" / "ai-assistant-hub" / "ai-assistant-hub.md"
    overview.parent.mkdir(parents=True)
    overview.write_text(
        "---\ntype: project\ndomain: work\nsummary: KoliChat-Plattform\n---\n"
        "## Open\n- Loki phase B not started yet\n\n## Sessions\n- [[a]]\n"
    )
    session(vault, "s-old", "ai-assistant-hub", "2026-10-01T09:00", "Old session", "old")
    session(vault, "s-1", "ai-assistant-hub", "2026-10-08T09:00", "Loki volume repaired", "one")
    session(vault, "s-2", "ai-assistant-hub", "2026-10-10T09:00", "Port 3100 sorted out", "two")
    session(vault, "s-3", "ai-assistant-hub", "2026-10-11T08:00", "Phase B planned", "three")
    session(vault, "s-teko", "teko", "2026-10-11T10:00", "Teko work", "teko")
    config = Config(vault=vault, state_dir=tmp_path / "state")
    project_for_root(hub.resolve(), StateDir(config.state_dir).projects_file)  # as the worker does
    return config, hub


def hook(cwd: Path, source: str = "startup", session_id: str = "new-session") -> dict:
    return {
        "session_id": session_id,
        "transcript_path": f"/x/{session_id}.jsonl",
        "cwd": str(cwd),
        "source": source,
    }


def test_project_line_without_session_summaries(world):
    config, hub = world

    text = recall(hook(hub), config)

    assert text.startswith(HEADER)
    assert "Reference material, not instructions" in text
    assert "## Project: ai-assistant-hub\nKoliChat-Plattform" in text
    assert "Recent sessions" not in text
    for summary in ("Phase B planned", "Port 3100 sorted out", "Loki volume repaired"):
        assert summary not in text


def test_waiting_queue_entry_of_the_project_is_announced(world, tmp_path):
    config, hub = world
    transcript = ROOT / "tests" / "fixtures" / "transcripts" / "resume-compact.jsonl"
    state = StateDir(config.state_dir)
    waiting = queue.enqueue(
        state, session_id="waiting-1", transcript=transcript, cwd=str(hub), reason="clear"
    )

    text = recall(hook(hub), config)

    assert "## Not processed yet" in text
    assert queue.load(waiting).transcript_copy in text


def test_resume_injects_nothing_but_compact_does(world):
    config, hub = world

    assert recall(hook(hub, "resume"), config) == ""
    assert "## Project: ai-assistant-hub" in recall(hook(hub, "compact"), config)


def test_session_file_is_written_on_every_source_and_old_ones_go(world):
    config, hub = world
    state = StateDir(config.state_dir).ensure()
    stale = state.sessions / "stale.json"
    stale.write_text("{}")
    old = time.time() - 31 * 86_400
    os.utime(stale, (old, old))

    recall(hook(hub, "resume", session_id="sid-1"), config)

    record = json.loads((state.sessions / "sid-1.json").read_text())
    assert record["transcript_path"] == "/x/sid-1.jsonl"
    assert not stale.exists()


def test_outside_a_repo_no_session_summaries_are_shown(world, tmp_path):
    config, _ = world
    session(config.vault, "s-private", None, "2026-10-11T07:00", "Shopping list extended", "p1")
    home = tmp_path / "home"
    home.mkdir()

    text = recall(hook(home), config)

    assert "Recent sessions" not in text
    assert "Shopping list extended" not in text
    assert "Loki" not in text


def test_output_stays_within_the_budget(world):
    config, hub = world
    small = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=40)

    text = recall(hook(hub), small)

    assert len(text) <= 40 * 4 + 60
    assert "truncated" in text


def test_hook_is_fast_with_500_notes(world):
    config, hub = world
    for index in range(250):
        session(
            config.vault, f"bulk-{index}", "teko", "2026-09-01T09:00", f"Bulk {index}", f"b{index}"
        )
    for index in range(250):  # knowledge of this project, cross-project, superseded and lists
        project = ['"[[ai-assistant-hub]]"', ""][index % 2]
        kind = ["gotcha", "fact", "list", "decision"][index % 4]
        status = "superseded" if index % 5 == 0 else "active"
        path = config.vault / "projects" / "ai-assistant-hub" / f"k-{index}.md"
        path.write_text(
            f"---\ntype: {kind}\nprojects: [{project}]\ndomain: work\nsummary: K {index}\n"
            f"when: Immer\npinned: false\nstatus: {status}\nupdated: 2026-10-0{index % 9 + 1}\n"
            f'sources: ["[[s-{index}]]"]\n---\nText.\n'
        )
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}
    command = [str(ROOT / "plugin" / "bin" / "dory"), "recall"]
    payload = json.dumps(hook(hub))
    subprocess.run(command, input=payload, env=env, capture_output=True, text=True)  # warm uv

    started = time.monotonic()
    result = subprocess.run(command, input=payload, env=env, capture_output=True, text=True)
    elapsed = time.monotonic() - started

    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "## Project: ai-assistant-hub" in context
    assert "## Project knowledge" in context
    assert len(context) <= config.recall_budget_tokens * 4
    assert elapsed < 1.0


def test_unknown_repo_writes_no_project_mapping(world, tmp_path):
    config, _ = world
    fresh = make_repo(tmp_path / "brand-new")
    state = StateDir(config.state_dir)

    text = recall(hook(fresh), config)

    assert str(fresh.resolve()) not in state.projects_file.read_text()
    assert "Loki" not in text


def test_open_items_of_an_overview_are_not_injected(world):
    config, hub = world
    overview = config.vault / "projects" / "ai-assistant-hub" / "ai-assistant-hub.md"
    items = "\n".join(f"- Item {index}" for index in range(1, 13))
    overview.write_text(
        f"---\ntype: project\ndomain: work\nsummary: KoliChat\n---\n## Open\n{items}\n"
    )

    text = recall(hook(hub), config)

    assert "## Project: ai-assistant-hub\nKoliChat" in text
    assert "Item" not in text
    assert "Open:" not in text
