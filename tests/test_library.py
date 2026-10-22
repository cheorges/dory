"""/dory:library: `library-context`, `library-write`, `link`, the guard of /dory:note, and how
linked entries reach the session start, the worker and the post-run checks."""

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from dory import baseline, queue
from dory.cli import main
from dory.config import Config
from dory.frontmatter import read_frontmatter
from dory.ingest import RunResult, make_process
from dory.library import LibraryError, guard, library_context, library_write, link
from dory.note import NoteError, add_note
from dory.project import Project, project_for_root
from dory.recall import recall
from dory.state import StateDir
from dory.worker import run

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "tests" / "fixtures" / "transcripts" / "tool-output-secrets.jsonl"
TODAY = date(2026, 10, 22)
HUB = "projects/ai-assistant-hub"
PYTHON = "---\ntype: topic\nupdated: 2026-10-20\n---\n## Pitfalls\n- **pip breaks.** Use uv.\n"
UV = "library/Python/Package management.md"


def write(vault: Path, relative: str, text: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def world(tmp_path):
    vault = tmp_path / "vault"
    config = Config(vault=vault, state_dir=tmp_path / "state")
    repos = {}
    for name in ("ai-assistant-hub", "haushalt"):
        repos[name] = (tmp_path / "code" / name).resolve()
        repos[name].mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=repos[name], check=True)
        project_for_root(repos[name], StateDir(config.state_dir).projects_file)
    write(vault, f"{HUB}/knowledge.md", "---\ntype: knowledge\ndomain: work\n---\n")
    write(vault, f"{HUB}/notes/Deploy.md", "---\ntype: note\ncreated: 2026-10-19\n---\nFridays.\n")
    write(vault, "notes/Python.md", PYTHON)
    write(vault, "notes/Shopping list.md", "---\ntype: list\n---\n- [ ] Milk\n")
    write(vault, UV, "---\ntype: library\n---\nPython packages with uv, never pip.\n")
    return config, repos


def hook(cwd: Path) -> dict:
    return {"session_id": "s1", "transcript_path": "", "cwd": str(cwd), "source": "startup"}


# The guard of /dory:note


def guarded(config: Config, file_path: str, cwd: str = "/") -> str | None:
    raw = json.dumps({"tool_name": "Write", "tool_input": {"file_path": file_path}, "cwd": cwd})
    return guard(config, raw)


def test_the_guard_blocks_every_path_in_the_library_and_names_dory_library(world):
    config, _ = world
    vault = config.vault

    for path in (
        f"{vault}/library/Python/New.md",
        f"{vault}/library",
        f"{vault}/Library/python/x.md",
        f"{vault}/notes/../library/x.md",
    ):
        message = guarded(config, path)
        assert message and "/dory:library" in message, path
    assert guarded(config, "library/x.md", cwd=str(vault))


def test_the_guard_lets_through_what_lies_outside_the_library(world, tmp_path):
    config, _ = world
    vault = config.vault

    for path in (
        f"{vault}/notes/Python.md",
        f"{vault}/{HUB}/notes/New.md",
        f"{vault}/library-old/x.md",
        f"{tmp_path}/elsewhere/library/x.md",
        "/private/tmp/x.md",  # macOS: /tmp is /private/tmp, which is no vault folder
    ):
        assert guarded(config, path) is None, path
    assert guard(config, json.dumps({"tool_name": "Write", "tool_input": {}})) is None


def test_the_guard_command_exits_2_with_its_message_and_0_otherwise(world, monkeypatch, capsys):
    config, _ = world
    monkeypatch.setenv("DORY_VAULT", str(config.vault))
    monkeypatch.setenv("DORY_STATE_DIR", str(config.state_dir))
    blocked = json.dumps({"tool_input": {"file_path": f"{config.vault}/library/x.md"}})
    allowed = json.dumps({"tool_input": {"file_path": f"{config.vault}/notes/x.md"}})

    monkeypatch.setattr("sys.stdin", _Stdin(blocked))
    assert main(["guard"]) == 2
    assert "/dory:library" in capsys.readouterr().err
    monkeypatch.setattr("sys.stdin", _Stdin(allowed))
    assert main(["guard"]) == 0
    monkeypatch.setattr("sys.stdin", _Stdin("not json"))
    assert main(["guard"]) == 0  # a broken guard must not block the rest of the session


class _Stdin:
    def __init__(self, text: str):
        self.text = text

    def read(self) -> str:
        return self.text


def test_the_note_skill_carries_the_guard_on_write_and_edit():
    skill = (ROOT / "plugin" / "skills" / "note" / "SKILL.md").read_text()
    head = skill.split("---", 2)[1]
    assert 'matcher: "Write|Edit"' in head
    assert '"${CLAUDE_PLUGIN_ROOT}/bin/dory" guard' in head
    assert "general" not in skill


# library-context and library-write


