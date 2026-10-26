"""Process one queue entry: bundle, snapshot, `claude -p` with dory:ingest, verify.

The run is confined with --restricted (Spike-Ergebnisse in record 001): file tools see only
the vault and the entry's own bundle directory, no CLAUDE.md, no user settings, no hooks.
"""

import contextlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from dory import baseline, catalog, context, queue, scopes, staleness, trace
from dory.config import Config
from dory.project import Project, project_for_root
from dory.secrets import redact
from dory.state import StateDir
from dory.vault import rules_text, snapshot
from dory.worker import Outcome, Process, prepare

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MAX_TURNS = 40
CATALOG = "catalog.md"  # in the bundle directory, next to task.md
MAX_BUDGET_USD = 1.0
# No hooks of the user's setup in the run; the user's project notes and library stay theirs. The
# library entries the run may read are copies in the bundle. Patterns without a leading slash are
# relative to the run's working directory, the vault; a Read rule also holds for Grep and Glob.
WORKER_SETTINGS = json.dumps(
    {
        "disableAllHooks": True,
        "permissions": {
            "deny": [
                "Read(library/**)",
                "Edit(library/**)",
                "Write(library/**)",
                "Edit(projects/*/notes/**)",
                "Write(projects/*/notes/**)",
            ]
        },
    }
)
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


