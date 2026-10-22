"""The session start loads a project's notes and knowledge and lists the files in `notes/`."""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from dory import queue
from dory.config import Config
from dory.project import project_for_root
from dory.recall import CUT_MARKER, HEADER, NOTES_TITLE, PATHS_TITLE, recall
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "tests" / "fixtures" / "transcripts" / "resume-compact.jsonl"
HUB = "projects/ai-assistant-hub"
NOTES_HEADING = NOTES_TITLE.removeprefix("## ")
OLD = time.mktime((2026, 10, 1, 12, 0, 0, 0, 0, -1))


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


def user_note(vault: Path, title: str, body: str, folder: str = HUB) -> Path:
    return write(
        vault, f"{folder}/notes/{title}.md", f"---\ntype: note\ncreated: 2026-10-19\n---\n{body}"
    )


def in_notes(vault: Path, title: str, kind: str, updated: str, body: str = "- item\n") -> Path:
    return write(vault, f"notes/{title}.md", f"---\ntype: {kind}\nupdated: {updated}\n---\n{body}")


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
    """A project with notes, a private project, topics and a list, and private notes."""
    knowledge(
        vault,
        HUB,
        "## Pitfalls\n- **Loki only starts if UID 10001 owns the data directory.** Run chown.\n\n"
        "## Facts\n- **The customer VMs reach the internet only through port 3128.** Proxy.\n",
        summary="KoliChat platform for customers",
    )
    user_note(vault, "Loki and Grafana", "Loki port 3100 clashes with Grafana.\n")
    user_note(
        vault,
        "Release steps",
        "Run the scripts with uv:\n```bash\n# no install step\nuv run script.py\n```\n",
    )
    knowledge(vault, "projects/haushalt", "## Facts\n- **Rent is due on the 25th.**\n", "private")
    in_notes(
        vault, "Notion", "topic", "2026-10-18", "- **Overwriting a Notion page loses data.** x\n"
    )
    in_notes(vault, "uv", "topic", "2026-10-20", "- **uv runs PEP 723 scripts.** Fast.\n")
    in_notes(vault, "Shopping list", "list", "2026-10-19")
    untyped = write(vault, "notes/Untyped.md", "- **An untyped topic.** By the user.\n")
    os.utime(untyped, (OLD, OLD))
    write(vault, "library/Employment contract.md", "Notice period three months.\n")
    write(vault, "library/Health.md", "Doctor appointment moved to Friday.\n")


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


def titles(text: str) -> list[str]:
    return text.split(NOTES_TITLE, 1)[1].strip("\n").splitlines()


def test_a_work_project_loads_its_notes_knowledge_and_topics_and_lists_the_rest(world):
    config, repos = world
    full_world(config.vault)

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert text.startswith(f"{HEADER}\nVault: {config.vault}")
    assert "## Project: ai-assistant-hub\nKoliChat platform for customers" in text
    assert headings(text)[1:] == [
        f"{HUB}/notes/Loki and Grafana.md",
        f"{HUB}/notes/Release steps.md",
        f"{HUB}/knowledge.md",
        "notes/uv.md",
        "notes/Notion.md",
        "notes/Untyped.md",
        NOTES_HEADING,
    ]
    assert f"## {HUB}/notes/Loki and Grafana.md\nLoki port 3100 clashes with Grafana." in text
    assert (
        f"## {HUB}/knowledge.md\n"
        "### Pitfalls\n- **Loki only starts if UID 10001 owns the data directory.** Run chown.\n\n"
        "### Facts\n- **The customer VMs reach the internet only through port 3128.** Proxy."
    ) in text
    assert "# no install step\n" in text  # a comment in a code block is no heading
    assert "## notes/Notion.md\n- **Overwriting a Notion page loses data.** x" in text
    assert titles(text) == ["- Shopping list (list): notes/Shopping list.md"]
    assert "- item" not in text  # a list's content is read when needed
    for absent in ("type: note", "updated:", "## library/", "Notice period", "Doctor", "Rent"):
        assert absent not in text