def test_the_context_lists_the_library_and_the_files_that_can_link_with_what_they_link(world):
    config, repos = world
    write(
        config.vault,
        "notes/Docker.md",
        '---\nlibrary: ["[[library/Python/Package management]]"]\n---\n',
    )

    text = library_context(config, repos["ai-assistant-hub"])

    assert "- Python/Package management" in text
    assert f"- {HUB}/notes/Deploy.md" in text
    assert "- notes/Docker.md (links library/Python/Package management)" in text
    assert "- notes/Python.md" in text
    assert "Shopping list" not in text  # a list links nothing
    assert "Snapshot: " in text


def test_a_new_entry_gets_its_frontmatter_and_an_existing_folder_keeps_its_spelling(world):
    config, _ = world

    written, new = library_write(config, "python", "Virtual environments", "Use uv venv.\n", TODAY)

    assert (written, new) == (Path("library/Python/Virtual environments.md"), True)
    assert (config.vault / written).read_text() == (
        "---\ntype: library\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\nUse uv venv.\n"
    )


def test_an_existing_entry_is_replaced_and_keeps_its_created_date(world):
    config, _ = world
    library_write(config, "Python", "Package management", "First.\n", date(2026, 10, 1))

    written, new = library_write(config, "Python", "package MANAGEMENT", "Second.\n", TODAY)

    assert (written, new) == (Path(UV), False)
    meta = read_frontmatter(config.vault / UV)
    assert (meta["created"], meta["updated"]) == ("2026-10-01", "2026-10-22")
    assert (config.vault / UV).read_text().endswith("---\nSecond.\n")


@pytest.mark.parametrize(
    ("folder", "title", "text"),
    [
        ("a/b/c", "Title", "x"),
        ("..", "Title", "x"),
        ("a:b", "Title", "x"),
        ("Python", "///", "x"),
        ("Python", "Title", "  \n"),
    ],
    ids=["too-deep", "parent", "colon", "empty-title", "empty-text"],
)
def test_a_bad_folder_title_or_text_writes_nothing(world, folder, title, text):
    config, _ = world
    before = sorted(config.vault.rglob("*"))

    with pytest.raises(LibraryError):
        library_write(config, folder, title, text, TODAY)

    assert sorted(config.vault.rglob("*")) == before


def test_an_entry_at_the_top_of_the_library_needs_no_folder(world):
    config, _ = world

    written, _ = library_write(config, "", "Reading list", "Books.\n", TODAY)

    assert written == Path("library/Reading list.md")


# link


def test_link_adds_the_entry_to_the_property_once_and_leaves_the_text(world):
    config, _ = world

    first = link(config, UV, ["notes/Python.md", f"{HUB}/notes/Deploy.md"])
    second = link(config, "Python/Package management", ["notes/Python.md"])

    item = "[[library/Python/Package management|Package management]]"
    assert first == [(Path("notes/Python.md"), True), (Path(f"{HUB}/notes/Deploy.md"), True)]
    assert second == [(Path("notes/Python.md"), False)]
    python = (config.vault / "notes/Python.md").read_text()
    assert read_frontmatter(config.vault / "notes/Python.md")["library"] == [item]
    assert python.endswith("---\n## Pitfalls\n- **pip breaks.** Use uv.\n")
    assert read_frontmatter(config.vault / "notes/Python.md")["type"] == "topic"


@pytest.mark.parametrize(
    "target",
    [f"{HUB}/knowledge.md", "notes/Shopping list.md", UV, "notes/Gone.md", "../outside.md"],
    ids=["knowledge", "list", "library", "missing", "outside"],
)
def test_link_refuses_every_other_file_and_writes_nothing(world, target):
    config, _ = world
    write(config.vault.parent, "outside.md", "x\n")
    before = {p: p.read_bytes() for p in config.vault.rglob("*.md")}

    with pytest.raises(LibraryError):
        link(config, UV, ["notes/Python.md", target])

    assert {p: p.read_bytes() for p in config.vault.rglob("*.md")} == before


def test_link_refuses_an_entry_outside_the_library(world):
    config, _ = world

    with pytest.raises(LibraryError):
        link(config, "notes/Python.md", [f"{HUB}/notes/Deploy.md"])


# The session start


def test_an_entry_linked_by_a_topic_loads_in_every_session_after_the_topic(world, tmp_path):
    config, repos = world
    link(config, UV, ["notes/Python.md"])

    for cwd in (repos["ai-assistant-hub"], repos["haushalt"], tmp_path):
        text = recall(hook(cwd), config)
        assert "## notes/Python.md" in text
        assert f"## {UV}\nPython packages with uv, never pip." in text
        assert text.index("## notes/Python.md") < text.index(f"## {UV}")


def test_a_link_in_a_topics_text_loads_nothing(world):
    config, repos = world
    write(config.vault, "notes/Python.md", PYTHON + "See [[library/Python/Package management]].\n")

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert f"## {UV}" not in text


