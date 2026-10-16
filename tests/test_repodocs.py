import json
import os
import subprocess
import time
from pathlib import Path

from dory import queue, repodocs
from dory.bundle import build_bundle
from dory.condense import Condensed
from dory.config import Config
from dory.project import Project
from dory.state import StateDir
from dory.worker import Outcome, dry_run, run

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True, capture_output=True)


def make_repo(path: Path, claude_md: str | None = "# Repo\n") -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    if claude_md is not None:
        (path / "CLAUDE.md").write_text(claude_md)
    return path.resolve()


def record(repo: Path, name: str, text: str) -> Path:
    path = repo / "docs" / "records" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def enqueue(state: StateDir, cwd: Path, session_id: str = "s1") -> Path:
    return queue.enqueue(
        state,
        session_id=session_id,
        transcript=FIXTURES / "resume-compact.jsonl",
        cwd=str(cwd),
        reason="clear",
    )


def docs_of(state: StateDir, entry_path: Path) -> Path:
    return repodocs.docs_dir(state, entry_path.stem)


def test_long_claude_md_is_captured_completely_when_the_session_is_queued(tmp_path):
    status = "## Current Status\n\n| Story | Status |\n|---|---|\n| Matrix | In Progress |\n"
    repo = make_repo(tmp_path / "hub", "# Hub\n\n" + "x" * 9_000 + "\n\n" + status + "y" * 32_000)
    state = StateDir(tmp_path / "state").ensure()

    entry_path = enqueue(state, repo)

    copy = docs_of(state, entry_path) / "CLAUDE.md"
    assert len(copy.read_text()) > 40_000
    assert "| Matrix | In Progress |" in copy.read_text()
    assert repodocs.source(docs_of(state, entry_path)) == repo


def test_worktree_records_merge_with_the_main_repository_and_the_branch_wins(tmp_path):
    main = make_repo(tmp_path / "hub")
    record(main, "001-shared.md", "# Shared, main version\n")
    git(main, "add", ".")
    git(main, "commit", "-q", "-m", "init")
    worktree = tmp_path / "worktrees" / "feature"
    git(main, "worktree", "add", "-q", "-b", "feature", str(worktree))
    record(worktree, "001-shared.md", "# Shared, branch version\n")
    record(worktree, "044-only-on-branch.md", "# Only on the branch\n")
    record(main, "043-only-on-main.md", "# Only on main\n")
    state = StateDir(tmp_path / "state").ensure()

    entry_path = enqueue(state, worktree)

    records = docs_of(state, entry_path) / "records"
    assert sorted(p.name for p in records.iterdir()) == [
        "001-shared.md",
        "043-only-on-main.md",
        "044-only-on-branch.md",
    ]
    assert "branch version" in (records / "001-shared.md").read_text()
    assert repodocs.source(docs_of(state, entry_path)) == worktree.resolve()


def test_a_cwd_outside_the_project_falls_back_to_the_main_repository(tmp_path):
    main = make_repo(tmp_path / "hub", "# Hub rules\n")
    elsewhere = make_repo(tmp_path / "other", "# Other rules\n")
    target = tmp_path / "repo"

    source = repodocs.capture(elsewhere, main, target)

    assert source == main
    assert (target / "CLAUDE.md").read_text() == "# Hub rules\n"


def test_project_without_claude_md_and_records_is_still_bundled(tmp_path):
    repo = make_repo(tmp_path / "bare", claude_md=None)
    state = StateDir(tmp_path / "state").ensure()
    entry_path = enqueue(state, repo)
    entry = queue.load(entry_path)

    text = build_bundle(
        entry,
        Project("bare", repo),
        Condensed(text="**User:** hi"),
        docs=docs_of(state, entry_path),
    )

    assert "- CLAUDE.md: none" in text
    assert "- Records: none" in text
    assert text.rstrip().endswith("**User:** hi")


def test_copies_are_redacted_and_odd_files_are_skipped_or_cut(tmp_path):
    repo = make_repo(tmp_path / "hub", "Deploy token: ghp_" + "a" * 36 + "\n")
    outside = tmp_path / "secret-notes.md"
    outside.write_text("# Private\n")
    records = repo / "docs" / "records"
    records.mkdir(parents=True)
    (records / "001-link.md").symlink_to(outside)
    (records / "002-latin1.md").write_bytes("# Zürich\n".encode("latin-1"))
    (records / "003-huge.md").write_text("# Huge\n" + "z" * 250_000)
    (records / "diagram.png").write_bytes(b"\x89PNG\r\n")
    (records / "041-spike").mkdir()
    (records / "041-spike" / "plan.md").write_text("# Nested\n")
    target = tmp_path / "repo"

    repodocs.capture(repo, repo, target)

    assert "[REDACTED]" in (target / "CLAUDE.md").read_text()
    assert "ghp_" not in (target / "CLAUDE.md").read_text()
    names = sorted(p.name for p in (target / "records").iterdir())
    assert names == ["002-latin1.md", "003-huge.md"]
    assert "Z�rich" in (target / "records" / "002-latin1.md").read_text()
    huge = (target / "records" / "003-huge.md").read_text()
    assert len(huge) < 200_100 and huge.rstrip().endswith("characters ...]")


