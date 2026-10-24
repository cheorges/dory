"""/dory:library: `library-context`, `library-write`, `link`, the guard of /dory:note, and how
linked entries reach the session start, the worker and the post-run checks."""

import hashlib
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
from dory.library import (
    CONTEXT_CHARS,
    MAX_OTHER_NOTES,
    LibraryError,
    guard,
    library_context,
    library_write,
    link,
)
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_the_context_lists_every_projects_notes_with_what_they_are_about_own_project_first(world):
    config, repos = world
    write(config.vault, "projects/dory/knowledge.md", "---\ntype: knowledge\ndomain: work\n---\n")
    write(
        config.vault,
        "projects/dory/notes/Release.md",
        "---\ntype: note\naliases: [Releasing]\ntags: [release, git]\n---\n# How dory is released\n"
        "Tag on main.\n",
    )
    write(
        config.vault,
        "projects/dory/notes/Vault.md",
        "---\ntype: note\ndescription: Where the vault lives\n---\nText only.\n",
    )
    write(config.vault, "projects/dory/notes/Tags.md", "---\ntype: note\n---\n#release\nPlain.\n")

    text = library_context(config, repos["ai-assistant-hub"])

    assert text.index(f"{HUB}/notes/Deploy.md") < text.index("projects/dory/notes/Release.md")
    assert (
        '- projects/dory/notes/Release.md: "How dory is released" (aliases: Releasing; '
        "tags: release, git)"
    ) in text
    assert '- projects/dory/notes/Vault.md: "Where the vault lives"' in text
    assert "- projects/dory/notes/Tags.md\n" in text


def test_the_context_names_each_entrys_aliases_and_hash(world):
    config, repos = world
    write(config.vault, UV, '---\ntype: library\naliases:\n  - "uv"\n  - "pip"\n---\nText.\n')

    text = library_context(config, repos["ai-assistant-hub"])

    assert (
        f"- Python/Package management (aliases: uv, pip; sha256 {sha(config.vault / UV)})" in text
    )


def test_a_private_projects_notes_appear_only_in_its_own_sessions(world):
    config, repos = world
    write(
        config.vault,
        "projects/haushalt/knowledge.md",
        "---\ntype: knowledge\ndomain: private\n---\n",
    )
    write(config.vault, "projects/haushalt/notes/Insurance.md", "---\ntype: note\n---\nPolicy.\n")

    from_work = library_context(config, repos["ai-assistant-hub"])
    from_home = library_context(config, repos["haushalt"])
    outside = library_context(config, config.vault.parent)

    assert "Insurance" not in from_work and "Insurance" not in outside
    assert "projects/haushalt/notes/Insurance.md" in from_home
    assert f"{HUB}/notes/Deploy.md" not in from_home
    assert f"{HUB}/notes/Deploy.md" in outside


def test_the_context_caps_the_notes_of_other_projects_and_counts_the_rest(world):
    config, repos = world
    for index in range(MAX_OTHER_NOTES + 3):
        write(config.vault, f"projects/big/notes/Note {index:02d}.md", "---\ntype: note\n---\nx\n")
    for index in range(MAX_OTHER_NOTES + 3):
        write(config.vault, f"{HUB}/notes/Own {index:02d}.md", "---\ntype: note\n---\nx\n")

    text = library_context(config, repos["ai-assistant-hub"])

    assert text.count("- projects/big/notes/") == MAX_OTHER_NOTES
    assert "- 3 more notes of big" in text
    assert text.count(f"- {HUB}/notes/Own ") == MAX_OTHER_NOTES + 3


def test_a_comment_in_a_code_block_is_no_heading(world):
    config, repos = world
    write(
        config.vault,
        f"{HUB}/notes/Setup.md",
        "---\ntype: note\n---\n```bash\n# install deps\nuv sync\n```\n## Local setup\n",
    )

    text = library_context(config, repos["ai-assistant-hub"])

    assert f'- {HUB}/notes/Setup.md: "Local setup"' in text


def test_an_unreadable_note_or_entry_does_not_fail_the_context(world, monkeypatch):
    config, repos = world
    monkeypatch.setattr("dory.library.snapshot", lambda config, state: "none")  # copies every file
    broken = write(config.vault, f"{HUB}/notes/Broken.md", "no frontmatter\n")
    for path in (broken, config.vault / UV):
        path.chmod(0)

    try:
        text = library_context(config, repos["ai-assistant-hub"])
    finally:
        for path in (broken, config.vault / UV):
            path.chmod(0o644)

    assert "- Python/Package management (unreadable)" in text
    assert f"- {HUB}/notes/Broken.md" in text and f"{HUB}/notes/Deploy.md" in text


def test_the_context_stops_listing_other_projects_at_its_budget(world):
    config, repos = world
    long = "A long description that fills the line with words " * 2
    for project in range(30):
        for index in range(20):
            write(
                config.vault,
                f"projects/p{project:02d}/notes/Note {index:02d}.md",
                f"---\ntype: note\ndescription: {long}\ntags: [a, b, c, d, e, f, g]\n---\n",
            )

    text = library_context(config, repos["ai-assistant-hub"])

    assert len(text) <= CONTEXT_CHARS + 2_000, len(text)
    assert f"{HUB}/notes/Deploy.md" in text and "notes/Python.md" in text
    assert "more projects" in text
    assert "tags: a, b, c, d, e)" in text


