import json
from datetime import date
from pathlib import Path

import pytest

from dory import baseline, queue, scopes
from dory.config import Config
from dory.frontmatter import read_frontmatter
from dory.ingest import RunResult, make_process
from dory.project import Project
from dory.state import StateDir
from dory.worker import run

FIXTURES = Path(__file__).parent / "fixtures"
TRANSCRIPT = FIXTURES / "transcripts" / "tool-output-secrets.jsonl"
HUB = Project(name="hub", root=Path("/repos/hub"))
KNOWLEDGE = """---
type: knowledge
domain: work
paths: ["/repos/hub"]
summary: The hub runs the assistants.
updated: 2026-10-18
---
## Pitfalls
- **Loki listens on port 3100.** It clashes with Grafana.
- **The probe script needs bash 5.** macOS ships bash 3.2.
"""


@pytest.fixture
def vault(tmp_path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "hub").mkdir(parents=True)
    (vault / "projects" / "hub" / "knowledge.md").write_text(KNOWLEDGE)
    (vault / "projects" / "hub" / "notes.md").write_text(
        "---\ntype: notes\n---\n- 2026-10-18: mine\n"
    )
    (vault / "projects" / "hub" / "Loki lauscht auf Port 3100.md").write_text("old 0.3.0 note\n")
    return vault


def prepared(vault: Path, tmp_path: Path) -> tuple[Path, list[Path]]:
    knowledge = scopes.knowledge_files(HUB)
    baseline.create_skeletons(vault, HUB, date(2026, 10, 19))
    target = tmp_path / "baseline"
    baseline.capture(vault, target, knowledge)
    return target, knowledge


def test_missing_knowledge_files_get_a_skeleton_and_existing_ones_stay(tmp_path):
    vault = tmp_path / "vault"
    (vault / "general").mkdir(parents=True)
    (vault / "general" / "knowledge.md").write_text("---\ntype: knowledge\n---\n- **Kept.**\n")

    baseline.create_skeletons(vault, HUB, date(2026, 10, 19))

    assert read_frontmatter(vault / "projects" / "hub" / "knowledge.md") == {
        "type": "knowledge",
        "domain": "work",
        "paths": ["/repos/hub"],
        "updated": "2026-10-19",
    }
    assert read_frontmatter(vault / "private" / "knowledge.md")["domain"] == "private"
    assert "paths" not in read_frontmatter(vault / "private" / "knowledge.md")
    assert (vault / "general" / "knowledge.md").read_text().endswith("- **Kept.**\n")


def test_a_project_marked_private_in_an_earlier_version_stays_private(tmp_path):
    vault = tmp_path / "vault"
    overview = vault / "projects" / "hub" / "hub.md"
    overview.parent.mkdir(parents=True)
    overview.write_text("---\ntype: project\ndomain: private\n---\n## Knowledge\n")

    baseline.create_skeletons(vault, HUB, date(2026, 10, 19))

    assert read_frontmatter(vault / "projects" / "hub" / "knowledge.md")["domain"] == "private"


def test_a_private_projects_run_may_not_write_the_general_file():
    assert scopes.knowledge_files(HUB, "private") == [
        Path("projects/hub/knowledge.md"),
        Path("private/knowledge.md"),
    ]


def test_a_session_without_project_has_only_the_general_and_private_files():
    assert scopes.knowledge_files(None) == [
        Path("general/knowledge.md"),
        Path("private/knowledge.md"),
    ]


def test_the_run_cannot_change_type_domain_or_paths(vault, tmp_path):
    target, knowledge = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    path.write_text(
        KNOWLEDGE.replace("domain: work", "domain: private").replace("type: knowledge\n", "")
    )

    changes = baseline.check(vault, target, knowledge)

    meta = read_frontmatter(path)
    assert (meta["type"], meta["domain"], meta["paths"]) == ("knowledge", "work", ["/repos/hub"])
    assert meta["summary"] == "The hub runs the assistants."  # the worker's own keys stay
    assert {
        "change": "restored",
        "file": "projects/hub/knowledge.md",
        "lead": "frontmatter: domain, type",
    } in changes


def test_a_dropped_frontmatter_is_put_back_in_front_of_the_entries(vault, tmp_path):
    target, knowledge = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    path.write_text("## Pitfalls\n- **Loki listens on port 3100.** It clashes with Grafana.\n")

    baseline.check(vault, target, knowledge)

    text = path.read_text()
    assert read_frontmatter(path)["domain"] == "work"
    assert text.endswith("## Pitfalls\n- **Loki listens on port 3100.** It clashes with Grafana.\n")


