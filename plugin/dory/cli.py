"""Command line entry point: `dory <command>`. Hooks call it with their JSON on stdin."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dory import __version__, ingest, note, ops, queue, recall, search, summarize, worker
from dory.config import load_config
from dory.spawn import spawn_worker
from dory.state import StateDir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dory")
    parser.add_argument("--version", action="version", version=f"dory {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    enqueue = commands.add_parser("enqueue", help="SessionEnd hook: queue the ended session")
    enqueue.add_argument("--session", help="/dory:save: queue this running session now")
    commands.add_parser("recall", help="SessionStart hook: print the memory to inject")
    work = commands.add_parser("worker", help="drain the queue")
    work.add_argument("--dry-run", action="store_true", help="only write the input bundles")
    commands.add_parser("prepare-note", help="/dory:note: snapshot and context for writing")
    add = commands.add_parser("add-note", help="/dory:note: append the user's note to a notes.md")
    add.add_argument("--scope", required=True, help="project, general or private")
    add.add_argument("text", nargs="*", help="the note; read from stdin when left out")
    find = commands.add_parser("search", help="/dory:search: find notes in the vault")
    find.add_argument("query", nargs="+")
    commands.add_parser("status", help="queue, failures, last error and costs")
    commands.add_parser("retry", help="move failed entries back into the queue")
    args = parser.parse_args(argv)

    if args.command == "enqueue" and args.session is not None:
        return _save(args.session)
    if args.command == "enqueue":
        return _enqueue_from_hook(sys.stdin.read())
    if args.command == "recall":
        return _recall_from_hook(sys.stdin.read())
    if args.command == "prepare-note":
        print(note.prepare_note(load_config(), Path.cwd()))
        return 0
    if args.command == "add-note":
        return _add_note(args.scope, " ".join(args.text) if args.text else sys.stdin.read())
    if args.command == "search":
        print(search.search(load_config(), Path.cwd(), " ".join(args.query)))
        return 0
    if args.command == "status":
        print(ops.status(StateDir(load_config().state_dir)))
        return 0
    if args.command == "retry":
        return _retry()
    return _worker(dry_run=args.dry_run)


def _add_note(scope: str, text: str) -> int:
    config = load_config()
    try:
        written = note.add_note(config, Path.cwd(), scope, text)
    except note.NoteError as error:
        print(f"dory add-note: {error}", file=sys.stderr)
        return 1
    print(f"Noted in {written.as_posix()} (vault {config.vault})")
    return 0


def _enqueue_from_hook(raw: str) -> int:
    # A hook must never fail loudly or block Claude Code from exiting: errors go to a log.
    if os.environ.get("DORY_WORKER") == "1":
        return 0  # sessions started by the worker itself are never queued
    try:
        hook = json.loads(raw or "{}")
        transcript = Path(hook.get("transcript_path", ""))
        if not hook.get("session_id") or not transcript.is_file():
            return 0
        state = StateDir(load_config().state_dir)
        queue.enqueue(
            state,
            session_id=hook["session_id"],
            transcript=transcript,
            cwd=hook.get("cwd", ""),
            reason=hook.get("reason", "other"),
        )
    except Exception as error:
        _log_hook_error("enqueue", error)
        return 0
    try:
        spawn_worker()
    except Exception as error:
        _log_hook_error("spawn", error)
    return 0


def _save(session_id: str) -> int:
    """Queue a running session. Its transcript path comes from the SessionStart hook."""
    state = StateDir(load_config().state_dir).ensure()
    record_file = state.sessions / f"{session_id}.json"
    try:
        record = json.loads(record_file.read_text())
        transcript = Path(record["transcript_path"])
        if not transcript.is_file():
            raise FileNotFoundError(transcript)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Session {session_id} not found ({error!r}); is the dory plugin enabled?")
        return 1
    queue.enqueue(
        state,
        session_id=session_id,
        transcript=transcript,
        cwd=record.get("cwd", ""),
        reason="save",
    )
    spawn_worker()
    print(f"Session {session_id[:8]} queued; the worker processes it in the background.")
    return 0


def _recall_from_hook(raw: str) -> int:
    if os.environ.get("DORY_WORKER") == "1":
        return 0
    try:
        output = recall.hook_output(recall.recall(json.loads(raw or "{}"), load_config()))
    except Exception as error:
        _log_hook_error("recall", error)
        return 0
    if output:
        print(output)
    return 0


def _log_hook_error(step: str, error: Exception) -> None:
    try:
        state_dir = Path(os.environ.get("DORY_STATE_DIR", "~/.local/state/dory-brain"))
        log = state_dir.expanduser() / "hook-errors.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as handle:
            handle.write(f"{datetime.now(UTC).isoformat()} {step}: {error!r}\n")
    except OSError:
        pass
    print(f"dory {step}: {error!r}", file=sys.stderr)


def _retry() -> int:
    moved = ops.retry(StateDir(load_config().state_dir))
    if moved is None:
        print("A worker is running right now; run dory retry again once it has finished")
        return 1
    print(f"{moved} {'entry' if moved == 1 else 'entries'} back in the queue")
    if moved:
        spawn_worker()
    return 0


def _worker(*, dry_run: bool) -> int:
    config = load_config()
    if dry_run:
        for bundle in worker.dry_run(config):
            print(bundle)
        return 0
    state = StateDir(config.state_dir)
    process = ingest.make_process(config, state)
    print(f"dory worker: {worker.run(state, process, summarize.make_summarize(config, state))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
