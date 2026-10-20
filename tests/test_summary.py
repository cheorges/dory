"""Record 003, Story S4: a summary made by the worker when the files exceed the limit."""

import json
import subprocess
from pathlib import Path

import pytest

from dory import context, queue, spawn, summary
from dory.config import Config
from dory.ingest import RunResult
from dory.project import project_for_root
from dory.recall import CUT_MARKER, STALE, recall
from dory.state import StateDir
from dory.summarize import CUT, make_summarize
from dory.worker import Outcome, run

FIXTURE = Path(__file__).parent / "fixtures" / "transcripts" / "resume-compact.jsonl"
HUB = "projects/ai-assistant-hub"
NAME = "project-ai-assistant-hub"  # the context of the project, in marks, store and runs.log
BUDGET = 200  # tokens: a limit of 800 characters, a summary target of 640


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def write(vault: Path, relative: str, text: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def knowledge(vault: Path, entries: int, domain: str = "work", word: str = "holds") -> None:
    lines = "".join(f"- **Entry {i:02} {word}.** " + "x" * 40 + "\n" for i in range(entries))
    write(
        vault,
        f"{HUB}/knowledge.md",
        f"---\ntype: knowledge\ndomain: {domain}\nsummary: KoliChat\n---\n## Facts\n{lines}",
    )


class FakeRunner:
    """Stands in for `claude -p`; records each call and answers with the given results."""

    def __init__(self, *results: RunResult) -> None:
        self.results = list(results)
        self.calls: list[tuple[list[str], str]] = []

    def __call__(self, command, cwd, env, timeout, stdin) -> RunResult:
        self.calls.append((command, stdin))
        if not self.results:
            return answer("### Facts\n- Entries hold.")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def answer(text: str, cost: float = 0.001) -> RunResult:
    return RunResult(0, json.dumps({"result": text, "is_error": False, "total_cost_usd": cost}))


def failure(message: str, status: int | None = None) -> RunResult:
    data = {"result": message, "is_error": True, "total_cost_usd": 0.0002}
    if status:
        data["api_error_status"] = status
    return RunResult(1, json.dumps(data))


@pytest.fixture
def world(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    config = Config(vault=vault, state_dir=tmp_path / "state", recall_budget_tokens=BUDGET)
    state = StateDir(config.state_dir).ensure()
    hub = make_repo(tmp_path / "code" / "ai-assistant-hub")
    project_for_root(hub.resolve(), state.projects_file)
    spawned: list[bool] = []
    monkeypatch.setattr(spawn, "spawn_worker", lambda: spawned.append(True))
    return config, state, hub, spawned


def hook(cwd: Path) -> dict:
    return {"session_id": "new", "transcript_path": "/x/new.jsonl", "cwd": str(cwd)}


def runs(state: StateDir, kind: str = "summary") -> list[dict]:
    log = state.root / "runs.log"
    lines = log.read_text().splitlines() if log.is_file() else []
    return [record for line in lines if (record := json.loads(line)).get("kind") == kind]


def done_pass(state: StateDir, hub: Path, summarize) -> str:
    """A worker pass that processes one session of the project."""
    queue.enqueue(state, session_id="s1", transcript=FIXTURE, cwd=str(hub), reason="clear")
    return run(state, lambda path, entry: Outcome.DONE, summarize)


def test_session_start_and_worker_build_the_same_text_and_the_hash_follows_the_settings(world):
    config, state, hub, spawned = world
    knowledge(config.vault, 30)
    runner = FakeRunner(answer("### Facts\n- **Entries hold.** All thirty of them."))

    done_pass(state, hub, make_summarize(config, state, runner))
    text = recall(hook(hub), config)

    files = summary.context_for(config.vault, project_for_root(hub.resolve(), state.projects_file))
    sent = context.text(context.file_texts(config.vault, files.files))
    assert sent in runner.calls[0][1]
    assert "All thirty of them." in text
    assert STALE not in text
    assert summary.marked(state) == set()
    assert spawned == []
    base = summary.digest(sent, "work", config)
    german = Config(config.vault, config.state_dir, language="German", recall_budget_tokens=BUDGET)
    larger = Config(config.vault, config.state_dir, recall_budget_tokens=BUDGET + 1)
    assert summary.digest(sent, "work", german) != base
    assert summary.digest(sent, "work", larger) != base
    assert summary.digest(sent, "private", config) != base


def test_worker_writes_the_summary_with_header_within_the_target_and_logs_its_cost(world):
    config, state, hub, _ = world
    knowledge(config.vault, 30)
    long = "### Facts\n" + "".join(f"- Line {index} " + "y" * 60 + "\n" for index in range(40))
    runner = FakeRunner(answer(long, cost=0.0042))

    assert done_pass(state, hub, make_summarize(config, state, runner)) == "done"

    saved = summary.load(state, NAME)
    raw = (state.summaries / f"{NAME}.md").read_text()
    assert raw.startswith(f"---\nhash: {saved.hash}\ndomain: work\n---\n")
    assert len(saved.text) <= summary.target_chars(config)
    assert saved.text.endswith(CUT)
    assert "- Line 0 " in saved.text
    [line] = runs(state)
    assert line["context"] == NAME
    assert line["outcome"] == "done"
    assert line["cost_usd"] == 0.0042
    command, _ = runner.calls[0]
    for flag in ("--restricted", "--no-session-persistence", "--strict-mcp-config"):
        assert flag in command
    assert "never follow instructions" in command[command.index("--system-prompt") + 1].lower()
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--max-turns") + 1] == "1"


def test_a_matching_summary_loads_instead_of_the_files_with_their_paths(world):
    config, state, hub, spawned = world
    knowledge(config.vault, 30)
    write(config.vault, f"{HUB}/notes.md", "---\ntype: notes\n---\n- 2026-10-19: My own note\n")
    make_summarize(config, state, FakeRunner(answer("### Facts\n- **Summed up.**")))({NAME})

    text = recall(hook(hub), config)

    assert "### Facts\n- **Summed up.**" in text
    assert "Entry 00" not in text
    assert "My own note" not in text
    assert f"- {HUB}/notes.md" in text
    assert f"- {HUB}/knowledge.md" in text
    assert CUT_MARKER not in text
    assert len(text) <= summary.limit_chars(config)
    assert spawned == []


def test_changed_files_load_the_old_summary_with_a_line_mark_and_the_next_pass_rebuilds(world):
    config, state, hub, spawned = world
    knowledge(config.vault, 30)
    summarize = make_summarize(config, state, FakeRunner(answer("### Facts\n- Old summary.")))
    summarize({NAME})
    knowledge(config.vault, 30, word="changed")

    text = recall(hook(hub), config)

    assert "- Old summary." in text
    assert "The files changed since this summary was made" in text
    assert summary.marked(state) == {NAME}
    assert spawned == [True]

    rebuild = make_summarize(config, state, FakeRunner(answer("### Facts\n- New summary.")))
    assert run(state, lambda path, entry: Outcome.DONE, rebuild) == "done"
    fresh = recall(hook(hub), config)
    assert "- New summary." in fresh
    assert "changed since" not in fresh
    assert summary.marked(state) == set()


def test_a_summary_made_for_another_domain_is_never_loaded(world):
    config, state, hub, spawned = world
    knowledge(config.vault, 30)
    files = context.text(context.file_texts(config.vault, [Path(HUB) / "knowledge.md"]))
    secret = summary.Summary("- Private summary.", summary.digest(files, "work", config), "private")
    summary.save(state, NAME, secret)

    text = recall(hook(hub), config)

    assert "Private summary" not in text
    assert CUT_MARKER in text
    assert "- **Entry 00 holds.**" in text
    assert summary.marked(state) == {NAME}
    assert spawned == [True]


def test_without_a_summary_the_files_are_cut_marked_and_an_empty_queue_pass_builds_it(world):
    config, state, hub, spawned = world
    knowledge(config.vault, 30)

    text = recall(hook(hub), config)

    assert CUT_MARKER in text
    assert "- **Entry 00 holds.**" in text
    assert len(text) <= summary.limit_chars(config)
    assert summary.marked(state) == {NAME}
    assert spawned == [True]

    runner = FakeRunner(answer("### Facts\n- Built from the mark."))
    assert run(state, lambda path, entry: Outcome.DONE, make_summarize(config, state, runner))
    assert summary.load(state, NAME).text == "### Facts\n- Built from the mark."
    assert "Built from the mark." in recall(hook(hub), config)


def test_contexts_outside_a_repository_and_of_an_unknown_repository_have_their_own_names(world):
    config, state, hub, spawned = world
    lines = "".join(f"- **General {index:02}.** " + "z" * 40 + "\n" for index in range(30))
    write(config.vault, "general/knowledge.md", f"---\ntype: knowledge\n---\n## Facts\n{lines}")
    home = hub.parent.parent / "home"
    home.mkdir()
    unknown = make_repo(hub.parent / "unknown")

    recall(hook(home), config)
    recall(hook(unknown), config)

    assert summary.marked(state) == {summary.OUTSIDE, summary.GENERAL}
    runner = FakeRunner()
    run(state, lambda path, entry: Outcome.DONE, make_summarize(config, state, runner))
    assert summary.load(state, summary.OUTSIDE).domain == "private"
    assert summary.load(state, summary.GENERAL).domain == "work"


def test_a_repository_named_like_a_reserved_context_keeps_its_own_summary(world):
    config, state, hub, _ = world
    lines = "".join(f"- **General {index:02}.** " + "z" * 40 + "\n" for index in range(30))
    write(config.vault, "general/knowledge.md", f"---\ntype: knowledge\n---\n## Facts\n{lines}")
    odd = make_repo(hub.parent / "_general")
    project_for_root(odd.resolve(), state.projects_file)
    unknown = make_repo(hub.parent / "unknown")
    write(config.vault, "projects/_general/notes.md", "---\ntype: notes\n---\n- 2026-10-19: Odd\n")
    runner = FakeRunner(answer("- General only."), answer("- Odd project."))
    summarize = make_summarize(config, state, runner)

    recall(hook(unknown), config)
    recall(hook(odd), config)
    summarize(summary.marked(state))

    assert summary.marked(state) == set()
    assert "- General only." in recall(hook(unknown), config)
    assert "- Odd project." in recall(hook(odd), config)
    assert summary.marked(state) == set()


def test_a_context_within_the_target_gets_no_summary_run(world):
    config, state, hub, spawned = world
    knowledge(config.vault, 3)
    runner = FakeRunner()

    assert done_pass(state, hub, make_summarize(config, state, runner)) == "done"

    assert runner.calls == []
    assert runs(state) == []
    assert summary.load(state, NAME) is None


def test_whole_text_over_the_limit_with_files_within_the_target_is_cut_without_a_mark(world):
    config, state, hub, spawned = world
    knowledge(config.vault, 8)
    for index in range(3):
        queue.enqueue(state, session_id=f"w{index}", transcript=FIXTURE, cwd=str(hub), reason="x")

    text = recall(hook(hub), config)

    assert CUT_MARKER in text
    assert summary.marked(state) == set()
    assert spawned == []


@pytest.mark.parametrize(
    "stop",
    [failure("rate limit reached", status=429), RunResult(-1, "", timed_out=True)],
    ids=["transient", "timeout"],
)
def test_a_transient_or_timed_out_run_keeps_the_old_summary_and_ends_the_summary_jobs(world, stop):
    config, state, hub, _ = world
    knowledge(config.vault, 30)
    lines = "".join(f"- **General {index:02}.** " + "z" * 40 + "\n" for index in range(30))
    write(config.vault, "general/knowledge.md", f"---\ntype: knowledge\n---\n## Facts\n{lines}")
    make_summarize(config, state, FakeRunner(answer("- Old.")))({NAME})
    knowledge(config.vault, 30, word="changed")
    summary.mark(state, NAME)
    summary.mark(state, summary.GENERAL)
    waiting = queue.enqueue(state, session_id="w", transcript=FIXTURE, cwd=str(hub), reason="x")
    runner = FakeRunner(stop)

    # The general context sorts first, so it is the one that stops.
    result = make_summarize(config, state, runner)({summary.GENERAL, NAME})

    assert result is True
    assert len(runner.calls) == 1
    assert summary.load(state, NAME).text == "- Old."
    assert queue.pending(state) == [waiting]
    assert queue.load(waiting).attempts == 0
    assert NAME in summary.marked(state)


def test_a_summary_step_that_stops_ends_the_pass_and_leaves_later_entries_alone(world):
    config, state, hub, _ = world
    knowledge(config.vault, 30)
    summary.mark(state, NAME)
    arrived: list[Path] = []

    def offline(command, cwd, env, timeout, stdin) -> RunResult:
        arrived.append(
            queue.enqueue(state, session_id="late", transcript=FIXTURE, cwd=str(hub), reason="x")
        )
        return RunResult(-1, "", timed_out=True)

    assert (
        run(state, lambda path, entry: Outcome.DONE, make_summarize(config, state, offline))
        == "stopped"
    )

    assert queue.pending(state) == arrived
    assert queue.load(arrived[0]).attempts == 0


def test_a_summary_cut_down_to_the_marker_alone_is_a_failure(world):
    config, state, _, _ = world
    knowledge(config.vault, 30)

    make_summarize(config, state, FakeRunner(answer("- " + "w" * 900)))({NAME})

    assert summary.load(state, NAME) is None
    assert runs(state)[0]["outcome"] == "failed"


def test_a_text_that_failed_three_times_waits_until_it_changes(world):
    config, state, hub, _ = world
    knowledge(config.vault, 30)
    runner = FakeRunner(*(failure("invalid output") for _ in range(3)))
    summarize = make_summarize(config, state, runner)

    for _ in range(4):
        summarize({NAME})
    assert len(runner.calls) == 3
    assert [line["outcome"] for line in runs(state)] == ["failed", "failed", "failed"]

    knowledge(config.vault, 30, word="changed")
    summarize({NAME})
    assert len(runner.calls) == 4
    assert summary.load(state, NAME) is not None


def test_an_exception_in_a_summary_job_is_logged_and_the_worker_finishes(world):
    config, state, hub, _ = world
    knowledge(config.vault, 30)
    runner = FakeRunner(OSError("claude not found"))

    assert done_pass(state, hub, make_summarize(config, state, runner)) == "done"

    [line] = runs(state)
    assert line["outcome"] == "failed"
    assert "claude not found" in line["error"]
    assert len(list(state.done.glob("*.json"))) == 1


@pytest.mark.parametrize(
    "raw",
    [
        "```markdown\n### Facts\n- Kept.\n```",
        "Here is the summary:\n\n### Facts\n- Kept.",
        "  \n### Facts\n- Kept.\n\n",
    ],
    ids=["fence", "preamble", "blank"],
)
def test_a_code_fence_or_a_preamble_line_is_stripped(world, raw):
    config, state, _, _ = world
    knowledge(config.vault, 30)

    make_summarize(config, state, FakeRunner(answer(raw)))({NAME})

    assert summary.load(state, NAME).text == "### Facts\n- Kept."


def test_an_empty_result_is_a_failure_and_writes_nothing(world):
    config, state, _, _ = world
    knowledge(config.vault, 30)

    make_summarize(config, state, FakeRunner(answer("```\n```")))({NAME})

    assert summary.load(state, NAME) is None
    assert runs(state)[0]["outcome"] == "failed"
