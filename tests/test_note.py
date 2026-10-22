"""/dory:note: `prepare-note` gives the skill its context, `add-note` creates a note file."""

import json
import os
import subprocess
import threading
import time
from datetime import date
from pathlib import Path

import pytest

from dory import baseline, queue, spawn, summary
from dory.config import Config
from dory.note import NoteError, add_note, prepare_note
from dory.project import project_for_root
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "transcripts" / "resume-compact.jsonl"
HUB = "projects/ai-assistant-hub"
TODAY = date(2026, 10, 19)


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path.resolve()


@pytest.fixture
def world(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    config = Config(vault=vault, state_dir=tmp_path / "state")
    hub = make_repo(tmp_path / "code" / "ai-assistant-hub")
    project_for_root(hub, StateDir(config.state_dir).projects_file)
    home = tmp_path / "home"
    home.mkdir()
    spawned: list[bool] = []
    monkeypatch.setattr(spawn, "spawn_worker", lambda: spawned.append(True))
    return config, hub, home, spawned


def write(vault: Path, relative: str, text: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def md_files(vault: Path) -> list[Path]:
    return sorted(vault.rglob("*.md")) if vault.exists() else []


def test_a_project_note_is_a_new_file_named_by_its_title(world):
    config, hub, _, spawned = world
    (hub / "src").mkdir()
    content = "Loki moved to port 3200,\nbecause Grafana takes 3100.\n"

    written = add_note(config, hub / "src", "project", "Loki: port 3200", content, TODAY)

    assert written == Path(f"{HUB}/notes/Loki port 3200.md")
    assert (config.vault / written).read_text() == (
        "---\ntype: note\ncreated: 2026-10-19\n---\n"
        "Loki moved to port 3200,\nbecause Grafana takes 3100.\n"
    )
    assert summary.marked(StateDir(config.state_dir)) == {"project-ai-assistant-hub"}
    assert spawned == [True]
    assert not (config.vault / HUB / "knowledge.md").exists()


def test_a_general_note_is_a_new_topic_file_and_needs_no_summary(world):
    config, hub, home, spawned = world
    entries = "## Preferences\n- **Python packages with uv instead of pip.** Faster.\n"

    from_project = add_note(config, hub, "general", "Python packaging", entries, TODAY)
    from_outside = add_note(config, home, "general", "Notion", "- **A.** B.\n", TODAY)

    assert from_project == Path("notes/Python packaging.md")
    assert from_outside == Path("notes/Notion.md")
    assert (config.vault / from_project).read_text() == (
        f"---\ntype: topic\nupdated: 2026-10-19\n---\n{entries}"
    )
    assert not (config.vault / HUB).exists()
    assert summary.marked(StateDir(config.state_dir)) == set()
    assert spawned == []


@pytest.mark.parametrize(
    ("scope", "where", "title", "text", "message"),
    [
        ("project", "home", "A title", "A note", "not in a git repository"),
        ("private", "hub", "A title", "A note", "unknown scope"),
        ("team", "hub", "A title", "A note", "unknown scope"),
        ("project", "hub", "A title", "  \n ", "empty"),
        ("project", "hub", " [#] ", "A note", "leaves no file name"),
    ],
    ids=["project-outside", "private-scope", "unknown-scope", "empty-text", "empty-title"],
)
def test_add_note_refuses_and_writes_nothing(world, scope, where, title, text, message):
    config, hub, home, spawned = world

    with pytest.raises(NoteError, match=message):
        add_note(config, {"hub": hub, "home": home}[where], scope, title, text, TODAY)

    assert md_files(config.vault) == []
    assert summary.marked(StateDir(config.state_dir)) == set()
    assert spawned == []


def test_an_existing_name_in_any_case_is_never_overwritten(world):
    config, hub, _, _ = world
    mine = write(config.vault, f"{HUB}/notes/Release steps.md", "mine\n")
    notion = write(config.vault, "notes/Notion.md", "---\ntype: topic\n---\n- **x.** y\n")
    shopping = write(config.vault, "notes/Shopping list.md", "---\ntype: list\n---\n- [ ] Milk\n")

    with pytest.raises(NoteError, match=f"{HUB}/notes/Release steps.md exists"):
        add_note(config, hub, "project", "release STEPS", "other", TODAY)
    with pytest.raises(NoteError, match=r"notes/Notion.md exists \(topic\): change that file"):
        add_note(config, hub, "general", "notion", "- **Other.** x\n", TODAY)
    with pytest.raises(NoteError, match=r"notes/Shopping list.md exists \(list\)"):
        add_note(config, hub, "general", "Shopping List", "- **Other.** x\n", TODAY)

    assert mine.read_text() == "mine\n"
    assert notion.read_text().endswith("- **x.** y\n")
    assert shopping.read_text().endswith("- [ ] Milk\n")
    assert len(md_files(config.vault)) == 3


def test_a_note_added_during_a_run_is_not_reported_by_its_checks(world):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    vault = config.vault
    write(vault, f"{HUB}/notes/Before.md", "---\ntype: note\n---\nBefore the run\n")
    path = queue.enqueue(state, session_id="s1", transcript=FIXTURE, cwd=str(hub), reason="x")
    project = project_for_root(hub, state.projects_file)
    baseline.create_skeletons(vault, project, TODAY)
    kept = baseline.baseline_dir(state, path.stem)
    baseline.capture(vault, kept, project, topics_allowed=True)

    add_note(config, hub, "project", "Added while the worker runs", "x", TODAY)
    changes = baseline.check(vault, kept)

    assert (vault / HUB / "notes" / "Added while the worker runs.md").is_file()
    assert changes == []


def test_a_checked_baseline_does_not_take_a_later_note(world):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    path = queue.enqueue(state, session_id="s1", transcript=FIXTURE, cwd=str(hub), reason="x")
    kept = baseline.baseline_dir(state, path.stem)
    baseline.capture(config.vault, kept, None, topics_allowed=True)
    baseline.mark_checked(kept)

    add_note(config, hub, "project", "After the check", "x", TODAY)

    assert f"{HUB}/notes/After the check.md" not in json.loads((kept / "hashes.json").read_text())


def test_add_note_waits_while_a_run_holds_the_notes_lock(world):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    note = config.vault / HUB / "notes" / "Written after the lock.md"
    done = threading.Event()

    def note_in_background() -> None:
        add_note(config, hub, "project", "Written after the lock", "x", TODAY)
        done.set()

    with baseline.notes_lock(state.baselines):
        writer = threading.Thread(target=note_in_background)
        writer.start()
        time.sleep(0.3)
        assert not note.exists()
    writer.join(5)

    assert done.is_set()
    assert note.is_file()


def test_two_sessions_adding_notes_at_once_keep_every_note(world):
    config, hub, _, _ = world

    def many(prefix: str) -> None:
        for index in range(15):
            add_note(config, hub, "project", f"{prefix} {index}", f"{prefix} {index}", TODAY)

    writers = [threading.Thread(target=many, args=(name,)) for name in ("left", "right")]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join(10)

    notes = config.vault / HUB / "notes"
    assert sorted(path.stem for path in notes.glob("*.md")) == sorted(
        f"{name} {index}" for name in ("left", "right") for index in range(15)
    )


def test_capture_and_the_checks_hold_the_notes_lock(world, monkeypatch):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    kept = baseline.baseline_dir(state, "entry")
    held: list[str] = []
    real = baseline.notes_lock

    def recording(baselines: Path):
        held.append("lock")
        return real(baselines)

    monkeypatch.setattr(baseline, "notes_lock", recording)

    baseline.capture(config.vault, kept, None, topics_allowed=True)
    baseline.check(config.vault, kept)

    assert held == ["lock", "lock"]


def cli(config: Config, cwd: Path, *args: str, stdin: str | None = None):
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}
    return subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), *args],
        input=stdin,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def test_cli_add_note_reads_the_text_from_stdin_and_prints_the_path(world):
    config, hub, _, _ = world

    result = cli(
        config,
        hub,
        "add-note",
        "--scope",
        "project",
        "--title",
        "Quoting",
        stdin='It\'s "quoted" and $HOME stays literal\n',
    )

    assert result.returncode == 0, result.stderr
    assert f"{HUB}/notes/Quoting.md" in result.stdout
    note = (config.vault / HUB / "notes" / "Quoting.md").read_text()
    assert note.endswith('It\'s "quoted" and $HOME stays literal\n')