def test_a_changed_notes_file_is_restored(vault, tmp_path):
    target, knowledge = prepared(vault, tmp_path)
    notes = vault / "projects" / "hub" / "notes.md"
    original = notes.read_bytes()
    notes.write_text("---\ntype: notes\n---\n- rewritten by the run\n")

    changes = baseline.check(vault, target, knowledge)

    assert notes.read_bytes() == original
    assert {
        "change": "restored",
        "file": "projects/hub/notes.md",
        "lead": "the user's notes",
    } in changes


def test_files_of_an_earlier_version_and_new_files_are_reported(vault, tmp_path):
    target, knowledge = prepared(vault, tmp_path)
    (vault / "projects" / "hub" / "Loki lauscht auf Port 3100.md").write_text("extended\n")
    (vault / "projects" / "hub" / "hub.md").write_text("an overview again\n")
    (vault / "projects" / "other").mkdir()
    (vault / "projects" / "other" / "knowledge.md").write_text("another project's file\n")

    changes = baseline.check(vault, target, knowledge)

    unexpected = sorted((c["file"], c["lead"]) for c in changes if c["change"] == "unexpected")
    assert unexpected == [
        ("projects/hub/Loki lauscht auf Port 3100.md", "changed"),
        ("projects/hub/hub.md", "created"),
        ("projects/other/knowledge.md", "created"),
    ]


def test_entry_changes_are_reported_per_file(vault, tmp_path):
    target, knowledge = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    path.write_text(
        KNOWLEDGE.replace("port 3100", "port 3200").replace(
            "- **The probe script needs bash 5.** macOS ships bash 3.2.\n", ""
        )
    )

    changes = baseline.check(vault, target, knowledge)

    assert changes == [
        {
            "change": "changed",
            "file": "projects/hub/knowledge.md",
            "lead": "Loki listens on port 3200.",
            "was": "Loki listens on port 3100.",
        },
        {
            "change": "removed",
            "file": "projects/hub/knowledge.md",
            "lead": "The probe script needs bash 5.",
        },
    ]


def test_a_file_the_checks_cannot_read_is_a_failure_and_the_rest_still_runs(vault, tmp_path):
    target, knowledge = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    notes = vault / "projects" / "hub" / "notes.md"
    original = notes.read_bytes()
    notes.write_text("rewritten\n")
    path.chmod(0o000)
    try:
        changes = baseline.check(vault, target, knowledge)
    finally:
        path.chmod(0o644)

    failed = [c for c in changes if c["change"] == "failed"]
    assert failed and all(c["file"] == "projects/hub/knowledge.md" for c in failed)
    assert notes.read_bytes() == original


def test_a_killed_attempt_keeps_its_baseline_and_a_checked_one_takes_a_new_one(vault, tmp_path):
    target, knowledge = prepared(vault, tmp_path)
    knowledge_file = vault / "projects" / "hub" / "knowledge.md"
    copy = target / "files" / "projects" / "hub" / "knowledge.md"
    knowledge_file.write_text("changed by an attempt that was killed before its checks\n")

    baseline.capture(vault, target, knowledge)
    assert copy.read_text() == KNOWLEDGE

    baseline.mark_checked(target)
    baseline.capture(vault, target, knowledge)
    assert copy.read_text().startswith("changed by an attempt")


def test_a_dangling_link_in_a_scope_folder_does_not_stop_the_checks(vault, tmp_path):
    (vault / "projects" / "hub" / "gone.md").symlink_to(tmp_path / "nowhere.md")
    target, knowledge = prepared(vault, tmp_path)

    assert baseline.check(vault, target, knowledge) == []


# Through the worker, with a fake `claude -p`.


@pytest.fixture
def setup(tmp_path):
    config = Config(vault=tmp_path / "vault", state_dir=tmp_path / "state", min_user_messages=1)
    state = StateDir(config.state_dir).ensure()
    path = queue.enqueue(
        state, session_id="abc12345-x", transcript=TRANSCRIPT, cwd="/tmp", reason="clear"
    )
    general = config.vault / "general"
    general.mkdir(parents=True)
    (general / "knowledge.md").write_text(KNOWLEDGE.replace('paths: ["/repos/hub"]\n', ""))
    return config, state, path


def success() -> str:
    return (FIXTURES / "claude-output" / "success.json").read_text()


def rate_limit() -> str:
    return (FIXTURES / "claude-output" / "rate-limit-429-synthetic.json").read_text()


