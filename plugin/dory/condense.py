"""Turn a Claude Code transcript (JSONL) into plain text a worker run may read.

Only what the user and Claude wrote survives. Tool output, attachments and command
wrappers are dropped because they carry foreign text (prompt injection) and personal
data (e-mail, git name, organisation id). Secrets are redacted before anything else.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from dory.secrets import redact

# User lines that carry command or tool output rather than something the user wrote.
_WRAPPER_START = (
    "<command-name>",
    "<command-message>",
    "<local-command-",
    "<bash-",
    "<task-notification>",
)
_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?(?:</system-reminder>|\Z)", re.S)
_CHARS_PER_TOKEN = 4


@dataclass
class Condensed:
    text: str
    uuids: list[str] = field(default_factory=list)
    user_messages: int = 0
    skipped: bool = False


def condense(
    transcript: Path,
    *,
    min_user_messages: int,
    seen: set[str] | None = None,
    max_tokens: int = 30_000,
) -> Condensed:
    seen = set(seen or ())
    lines = _read_lines(transcript)
    user_messages = sum(1 for line in lines if _user_text(line))
    if user_messages < min_user_messages:
        return Condensed(text="", user_messages=user_messages, skipped=True)

    entries: list[str] = []
    compact_summaries: list[str] = []
    new_uuids: list[str] = []
    for line in lines:
        uuid = line.get("uuid")
        if not uuid or uuid in seen:
            continue
        new_uuids.append(uuid)
        seen.add(uuid)
        if line.get("isCompactSummary"):
            compact_summaries.append(_clean(_content_text(line)))
            continue
        entries.extend(_entries_for(line))

    text = _fit("\n\n".join(entries), entries, compact_summaries, max_tokens)
    return Condensed(text=text, uuids=new_uuids, user_messages=user_messages)


def _read_lines(transcript: Path) -> list[dict]:
    lines = []
    for raw in transcript.read_text(errors="replace").splitlines():
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue  # a live transcript may end in a half-written line
    return lines


def _is_conversation(line: dict) -> bool:
    return (
        line.get("type") in ("user", "assistant")
        and not line.get("isMeta")
        and not line.get("isSidechain")
        and not line.get("isCompactSummary")
    )


def _user_text(line: dict) -> str:
    if not _is_conversation(line) or line.get("type") != "user":
        return ""
    text = _clean(_content_text(line))
    if text.startswith(_WRAPPER_START):
        return ""
    return text


def _content_text(line: dict) -> str:
    content = (line.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _clean(text: str) -> str:
    return redact(_SYSTEM_REMINDER.sub("", text)).strip()


def _entries_for(line: dict) -> list[str]:
    if not _is_conversation(line):
        return []
    if line["type"] == "user":
        return _user_entries(line)
    return _assistant_entries(line)


def _user_entries(line: dict) -> list[str]:
    entries = []
    text = _user_text(line)
    if text:
        entries.append(f"**User:** {text}")
    content = (line.get("message") or {}).get("content")
    if isinstance(content, list):
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and block.get("is_error")
            ):
                entries.append(f"[Tool-Fehler: {_first_line(block.get('content'))}]")
    return entries


def _assistant_entries(line: dict) -> list[str]:
    content = (line.get("message") or {}).get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    entries = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = _clean(block.get("text", ""))
            if text:
                entries.append(f"**Claude:** {text}")
        elif block.get("type") == "tool_use":
            entries.append(f"[Tool: {block.get('name', '?')}]")
    return entries


def _first_line(content: object) -> str:
    if isinstance(content, list):
        content = " ".join(block.get("text", "") for block in content if isinstance(block, dict))
    first = str(content or "").strip().splitlines()
    return redact(first[0][:200]) if first else ""


def _fit(text: str, entries: list[str], summaries: list[str], max_tokens: int) -> str:
    budget = max_tokens * _CHARS_PER_TOKEN
    if len(text) <= budget:
        return text
    entries = [e if len(e) <= budget else e[:budget] + " [... truncated ...]" for e in entries]
    if len(entries) < 3:
        return "\n\n".join(entries)[:budget] + " [... truncated ...]"
    head_budget, tail_budget = budget * 2 // 5, budget * 3 // 5
    head = _take(entries, head_budget)
    tail = _take(entries[len(head) :][::-1], tail_budget)[::-1]
    skipped = len(entries) - len(head) - len(tail)
    middle = [f"[... {skipped} entries truncated ...]"]
    middle += [f"**Summary from compaction:** {s}" for s in summaries if s]
    return "\n\n".join(head + middle + tail)


def _take(entries: list[str], budget: int) -> list[str]:
    taken, used = [], 0
    for entry in entries:
        if taken and used + len(entry) > budget:
            break
        taken.append(entry)
        used += len(entry)
    return taken
