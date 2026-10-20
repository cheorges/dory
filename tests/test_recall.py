"""Record 003, Story S3: the session start loads the knowledge and notes files of its context."""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from dory import queue
from dory.config import Config
from dory.project import project_for_root
from dory.recall import CUT_MARKER, HEADER, recall
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "tests" / "fixtures" / "transcripts" / "resume-compact.jsonl"
HUB = "projects/ai-assistant-hub"


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def write(vault: Path, relative: str, text: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def knowledge(vault: Path, folder: str, sections: str, domain: str = "work", summary: str = ""):
    line = f"summary: {summary}\n" if summary else ""
    head = f"---\ntype: knowledge\ndomain: {domain}\n{line}paths: []\nupdated: 2026-10-19\n---\n"
    return write(vault, f"{folder}/knowledge.md", head + sections)


def notes(vault: Path, folder: str, *lines: str) -> Path:
    bullets = "".join(f"- 2026-10-19: {line}\n" for line in lines)
    return write(vault, f"{folder}/notes.md", f"---\ntype: notes\n---\n{bullets}")


def catalog(vault: Path, name: str, kind: str, domain: str | None) -> None:
    line = f"domain: {domain}\n" if domain else ""
    write(vault, f"notes/{name}.md", f"---\ntype: {kind}\n{line}summary: {name}\n---\n- item\n")


@pytest.fixture
def world(tmp_path):
    vault = tmp_path / "vault"
    config = Config(vault=vault, state_dir=tmp_path / "state")
    projects_file = StateDir(config.state_dir).projects_file
    repos = {}
    for name in ("ai-assistant-hub", "haushalt"):
        repos[name] = make_repo(tmp_path / "code" / name)
        project_for_root(repos[name].resolve(), projects_file)  # as the worker does
    repos["unknown"] = make_repo(tmp_path / "code" / "unknown")
    repos["home"] = tmp_path / "home"
    repos["home"].mkdir()
    return config, repos


def full_world(vault: Path) -> None:
    """Every scope with both files, and a private project."""
    knowledge(
        vault,
        HUB,
        "## Pitfalls\n- **Loki only starts if UID 10001 owns the data directory.** Run chown.\n\n"
        "## Facts\n- **The customer VMs reach the internet only through port 3128.** Proxy.\n",
        summary="KoliChat platform for customers",
    )
    notes(vault, HUB, "Loki port 3100 clashes with Grafana")
    knowledge(
        vault,
        "general",
        "## How-to\n- **uv runs PEP 723 scripts without a venv.** Example:\n"
        "  ```bash\n# no install step\nuv run script.py\n  ```\n",
    )
    notes(vault, "general", "Prefer uv over pip")
    knowledge(vault, "private", "## Facts\n- **The NAS backs up at 02:00.** Synology.\n")
    notes(vault, "private", "Doctor appointment moved to Friday")
    knowledge(vault, "projects/haushalt", "## Facts\n- **Rent is due on the 25th.**\n", "private")


def wait(config: Config, cwd: Path, session_id: str) -> Path:
    state = StateDir(config.state_dir)
    return queue.enqueue(
        state, session_id=session_id, transcript=TRANSCRIPT, cwd=str(cwd), reason="clear"
    )


def hook(cwd: Path, source: str = "startup", session_id: str = "new-session") -> dict:
    return {
        "session_id": session_id,
        "transcript_path": f"/x/{session_id}.jsonl",
        "cwd": str(cwd),
        "source": source,
    }


def headings(text: str) -> list[str]:
    return [line[3:] for line in text.splitlines() if line.startswith("## ")]


def test_work_project_loads_project_and_general_files_in_order_and_nothing_private(world):
    config, repos = world
    full_world(config.vault)

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert text.startswith(f"{HEADER}\nVault: {config.vault}")
    assert "## Project: ai-assistant-hub\nKoliChat platform for customers" in text
    assert headings(text)[1:] == [
        f"{HUB}/notes.md",
        f"{HUB}/knowledge.md",
        "general/notes.md",
        "general/knowledge.md",
    ]
    assert (
        f"## {HUB}/knowledge.md\n"
        "### Pitfalls\n- **Loki only starts if UID 10001 owns the data directory.** Run chown.\n\n"
        "### Facts\n- **The customer VMs reach the internet only through port 3128.** Proxy."
    ) in text
    assert f"## {HUB}/notes.md\n- 2026-10-19: Loki port 3100 clashes with Grafana" in text
    assert "# no install step\n" in text  # a comment in a code block is no heading
    assert "type: knowledge" not in text
    assert "updated:" not in text
    for private in ("## private/", "- private/", "NAS", "Doctor", "Rent"):
        assert private not in text


def test_private_project_and_outside_a_repo_load_private_too(world):
    config, repos = world
    full_world(config.vault)

    private_project = recall(hook(repos["haushalt"]), config)
    outside = recall(hook(repos["home"]), config)

    assert headings(private_project)[1:] == [
        "projects/haushalt/knowledge.md",
        "general/notes.md",
        "general/knowledge.md",
        "private/notes.md",
        "private/knowledge.md",
    ]
    assert "Rent is due" in private_project
    assert headings(outside) == [
        "general/notes.md",
        "general/knowledge.md",
        "private/notes.md",
        "private/knowledge.md",
    ]
    assert "Doctor appointment" in outside
    assert "Loki" not in outside


def test_project_marked_private_in_an_earlier_overview_loads_private_until_its_file_exists(world):
    config, repos = world
    full_world(config.vault)
    (config.vault / HUB / "knowledge.md").unlink()
    write(config.vault, f"{HUB}/ai-assistant-hub.md", "---\ntype: project\ndomain: private\n---\n")

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert "## private/knowledge.md" in text  # the domain the worker's skeleton will take
    assert "ai-assistant-hub.md" not in text


def test_unknown_repository_loads_general_only(world):
    config, repos = world
    full_world(config.vault)

    text = recall(hook(repos["unknown"]), config)

    assert headings(text) == ["general/notes.md", "general/knowledge.md"]
    assert "## Project" not in text
    assert "NAS" not in text


def test_over_the_limit_files_are_cut_in_load_order_with_marker_and_all_paths(world):
    config, repos = world
    full_world(config.vault)
    entries = "".join(f"- **Entry {index:02} holds.** " + "x" * 60 + "\n" for index in range(30))
    knowledge(config.vault, HUB, f"## Facts\n{entries}", summary="KoliChat")
    small = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=300)

    text = recall(hook(repos["ai-assistant-hub"]), small)

    assert len(text) <= 300 * 4
    assert len(text) > 300 * 4 - 200  # the files fill what the limit leaves
    loaded, _, rest = text.partition(CUT_MARKER)
    assert rest
    assert "Loki port 3100 clashes with Grafana" in loaded  # notes before knowledge
    assert "- **Entry 00 holds.**" in loaded
    assert "Entry 29" not in loaded
    assert "Prefer uv over pip" not in loaded  # general/ comes after the project
    assert all(line.endswith("x") for line in loaded.splitlines() if "Entry" in line)
    for path in (f"{HUB}/notes.md", f"{HUB}/knowledge.md", "general/notes.md"):
        assert f"- {path}" in rest
    assert "- general/knowledge.md" in rest
    assert "## private/" not in text
    assert "- private/" not in text


