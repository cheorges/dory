"""SessionStart context block and catch-up of missed sessions."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from frontmatter import open_items, parse
from state import Config, failed_ids, load_anchors, queue_items, set_anchor
from transcript import cwd_of, is_interactive, last_uuid, read_entries
from vault import active_notes, find_project_note, hot_line, project_root

TARGET_CHARS = 4000
HARD_CHARS = 9000
CATCHUP_MAX_AGE = 7 * 86400
CATCHUP_MIN_IDLE = 2 * 3600

HEADER = ("dory: second brain in {vault}.\n"
          "Look things up with the skill dory:search as soon as a project, customer, tool or earlier decision "
          "comes up that is not in the current context, and before saying you don't know something. "
          "Every state carries a date and may be outdated.")


def _current_project(cfg: Config, cwd: str):
    note = find_project_note(cfg.vault, project_root(cwd)) if cwd else None
    if not note:
        return None, []
    meta, body = parse(note.read_text(encoding="utf-8"))
    block = [f"## Current project: [[{note.stem}]] ({meta.get('last_active', '?')})", str(meta.get("summary", ""))]
    items = open_items(body)
    if items:
        block.append("Open: " + "; ".join(items))
    return note, block


def render(cfg: Config, cwd: str, notices: list, today: date, target: int = TARGET_CHARS,
           hard: int = HARD_CHARS) -> str:
    note, project_block = _current_project(cfg, cwd)
    active = [n for n in active_notes(cfg.vault, today, cfg.active_days) if n[0] != note]
    lines = [hot_line(*n) for n in active]
    pinned = [n[1].get("pinned") is True for n in active]

    def assemble(dropped: int) -> str:
        parts = [HEADER.format(vault=cfg.vault)]
        if project_block:
            parts.append("\n".join(project_block))
        if lines or dropped:
            more = [f"+{dropped} more in hot.md"] if dropped else []
            parts.append("\n".join([f"## Active (last {cfg.active_days} days)"] + lines + more))
        if notices:
            parts.append("\n".join(["## Notices"] + [f"- {n}" for n in notices]))
        return "\n\n".join(parts)

    dropped = 0
    text = assemble(dropped)
    while len(text) > target and not all(pinned):
        i = max(k for k, p in enumerate(pinned) if not p)  # oldest unpinned line
        del lines[i], pinned[i]
        dropped += 1
        text = assemble(dropped)
    if len(text) > hard:
        text = text[: hard - 20] + "\n[... truncated]"
    return text


def find_missed(cfg: Config, current_session, now: float, installed_at: float) -> list:
    anchors = load_anchors(cfg)
    queued = {p.stem for p, _ in queue_items(cfg)} | failed_ids(cfg)
    missed = []
    for path in sorted(Path(cfg.projects_dir).glob("*/*.jsonl")):
        sid = path.stem
        if sid == current_session or sid in queued:
            continue
        mtime = path.stat().st_mtime
        if mtime < installed_at or mtime < now - CATCHUP_MAX_AGE or mtime > now - CATCHUP_MIN_IDLE:
            continue
        if sid in anchors and mtime <= anchors[sid].get("at", 0):
            continue
        entries = read_entries(path)
        last = last_uuid(entries)
        if last is None or anchors.get(sid, {}).get("uuid") == last:
            continue
        cwd = cwd_of(entries) or ""
        if not is_interactive(entries) or cfg.excluded(cwd):
            set_anchor(cfg, sid, last)  # ponytail: remember the decision so the file is not re-read every start
            continue
        missed.append({"session_id": sid, "transcript_path": str(path), "cwd": cwd, "reason": "catch-up"})
    return missed
