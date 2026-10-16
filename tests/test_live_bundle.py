"""Live checks of what the confined worker run can do with the repository documents.

They count against the usage limit and depend on the model, so they are skipped by default:
    DORY_LIVE=1 uv run pytest -m live tests/test_live_bundle.py   # DORY_LIVE_MODEL, default haiku
"""

import json
import os
import subprocess

import pytest

from dory.config import Config
from dory.ingest import _worker_env, build_command

pytestmark = pytest.mark.live

PHRASE = "the ferry to Vitznau leaves at 07:42"


@pytest.fixture
def bundle(tmp_path):
    if os.environ.get("DORY_LIVE") != "1":
        pytest.skip("live test: set DORY_LIVE=1")
    directory = tmp_path / "work" / "entry"
    records = directory / "repo" / "records"
    records.mkdir(parents=True)
    for index in range(12):
        (records / f"0{index:02d}-decoy.md").write_text(f"# Decoy {index}\n\nNothing here.\n")
    (records / "013-timetable.md").write_text(f"# Timetable\n\nNote: {PHRASE}.\n")
    vault = tmp_path / "vault"
    vault.mkdir()
    return directory, vault


def test_confined_run_can_search_the_bundle_directory_with_grep(bundle):
    directory, vault = bundle
    config = Config(vault=vault, state_dir=directory.parent, model=_model())
    command = build_command(config, directory)
    command[2] = (
        f"Use the Grep tool, and only Grep, to search {directory}/repo/records for the word "
        "Vitznau. Reply with the matching line exactly as Grep returned it."
    )
    command[command.index("json")] = "stream-json"
    command.append("--verbose")

    result = subprocess.run(
        command, cwd=vault, env=_worker_env(), capture_output=True, text=True, timeout=300
    )

    events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    grep_results = [
        block
        for event in events
        if event.get("type") == "user"
        for block in event["message"]["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]
    grep_calls = [
        block
        for event in events
        if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if isinstance(block, dict) and block.get("type") == "tool_use"
    ]
    assert any(call["name"] == "Grep" for call in grep_calls), result.stdout[-2000:]
    assert not any(block.get("is_error") for block in grep_results), grep_results
    assert "013-timetable.md" in json.dumps(grep_results) or PHRASE in json.dumps(grep_results)
    assert "Vitznau" in events[-1].get("result", ""), events[-1]


def _model() -> str:
    return os.environ.get("DORY_LIVE_MODEL", "haiku")
