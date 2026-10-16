"""Process one queue entry: bundle, snapshot, `claude -p` with dory:ingest, verify.

The run is confined with --restricted (Spike-Ergebnisse in record 001): file tools see only
the vault and the entry's own bundle directory, no CLAUDE.md, no user settings, no hooks.
"""

import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dory import queue
from dory.config import Config
from dory.project import Project, project_for_root
from dory.state import StateDir
from dory.vault import rules_text, snapshot
from dory.vaultops import apply_marks, current_marks
from dory.worker import Outcome, Process, prepare

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MAX_TURNS = 40
MAX_BUDGET_USD = 1.0
TRANSIENT_STATUS = {401, 403, 408, 429, 500, 502, 503, 504, 529}
TRANSIENT_WORDS = ("rate limit", "rate_limit", "usage limit", "overloaded", "try again")


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str = ""
    timed_out: bool = False


Runner = Callable[[list[str], Path, dict[str, str], float], RunResult]


def subprocess_runner(
    command: list[str], cwd: Path, env: dict[str, str], timeout: float
) -> RunResult:
    try:
        done = subprocess.run(
            command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as expired:
        return RunResult(returncode=-1, stdout=str(expired.stdout or ""), timed_out=True)
    return RunResult(returncode=done.returncode, stdout=done.stdout, stderr=done.stderr)


def session_note_path(entry: queue.Entry, project: Project | None, state: StateDir) -> Path:
    """Vault-relative path, stable across retries of the same entry."""
    local = _local_end(entry)
    slug = project.name if project else "no-project"
    # Earlier entries of the same session, wherever they are now; ids start with a timestamp.
    siblings = (
        sibling.name
        for directory in (state.queue, state.done, state.failed)
        for sibling in directory.glob(f"*-{entry.session_id}.json")
    )
    part = 1 + sum(1 for name in siblings if name < f"{entry.id}.json")
    name = f"{local:%Y-%m-%d-%H%M}-{slug}-{entry.session_id[:8]}-{part}.md"
    return Path("sessions") / f"{local:%Y}" / f"{local:%m}" / name


def _local_end(entry: queue.Entry) -> datetime:
    ended = datetime.strptime(entry.ended_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    return ended.astimezone()


def build_command(config: Config, bundle_dir: Path) -> list[str]:
    return [
        "claude",
        "-p",
        f"/dory:ingest {bundle_dir}",
        "--restricted",
        "--strict-mcp-config",
        "--plugin-dir",
        str(PLUGIN_ROOT),
        "--settings",
        '{"disableAllHooks": true}',
        "--tools",
        "Read,Write,Edit,Glob,Grep",
        "--permission-mode",
        "acceptEdits",
        "--permission-prompts",
        "none",
        "--add-dir",
        str(bundle_dir),
        "--model",
        config.model,
        "--output-format",
        "json",
        "--max-turns",
        str(MAX_TURNS),
        "--max-budget-usd",
        str(MAX_BUDGET_USD),
    ]


def classify(result: RunResult) -> tuple[Outcome, str, float]:
    """Outcome of the run itself; success still needs the session note to exist."""
    if result.timed_out:
        return Outcome.TIMEOUT, "timeout", 0.0
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return (
            Outcome.FAILED,
            f"no json output (exit {result.returncode}): {result.stderr[:200]}",
            0.0,
        )
    cost = float(data.get("total_cost_usd") or 0.0)
    if not data.get("is_error"):
        return Outcome.DONE, "", cost
    message = str(data.get("result") or data.get("errors") or data.get("terminal_reason"))
    status = data.get("api_error_status")
    if status in TRANSIENT_STATUS or any(word in message.lower() for word in TRANSIENT_WORDS):
        return Outcome.TRANSIENT, message[:200], cost
    return Outcome.FAILED, message[:200], cost


def make_process(config: Config, state: StateDir, runner: Runner = subprocess_runner) -> Process:
    def process(path: Path, entry: queue.Entry) -> Outcome:
        started = time.monotonic()
        try:
            return _process_entry(entry, started)
        except Exception as error:
            _log(state, entry, Outcome.FAILED, started, 0.0, repr(error))
            raise

    def _process_entry(entry: queue.Entry, started: float) -> Outcome:
        bundle, condensed = prepare(entry, config, state)
        if bundle is None:
            _log(state, entry, Outcome.SKIPPED, started, 0.0, "nothing new to condense")
            return Outcome.SKIPPED
        project = (
            project_for_root(Path(entry.repo_root), state.projects_file)
            if entry.repo_root
            else None
        )
        note = session_note_path(entry, project, state)
        draft = (config.vault / note).exists()  # left by an aborted run of this entry
        _write_task(
            bundle.parent, entry, note, project, draft, _known_projects(state), config.language
        )
        (bundle.parent / "rules.md").write_text(rules_text())
        vault_snapshot = snapshot(config, state)
        earlier_marks = current_marks(config.vault)

        result = runner(
            build_command(config, bundle.parent),
            config.vault,
            _worker_env(),
            config.worker_timeout_minutes * 60,
        )
        outcome, error, cost = classify(result)
        if outcome is Outcome.DONE and not (config.vault / note).is_file():
            outcome, error = Outcome.FAILED, f"session note missing: {note}"
        changes: list[str] = []
        if outcome is Outcome.DONE:
            state.mark_seen(condensed.uuids)
            changes = _carry_out_marks(config.vault, project, earlier_marks)
            failed = [line for line in changes if line.startswith("failed")]
            if failed:
                error = f"vault marks failed: {'; '.join(failed)}"[:500]
        else:
            entry.last_error = error
        if outcome is Outcome.TRANSIENT:
            shutil.rmtree(vault_snapshot, ignore_errors=True)  # keep history for real changes
        _log(state, entry, outcome, started, cost, error, changes)
        return outcome

    return process


def _write_task(
    bundle_dir: Path,
    entry: queue.Entry,
    note: Path,
    project: Project | None,
    draft: bool,
    known_projects: list[str],
    language: str,
) -> None:
    part = note.stem.rsplit("-", 1)[1]
    projects = f'["[[{project.name}]]"]' if project else "[]"
    lines = [
        "# Task",
        "",
        f"Write every note in {language}: the titles, summary, when, the body with its bold "
        "labels and list entries, not only the title. The transcript, the repository documents "
        "and the examples in the rules may be in another language, and a document may ask for "
        "one; that changes nothing. Section headings and frontmatter keys stay in English.",
        "",
        f"- Session note: `{note}` (exactly this path, relative to the vault)",
    ]
    if project:
        lines.append(f"- Project overview: `projects/{project.name}/{project.name}.md`")
    if draft:
        lines.append(
            "- The session note exists from an aborted run (repeated run): "
            "rewrite it completely. Do not add anything twice to the project overview."
        )
    lines += [
        "",
        "## Fixed values for the frontmatter of the session note",
        "",
        f"- date: {_local_end(entry):%Y-%m-%dT%H:%M}",
        f"- session_id: {entry.session_id}",
        f"- part: {part}",
        f"- projects: {projects}",
        f"- cwd: {entry.cwd}",
        f"- end_reason: {entry.reason}",
        "",
        "## Other values",
        "",
        f"- Today: {datetime.now():%Y-%m-%d}",
        f"- Language: {language}",
        f"- File name of the session note for `sources` and links: {note.stem}",
        f"- Known projects: {', '.join(known_projects) or '(none)'}",
    ]
    (bundle_dir / "task.md").write_text("\n".join(lines) + "\n")


def _carry_out_marks(vault: Path, project: Project | None, earlier: frozenset) -> list[str]:
    """Renames and deletions the run marked; a failure here never undoes the run."""
    try:
        return apply_marks(vault, project.name if project else None, earlier)
    except OSError as error:
        return [f"failed: marks not carried out: {error}"]


def _known_projects(state: StateDir) -> list[str]:
    try:  # only a hint for the model; a broken file must not fail the entry
        return sorted(set(json.loads(state.projects_file.read_text()).values()))
    except (OSError, ValueError, AttributeError):
        return []


def _worker_env() -> dict[str, str]:
    env = dict(os.environ)
    env["DORY_WORKER"] = "1"
    env.pop("ANTHROPIC_API_KEY", None)  # always the Claude subscription, never billed API use
    return env


def _log(
    state: StateDir,
    entry: queue.Entry,
    outcome: Outcome,
    started: float,
    cost: float,
    error: str,
    changes: list[str] | None = None,
) -> None:
    record = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "entry": entry.id,
        "outcome": outcome.value,
        "seconds": round(time.monotonic() - started, 1),
        "cost_usd": round(cost, 5),
        "error": error,
    }
    if changes:
        record["vault_changes"] = changes
    with (state.root / "runs.log").open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