def test_header_queue_lines_and_list_paths_count_against_the_limit(world):
    config, repos = world
    full_world(config.vault)
    hub = repos["ai-assistant-hub"]
    alone = recall(hook(hub), config)
    for index in range(3):
        catalog(config.vault, f"customer-register-{index}", "register", "work")
    for index in range(2):
        wait(config, hub, f"wait-{index}")
    whole = recall(hook(hub), config)
    tokens = (len(whole) - 20) // 4  # just too small for everything
    assert len(alone) <= tokens * 4  # but the files alone would fit
    tight = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=tokens)

    text = recall(hook(hub), tight)

    assert len(text) <= tokens * 4
    assert CUT_MARKER in text
    assert text.count("- Session wait-") == 2
    assert "- customer-register-2: notes/customer-register-2.md" in text
    assert "Loki port 3100 clashes with Grafana" in text  # the files get what is left
    assert "Prefer uv over pip" not in text


def test_lists_and_registers_appear_by_domain_and_earlier_notes_never(world):
    config, repos = world
    full_world(config.vault)
    vault = config.vault
    catalog(vault, "shopping-list", "list", None)  # lists are private unless they say otherwise
    catalog(vault, "customers", "register", "work")
    write(
        vault,
        f"{HUB}/ai-assistant-hub.md",
        "---\ntype: project\ndomain: work\nsummary: Old overview line\n---\n## Open\n- x\n",
    )
    write(
        vault,
        f"{HUB}/ai-assistant-hub-loki-uid.md",
        '---\ntype: gotcha\nprojects: ["[[ai-assistant-hub]]"]\nsummary: Old single note\n---\n',
    )
    write(vault, "general/uv-instead-of-pip.md", "---\ntype: fact\nsummary: Old shared\n---\n")

    work = recall(hook(repos["ai-assistant-hub"]), config)
    outside = recall(hook(repos["home"]), config)

    assert "- customers: notes/customers.md" in work
    assert "shopping-list" not in work
    assert "- shopping-list: notes/shopping-list.md" in outside
    assert "- customers: notes/customers.md" in outside
    assert "- shopping-list: notes/shopping-list.md" in recall(hook(repos["haushalt"]), config)
    assert "shopping-list" not in recall(hook(repos["unknown"]), config)
    for earlier in ("Old overview line", "ai-assistant-hub.md", "Old single note", "loki-uid"):
        assert earlier not in work
    assert "uv-instead-of-pip" not in work
    assert "Old shared" not in outside