def test_a_new_entry_gets_its_frontmatter_and_an_existing_folder_keeps_its_spelling(world):
    config, _ = world

    written, new = library_write(config, "python", "Virtual environments", "Use uv venv.\n", TODAY)

    assert (written, new) == (Path("library/Python/Virtual environments.md"), True)
    assert (config.vault / written).read_text() == (
        "---\ntype: library\ncreated: 2026-10-22\nupdated: 2026-10-22\n---\nUse uv venv.\n"
    )


def test_an_existing_entry_is_replaced_and_keeps_its_created_date(world):
    config, _ = world
    (config.vault / UV).unlink()
    library_write(config, "Python", "Package management", "First.\n", date(2026, 10, 1))

    written, new = library_write(
        config, "Python", "package MANAGEMENT", "Second.\n", TODAY, expect=sha(config.vault / UV)
    )

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


# Review findings and open acceptance criteria


def test_a_shared_entry_loads_with_the_topic_that_fits_not_with_a_newer_one_that_does_not(world):
    config, repos = world
    config = Config(vault=config.vault, state_dir=config.state_dir, recall_budget_tokens=250)
    big = "---\ntype: topic\nupdated: 2026-10-21\n---\n" + "- **Big.** " + "x" * 2000 + "\n"
    write(config.vault, "notes/Big.md", big)
    write(config.vault, "notes/Empty.md", "---\ntype: topic\nupdated: 2026-10-22\n---\n")
    link(config, UV, ["notes/Big.md", "notes/Python.md", "notes/Empty.md"])

    text = recall(hook(repos["haushalt"]), config)

    assert "## notes/Big.md" not in text and "## notes/Python.md" in text
    assert f"## {UV}\nPython packages with uv, never pip." in text


def test_a_link_made_to_a_topic_created_while_a_run_waits_survives_its_checks(world, tmp_path):
    config, repos = world
    state = StateDir(config.state_dir).ensure()
    entry = queue.enqueue(state, session_id="s1", transcript=TRANSCRIPT, cwd="/", reason="clear")
    target = prepared(config.vault, tmp_path / "x")
    kept = state.baselines / entry.stem
    target.rename(kept)

    add_note(config, repos["ai-assistant-hub"], "notes", "Docker", "## Pitfalls\n- **x.** y\n")
    link(config, UV, ["notes/Docker.md"])
    changes = baseline.check(config.vault, kept)

    assert "library" in read_frontmatter(config.vault / "notes/Docker.md")
    assert not [c for c in changes if c["lead"] == "frontmatter: library"]


def test_a_bare_path_in_a_project_notes_property_loads_the_entry(world):
    config, repos = world
    write(
        config.vault,
        f"{HUB}/notes/Deploy.md",
        "---\ntype: note\nlibrary: library/Python/Package management\n---\nFridays.\n",
    )

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert f"## {UV}" in text


def test_a_project_notes_property_loads_the_entry_only_in_that_project(world):
    config, repos = world
    link(config, UV, [f"{HUB}/notes/Deploy.md"])

    assert f"## {UV}" in recall(hook(repos["ai-assistant-hub"]), config)
    assert f"## {UV}" not in recall(hook(repos["haushalt"]), config)


def test_a_link_into_the_old_private_folder_loads_nothing(world):
    config, repos = world
    write(config.vault, "private/Health.md", "Blood pressure.\n")
    write(config.vault, f"{HUB}/notes/Deploy.md", "See [[private/Health]] and [[Health]].\n")

    text = recall(hook(repos["ai-assistant-hub"]), config)

    assert "Blood pressure" not in text


def test_replacing_an_entry_keeps_the_properties_the_user_added(world):
    config, _ = world
    write(
        config.vault,
        UV,
        "---\ntype: library\ncreated: 2026-10-01\ntags:\n  - python\naliases: [uv]\n---\nOld.\n",
    )

    library_write(
        config, "Python", "Package management", "New.\n", TODAY, expect=sha(config.vault / UV)
    )

    meta = read_frontmatter(config.vault / UV)
    assert meta["tags"] == ["python"] and meta["aliases"] == ["uv"]
    assert (meta["type"], meta["created"], meta["updated"]) == (
        "library",
        "2026-10-01",
        "2026-10-22",
    )
    assert (config.vault / UV).read_text().endswith("---\nNew.\n")


@pytest.mark.parametrize("title", ['Say "hi"', "Cost $5", "Run `ls`"])
def test_a_title_with_a_quote_dollar_or_backtick_is_refused(world, title):
    config, repos = world
    before = sorted(config.vault.rglob("*"))

    with pytest.raises(LibraryError, match="holds no"):
        library_write(config, "Python", title, "x\n", TODAY)
    with pytest.raises(LibraryError, match="holds no"):
        library_write(config, title, "Fine", "x\n", TODAY)
    with pytest.raises(NoteError, match="holds no"):
        add_note(config, repos["ai-assistant-hub"], "project", title, "x\n")

    assert sorted(config.vault.rglob("*")) == before