class Attempts:
    """A first attempt that drops an entry and hits the rate limit, then a successful one."""

    def __init__(self, vault: Path, first_edit=None):
        self.vault = vault
        self.first_edit = first_edit or self.drop_probe_entry
        self.calls = 0

    def drop_probe_entry(self) -> None:
        path = self.vault / "general" / "knowledge.md"
        path.write_text(
            path.read_text().replace(
                "- **The probe script needs bash 5.** macOS ships bash 3.2.\n", ""
            )
        )

    def __call__(self, command, cwd, env, timeout):
        self.calls += 1
        bundle_dir = Path(command[command.index("--add-dir") + 1])
        if self.calls == 1:
            self.first_edit()
            return RunResult(returncode=0, stdout=rate_limit())
        note = self.vault / (bundle_dir / "task.md").read_text().split("`")[1]
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("---\ntype: session\n---\n")
        return RunResult(returncode=0, stdout=success())


def last_log(state: StateDir) -> dict:
    return json.loads((state.root / "runs.log").read_text().splitlines()[-1])


def test_each_attempt_reports_its_own_changes_and_keeps_edits_made_in_between(setup):
    config, state, path = setup
    notes = config.vault / "general" / "notes.md"
    notes.write_text("---\ntype: notes\n---\n- 2026-10-18: first\n")
    runner = Attempts(config.vault)

    run(state, make_process(config, state, runner))  # drops an entry, then the rate limit
    first = last_log(state)
    notes.write_text(notes.read_text() + "- 2026-10-19: typed in while the entry waited\n")
    run(state, make_process(config, state, runner))

    probe = {
        "change": "removed",
        "file": "general/knowledge.md",
        "lead": "The probe script needs bash 5.",
    }
    assert first["outcome"] == "transient" and probe in first["vault_changes"]
    second = last_log(state)
    assert second["outcome"] == "done" and probe not in second.get("vault_changes", [])
    assert "typed in while the entry waited" in notes.read_text()
    assert len(list((state.root / "snapshots").iterdir())) == 2  # the first attempt changed it
    assert not (state.baselines / path.stem).exists()  # the entry left the queue


def test_a_kept_baseline_is_checked_even_when_the_next_attempt_changes_nothing(setup):
    config, state, path = setup
    notes = config.vault / "general" / "notes.md"
    notes.write_text("---\ntype: notes\n---\n- 2026-10-18: mine\n")
    knowledge = scopes.knowledge_files(None)
    baseline.create_skeletons(config.vault, None, date(2026, 10, 19))
    baseline.capture(config.vault, state.baselines / path.stem, knowledge)
    notes.write_text("rewritten by a run that was killed before its checks\n")

    def rate_limited(command, cwd, env, timeout):
        return RunResult(returncode=0, stdout=rate_limit())

    run(state, make_process(config, state, rate_limited))

    assert notes.read_text().endswith("- 2026-10-18: mine\n")
    restored = {"change": "restored", "file": "general/notes.md", "lead": "the user's notes"}
    assert restored in last_log(state)["vault_changes"]


def test_a_claude_that_does_not_start_leaves_no_unchecked_baseline(setup):
    config, state, path = setup

    def missing_claude(command, cwd, env, timeout):
        raise FileNotFoundError("claude")

    run(state, make_process(config, state, missing_claude))

    assert (state.baselines / path.stem / "CHECKED").exists()


def test_skeletons_exist_before_the_run(setup):
    config, state, _ = setup
    seen = []

    def claude(command, cwd, env, timeout):
        seen.append(
            sorted(str(p.relative_to(config.vault)) for p in config.vault.rglob("knowledge.md"))
        )
        return RunResult(returncode=0, stdout=rate_limit())

    run(state, make_process(config, state, claude))

    assert seen == [["general/knowledge.md", "private/knowledge.md"]]


def test_a_failing_check_leaves_the_outcome_and_is_logged(setup):
    config, state, _ = setup
    path = config.vault / "general" / "knowledge.md"

    def lock_file():
        path.write_text("rewritten without frontmatter\n")
        path.chmod(0o000)

    runner = Attempts(config.vault, first_edit=lock_file)
    try:
        run(state, make_process(config, state, runner))
    finally:
        path.chmod(0o644)

    log = last_log(state)
    assert log["outcome"] == "transient"
    assert any(
        c["change"] == "failed" and c["file"] == "general/knowledge.md"
        for c in log["vault_changes"]
    )