def test_a_note_with_an_empty_or_list_type_under_notes_does_not_break_the_start(world):
    config, repos = world
    full_world(config.vault)
    catalog(config.vault, "customers", "register", "work")
    write(config.vault, "notes/empty-type.md", "---\ntype:\ndomain: work\n---\n")
    write(config.vault, "notes/list-type.md", "---\ntype: [list]\n---\n")

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert "- customers: notes/customers.md" in text
    assert "empty-type" not in text


def test_notes_without_knowledge_load_and_the_project_line_says_so(world):
    config, repos = world
    hub = repos["ai-assistant-hub"]
    notes(config.vault, HUB, "Loki port 3100 clashes with Grafana")
    write(
        config.vault,
        f"{HUB}/ai-assistant-hub.md",
        "---\ntype: project\ndomain: work\nsummary: Old overview line\n---\n",
    )
    waiting = wait(config, hub, "waiting-1")

    text = recall(hook(hub), config)

    assert "## Project: ai-assistant-hub\n(no knowledge for this project in the vault yet)" in text
    assert "Old overview line" not in text
    assert f"## {HUB}/notes.md\n- 2026-10-19: Loki port 3100" in text
    assert "## Not processed yet (read the transcript if needed)" in text
    assert queue.load(waiting).transcript_copy in text


def test_no_heading_without_content(world):
    config, repos = world
    knowledge(config.vault, HUB, "", summary="KoliChat")  # a skeleton the worker left empty
    write(config.vault, "general/notes.md", "---\ntype: notes\n---\n\n")
    notes(config.vault, "private", "Doctor appointment moved to Friday")

    for cwd in (repos["ai-assistant-hub"], repos["home"]):
        text = recall(hook(cwd), config)
        assert f"## {HUB}/knowledge.md" not in text
        assert "## general/notes.md" not in text
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("## "):
                following = lines[index + 1] if index + 1 < len(lines) else ""
                assert following.strip(), f"empty section: {line}"
                assert not following.startswith("## "), f"empty section: {line}"


def test_empty_vault_outside_a_repo_injects_nothing(world):
    config, repos = world

    assert recall(hook(repos["home"]), config) == ""


def test_resume_injects_nothing_but_compact_does(world):
    config, repos = world
    full_world(config.vault)
    hub = repos["ai-assistant-hub"]

    assert recall(hook(hub, "resume"), config) == ""
    assert "## Project: ai-assistant-hub" in recall(hook(hub, "compact"), config)


def test_session_file_is_written_on_every_source_and_old_ones_go(world):
    config, repos = world
    state = StateDir(config.state_dir).ensure()
    stale = state.sessions / "stale.json"
    stale.write_text("{}")
    old = time.time() - 31 * 86_400
    os.utime(stale, (old, old))

    recall(hook(repos["ai-assistant-hub"], "resume", session_id="sid-1"), config)

    record = json.loads((state.sessions / "sid-1.json").read_text())
    assert record["transcript_path"] == "/x/sid-1.jsonl"
    assert not stale.exists()


def test_unknown_repo_writes_no_project_mapping(world):
    config, repos = world
    state = StateDir(config.state_dir)

    recall(hook(repos["unknown"]), config)

    assert str(repos["unknown"].resolve()) not in state.projects_file.read_text()


def test_hook_is_fast_with_500_earlier_notes(world):
    config, repos = world
    full_world(config.vault)
    for index in range(500):
        write(
            config.vault,
            f"{HUB}/k-{index}.md",
            f'---\ntype: gotcha\nprojects: ["[[ai-assistant-hub]]"]\nsummary: K {index}\n---\nx\n',
        )
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}
    command = [str(ROOT / "plugin" / "bin" / "dory"), "recall"]
    payload = json.dumps(hook(repos["ai-assistant-hub"]))
    subprocess.run(command, input=payload, env=env, capture_output=True, text=True)  # warm uv

    started = time.monotonic()
    result = subprocess.run(command, input=payload, env=env, capture_output=True, text=True)
    elapsed = time.monotonic() - started

    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert f"## {HUB}/knowledge.md" in context
    assert "K 499" not in context
    assert elapsed < 1.0