def test_a_secret_across_the_cut_is_redacted_whole(tmp_path):
    repo = make_repo(tmp_path / "hub")
    text = "# Long\n" + "z " * ((repodocs.MAX_CHARS - 20) // 2) + "ghp_" + "a" * 36 + "\n"
    record(repo, "001-long.md", text + "tail " * 1_000)
    target = tmp_path / "repo"

    repodocs.capture(repo, repo, target)

    copy = (target / "records" / "001-long.md").read_text()
    assert "ghp_" not in copy
    assert copy.rstrip().endswith("characters ...]")


def test_a_failed_capture_still_queues_the_session(tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "hub")
    state = StateDir(tmp_path / "state").ensure()

    def broken(cwd, project_root, target):
        (target / "records").mkdir(parents=True)  # a partial copy must not stay behind
        raise OSError("disk full")

    monkeypatch.setattr(repodocs, "capture", broken)

    entry_path = enqueue(state, repo)

    assert queue.load(entry_path).session_id == "s1"
    assert not docs_of(state, entry_path).exists()


def test_an_incomplete_capture_counts_as_not_captured(tmp_path):
    repo = make_repo(tmp_path / "hub", "# Hub\n")
    docs = tmp_path / "work" / "entry" / "repo"
    docs.mkdir(parents=True)
    (docs / "CLAUDE.md").write_text("# Hub, half copied\n")  # killed before SOURCE was written
    entry = queue.Entry("s1", "/x.jsonl", str(repo), "clear", "2026-10-15T10:00:00.000000Z")

    text = build_bundle(entry, Project("hub", repo), Condensed(text="**User:** hi"), docs=docs)

    assert repodocs.source(docs) is None
    assert "not captured" in text


def test_an_entry_written_by_a_newer_version_still_loads(tmp_path):
    state = StateDir(tmp_path / "state").ensure()
    path = enqueue(state, tmp_path)
    data = json.loads(path.read_text())
    path.write_text(json.dumps({**data, "field_from_the_future": 1}))

    assert queue.load(path).session_id == "s1"


def test_copies_go_when_the_entry_leaves_the_queue_and_stay_for_a_retry(tmp_path):
    repo = make_repo(tmp_path / "hub")
    state = StateDir(tmp_path / "state").ensure()
    outcomes = {"done": Outcome.DONE, "skip": Outcome.SKIPPED, "fail": Outcome.FAILED}
    paths = {sid: enqueue(state, repo, session_id=sid) for sid in [*outcomes, "later"]}
    seen: set[str] = set()

    def process(path, entry):
        if entry.session_id == "later":
            return Outcome.TRANSIENT
        seen.add(entry.session_id)
        return outcomes[entry.session_id]

    for _ in range(3):  # a failure is parked after three attempts
        run(state, process)

    for sid in outcomes:
        assert not docs_of(state, paths[sid]).exists(), sid
    assert docs_of(state, paths["later"]).exists()
    assert seen == set(outcomes)


def test_a_worker_run_sweeps_copies_left_by_entries_no_longer_queued(tmp_path):
    state = StateDir(tmp_path / "state").ensure()
    orphan = repodocs.docs_dir(state, "20261015T000000.000000Z-gone")
    orphan.mkdir(parents=True)
    (orphan / "CLAUDE.md").write_text("# left behind\n")
    (orphan.parent / "bundle.md").write_text("bundle")
    old = time.time() - 3600
    os.utime(orphan, (old, old))
    capturing = repodocs.docs_dir(state, "20261015T000001.000000Z-arriving")
    capturing.mkdir(parents=True)  # a hook that has not written its entry yet

    run(state, lambda path, entry: Outcome.DONE)

    assert not orphan.exists()
    assert (orphan.parent / "bundle.md").exists()
    assert capturing.exists()


def test_dry_run_copies_nothing_and_says_what_is_missing(tmp_path):
    repo = make_repo(tmp_path / "hub", "# Hub\n")
    state = StateDir(tmp_path / "state").ensure()
    entry_path = enqueue(state, repo)
    docs = docs_of(state, entry_path)
    for path in sorted(docs.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    docs.rmdir()

    config = Config(vault=tmp_path / "vault", state_dir=state.root, min_user_messages=1)
    [bundle] = dry_run(config)

    assert not docs.exists()
    assert "not captured" in bundle.read_text()
