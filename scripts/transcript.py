"""Claude Code transcript (JSONL) reading, reduction and redaction."""
from __future__ import annotations

import json
import re
from pathlib import Path

TRANSCRIPT_LIMIT = 150_000
_SLASH_COMMAND_MARKERS = ("<command-name>", "<command-message>", "<local-command-")
_TARGET_KEYS = ("file_path", "path", "command", "pattern", "url", "query", "skill", "description")

_SECRETS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abps]-[A-Za-z0-9-]{10,}"),
]
# "key" only counts with a separator in front (api_key, X-Api-Key), so key=lambda, monkey: and Keyword: stay
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b[\w.-]*(?:[_.-]key|apikey|token|secret|password|passwd)[\"']?[ \t]*[=:][ \t]*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|\S[^\n]*)")
_AUTH_HEADER = re.compile(r"(?i)\b(authorization:[ \t]*(?:bearer|basic)|bearer)[ \t]+[A-Za-z0-9._~+/=-]{16,}")


def read_entries(path) -> list:
    entries = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # ponytail: a killed session can leave a half-written last line
    return entries


def after_anchor(entries: list, anchor) -> list:
    if anchor:
        for i, e in enumerate(entries):
            if e.get("uuid") == anchor:
                return entries[i + 1:]
    return entries


def last_uuid(entries: list):
    return next((e["uuid"] for e in reversed(entries) if e.get("uuid")), None)


def _blocks(e: dict):
    content = (e.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _is_conversation(e: dict) -> bool:
    return e.get("type") in ("user", "assistant") and not e.get("isMeta") and not e.get("isSidechain")


def count_user_messages(entries: list) -> int:
    n = 0
    for e in entries:
        if e.get("type") != "user" or not _is_conversation(e):
            continue
        blocks = _blocks(e)
        if any(b.get("type") == "tool_result" for b in blocks):
            continue
        texts = [str(b.get("text", "")).strip() for b in blocks if b.get("type") == "text"]
        if any(t and not t.startswith(_SLASH_COMMAND_MARKERS) for t in texts):
            n += 1
    return n


def is_interactive(entries: list) -> bool:
    # ponytail: relies on "entrypoint" ("cli" interactive, "sdk-*" for claude -p); see spike item 8
    for e in entries:
        ep = e.get("entrypoint")
        if ep:
            return not str(ep).startswith("sdk")
    return True


def cwd_of(entries: list):
    return next((e["cwd"] for e in entries if e.get("cwd")), None)


def _tool_line(block: dict) -> str:
    inp = block.get("input") or {}
    target = redact(next((str(inp[k]) for k in _TARGET_KEYS if inp.get(k)), ""))
    target = " " + target.replace("\n", " ")[:80] if target else ""
    return f"[tool_use: {block.get('name', '?')}{target}]"


def reduce(entries: list, limit: int = TRANSCRIPT_LIMIT) -> str:
    turns = []
    for e in entries:
        if not _is_conversation(e):
            continue
        parts = []
        for b in _blocks(e):
            if b.get("type") == "text" and str(b.get("text", "")).strip():
                parts.append(redact(str(b["text"]).strip()))
            elif b.get("type") == "tool_use":
                parts.append(_tool_line(b))
        if parts:
            turns.append(f"{e['type'].upper()}: " + "\n".join(parts))
    out = "\n\n".join(turns)
    if len(out) > limit:
        half = limit // 2
        out = f"{out[:half]}\n\n[... {len(out) - 2 * half} characters truncated ...]\n\n{out[-half:]}"
    return out


def redact(text: str) -> str:
    for pattern in _SECRETS:
        text = pattern.sub("[REDACTED]", text)
    text = _AUTH_HEADER.sub(lambda m: m.group(1) + " [REDACTED]", text)
    return _SECRET_ASSIGNMENT.sub(lambda m: m.group(1) + "[REDACTED]", text)


def find_transcript(projects_dir: Path, session_id):
    projects_dir = Path(projects_dir)
    if not projects_dir.is_dir():
        return None
    if session_id:
        exact = next(projects_dir.glob(f"*/{session_id}.jsonl"), None)
        if exact:
            return exact
    candidates = list(projects_dir.glob("*/*.jsonl"))
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None
