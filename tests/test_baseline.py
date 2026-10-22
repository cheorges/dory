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
TOPIC = """---
type: topic
updated: 2026-10-18
---
## Pitfalls
- **Overwriting a Notion page deletes its embedded databases.** Append blocks instead.
- **The Notion API returns at most 100 blocks per call.** Page through the rest.
"""
SHOPPING_LIST = """---
type: list
summary: Shopping list
updated: 2026-10-18
---
- [ ] Milk
- [ ] Bread
- [ ] Coffee
"""


def write(vault: Path, relative: str, text: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def vault(tmp_path) -> Path:
    vault = tmp_path / "vault"
    write(vault, "projects/hub/knowledge.md", KNOWLEDGE)
    write(vault, "projects/hub/notes/Deploy only on fridays.md", "---\ntype: note\n---\nMine.\n")
    write(vault, "projects/hub/notes/Release steps.md", "---\ntype: note\n---\nAlso mine.\n")
    write(vault, "projects/hub/Loki lauscht auf Port 3100.md", "old 0.3.0 note\n")
    write(vault, "notes/Notion.md", TOPIC)
    write(vault, "notes/Shopping list.md", SHOPPING_LIST)
    write(vault, "library/Employment contract.md", "Notice period three months.\n")
    write(vault, "library/family/Holidays.md", "Summer in Ticino.\n")
    return vault


def prepared(vault: Path, tmp_path: Path, *, topics_allowed: bool = True) -> Path:
    baseline.create_skeletons(vault, HUB, date(2026, 10, 19))
    target = tmp_path / "baseline"
    baseline.capture(vault, target, HUB, topics_allowed=topics_allowed)
    return target


def unexpected(changes: list[dict]) -> list[tuple[str, str]]:
    return sorted((c["file"], c["lead"]) for c in changes if c["change"] == "unexpected")


def test_the_project_gets_a_skeleton_and_an_empty_library(tmp_path):
    vault = tmp_path / "vault"

    baseline.create_skeletons(vault, HUB, date(2026, 10, 19))

    assert read_frontmatter(vault / "projects" / "hub" / "knowledge.md") == {
        "type": "knowledge",
        "domain": "work",
        "paths": ["/repos/hub"],
        "updated": "2026-10-19",
    }
    assert (vault / "library").is_dir() and not list((vault / "library").iterdir())
    assert not (vault / "general").exists()


def test_an_existing_knowledge_file_and_library_stay_as_they_are(vault):
    before = (vault / "projects" / "hub" / "knowledge.md").read_text()

    baseline.create_skeletons(vault, HUB, date(2026, 10, 19))
    baseline.create_skeletons(vault, None, date(2026, 10, 19))

    assert (vault / "projects" / "hub" / "knowledge.md").read_text() == before
    assert sorted(p.name for p in (vault / "library").rglob("*.md")) == [
        "Employment contract.md",
        "Holidays.md",
    ]


def test_a_project_marked_private_in_an_earlier_version_stays_private(tmp_path):
    vault = tmp_path / "vault"
    write(vault, "projects/hub/hub.md", "---\ntype: project\ndomain: private\n---\n## Knowledge\n")

    baseline.create_skeletons(vault, HUB, date(2026, 10, 19))

    assert read_frontmatter(vault / "projects" / "hub" / "knowledge.md")["domain"] == "private"


def test_the_knowledge_file_belongs_to_a_known_project_only():
    assert scopes.knowledge_file(HUB) == Path("projects/hub/knowledge.md")
    assert scopes.knowledge_file(None) is None
    assert scopes.knowledge_file(Project(name="", root=Path("/repos/new"))) is None


def test_the_run_cannot_change_type_domain_or_paths(vault, tmp_path):
    target = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    path.write_text(
        KNOWLEDGE.replace("domain: work", "domain: private").replace("type: knowledge\n", "")
    )

    changes = baseline.check(vault, target)

    meta = read_frontmatter(path)
    assert (meta["type"], meta["domain"], meta["paths"]) == ("knowledge", "work", ["/repos/hub"])
    assert meta["summary"] == "The hub runs the assistants."  # the worker's own keys stay
    assert {
        "change": "restored",
        "file": "projects/hub/knowledge.md",
        "lead": "frontmatter: domain, type",
    } in changes


def test_a_dropped_frontmatter_is_put_back_in_front_of_the_entries(vault, tmp_path):
    target = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    path.write_text("## Pitfalls\n- **Loki listens on port 3100.** It clashes with Grafana.\n")

    baseline.check(vault, target)

    text = path.read_text()
    assert read_frontmatter(path)["domain"] == "work"
    assert text.endswith("## Pitfalls\n- **Loki listens on port 3100.** It clashes with Grafana.\n")


def test_project_notes_a_run_touched_are_reported_and_left_as_the_run_left_them(vault, tmp_path):
    target = prepared(vault, tmp_path)
    notes = vault / "projects" / "hub" / "notes"
    (notes / "Deploy only on fridays.md").write_text("rewritten by the run\n")
    (notes / "Release steps.md").unlink()
    (notes / "Written by the run.md").write_text("new\n")

    changes = baseline.check(vault, target)

    assert unexpected(changes) == [
        ("projects/hub/notes/Deploy only on fridays.md", "changed"),
        ("projects/hub/notes/Release steps.md", "deleted"),
        ("projects/hub/notes/Written by the run.md", "created"),
    ]
    assert (notes / "Deploy only on fridays.md").read_text() == "rewritten by the run\n"
    assert not (notes / "Release steps.md").exists()
    assert not [c for c in changes if c["change"] == "restored"]


def test_files_of_an_earlier_version_and_other_projects_files_are_reported(vault, tmp_path):
    target = prepared(vault, tmp_path)
    write(vault, "projects/hub/Loki lauscht auf Port 3100.md", "extended\n")
    write(vault, "projects/hub/hub.md", "an overview again\n")
    write(vault, "projects/other/knowledge.md", "another project's file\n")

    changes = baseline.check(vault, target)

    assert unexpected(changes) == [
        ("projects/hub/Loki lauscht auf Port 3100.md", "changed"),
        ("projects/hub/hub.md", "created"),
        ("projects/other/knowledge.md", "created"),
    ]


def test_library_files_a_run_touched_are_reported_and_dory_writes_nothing_there(vault, tmp_path):
    target = prepared(vault, tmp_path)
    library = vault / "library"
    (library / "Employment contract.md").write_text("changed by the run\n")
    (library / "family" / "Holidays.md").unlink()
    (library / "family" / "New.md").write_text("created by the run\n")
    (library / "scan.pdf").write_bytes(b"an attachment, not a note")

    changes = baseline.check(vault, target)

    assert unexpected(changes) == [
        ("library/Employment contract.md", "changed"),
        ("library/family/Holidays.md", "deleted"),
        ("library/family/New.md", "created"),
    ]
    assert (library / "Employment contract.md").read_text() == "changed by the run\n"
    assert not (library / "family" / "Holidays.md").exists()


def test_a_kept_baseline_of_the_previous_layout_is_discarded(vault, tmp_path):
    target = tmp_path / "baseline"
    write(target, "files/private/knowledge.md", "---\ntype: knowledge\ndomain: private\n---\n")
    (target / "knowledge-files.json").write_text(json.dumps(["private/knowledge.md"]))
    (target / "hashes.json").write_text("{}")
    (target / "COMPLETE").touch()
    write(vault, "private/knowledge.md", "the user's private note now\n")

    kept = baseline.capture(vault, target, HUB, topics_allowed=True)
    changes = baseline.check(vault, target)

    assert kept is False
    assert not (target / "files" / "private").exists()
    assert (vault / "private" / "knowledge.md").read_text() == "the user's private note now\n"
    assert changes == []


def test_entry_changes_of_the_knowledge_file_are_reported(vault, tmp_path):
    target = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    path.write_text(
        KNOWLEDGE.replace("port 3100", "port 3200").replace(
            "- **The probe script needs bash 5.** macOS ships bash 3.2.\n", ""
        )
    )

    changes = baseline.check(vault, target)

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


def test_topic_files_are_compared_entry_by_entry_and_lists_are_not(vault, tmp_path):
    write(vault, "notes/Untyped.md", "## Facts\n- **Grafana listens on port 3100.** Since 2024.\n")
    write(vault, "notes/archive/Old.md", "---\ntype: topic\n---\n- **Old.** Kept aside.\n")
    write(vault, "notes/diagram.png", "not a note")
    target = prepared(vault, tmp_path)
    write(vault, "notes/Notion.md", TOPIC.replace(TOPIC.splitlines()[-1] + "\n", ""))
    untyped = vault / "notes" / "Untyped.md"
    untyped.write_text(untyped.read_text() + "- **Grafana needs a reverse proxy.** For TLS.\n")
    write(vault, "notes/Docker.md", "---\ntype: topic\n---\n- **Docker needs 4 GB.** At least.\n")
    write(vault, "notes/Shopping list.md", SHOPPING_LIST.replace("- [ ] Milk\n- [ ] Bread\n", ""))
    write(vault, "notes/archive/Old.md", "rewritten\n")
    write(vault, "notes/diagram.png", "changed")

    changes = baseline.check(vault, target)

    assert changes == [
        {"change": "added", "file": "notes/Docker.md", "lead": "Docker needs 4 GB."},
        {
            "change": "removed",
            "file": "notes/Notion.md",
            "lead": "The Notion API returns at most 100 blocks per call.",
        },
        {"change": "added", "file": "notes/Untyped.md", "lead": "Grafana needs a reverse proxy."},
    ]


def test_the_type_of_a_file_in_notes_is_kept_and_a_new_file_gets_one(vault, tmp_path):
    target = prepared(vault, tmp_path)
    write(vault, "notes/Shopping list.md", SHOPPING_LIST.replace("type: list", "type: topic"))
    write(vault, "notes/Postgres.md", "## Facts\n- **Postgres runs on 5432.** Default.\n")

    changes = baseline.check(vault, target)

    assert read_frontmatter(vault / "notes" / "Shopping list.md")["type"] == "list"
    assert (vault / "notes" / "Postgres.md").read_text().startswith("---\ntype: topic\n---\n")
    restored = sorted((c["file"], c["lead"]) for c in changes if c["change"] == "restored")
    assert restored == [
        ("notes/Postgres.md", "frontmatter: type"),
        ("notes/Shopping list.md", "frontmatter: type"),
    ]


def test_a_list_type_the_run_gives_an_untyped_topic_is_taken_back(vault, tmp_path):
    untyped = write(vault, "notes/Grafana.md", "- **Grafana uses 3000.** Default.\n- **B.** C.\n")
    target = prepared(vault, tmp_path)
    untyped.write_text("---\ntype: list\n---\n- **Grafana uses 3000.** Default.\n")

    changes = baseline.check(vault, target)

    assert untyped.read_text() == "- **Grafana uses 3000.** Default.\n"
    assert {
        "change": "restored",
        "file": "notes/Grafana.md",
        "lead": "frontmatter: type",
    } in changes
    assert {"change": "removed", "file": "notes/Grafana.md", "lead": "B."} in changes


def test_an_unreadable_file_in_notes_does_not_stop_the_baseline(vault, tmp_path):
    locked = write(vault, "notes/Locked.md", "---\ntype: topic\n---\n- **Locked.** Yes.\n")
    locked.chmod(0o000)
    try:
        target = prepared(vault, tmp_path)
        changes = baseline.check(vault, target)
    finally:
        locked.chmod(0o644)

    failed = [c for c in changes if c["change"] == "failed"]
    assert failed and all(c["file"] == "notes/Locked.md" for c in failed)


def test_a_file_unreadable_when_the_baseline_was_taken_is_reported_once_and_left_alone(
    vault, tmp_path
):
    locked = write(vault, "notes/Locked.md", "- **Locked.** Yes.\n")
    locked.chmod(0o000)
    try:
        target = prepared(vault, tmp_path, topics_allowed=False)
    finally:
        locked.chmod(0o644)  # readable again by the time the checks run

    changes = baseline.check(vault, target)

    assert changes == [
        {
            "change": "failed",
            "file": "notes/Locked.md",
            "lead": "not readable when the baseline was taken",
        }
    ]
    assert locked.read_text() == "- **Locked.** Yes.\n"


def test_a_new_file_in_notes_whose_name_breaks_the_rules_is_reported_and_keeps_it(vault, tmp_path):
    target = prepared(vault, tmp_path)
    write(vault, "notes/C# tips.md", "---\ntype: topic\n---\n- **Use records.** Short.\n")

    changes = baseline.check(vault, target)

    assert ("notes/C# tips.md", "name breaks the naming rules") in unexpected(changes)
    assert (vault / "notes" / "C# tips.md").exists()


def test_a_private_projects_run_that_writes_a_topic_is_reported(vault, tmp_path):
    target = prepared(vault, tmp_path, topics_allowed=False)
    notion = vault / "notes" / "Notion.md"
    notion.write_text(TOPIC + "- **Notion has no offline mode.** Plan for it.\n")
    write(vault, "notes/Docker.md", "---\ntype: topic\n---\n- **Docker needs 4 GB.** At least.\n")
    write(vault, "notes/Shopping list.md", SHOPPING_LIST + "- [ ] Butter\n")

    changes = baseline.check(vault, target)

    assert unexpected(changes) == [
        ("notes/Docker.md", "created by a private project's run"),
        ("notes/Notion.md", "changed by a private project's run"),
    ]


def test_a_file_the_checks_cannot_read_is_a_failure_and_the_rest_still_runs(vault, tmp_path):
    target = prepared(vault, tmp_path)
    path = vault / "projects" / "hub" / "knowledge.md"
    note = vault / "projects" / "hub" / "notes" / "Release steps.md"
    note.write_text("rewritten\n")
    path.chmod(0o000)
    try:
        changes = baseline.check(vault, target)
    finally:
        path.chmod(0o644)

    failed = [c for c in changes if c["change"] == "failed"]
    assert failed and all(c["file"] == "projects/hub/knowledge.md" for c in failed)
    assert ("projects/hub/notes/Release steps.md", "changed") in unexpected(changes)


def test_a_killed_attempt_keeps_its_baseline_and_a_checked_one_takes_a_new_one(vault, tmp_path):
    target = prepared(vault, tmp_path)
    knowledge_file = vault / "projects" / "hub" / "knowledge.md"
    copy = target / "files" / "projects" / "hub" / "knowledge.md"
    knowledge_file.write_text("changed by an attempt that was killed before its checks\n")

    assert baseline.capture(vault, target, HUB, topics_allowed=True) is True
    assert copy.read_text() == KNOWLEDGE

    baseline.mark_checked(target)
    assert baseline.capture(vault, target, HUB, topics_allowed=True) is False
    assert copy.read_text().startswith("changed by an attempt")


def test_a_dangling_link_in_a_watched_folder_does_not_stop_the_checks(vault, tmp_path):
    (vault / "projects" / "hub" / "gone.md").symlink_to(tmp_path / "nowhere.md")
    (vault / "library" / "gone.md").symlink_to(tmp_path / "nowhere.md")
    target = prepared(vault, tmp_path)

    assert baseline.check(vault, target) == []


def test_a_file_dory_writes_while_a_run_waits_is_not_reported(vault, tmp_path):
    config = Config(vault=vault, state_dir=tmp_path / "state")
    state = StateDir(config.state_dir).ensure()
    path = queue.enqueue(state, session_id="s1", transcript=TRANSCRIPT, cwd="/tmp", reason="x")
    kept = baseline.baseline_dir(state, path.stem)
    baseline.capture(vault, kept, HUB, topics_allowed=True)
    other = baseline.baseline_dir(state, "left-the-queue")
    baseline.capture(vault, other, HUB, topics_allowed=True)

    with baseline.notes_lock(state.baselines):
        written = write(vault, "projects/hub/notes/Added by dory.md", "---\ntype: note\n---\nx\n")
        baseline.record_dory_write(state, vault, written.relative_to(vault))
        baseline.record_dory_write(state, vault, Path("notes/Notion.md"))

    assert baseline.check(vault, kept) == []
    assert ("projects/hub/notes/Added by dory.md", "created") in unexpected(
        baseline.check(vault, other)
    )


# Through the worker, with a fake `claude -p`.


@pytest.fixture
def setup(tmp_path):
    config = Config(vault=tmp_path / "vault", state_dir=tmp_path / "state", min_user_messages=1)
    state = StateDir(config.state_dir).ensure()
    path = queue.enqueue(
        state, session_id="abc12345-x", transcript=TRANSCRIPT, cwd="/tmp", reason="clear"
    )
    write(config.vault, "notes/Probe.md", KNOWLEDGE.replace("type: knowledge", "type: topic"))
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
        path = self.vault / "notes" / "Probe.md"
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


PROBE_REMOVED = {
    "change": "removed",
    "file": "notes/Probe.md",
    "lead": "The probe script needs bash 5.",
}


def test_each_attempt_reports_its_own_changes_and_keeps_edits_made_in_between(setup):
    config, state, path = setup
    other = write(config.vault, "notes/Other.md", "---\ntype: topic\n---\n- **First.** Mine.\n")
    runner = Attempts(config.vault)

    run(state, make_process(config, state, runner))  # drops an entry, then the rate limit
    first = last_log(state)
    other.write_text(other.read_text() + "- **Typed in while the entry waited.** Mine too.\n")
    run(state, make_process(config, state, runner))

    assert first["outcome"] == "transient" and PROBE_REMOVED in first["vault_changes"]
    second = last_log(state)
    assert second["outcome"] == "done" and not second.get("vault_changes")
    assert "Typed in while the entry waited" in other.read_text()
    assert len(list((state.root / "snapshots").iterdir())) == 2  # the first attempt changed it
    assert not (state.baselines / path.stem).exists()  # the entry left the queue


def test_a_kept_baseline_is_checked_even_when_the_next_attempt_changes_nothing(setup):
    config, state, path = setup
    baseline.capture(config.vault, state.baselines / path.stem, None, topics_allowed=True)
    Attempts(config.vault).drop_probe_entry()  # by a run that was killed before its checks

    def rate_limited(command, cwd, env, timeout):
        return RunResult(returncode=0, stdout=rate_limit())

    run(state, make_process(config, state, rate_limited))

    assert PROBE_REMOVED in last_log(state)["vault_changes"]


def test_a_claude_that_does_not_start_leaves_no_unchecked_baseline(setup):
    config, state, path = setup

    def missing_claude(command, cwd, env, timeout):
        raise FileNotFoundError("claude")

    run(state, make_process(config, state, missing_claude))

    assert (state.baselines / path.stem / "CHECKED").exists()


def test_the_private_folder_exists_before_the_run_and_nothing_is_written_into_it(setup):
    config, state, _ = setup
    seen = []

    def claude(command, cwd, env, timeout):
        private = config.vault / "library"
        seen.append(
            (private.is_dir(), list(private.iterdir()), (config.vault / "general").exists())
        )
        return RunResult(returncode=0, stdout=rate_limit())

    run(state, make_process(config, state, claude))

    assert seen == [(True, [], False)]


def test_a_failing_check_leaves_the_outcome_and_is_logged(setup):
    config, state, _ = setup
    path = config.vault / "notes" / "Probe.md"

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
        c["change"] == "failed" and c["file"] == "notes/Probe.md" for c in log["vault_changes"]
    )