# Replacing only on purpose, aliases and source


def test_an_existing_entry_is_never_replaced_without_being_asked_to(world):
    config, _ = world
    before = (config.vault / UV).read_text()

    with pytest.raises(LibraryError, match=f"exists.*{sha(config.vault / UV)}"):
        library_write(config, "Python", "package management", "Other.\n", TODAY)

    assert (config.vault / UV).read_text() == before


def test_a_stale_hash_replaces_nothing_and_names_the_current_one(world):
    config, _ = world
    read = sha(config.vault / UV)
    write(config.vault, UV, "---\ntype: library\n---\nChanged in Obsidian meanwhile.\n")

    with pytest.raises(LibraryError, match=f"changed.*{sha(config.vault / UV)}"):
        library_write(config, "Python", "Package management", "Mine.\n", TODAY, expect=read)

    assert "meanwhile" in (config.vault / UV).read_text()


def test_a_hash_for_a_new_entry_is_refused(world):
    config, _ = world

    with pytest.raises(LibraryError, match="no entry"):
        library_write(config, "Python", "Packaging", "x\n", TODAY, expect="0" * 64)

    assert not (config.vault / "library/Python/Packaging.md").exists()


def test_aliases_and_source_land_in_the_frontmatter_quoted(world):
    config, _ = world

    written, _ = library_write(
        config,
        "Python",
        "Virtual environments",
        "Use uv venv.\n",
        TODAY,
        aliases=["venv", "Virtuelle Umgebung"],
        source="[[projects/ai-assistant-hub/notes/Deploy|Deploy]]",
    )

    text = (config.vault / written).read_text()
    assert 'aliases:\n  - "venv"\n  - "Virtuelle Umgebung"\n' in text
    assert 'source: "[[projects/ai-assistant-hub/notes/Deploy|Deploy]]"\n' in text
    meta = read_frontmatter(config.vault / written)
    assert meta["aliases"] == ["venv", "Virtuelle Umgebung"]
    assert meta["source"] == "[[projects/ai-assistant-hub/notes/Deploy|Deploy]]"


def test_a_replace_keeps_aliases_and_source_it_is_not_given_and_replaces_those_it_is(world):
    config, _ = world
    write(
        config.vault,
        UV,
        '---\ntype: library\ncreated: 2026-10-01\naliases:\n  - "uv"\n'
        'source: "https://docs.astral.sh/uv/"\ntags: [python]\n---\nOld.\n',
    )

    library_write(
        config, "Python", "Package management", "New.\n", TODAY, expect=sha(config.vault / UV)
    )
    kept = read_frontmatter(config.vault / UV)
    library_write(
        config,
        "Python",
        "Package management",
        "Newer.\n",
        TODAY,
        expect=sha(config.vault / UV),
        aliases=["Paketverwaltung"],
    )
    replaced = read_frontmatter(config.vault / UV)

    assert (kept["aliases"], kept["source"], kept["tags"]) == (
        ["uv"],
        "https://docs.astral.sh/uv/",
        ["python"],
    )
    assert (replaced["aliases"], replaced["source"]) == (
        ["Paketverwaltung"],
        "https://docs.astral.sh/uv/",
    )


@pytest.mark.parametrize(
    ("aliases", "source"),
    [
        (['Say "hi"'], None),
        (["ok"], "https://x.ch/$HOME"),
        (["two\nlines"], None),
        ([" "], None),
        (["ok"], "C:\\Users\\me"),
    ],
    ids=["quote-alias", "dollar-source", "newline", "blank-alias", "backslash-source"],
)
def test_a_bad_alias_or_source_writes_nothing(world, aliases, source):
    config, _ = world
    before = sorted(config.vault.rglob("*"))

    with pytest.raises(LibraryError):
        library_write(config, "Python", "Fresh", "x\n", TODAY, aliases=aliases, source=source)

    assert sorted(config.vault.rglob("*")) == before


def test_the_write_command_replaces_only_with_replace_and_expect(world, monkeypatch, capsys):
    config, _ = world
    monkeypatch.setattr("dory.cli.load_config", lambda: config)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("Replaced.\n"))
    current = sha(config.vault / UV)

    refused = main(["library-write", "--folder", "Python", "--title", "Package management"])
    without_hash = main(
        ["library-write", "--folder", "Python", "--title", "Package management", "--replace"]
    )
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("Replaced.\n"))
    done = main(
        [
            "library-write",
            "--folder",
            "Python",
            "--title",
            "Package management",
            "--replace",
            "--expect",
            current,
            "--alias",
            "uv",
            "--alias",
            "pip replacement",
            "--source",
            "https://docs.astral.sh/uv/",
        ]
    )

    err = capsys.readouterr()
    assert (refused, without_hash, done) == (1, 1, 0), err
    assert (
        "--replace --expect" in err.err
        and "Replaced library/Python/Package management.md" in err.out
    )
    assert read_frontmatter(config.vault / UV)["aliases"] == ["uv", "pip replacement"]
