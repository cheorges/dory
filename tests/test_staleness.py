import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dory import staleness
from dory.state import StateDir

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def write(vault: Path, relative: str, text: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def knowledge(root: Path, body: str) -> str:
    return f'---\ntype: knowledge\ndomain: work\npaths: ["{root}"]\n---\n{body}'


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "code" / "hub"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "deploy.sh").write_text("#!/bin/sh\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def test_observe_dates_new_entries_and_forgets_vanished_ones(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    topic = write(vault, "notes/GitHub.md", "---\ntype: topic\n---\n- **A.** x\n- **B.** y\n")
    staleness.observe(state, vault, NOW)
    topic.write_text("---\ntype: topic\n---\n- **A.** x\n")
    staleness.observe(state, vault, NOW + timedelta(days=1))

    store = staleness.load(state)
    assert set(store["notes/GitHub.md"]) == {"a"}
    assert store["notes/GitHub.md"]["a"]["added"] == NOW.isoformat()


def test_record_keeps_the_added_date_across_a_new_lead(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    topic = write(vault, "notes/X.md", "---\ntype: topic\n---\n- **Port 3100.** x\n")
    staleness.observe(state, vault, NOW)
    topic.write_text("---\ntype: topic\n---\n- **Port 3200.** x\n")
    later = NOW + timedelta(days=5)
    changes = [
        {"change": "changed", "file": "notes/X.md", "lead": "Port 3200.", "was": "Port 3100."}
    ]

    staleness.record(state, changes, "entry-2", later)
    staleness.observe(state, vault, later)

    record = staleness.load(state)["notes/X.md"]["port 3200"]
    assert (record["added"], record["changed"], record["by"]) == (
        NOW.isoformat(),
        later.isoformat(),
        "entry-2",
    )


def test_flags_old_entries_missing_paths_and_newer_changes(tmp_path):
    state, vault, root = StateDir(tmp_path / "state").ensure(), tmp_path / "vault", repo(tmp_path)
    write(
        vault,
        "projects/hub/knowledge.md",
        knowledge(
            root,
            "## Pitfalls\n- **Run `scripts/deploy.sh` first.** ok\n"
            "- **Run `scripts/gone.sh` first.** stale\n"
            "- **Ask `cheorges/other-repo` on GitHub.** not a repo path\n",
        ),
    )
    write(vault, "notes/Old.md", "---\ntype: topic\n---\n- **Old fact.** x\n")
    staleness.observe(state, vault, NOW - timedelta(days=120))
    staleness.record(
        state,
        [
            {
                "change": "added",
                "file": "projects/hub/knowledge.md",
                "lead": "Run `scripts/deploy.sh` first.",
            }
        ],
        "entry-9",
        NOW,
    )

    flags = staleness.flags(
        state, vault, session_ended=NOW - timedelta(days=1), entry_id="e1", now=NOW
    )

    hub = flags["projects/hub/knowledge.md"]
    assert hub["run `scripts/gone.sh` first"] == [
        "missing path `scripts/gone.sh`",
        "unchanged since 2026-06-26",
    ]
    assert hub["run `scripts/deploy.sh` first"] == ["changed after this session"]
    assert hub["ask `cheorges/other-repo` on github"] == ["unchanged since 2026-06-26"]
    assert flags["notes/Old.md"]["old fact"] == ["unchanged since 2026-06-26"]


def test_an_entry_the_same_entry_changed_is_not_newer(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    write(vault, "notes/X.md", "---\ntype: topic\n---\n- **A.** x\n")
    staleness.record(state, [{"change": "added", "file": "notes/X.md", "lead": "A."}], "e1", NOW)

    flags = staleness.flags(
        state, vault, session_ended=NOW - timedelta(days=1), entry_id="e1", now=NOW
    )
    assert flags.get("notes/X.md", {}).get("a") is None


def test_mark_missing_adds_a_marker_to_the_entry_only(tmp_path):
    root = repo(tmp_path)
    text = (
        "## Pitfalls\n- **Run `scripts/gone.sh` first.** stale\n  more\n"
        "- **Run `scripts/deploy.sh`.** ok\n"
    )

    marked = staleness.mark_missing(text, root)

    assert (
        "- **Run `scripts/gone.sh` first.** stale "
        "(check: `scripts/gone.sh` no longer exists in the repository)\n  more" in marked
    )
    assert "- **Run `scripts/deploy.sh`.** ok\n" in marked
    assert staleness.mark_missing(text, None) == text


def test_counts_for_status(tmp_path):
    state, vault, root = StateDir(tmp_path / "state").ensure(), tmp_path / "vault", repo(tmp_path)
    write(vault, "projects/hub/knowledge.md", knowledge(root, "- **Run `scripts/gone.sh`.** x\n"))
    write(vault, "notes/Old.md", "---\ntype: topic\n---\n- **Old.** x\n")
    staleness.observe(state, vault, NOW - timedelta(days=100))

    assert staleness.counts(state, vault, NOW) == {"missing path": 1, "unchanged": 2}


def test_the_first_sighting_of_a_vault_dates_nothing_as_changed(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    write(vault, "notes/X.md", "---\ntype: topic\n---\n- **A.** x\n")
    staleness.observe(state, vault, NOW)

    flags = staleness.flags(
        state, vault, session_ended=NOW - timedelta(days=1), entry_id="e1", now=NOW
    )
    assert flags == {}


def test_an_edit_of_the_text_under_the_same_lead_counts_as_a_change(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    topic = write(vault, "notes/X.md", "---\ntype: topic\n---\n- **A.** x\n")
    staleness.observe(state, vault, NOW - timedelta(days=200))
    topic.write_text("---\ntype: topic\n---\n- **A.** x, and more the user wrote\n")
    staleness.observe(state, vault, NOW)

    flags = staleness.flags(
        state, vault, session_ended=NOW - timedelta(days=1), entry_id="e1", now=NOW
    )
    assert flags["notes/X.md"]["a"] == ["changed after this session"]


def test_a_runs_own_change_stays_its_own_after_the_sync(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    topic = write(vault, "notes/X.md", "---\ntype: topic\n---\n- **A.** x\n")
    staleness.observe(state, vault, NOW - timedelta(days=1))
    topic.write_text("---\ntype: topic\n---\n- **A.** y\n")
    staleness.record(state, [{"change": "changed", "file": "notes/X.md", "lead": "A."}], "e1", NOW)
    staleness.observe(state, vault, NOW)

    assert staleness.load(state)["notes/X.md"]["a"]["by"] == "e1"


def test_a_path_under_an_ignored_folder_that_exists_is_not_missing(tmp_path):
    root = repo(tmp_path)
    (root / ".gitignore").write_text("vendor/\n")
    (root / "vendor").mkdir()
    (root / "vendor" / "lib.py").write_text("x\n")

    text = "- **Patch `vendor/lib.py`.** x\n- **Run `vendor/gone.py`.** y\n"
    marked = staleness.mark_missing(text, root)

    assert "`vendor/lib.py`.** x\n" in marked
    assert "`vendor/gone.py` no longer exists" in marked


def test_the_marker_lands_on_its_own_entry(tmp_path):
    root = repo(tmp_path)
    text = (
        "- **Run `scripts/gone.sh`.** first, then more\n"
        "- **Run `scripts/gone.sh`.**\n"
        "- **Run `scripts/gone.sh`.**\n"
    )

    lines = staleness.mark_missing(text, root).splitlines()

    assert all(line.count("no longer exists") == 1 for line in lines), lines


def test_no_git_means_no_markers(tmp_path, monkeypatch):
    root = repo(tmp_path)

    def broken(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(staleness.subprocess, "run", broken)
    text = "- **Run `scripts/gone.sh`.** x\n"
    assert staleness.mark_missing(text, root) == text


def test_an_earlier_cut_of_the_same_session_is_not_newer_than_it(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    write(vault, "notes/X.md", "---\ntype: topic\n---\n- **A.** x\n")
    staleness.observe(state, vault, NOW - timedelta(days=200))
    saved = "20261024T100000.000000Z-0105a494-1400-41f1-8b49-d1d7bf2e1160"
    ended = "20261024T103000.000000Z-0105a494-1400-41f1-8b49-d1d7bf2e1160"
    staleness.record(state, [{"change": "changed", "file": "notes/X.md", "lead": "A."}], saved, NOW)
    staleness.observe(state, vault, NOW)

    same = staleness.flags(
        state, vault, session_ended=NOW - timedelta(minutes=5), entry_id=ended, now=NOW
    )
    other = staleness.flags(
        state,
        vault,
        session_ended=NOW - timedelta(minutes=5),
        entry_id="20261024T103000.000000Z-ffffffff-0000-0000-0000-000000000000",
        now=NOW,
    )

    assert same == {}
    assert other["notes/X.md"]["a"] == ["changed after this session"]


def test_a_killed_runs_edits_count_as_its_entrys_not_the_users(tmp_path):
    state, vault = StateDir(tmp_path / "state").ensure(), tmp_path / "vault"
    topic = write(vault, "notes/X.md", "---\ntype: topic\n---\n- **A.** x\n")
    staleness.observe(state, vault, NOW - timedelta(days=200))
    topic.write_text("---\ntype: topic\n---\n- **A.** x, half rewritten by a killed run\n")

    staleness.observe(state, vault, NOW, by="e1")

    flags = staleness.flags(
        state, vault, session_ended=NOW - timedelta(days=1), entry_id="e1", now=NOW
    )
    assert flags == {}
    assert staleness.load(state)["notes/X.md"]["a"]["by"] == "e1"
