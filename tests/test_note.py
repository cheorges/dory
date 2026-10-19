"""/dory:note: what `dory prepare-note` tells the skill, and `dory add-note` (Record 003, S5)."""

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


def test_add_note_creates_the_project_notes_marks_the_context_and_starts_the_worker(world):
    config, hub, _, spawned = world
    (hub / "src").mkdir()

    written = add_note(config, hub / "src", "project", "Loki port 3100 clashes with Grafana", TODAY)

    assert written == Path(HUB) / "notes.md"
    text = (config.vault / written).read_text()
    assert text == "---\ntype: notes\n---\n- 2026-10-19: Loki port 3100 clashes with Grafana\n"
    assert summary.marked(StateDir(config.state_dir)) == {"project-ai-assistant-hub"}
    assert spawned == [True]
    assert not (config.vault / HUB / "knowledge.md").exists()


def test_add_note_appends_newest_last_in_the_users_words(world):
    config, hub, _, _ = world
    write(config.vault, f"{HUB}/notes.md", "---\ntype: notes\n---\n- 2026-10-01: Erste Notiz")

    add_note(config, hub, "project", "Zweite Notiz:\n  mit Umbruch", TODAY)

    assert (config.vault / HUB / "notes.md").read_text() == (
        "---\ntype: notes\n---\n- 2026-10-01: Erste Notiz\n"
        "- 2026-10-19: Zweite Notiz: mit Umbruch\n"
    )


def test_general_and_private_scopes_from_a_project_and_from_outside(world):
    config, hub, home, _ = world

    general = add_note(config, hub, "general", "Python packages with uv instead of pip", TODAY)
    private = add_note(config, home, "private", "The NAS backs up at 02:00", TODAY)

    assert general == Path("general/notes.md")
    assert private == Path("private/notes.md")
    assert "uv instead of pip" in (config.vault / general).read_text()
    assert "NAS" in (config.vault / private).read_text()
    assert not (config.vault / HUB / "notes.md").exists()
    assert summary.marked(StateDir(config.state_dir)) == {"project-ai-assistant-hub", "_outside"}


def test_a_private_note_from_a_work_project_marks_the_context_that_loads_it(world):
    config, hub, _, _ = world

    add_note(config, hub, "private", "The NAS backs up at 02:00", TODAY)

    assert summary.marked(StateDir(config.state_dir)) == {"_outside"}


@pytest.mark.parametrize(
    ("scope", "where", "text", "message"),
    [
        ("project", "home", "A note", "not in a git repository"),
        ("team", "hub", "A note", "unknown scope"),
        ("project", "hub", "  \n ", "empty"),
    ],
    ids=["project-outside", "unknown-scope", "empty-text"],
)
def test_add_note_refuses_and_writes_nothing(world, scope, where, text, message):
    config, hub, home, spawned = world

    with pytest.raises(NoteError, match=message):
        add_note(config, {"hub": hub, "home": home}[where], scope, text, TODAY)

    assert not config.vault.exists() or not list(config.vault.rglob("*.md"))
    assert summary.marked(StateDir(config.state_dir)) == set()
    assert spawned == []


def test_a_note_added_during_a_run_survives_its_post_run_checks(world):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    vault = config.vault
    write(vault, f"{HUB}/notes.md", "---\ntype: notes\n---\n- 2026-10-01: Before the run\n")
    path = queue.enqueue(state, session_id="s1", transcript=FIXTURE, cwd=str(hub), reason="x")
    knowledge = [Path(HUB) / "knowledge.md"]
    project = project_for_root(hub, state.projects_file)
    baseline.create_skeletons(vault, project, TODAY)
    kept = baseline.baseline_dir(state, path.stem)
    baseline.capture(vault, kept, knowledge)

    add_note(config, hub, "project", "Added while the worker runs", TODAY)
    add_note(config, hub, "general", "A new general note while it runs", TODAY)
    changes = baseline.check(vault, kept, knowledge)

    assert "Added while the worker runs" in (vault / HUB / "notes.md").read_text()
    assert "A new general note" in (vault / "general" / "notes.md").read_text()
    assert changes == []


def test_a_run_that_changed_the_notes_is_undone_and_the_users_line_stays(world):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    vault = config.vault
    write(vault, f"{HUB}/notes.md", "---\ntype: notes\n---\n- 2026-10-01: Before the run\n")
    path = queue.enqueue(state, session_id="s1", transcript=FIXTURE, cwd=str(hub), reason="x")
    kept = baseline.baseline_dir(state, path.stem)
    baseline.capture(vault, kept, [])
    notes = vault / HUB / "notes.md"
    notes.write_text(notes.read_text() + "- 2026-10-19: Written by the model\n")

    add_note(config, hub, "project", "Added while the worker runs", TODAY)
    changes = baseline.check(vault, kept, [])

    assert notes.read_text() == (
        "---\ntype: notes\n---\n- 2026-10-01: Before the run\n"
        "- 2026-10-19: Added while the worker runs\n"
    )
    assert [change["change"] for change in changes] == ["restored"]


