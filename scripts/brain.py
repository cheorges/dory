#!/usr/bin/env python3
"""dory entry point: hooks, background worker and the finish step for /dory:save and /dory:note."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from startctx import find_missed, render  # noqa: E402
from state import (Config, acquire_lock, add_notice, enqueue, ensure_installed_at, failed_count,  # noqa: E402
                   load_anchors, drop_begin, load_begin, log_error, log_event, pop_notices, queue_items, record_failure, release_lock,
                   save_begin, set_anchor)
from transcript import (after_anchor, count_user_messages, cwd_of, find_transcript, is_interactive,  # noqa: E402
                        last_uuid, read_entries, reduce)
from vault import find_session_note, project_name, seed, snapshot, writable  # noqa: E402
from writer import build_prompt, finish, run_writer  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
FINISH_LOCK_WAIT = 60


def _child() -> bool:
    return bool(os.environ.get("BRAIN_CHILD"))


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def spawn_worker(cfg: Config) -> None:
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "worker"], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def session_end(cfg: Config, payload: dict, spawn=spawn_worker) -> None:
    if not _child():
        log_event(cfg, "end", payload.get("session_id"), "reason", payload.get("reason"))
    if _child() or not cfg.vault or not cfg.auto_capture or not payload.get("session_id"):
        return
    if cfg.excluded(payload.get("cwd", "")):
        return
    ensure_installed_at(cfg)
    enqueue(cfg, {k: payload.get(k) for k in ("session_id", "transcript_path", "cwd", "reason")})
    spawn(cfg)


def session_start(cfg: Config, payload: dict, spawn=spawn_worker, today: date = None):
    if _child():
        return None
    log_event(cfg, "start", payload.get("session_id"), "source", payload.get("source"))
    if not cfg.vault:
        return "dory: vault_path is not set. Set it with /config (plugin dory) to enable the second brain."
    installed_at = ensure_installed_at(cfg)
    notices = pop_notices(cfg)
    if not writable(cfg.vault):
        notices.append(f"Vault not writable: {cfg.vault}")
    failed = failed_count(cfg)
    if failed:
        notices.append(f"{failed} session(s) could not be written, see {cfg.data / 'errors.log'}")
    if cfg.auto_capture:
        for item in find_missed(cfg, payload.get("session_id"), time.time(), installed_at):
            enqueue(cfg, item)
        if queue_items(cfg):
            spawn(cfg)
    if payload.get("source") == "clear":
        notices.append("The previous session is being written to the vault right now (sessions/). "
                       "Look it up in 1-2 minutes if you need it.")
    if not cfg.vault.is_dir():
        return "\n".join(["dory: vault not found: " + str(cfg.vault)] + notices)
    return render(cfg, payload.get("cwd") or os.getcwd(), notices, today or date.today())


def process(cfg: Config, item: dict, today: date) -> str:
    sid = item["session_id"]
    entries = read_entries(item["transcript_path"])
    new = after_anchor(entries, load_anchors(cfg).get(sid, {}).get("uuid"))
    last = last_uuid(entries)
    if not is_interactive(entries) or count_user_messages(new) < cfg.min_user_messages:
        set_anchor(cfg, sid, last)
        return "skipped"
    cwd = item.get("cwd") or cwd_of(entries) or ""
    project, root = project_name(cfg.vault, cwd)
    existing = find_session_note(cfg.vault, sid)
    types_md = cfg.vault / "types.md"
    prompt = build_prompt(
        (PLUGIN_ROOT / "rules" / "writer.md").read_text(encoding="utf-8"),
        types_md.read_text(encoding="utf-8") if types_md.exists() else "",
        {"vault": cfg.vault, "date": today.isoformat(), "language": cfg.language, "project": project,
         "project_root": root, "session_id": sid,
         "existing_note": existing.relative_to(cfg.vault).as_posix() if existing else None},
        reduce(new),
    )
    before, started = snapshot(cfg.vault), time.time()
    answer = run_writer(cfg, prompt)
    set_anchor(cfg, sid, last)
    finish(cfg, session_id=sid, written_by="background", started=started, before=before, project=project, cwd=cwd,
           today=today, now=_now())
    return "skip-answer" if answer.strip().upper() == "SKIP" else "written"


def worker(cfg: Config, today: date = None) -> None:
    if not cfg.vault or not acquire_lock(cfg):
        return
    try:
        if not writable(cfg.vault):
            log_error(cfg, f"vault not writable: {cfg.vault}")
            return
        seed(cfg.vault, PLUGIN_ROOT / "vault-seed")
        tried = set()
        while True:
            pending = [(p, i) for p, i in queue_items(cfg) if p.name not in tried]
            if not pending:
                break
            path, item = pending[0]
            tried.add(path.name)
            picked_at = path.stat().st_mtime_ns
            try:
                process(cfg, item, today or date.today())
                if path.stat().st_mtime_ns == picked_at:
                    path.unlink(missing_ok=True)
                else:
                    tried.discard(path.name)  # re-enqueued while processing (/resume): run it again
            except Exception as e:  # noqa: BLE001  one bad session must not stop the queue
                record_failure(cfg, path, item, f"{type(e).__name__}: {e}")
    finally:
        release_lock(cfg)


def begin(cfg: Config, key: str) -> None:
    save_begin(cfg, key, time.time(), sorted(snapshot(cfg.vault)))


def finish_cmd(cfg: Config, session_id, written_by: str, today: date = None) -> int:
    if not acquire_lock(cfg, wait=FINISH_LOCK_WAIT):
        print("dory: the background run is writing right now. Run the finish step again in a minute.")
        return 1
    try:
        seed(cfg.vault, PLUGIN_ROOT / "vault-seed")
        key = session_id or "note"
        started, before = load_begin(cfg, key) or (time.time() - 1800, set())
        path = find_transcript(cfg.projects_dir, session_id)
        entries = read_entries(path) if path else []
        cwd = cwd_of(entries) or os.getcwd()
        project, _ = project_name(cfg.vault, cwd)
        sid = session_id or (path.stem if path and written_by == "save" else None)
        changed = finish(cfg, session_id=sid if written_by == "save" else None, written_by=written_by,
                         started=started, before=before, project=project, cwd=cwd, today=today or date.today(),
                         now=_now())
        if written_by == "save" and sid:
            set_anchor(cfg, sid, last_uuid(entries))
        drop_begin(cfg, key)
        print("dory: wrote " + (", ".join(p.relative_to(cfg.vault).as_posix() for p in changed) or "nothing"))
        return 0
    finally:
        release_lock(cfg)


def _payload() -> dict:
    try:
        data = json.load(sys.stdin)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def main(argv: list = None) -> int:
    ap = argparse.ArgumentParser(prog="brain.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("session-end")
    sub.add_parser("session-start")
    sub.add_parser("worker")
    for name in ("begin", "finish"):
        p = sub.add_parser(name)
        p.add_argument("--session")
        p.add_argument("--vault")
        p.add_argument("--data")
        p.add_argument("--projects")
        p.add_argument("--active-days", type=int)
        if name == "finish":
            p.add_argument("--written-by", choices=["save", "note"], required=True)
    args = ap.parse_args(argv)
    cfg = Config.from_env()
    if getattr(args, "vault", None):
        cfg.vault = Path(args.vault).expanduser()
    if getattr(args, "data", None):
        cfg.data = Path(args.data).expanduser()
    if getattr(args, "projects", None):
        cfg.projects_dir = Path(args.projects).expanduser()
    if getattr(args, "active_days", None):
        cfg.active_days = args.active_days
    session = getattr(args, "session", None)
    if session and session.startswith("${"):
        session = None  # ponytail: placeholder was not substituted (spike item 6), fall back to newest transcript
    try:
        if args.cmd == "session-end":
            session_end(cfg, _payload())
        elif args.cmd == "session-start":
            ctx = session_start(cfg, _payload())
            if ctx:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                         "additionalContext": ctx}}, ensure_ascii=False))
        elif args.cmd == "worker":
            worker(cfg)
        elif args.cmd == "begin":
            begin(cfg, session or "note")
        elif args.cmd == "finish":
            return finish_cmd(cfg, session, args.written_by)
    except Exception as e:  # noqa: BLE001  hooks must never break a session
        try:
            log_error(cfg, f"{args.cmd}: {type(e).__name__}: {e}")
        except OSError:
            pass
        if args.cmd in ("begin", "finish"):
            print(f"dory: {args.cmd} failed: {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