def test_a_topic_that_does_not_fit_whole_is_listed_by_title(world):
    config, repos = world
    knowledge(config.vault, HUB, "## Facts\n- **Small.** x\n", summary="KoliChat")
    in_notes(
        config.vault, "Recent", "topic", "2026-10-21", "- **Recent fits.** " + "r" * 200 + "\n"
    )
    in_notes(
        config.vault, "Older", "topic", "2026-10-20", "- **Older is long.** " + "o" * 3000 + "\n"
    )
    in_notes(config.vault, "Shopping list", "list", "2026-10-19")
    small = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=500)

    text = recall(hook(repos["ai-assistant-hub"]), small)

    assert len(text) <= 500 * 4
    assert "## notes/Recent.md\n- **Recent fits.**" in text
    assert "Older is long" not in text
    assert titles(text) == [
        "- Older: notes/Older.md",
        "- Shopping list (list): notes/Shopping list.md",
    ]


def test_a_linked_library_entry_loads_once_right_after_the_first_note_that_links_it(world):
    config, repos = world
    full_world(config.vault)
    user_note(config.vault, "A first", "Expenses: see [[library/Employment contract]].\n")
    user_note(
        config.vault,
        "B second",
        "Again ![[employment contract.md|the contract]] and "
        "[it](library/Employment%20contract.md).\n",
    )
    write(config.vault, "library/Employment contract.md", "Notice period. See [[Health]].\n")

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert headings(text)[1:4] == [
        f"{HUB}/notes/A first.md",
        "library/Employment contract.md",
        f"{HUB}/notes/B second.md",
    ]
    assert text.count("## library/") == 1
    assert "Doctor" not in text  # one level only


def test_links_in_code_out_of_the_library_or_into_notes_load_nothing(world, tmp_path):
    config, repos = world
    full_world(config.vault)
    secret = write(tmp_path, "elsewhere/secret.md", "Outside the vault.\n")
    (config.vault / "library" / "escape.md").symlink_to(secret)
    user_note(
        config.vault,
        "Links",
        "```\n[[library/Health]]\n```\n"
        "[[library/../notes/Notion]] [[escape]] [[notes/Notion]] [[library/Gone]]\n",
    )

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert "## library/" not in text
    for absent in ("Doctor", "Outside the vault"):
        assert absent not in text


def test_outside_a_repository_and_in_an_unknown_one_only_the_titles_load(world):
    config, repos = world
    full_world(config.vault)

    for cwd in (repos["home"], repos["unknown"]):
        text = recall(hook(cwd), config)
        assert headings(text) == [
            "notes/uv.md",
            "notes/Notion.md",
            "notes/Untyped.md",
            NOTES_HEADING,
        ]
        assert "- Shopping list (list): notes/Shopping list.md" in text
        for absent in ("## Project", "Loki", "Rent", "Notice period", "Doctor"):
            assert absent not in text


def test_a_private_project_loads_its_own_files_and_nothing_unlinked_from_the_library(world):
    config, repos = world
    full_world(config.vault)

    text = recall(hook(repos["haushalt"]), config)

    assert headings(text)[:2] == ["Project: haushalt", "projects/haushalt/knowledge.md"]
    assert "Rent is due" in text
    assert "Doctor" not in text and "Notice period" not in text


def test_titles_that_do_not_fit_end_with_a_line_that_counts_the_rest(world):
    config, repos = world
    full_world(config.vault)
    for index in range(60):
        in_notes(config.vault, f"List number {index:02}", "list", "2026-10-02")
    small = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=400)

    text = recall(hook(repos["ai-assistant-hub"]), small)

    assert len(text) <= 400 * 4
    assert CUT_MARKER not in text and PATHS_TITLE not in text  # the project's files fit
    assert "Loki port 3100 clashes with Grafana." in text
    assert "## notes/uv.md" in text  # the most recent topic loads whole
    listed = titles(text)
    shown = [line for line in listed if ": notes/" in line]
    loaded = text.count("## notes/")
    assert listed[-1] == f"- {64 - loaded - len(shown)} more in notes/: list the folder for them"


def test_files_cut_without_a_summary_keep_their_paths_before_the_titles(world):
    config, repos = world
    full_world(config.vault)
    entries = "".join(f"- **Entry {index:02} holds.** " + "x" * 60 + "\n" for index in range(30))
    knowledge(config.vault, HUB, f"## Facts\n{entries}", summary="KoliChat")
    for index in range(30):
        in_notes(config.vault, f"Topic number {index:02}", "topic", "2026-10-02")
    small = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=300)

    text = recall(hook(repos["ai-assistant-hub"]), small)

    assert len(text) <= 300 * 4
    assert text.index(CUT_MARKER) < text.index(PATHS_TITLE) < text.index(NOTES_TITLE)
    assert "Loki port 3100 clashes with Grafana." in text  # the notes come before knowledge
    assert "- **Entry 00 holds.**" in text and "Entry 29" not in text
    for path in (f"{HUB}/notes/Loki and Grafana.md", f"{HUB}/knowledge.md"):
        assert f"- {path}" in text
    assert titles(text)[-1].endswith("more in notes/: list the folder for them")


