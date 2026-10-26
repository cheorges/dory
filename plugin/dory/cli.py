"""Command line entry point: `dory <command>`. Hooks call it with their JSON on stdin."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dory import (
    __version__,
    candidates,
    ingest,
    library,
    note,
    ops,
    queue,
    recall,
    search,
    summarize,
    worker,
)
from dory.config import load_config
from dory.project import detect_project
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
    add = commands.add_parser("add-note", help="/dory:note: create a note file with its title")
    add.add_argument("--scope", required=True, help="project or notes")
    add.add_argument("--title", required=True, help="the note's title, its file name")
    add.add_argument("text", nargs="*", help="the note; read from stdin when left out")
    commands.add_parser("guard", help="/dory:note hook: block Write and Edit in library/")
    commands.add_parser("library-context", help="/dory:library: snapshot and context")
    commands.add_parser(
        "library-candidates", help="/dory:library: files to link from and possible duplicates"
    )
    write = commands.add_parser("library-write", help="/dory:library: create or replace an entry")
    write.add_argument("--folder", default="", help="folder below library/, at most two levels")
    write.add_argument("--title", required=True, help="the entry's title, its file name")
    write.add_argument("--replace", action="store_true", help="replace the existing entry")
    write.add_argument("--expect", help="with --replace: sha256 of the entry as it was read")
    write.add_argument("--alias", action="append", help="an alias of the entry; repeatable")
    write.add_argument("--source", help="where the knowledge comes from: a URL or a [[link]]")
    linking = commands.add_parser("link", help="/dory:library: link an entry from a note or topic")
    linking.add_argument("--entry", required=True, help="the entry, e.g. library/Python/uv")
    linking.add_argument("files", nargs="+", help="project notes or topic files in notes/")
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
        text = " ".join(args.text) if args.text else sys.stdin.read()
        return _add_note(args.scope, args.title, text)
    if args.command == "guard":
        return _guard(sys.stdin.read())
    if args.command == "library-context":
        print(library.library_context(load_config(), Path.cwd()))
        return 0
    if args.command == "library-candidates":
        return _library_candidates(sys.stdin.read())
    if args.command == "library-write":
        return _library_write(args, sys.stdin.read())
    if args.command == "link":
        return _link(args.entry, args.files)
    if args.command == "search":
        print(search.search(load_config(), Path.cwd(), " ".join(args.query)))
        return 0
    if args.command == "status":
        config = load_config()
        print(ops.status(StateDir(config.state_dir), vault=config.vault))
        return 0
    if args.command == "retry":
        return _retry()
    return _worker(dry_run=args.dry_run)


def _add_note(scope: str, title: str, text: str) -> int:
    config = load_config()
    try:
        written = note.add_note(config, Path.cwd(), scope, title, text)
    except note.NoteError as error:
        print(f"dory add-note: {error}", file=sys.stderr)
        return 1
    print(f"Noted in {written.as_posix()} (vault {config.vault})")
    return 0


def _guard(raw: str) -> int:
    """Exit 2 blocks the tool call and shows the message to Claude. A guard that fails lets the
    call through: it stays active for the rest of the session and must not block all writes."""
    try:
        message = library.guard(load_config(), raw)
    except Exception as error:
        _log_hook_error("guard", error)
        return 0
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


def _library_candidates(text: str) -> int:
    config = load_config()
    try:
        draft = candidates.parse_draft(text)
    except ValueError as error:
        print(f"dory library-candidates: {error}", file=sys.stderr)
        return 1
    project = detect_project(Path.cwd(), StateDir(config.state_dir).ensure().projects_file)
    found, duplicates = candidates.candidates(config.vault, project, draft)
    print(candidates.render(config.vault, found, duplicates))
    return 0


def _library_write(args: argparse.Namespace, text: str) -> int:
    config = load_config()
    try:
        if args.replace != (args.expect is not None):
            raise library.LibraryError("--replace and --expect go together")
        written, new = library.library_write(
            config,
            args.folder,
            args.title,
            text,
            expect=args.expect,
            aliases=args.alias,
            source=args.source,
        )
    except library.LibraryError as error:
        print(f"dory library-write: {error}", file=sys.stderr)
        return 1
    print(f"{'Created' if new else 'Replaced'} {written.as_posix()} (vault {config.vault})")
    return 0


def _link(entry: str, files: list[str]) -> int:
    config = load_config()
    try:
        done = library.link(config, entry, files)
    except library.LibraryError as error:
        print(f"dory link: {error}", file=sys.stderr)
        return 1
    for relative, changed in done:
        print(f"{'Linked from' if changed else 'Already linked from'} {relative.as_posix()}")
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