def _ended(entry: queue.Entry) -> datetime:
    return datetime.strptime(entry.ended_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _local_end(entry: queue.Entry) -> datetime:
    return _ended(entry).astimezone()


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
        WORKER_SETTINGS,
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
        baseline.create_skeletons(config.vault, project, date.today())
        domain = scopes.project_domain(config.vault, project)
        kept = baseline.baseline_dir(state, entry.id)
        files = _task_files(config.vault, project)
        _copy_library(config.vault, bundle.parent, files.library)
        now = datetime.now(UTC)
        # Edits since the last run count from now: the user's, or a killed attempt's of this entry.
        killed = baseline.unchecked(kept)
        staleness.observe(state, config.vault, now, by=entry.id if killed else "")
        flags = staleness.flags(
            state, config.vault, session_ended=_ended(entry), entry_id=entry.id, now=now
        )
        (bundle.parent / CATALOG).write_text(
            catalog.build(config.vault, project, private=domain == "private", flags=flags)
        )
        _write_task(
            bundle.parent,
            entry,
            SessionTarget(note, project, domain, draft),
            files,
            config.language,
        )
        (bundle.parent / "rules.md").write_text(rules_text())
        vault_snapshot = snapshot(config, state)
        before = baseline.vault_state(config.vault)
        topics_allowed = domain != "private"  # every session lists the topics
        unchecked = baseline.capture(config.vault, kept, project, topics_allowed=topics_allowed)

        try:
            result = runner(
                build_command(config, bundle.parent),
                config.vault,
                _worker_env(),
                config.worker_timeout_minutes * 60,
            )
        except Exception:  # `claude` did not start, so the vault holds nothing to check
            if not unchecked:
                baseline.mark_checked(kept)
            raise
        outcome, error, cost = classify(result)
        if outcome is Outcome.DONE and not (config.vault / note).is_file():
            outcome, error = Outcome.FAILED, f"session note missing: {note}"
        changed = baseline.vault_state(config.vault) != before
        due = changed or unchecked  # a kept baseline still holds a killed run's changes
        changes = baseline.check(config.vault, kept) if due else []
        replaced = baseline.replaced(config.vault, kept) if due else []
        baseline.mark_checked(kept)
        staleness.record(state, changes, entry.id, datetime.now(UTC))
        staleness.observe(state, config.vault, datetime.now(UTC))
        if outcome is Outcome.DONE:
            with contextlib.suppress(OSError, ValueError):  # the trace is a by-product
                trace.append(config.vault / note, [*trace.take(state, entry.id), *replaced])
        else:
            trace.keep(state, entry.id, replaced)
        if outcome is Outcome.DONE:
            state.mark_seen(condensed.uuids)
        else:
            entry.last_error = error
        if outcome is Outcome.TRANSIENT and not changed:
            shutil.rmtree(vault_snapshot, ignore_errors=True)  # keep history for real changes
        _log(state, entry, outcome, started, cost, error, changes)
        return outcome

    return process


@dataclass(frozen=True)
class SessionTarget:
    """Where a run writes its session note and for which project."""

    note: Path
    project: Project | None
    domain: str
    draft: bool  # the session note exists from an aborted run of this entry


@dataclass(frozen=True)
class TaskFiles:
    """The files a run may change and the user's notes it must leave alone."""

    knowledge: Path | None
    notes: list[tuple[Path, str]]  # every file in `notes/`, with its type
    user_notes: list[Path]
    library: list[Path] = field(default_factory=list)  # entries a session start here may load


def _task_files(vault: Path, project: Project | None) -> TaskFiles:
    return TaskFiles(
        knowledge=scopes.knowledge_file(project),
        notes=[(path, scopes.file_type(vault / path)) for path in scopes.notes_folder_files(vault)],
        user_notes=scopes.project_notes(vault, project),
        library=context.library_files(vault, project),
    )


def _copy_library(vault: Path, bundle_dir: Path, entries: list[Path]) -> None:
    """Redacted copies of the library entries the run may read; it cannot read `library/`."""
    shutil.rmtree(bundle_dir / scopes.LIBRARY, ignore_errors=True)
    for relative in entries:
        try:
            text = (vault / relative).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        copy = bundle_dir / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_text(redact(text))


def _write_task(
    bundle_dir: Path,
    entry: queue.Entry,
    target: SessionTarget,
    files: TaskFiles,
    language: str,
) -> None:
    note, project = target.note, target.project
    part = note.stem.rsplit("-", 1)[1]
    projects = f'["[[projects/{project.name}/knowledge|{project.name}]]"]' if project else "[]"
    lines = [
        "# Task",
        "",
        f"Write every note in {language}: the knowledge entries with their bold leads, "
        "summary, the session note and list entries, not only the headings. The transcript, "
        "the repository documents and the examples in the rules may be in another language, and "
        "a document may ask for one; that changes nothing. Section headings and frontmatter keys "
        "stay in English.",
        "",
        f"- Session note: `{note}` (exactly this path, relative to the vault)",
        *_task_file_lines(files, bundle_dir, private=target.domain == "private"),
    ]
    if target.draft:
        lines.append(
            "- The session note exists from an aborted run (repeated run): rewrite it "
            "completely. Entries that run added are in the knowledge and topic files already: "
            "do not add them twice."
        )
    lines += [
        "",
        "## Fixed values for the frontmatter of the session note",
        "",
        f"- date: {_local_end(entry):%Y-%m-%dT%H:%M}",
        f"- session_id: {entry.session_id}",
        f"- part: {part}",
        f"- projects: {projects}",
        *([f"- domain: {target.domain}"] if project else []),
        f"- cwd: {entry.cwd}",
        f"- end_reason: {entry.reason}",
        "",
        "## Other values",
        "",
        f"- Today: {datetime.now():%Y-%m-%d}",
        f"- Language: {language}",
        f"- File name of the session note: {note.stem}",
    ]
    (bundle_dir / "task.md").write_text("\n".join(lines) + "\n")


def _task_file_lines(files: TaskFiles, bundle_dir: Path, *, private: bool) -> list[str]:
    lines = []
    if files.knowledge:
        lines.append(
            f"- The project's knowledge file, change it with Edit (it exists, with its "
            f"frontmatter): `{files.knowledge}`"
        )
    lines.append("- The files in `notes/`, for everything without a project, with their type:")
    lines += [f"  - `{path}` ({kind})" for path, kind in files.notes] or ["  - none yet"]
    if private:
        lines.append(
            "- This is a private project: update the lists and registers in `notes/` the "
            "session touched, but change or create no topic file. What applies beyond the "
            "project becomes no entry."
        )
    else:
        lines.append(
            "- Change a topic, list or register in `notes/` with Edit; create a new topic file "
            "there only for a subject no file covers."
        )
    if files.knowledge:
        lines.append(
            "- The user's notes for this project, read in full and never changed: "
            + (", ".join(f"`{path}`" for path in files.user_notes) or "none yet")
            + ". Nothing they say becomes an entry: a session that only repeats a note adds "
            "nothing."
        )
    if files.library:
        lines.append(
            "- Library entries the user filed, copied from `library/` for reference, read in full "
            "and never changed: "
            + ", ".join(f"`{bundle_dir / path}`" for path in files.library)
            + ". What they say becomes no entry: a session that only repeats one adds nothing."
        )
    if private:
        target = "the project's knowledge file."
    elif files.knowledge:
        target = "the project's knowledge file or in a topic file."
    else:
        target = "a topic file."
    lines.append(
        f"- The catalog of every entry in the vault: `{bundle_dir / CATALOG}`. Check each "
        f"insight against it before you write: extend the entry it matches in {target} "
        "The rules say what to do when another project's file states it."
    )
    lines += [
        "- `library/` is the user's folder: you cannot read it, and you never write into it or "
        "link to it, not in the text and not in a `library` property.",
        "- Every other file in `projects/` belongs to another project or to an earlier version "
        "of dory: neither read nor write it.",
    ]
    return lines


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
    changes: list[dict] | None = None,
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