def test_cli_add_note_takes_the_text_as_arguments(world):
    config, hub, _, _ = world

    result = cli(config, hub, "add-note", "--scope", "general", "--title", "uv", "- **uv.** x")

    assert result.returncode == 0, result.stderr
    assert "notes/uv.md" in result.stdout
    assert (config.vault / "notes" / "uv.md").read_text().endswith("- **uv.** x\n")


def test_cli_add_note_fails_with_a_message_and_needs_a_title(world):
    config, hub, home, _ = world

    outside = cli(config, home, "add-note", "--scope", "project", "--title", "T", "A note")
    untitled = cli(config, hub, "add-note", "--scope", "project", "A note")

    assert outside.returncode == 1
    assert "not in a git repository" in outside.stderr
    assert untitled.returncode == 2
    assert "--title" in untitled.stderr
    assert md_files(config.vault) == []


def test_snapshot_exists_before_anything_is_written(world):
    config, hub, _, _ = world
    write(config.vault, f"{HUB}/knowledge.md", "---\ntype: knowledge\ndomain: work\n---\n")

    text = prepare_note(config, hub)

    snapshots = list((config.state_dir / "snapshots").iterdir())
    assert len(snapshots) == 1
    assert (snapshots[0] / HUB / "knowledge.md").is_file()
    assert f"Snapshot: {snapshots[0]}" in text