def test_an_entry_the_project_loads_comes_once(world):
    config, repos = world
    link(config, UV, ["notes/Python.md", f"{HUB}/notes/Deploy.md"])

    hub = recall(hook(repos["ai-assistant-hub"]), config)
    other = recall(hook(repos["haushalt"]), config)

    assert hub.count(f"## {UV}") == 1
    assert hub.index(f"## {HUB}/notes/Deploy.md") < hub.index(f"## {UV}") < hub.index("## notes/")
    assert other.count(f"## {UV}") == 1


def test_a_private_folder_with_files_asks_to_rename_it(world):
    config, repos = world
    write(config.vault, "private/Health.md", "x\n")
    write(config.vault, "private/family/Holidays.md", "y\n")

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert "`private/` holds 2 files" in text and "Rename the folder to `library`" in text
    (config.vault / "private" / "Health.md").unlink()
    (config.vault / "private" / "family" / "Holidays.md").unlink()
    assert "`private/`" not in recall(hook(repos["ai-assistant-hub"]), config)


# The worker's checks and bundle


def prepared(vault: Path, tmp_path: Path) -> Path:
    project = Project(name="ai-assistant-hub", root=Path("/repos/hub"))
    baseline.create_skeletons(vault, project, TODAY)
    target = tmp_path / "baseline"
    baseline.capture(vault, target, project, topics_allowed=True)
    return target


def test_a_run_that_drops_or_adds_a_library_property_is_undone(world, tmp_path):
    config, _ = world
    link(config, UV, ["notes/Python.md"])
    target = prepared(config.vault, tmp_path)
    write(config.vault, "notes/Python.md", PYTHON + "- **New.** x\n")
    write(config.vault, "notes/Docker.md", '---\ntype: topic\nlibrary: ["[[library/x]]"]\n---\nx\n')

    changes = baseline.check(config.vault, target)

    assert read_frontmatter(config.vault / "notes/Python.md")["library"] == [
        "[[library/Python/Package management|Package management]]"
    ]
    assert "- **New.** x" in (config.vault / "notes/Python.md").read_text()
    assert "library" not in read_frontmatter(config.vault / "notes/Docker.md")
    restored = {(c["file"], c["lead"]) for c in changes if c["change"] == "restored"}
    assert restored == {
        ("notes/Python.md", "frontmatter: library"),
        ("notes/Docker.md", "frontmatter: library"),
    }


def test_a_link_set_while_a_run_waits_survives_its_checks(world, tmp_path):
    config, _ = world
    state = StateDir(config.state_dir).ensure()
    entry = queue.enqueue(state, session_id="s1", transcript=TRANSCRIPT, cwd="/", reason="clear")
    target = prepared(config.vault, tmp_path / "x")
    kept = state.baselines / entry.stem
    target.rename(kept)

    link(config, UV, ["notes/Python.md", f"{HUB}/notes/Deploy.md"])
    changes = baseline.check(config.vault, kept)

    assert "library" in read_frontmatter(config.vault / "notes/Python.md")
    assert not [c for c in changes if c["change"] in ("restored", "unexpected")]


def test_the_worker_reads_copies_of_the_entries_its_session_could_load(world, tmp_path):
    config, repos = world
    config = Config(vault=config.vault, state_dir=config.state_dir, min_user_messages=1)
    state = StateDir(config.state_dir).ensure()
    write(config.vault, "library/Health.md", "Not linked.\n")
    write(config.vault, "library/Contract.md", "api_key = sk-ant-abcdefghijklmnopqrstuvwxyz0123\n")
    link(config, UV, ["notes/Python.md"])
    link(config, "library/Contract.md", [f"{HUB}/notes/Deploy.md"])
    queue.enqueue(
        state, session_id="s2", transcript=TRANSCRIPT, cwd=str(repos["ai-assistant-hub"]),
        reason="clear",
    )  # fmt: skip
    seen = {}

    def fake(command, cwd, env, timeout):
        bundle = Path(command[command.index("--add-dir") + 1])
        task = (bundle / "task.md").read_text()
        seen["task"], seen["bundle"] = task, bundle
        seen["files"] = sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*.md"))
        seen["contract"] = (bundle / "library/Contract.md").read_text()
        note = config.vault / task.split("`")[1]
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("---\ntype: session\n---\n")
        return RunResult(returncode=0, stdout=json.dumps({"is_error": False}))

    run(state, make_process(config, state, fake))

    assert "library/Contract.md" in seen["files"] and UV in seen["files"]
    assert "library/Health.md" not in seen["files"]
    assert "sk-ant-abcdefghijklmnopqrstuvwxyz0123" not in seen["contract"]
    assert f"`{seen['bundle'] / UV}`" in seen["task"]
    assert "`library/` is the user's folder" in seen["task"]


# /dory:note


def test_add_note_knows_the_scope_notes_and_not_general(world):
    config, repos = world

    written = add_note(config, repos["ai-assistant-hub"], "notes", "Docker", "## Pitfalls\n- x\n")

    assert written == Path("notes/Docker.md")
    with pytest.raises(NoteError, match="project or notes"):
        add_note(config, repos["ai-assistant-hub"], "general", "Other", "x")