def test_add_note_waits_while_a_run_holds_the_notes_lock(world):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    notes = config.vault / HUB / "notes.md"
    done = threading.Event()

    def note_in_background() -> None:
        add_note(config, hub, "project", "Written after the lock", TODAY)
        done.set()

    with baseline.notes_lock(state.baselines):
        writer = threading.Thread(target=note_in_background)
        writer.start()
        time.sleep(0.3)
        assert not notes.exists()
    writer.join(5)

    assert done.is_set()
    assert "Written after the lock" in notes.read_text()


def test_two_sessions_adding_notes_at_once_keep_every_line(world):
    config, hub, _, _ = world

    def many(prefix: str) -> None:
        for index in range(15):
            add_note(config, hub, "project", f"{prefix} {index}", TODAY)

    writers = [threading.Thread(target=many, args=(name,)) for name in ("left", "right")]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join(10)

    text = (config.vault / HUB / "notes.md").read_text()
    assert all(f": {name} {index}\n" in text for name in ("left", "right") for index in range(15))


def test_capture_and_the_notes_restore_hold_the_notes_lock(world, monkeypatch):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    kept = baseline.baseline_dir(state, "entry")
    held: list[str] = []
    real = baseline.notes_lock

    def recording(baselines: Path):
        held.append("lock")
        return real(baselines)

    monkeypatch.setattr(baseline, "notes_lock", recording)
    write(config.vault, f"{HUB}/notes.md", "---\ntype: notes\n---\n- 2026-10-01: Mine\n")

    baseline.capture(config.vault, kept, [])
    baseline.check(config.vault, kept, [])

    assert held == ["lock", "lock"]


def test_checked_baselines_get_no_copy(world):
    config, hub, _, _ = world
    state = StateDir(config.state_dir).ensure()
    path = queue.enqueue(state, session_id="s1", transcript=FIXTURE, cwd=str(hub), reason="x")
    kept = baseline.baseline_dir(state, path.stem)
    baseline.capture(config.vault, kept, [])
    baseline.mark_checked(kept)

    add_note(config, hub, "project", "After the check", TODAY)

    assert not (kept / "files" / HUB / "notes.md").exists()


def test_cli_add_note_reads_the_text_from_stdin_and_prints_the_path(world):
    config, hub, _, _ = world
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}

    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "add-note", "--scope", "project"],
        input='It\'s "quoted" and $HOME stays literal\n',
        cwd=hub,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert f"{HUB}/notes.md" in result.stdout
    notes = (config.vault / HUB / "notes.md").read_text()
    assert ': It\'s "quoted" and $HOME stays literal\n' in notes


def test_cli_add_note_takes_the_text_as_arguments(world):
    config, hub, _, _ = world
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}

    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "add-note", "--scope", "general", "uv", "not pip"],
        cwd=hub,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "general/notes.md" in result.stdout
    assert (config.vault / "general" / "notes.md").read_text().endswith(": uv not pip\n")


def test_cli_add_note_fails_with_a_message_outside_a_repository(world):
    config, _, home, _ = world
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}

    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "add-note", "--scope", "project", "A note"],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "not in a git repository" in result.stderr
    assert not config.vault.exists() or not list(config.vault.rglob("*.md"))


def test_snapshot_exists_before_anything_is_written(world):
    config, hub, _, _ = world
    write(config.vault, f"{HUB}/knowledge.md", "---\ntype: knowledge\ndomain: work\n---\n")

    text = prepare_note(config, hub)

    snapshots = list((config.state_dir / "snapshots").iterdir())
    assert len(snapshots) == 1
    assert (snapshots[0] / HUB / "knowledge.md").is_file()
    assert f"Snapshot: {snapshots[0]}" in text


def test_prepare_note_names_project_domain_scopes_and_rules(world):
    config, hub, _, _ = world
    write(config.vault, f"{HUB}/knowledge.md", "---\ntype: knowledge\ndomain: private\n---\n")
    (hub / "src").mkdir()

    text = prepare_note(config, hub / "src")  # a subdirectory still belongs to the repo

    assert f"Vault: {config.vault}" in text
    assert "Project: ai-assistant-hub" in text
    assert "Domain: private" in text
    assert f"- project: {HUB}/notes.md" in text
    assert "- general: general/notes.md" in text
    assert "- private: private/notes.md" in text
    assert "Language: English" in text
    assert "# Writing rules for the dory-brain vault" in text  # the rules, verbatim
    assert "overview" not in text.split("# Writing rules")[0].lower()
    assert "Known projects" not in text


def test_outside_a_repo_there_is_no_project_scope(world):
    config, _, home, _ = world

    text = prepare_note(config, home)

    assert "Project: none" in text
    assert "- project:" not in text
    assert "- general: general/notes.md" in text
    assert "- private: private/notes.md" in text


def test_cli_prepare_note_uses_the_current_directory(world):
    config, hub, _, _ = world
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}

    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "prepare-note"],
        cwd=hub,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Project: ai-assistant-hub" in result.stdout