def test_prepare_note_names_the_scopes_and_the_titles_with_their_types(world):
    config, hub, _, _ = world
    write(config.vault, f"{HUB}/knowledge.md", "---\ntype: knowledge\ndomain: private\n---\n")
    write(config.vault, f"{HUB}/notes/Release steps.md", "mine\n")
    write(config.vault, "notes/Notion.md", "---\ntype: topic\n---\n")
    write(config.vault, "notes/Shopping list.md", "---\ntype: list\n---\n")
    (hub / "src").mkdir()

    text = prepare_note(config, hub / "src")  # a subdirectory still belongs to the repo

    head = text.split("# Writing rules")[0]
    assert f"Vault: {config.vault}" in head
    assert "Project: ai-assistant-hub" in head
    assert "Domain: private" in head
    assert f"- project: {HUB}/notes/\n- general: notes/ (a new topic file)" in head
    assert "The project's notes:\n- Release steps\n" in head
    assert "- Notion (topic)\n- Shopping list (list)" in head
    assert not [line for line in head.splitlines() if line.startswith("- private")]
    assert "Language: English" in head
    assert "# Writing rules for the dory-brain vault" in text  # the rules, verbatim


def test_outside_a_repo_there_is_no_project_scope(world):
    config, _, home, _ = world

    text = prepare_note(config, home)

    head = text.split("# Writing rules")[0]
    assert "Project: none" in head
    assert "- project:" not in head
    assert "- general: notes/ (a new topic file)" in head
    assert "The project's notes" not in head


def test_cli_prepare_note_uses_the_current_directory(world):
    config, hub, _, _ = world

    result = cli(config, hub, "prepare-note")

    assert result.returncode == 0, result.stderr
    assert "Project: ai-assistant-hub" in result.stdout
