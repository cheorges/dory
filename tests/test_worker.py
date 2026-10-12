import threading
from pathlib import Path

from dory import queue
from dory.config import Config
from dory.state import StateDir
from dory.worker import MAX_ATTEMPTS, Outcome, dry_run, prepare, run

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
# The fixture transcripts hold German user text; assertions quote it verbatim.


def add(state: StateDir, session_id: str, fixture: str = "resume-compact.jsonl") -> Path:
    return queue.enqueue(
        state, session_id=session_id, transcript=FIXTURES / fixture, cwd="/tmp", reason="clear"
    )


def test_second_worker_finds_the_lock_and_leaves(tmp_path):
    state = StateDir(tmp_path).ensure()
    add(state, "s1")
    inside, release = threading.Event(), threading.Event()

    def slow(path, entry):
        inside.set()
        release.wait(5)
        return Outcome.DONE

    first = threading.Thread(target=run, args=(state, slow))
    first.start()
    inside.wait(5)
    second = run(state, lambda path, entry: Outcome.DONE)
    release.set()
    first.join(5)

    assert second == "busy"
    assert queue.pending(state) == []
    assert len(list(state.done.glob("*.json"))) == 1


def test_entry_arriving_during_the_pass_is_processed_in_the_same_run(tmp_path):
    state = StateDir(tmp_path).ensure()
    add(state, "s1")
    seen = []

    def process(path, entry):
        seen.append(entry.session_id)
        if entry.session_id == "s1":
            add(state, "s2")
        return Outcome.DONE

    assert run(state, process) == "done"
    assert seen == ["s1", "s2"]


def test_transient_error_stops_the_pass_without_counting(tmp_path):
    state = StateDir(tmp_path).ensure()
    path = add(state, "s1")

    assert run(state, lambda p, e: Outcome.TRANSIENT) == "stopped"
    assert queue.load(path).attempts == 0


def test_failing_entry_is_tried_once_per_run_and_parked_after_three(tmp_path):
    state = StateDir(tmp_path).ensure()
    path = add(state, "s1")
    calls = []

    def broken(p, e):
        calls.append(e.session_id)
        raise RuntimeError("boom")

    for _ in range(MAX_ATTEMPTS):
        run(state, broken)

    assert calls == ["s1"] * MAX_ATTEMPTS
    assert not path.exists()
    assert (state.failed / path.name).exists()


def test_dry_run_writes_a_bundle_without_tool_output_or_secrets(tmp_path):
    config = Config(vault=tmp_path / "vault", state_dir=tmp_path / "state")
    state = StateDir(config.state_dir).ensure()
    add(state, "s1", "tool-output-secrets.jsonl")

    [bundle] = dry_run(config)
    text = bundle.read_text()

    assert bundle.parent.parent == state.work
    assert "session_id: s1" in text
    assert "No project" in text
    assert "Lies README.md" in text
    assert "sk-ant-" not in text and "ghp_" not in text and "Hinweis an KI-Assistenten" not in text


def test_entry_without_new_conversation_writes_no_bundle(tmp_path):
    config = Config(vault=tmp_path / "vault", state_dir=tmp_path / "state", min_user_messages=1)
    state = StateDir(config.state_dir).ensure()
    path = add(state, "s1")
    entry = queue.load(path)
    from dory.condense import condense

    state.mark_seen(condense(Path(entry.transcript_copy), min_user_messages=1).uuids)

    bundle, condensed = prepare(entry, config, state)

    assert bundle is None
    assert condensed.text == ""


def test_project_survives_removal_of_the_worktree_before_processing(tmp_path):
    import subprocess

    repo = tmp_path / "ai-assistant-hub"
    repo.mkdir()
    for args in (
        ["init", "-q"],
        ["-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "--allow-empty", "-m", "i"],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    worktree = tmp_path / "herdr-worktree"
    subprocess.run(
        ["git", "worktree", "add", "-q", str(worktree)], cwd=repo, check=True, capture_output=True
    )
    config = Config(vault=tmp_path / "vault", state_dir=tmp_path / "state", min_user_messages=1)
    state = StateDir(config.state_dir).ensure()
    path = queue.enqueue(
        state,
        session_id="s1",
        transcript=FIXTURES / "resume-compact.jsonl",
        cwd=str(worktree),
        reason="clear",
    )
    subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo, check=True)

    bundle, _ = prepare(queue.load(path), config, state)

    assert "- name: ai-assistant-hub" in bundle.read_text()


def test_unreadable_entry_is_parked_and_the_queue_moves_on(tmp_path):
    state = StateDir(tmp_path).ensure()
    broken = state.queue / "00000000-broken.json"
    broken.write_text("{not json")
    add(state, "s1")

    assert run(state, lambda p, e: Outcome.DONE) == "done"
    assert (state.failed / broken.name).exists()
    assert len(list(state.done.glob("*.json"))) == 1