def test_header_and_queue_lines_count_against_the_limit(world):
    config, repos = world
    full_world(config.vault)
    hub = repos["ai-assistant-hub"]
    for index in range(2):
        wait(config, hub, f"wait-{index}")
    whole = recall(hook(hub), config)
    tokens = (len(whole) - 20) // 4  # just too small for everything
    tight = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=tokens)

    text = recall(hook(hub), tight)

    assert len(text) <= tokens * 4
    assert text.count("- Session wait-") == 2
    assert "Loki port 3100 clashes with Grafana." in text
    assert titles(text)[-1].endswith("more in notes/: list the folder for them")


def test_files_of_an_earlier_version_never_appear(world):
    config, repos = world
    full_world(config.vault)
    vault = config.vault
    write(vault, "general/knowledge.md", "---\ntype: knowledge\n---\n- **Old general.** x\n")
    write(vault, "general/notes.md", "---\ntype: notes\n---\n- 2026-10-19: Old general note\n")
    write(vault, f"{HUB}/notes.md", "---\ntype: notes\n---\n- 2026-10-19: Old project note\n")
    write(vault, "private/knowledge.md", "---\ntype: knowledge\n---\n- **Old private.** x\n")
    write(vault, f"{HUB}/ai-assistant-hub.md", "---\ntype: project\nsummary: Old overview\n---\n")
    write(vault, f"{HUB}/Loki UID.md", "---\ntype: gotcha\nsummary: Old single note\n---\n")

    for cwd in (repos["ai-assistant-hub"], repos["home"]):
        text = recall(hook(cwd), config)
        for earlier in ("Old general", "Old project note", "Old private", "Old overview"):
            assert earlier not in text
        for path in ("general/", f"{HUB}/notes.md", "Loki UID"):
            assert path not in text


def test_a_type_dory_does_not_know_lists_the_file_as_a_topic(world):
    config, repos = world
    full_world(config.vault)
    write(config.vault, "notes/Empty type.md", "---\ntype:\nupdated: 2026-10-21\n---\n")
    write(config.vault, "notes/Odd type.md", "---\ntype: [list]\nupdated: 2026-10-21\n---\n")

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert "- Empty type: notes/Empty type.md" in text
    assert "- Odd type: notes/Odd type.md" in text


def test_a_project_without_knowledge_loads_its_notes_and_the_project_line_says_so(world):
    config, repos = world
    hub = repos["ai-assistant-hub"]
    user_note(config.vault, "Loki and Grafana", "Loki port 3100 clashes with Grafana.\n")
    write(
        config.vault, f"{HUB}/ai-assistant-hub.md", "---\ntype: project\nsummary: Old line\n---\n"
    )
    waiting = wait(config, hub, "waiting-1")

    text = recall(hook(hub), config)

    assert "## Project: ai-assistant-hub\n(no knowledge for this project in the vault yet)" in text
    assert "Old line" not in text
    assert f"## {HUB}/notes/Loki and Grafana.md\nLoki port 3100" in text
    assert "## Not processed yet (read the transcript if needed)" in text
    assert queue.load(waiting).transcript_copy in text


def test_no_heading_without_content(world):
    config, repos = world
    knowledge(config.vault, HUB, "", summary="KoliChat")  # a skeleton the worker left empty
    user_note(config.vault, "Empty", "\n")
    in_notes(config.vault, "Notion", "topic", "2026-10-18")

    for cwd in (repos["ai-assistant-hub"], repos["home"]):
        text = recall(hook(cwd), config)
        assert f"## {HUB}/knowledge.md" not in text
        assert f"## {HUB}/notes/Empty.md" not in text
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


def test_hook_is_fast_with_500_files_in_notes_and_500_earlier_notes(world):
    config, repos = world
    full_world(config.vault)
    for index in range(500):
        in_notes(config.vault, f"Topic {index:03}", "topic", "2026-10-02")
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
