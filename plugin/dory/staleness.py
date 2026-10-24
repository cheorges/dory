"""Signals for entries that may be stale, computed when read; nothing is deleted.

dory keeps per entry of the knowledge and topic files when it was added and last changed, in
the state directory, updated from the baseline diff of every run and synced with the files, so
edits in Obsidian count from the run that first sees them. Three flags follow from it:

- `missing path`: a project's entry names a repository path that no longer exists,
- `unchanged since <date>`: nothing changed the entry for more than 90 days,
- `changed after this session`: another run or the user changed it after the session being
  processed ended, so the entry holds newer knowledge than that session.

The worker sees all three in its catalog; `dory status` counts the first two; the session start
marks only a missing path, the one flag that is a fact rather than a hint.
"""

import contextlib
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from dory import entries, scopes
from dory.frontmatter import read_frontmatter
from dory.state import StateDir

STORE = "entries.json"
STALE_DAYS = 90
GIT_TIMEOUT_SECONDS = 5  # the session start waits for it
_CODE = re.compile(r"`([^`\s]+)`")
_NOT_A_PATH = re.compile(r"[<>*{}|:$]|^[/~.]")


def load(state: StateDir) -> dict[str, dict[str, dict[str, str]]]:
    try:
        return json.loads((state.root / STORE).read_text())
    except (OSError, ValueError):
        return {}


def record(state: StateDir, changes: list[dict], entry_id: str, now: datetime) -> None:
    """Date the entries a run added or changed, from the checks' report of that run."""
    store = load(state)
    stamp = now.isoformat()
    for change in changes:
        kind, relative = change.get("change"), change.get("file", "")
        if kind not in ("added", "changed", "removed"):
            continue
        records = store.setdefault(relative, {})
        key = entries.key(change.get("lead", ""))
        if kind == "removed":
            records.pop(key, None)
            continue
        old = records.pop(entries.key(change["was"]), None) if change.get("was") else None
        old = old or records.get(key) or {}
        # The new text is read by `observe`, which runs right after and keeps this run as author.
        records[key] = {
            "added": old.get("added", stamp),
            "changed": stamp,
            "by": entry_id,
            "hash": "",
        }
    _save(state, store)


def observe(state: StateDir, vault: Path, now: datetime, by: str = "") -> None:
    """Sync the store with the files: date entries seen for the first time, drop vanished ones.

    A change found here is the user's, unless `by` names the queue entry whose earlier attempt
    was killed before its checks ran and so left its edits undated."""
    store = load(state)
    stamp = now.isoformat()
    synced: dict[str, dict[str, dict[str, str]]] = {}
    for relative in _files(vault):
        name = relative.as_posix()
        first_sight = name not in store  # a file from before: its entries' history is unknown
        known = store.get(name, {})
        records = {}
        for item in _entries(vault / relative):
            digest = _hash(item.text)
            old = known.get(item.key)
            if old is None:
                changed = "" if first_sight else stamp
                records[item.key] = {"added": stamp, "changed": changed, "by": by, "hash": digest}
            elif not old.get("hash"):  # dated by `record` in this run
                records[item.key] = {**old, "hash": digest}
            elif old["hash"] != digest:  # edited outside a run, by the user or a killed run
                records[item.key] = {**old, "changed": stamp, "by": by, "hash": digest}
            else:
                records[item.key] = old
        synced[name] = records
    _save(state, synced)


def flags(
    state: StateDir, vault: Path, *, session_ended: datetime, entry_id: str, now: datetime
) -> dict[str, dict[str, list[str]]]:
    """Per file and entry key, the flags the worker's catalog shows."""
    store = load(state)
    found: dict[str, dict[str, list[str]]] = {}
    for relative in _files(vault):
        name = relative.as_posix()
        repo = _repo_files(project_root(vault, relative))
        for item in _entries(vault / relative):
            labels = [f"missing path `{path}`" for path in _missing(item.text, repo)]
            dated = store.get(name, {}).get(item.key)
            if dated:
                known = dated.get("changed")  # empty: dated before dory kept history
                changed = datetime.fromisoformat(known or dated["added"])
                by = str(dated.get("by") or "")
                if known and changed > session_ended and _session(by) != _session(entry_id):
                    labels.insert(0, "changed after this session")
                if changed < now - timedelta(days=STALE_DAYS):
                    labels.append(f"unchanged since {changed:%Y-%m-%d}")
            if labels:
                found.setdefault(name, {})[item.key] = labels
    return found


def counts(state: StateDir, vault: Path, now: datetime) -> dict[str, int]:
    """The flags `dory status` counts."""
    total = {"missing path": 0, "unchanged": 0}
    for per_file in flags(state, vault, session_ended=now, entry_id="", now=now).values():
        for labels in per_file.values():
            total["missing path"] += any(label.startswith("missing path") for label in labels)
            total["unchanged"] += any(label.startswith("unchanged") for label in labels)
    return total


def mark_missing(text: str, root: Path | None) -> str:
    """The text of a project's knowledge file with a marker on each entry whose path is gone."""
    repo = _repo_files(root)
    if repo is None:
        return text
    cursor = 0
    for item in entries.parse(text):
        first = item.text.splitlines()[0]
        found = re.compile(rf"^{re.escape(first)}[ \t]*$", re.M).search(text, cursor)
        if found is None:
            continue
        cursor = found.end()
        missing = _missing(item.text, repo)
        if missing:
            paths = ", ".join(f"`{path}`" for path in missing)
            marker = f" (check: {paths} no longer exists in the repository)"
            text = text[:cursor] + marker + text[cursor:]
            cursor += len(marker)
    return text


def project_root(vault: Path, relative: Path) -> Path | None:
    """The repository of a project's knowledge file, from its `paths`; None for topic files."""
    if relative.name != scopes.KNOWLEDGE or relative.parts[0] != "projects":
        return None
    paths = read_frontmatter(vault / relative).get("paths")
    for path in paths if isinstance(paths, list) else []:
        if Path(str(path)).is_dir():
            return Path(str(path))
    return None


def _missing(text: str, repo: tuple[Path, set[str], set[str]] | None) -> list[str]:
    """Repository paths an entry names that do not exist: their first part must exist, so a
    path elsewhere (`cheorges/other-repo`, `notes/GitHub.md`) is not taken for one."""
    if repo is None:
        return []
    root, files, tops = repo
    missing = []
    for candidate in _CODE.findall(text):
        path = candidate.rstrip("/")
        if "/" not in path or _NOT_A_PATH.search(path) or path.split("/")[0] not in tops:
            continue
        listed = path in files or any(name.startswith(path + "/") for name in files)
        if not listed and not (root / path).exists():  # ignored files exist without a listing
            missing.append(candidate)
    return missing


def _repo_files(root: Path | None) -> tuple[Path, set[str], set[str]] | None:
    """The repository with its files and top-level names; None when git cannot list them."""
    if root is None:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        names = {path.name for path in root.iterdir()}
    except (OSError, subprocess.TimeoutExpired):  # no markers rather than no session start
        return None
    if result.returncode != 0:
        return None
    files = set(result.stdout.splitlines())
    return root, files, {name.split("/")[0] for name in files} | names


def _files(vault: Path) -> list[Path]:
    knowledge = sorted((vault / "projects").glob(f"*/{scopes.KNOWLEDGE}"))
    return [path.relative_to(vault) for path in knowledge if path.is_file()] + [
        path
        for path in scopes.notes_folder_files(vault)
        if scopes.file_type(vault / path) == "topic"
    ]


def _entries(path: Path) -> list[entries.Entry]:
    with contextlib.suppress(OSError):
        return entries.parse(path.read_text(encoding="utf-8", errors="replace"))
    return []


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _save(state: StateDir, store: dict) -> None:
    path = state.root / STORE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=1, ensure_ascii=False))
    tmp.replace(path)


def _session(entry_id: str) -> str:
    """The session of a queue entry id (`<ended>-<session id>`): a `/dory:save` cut and the
    session's end are two entries of one session. Empty for the user; an id without a session
    part stands for itself."""
    _, separator, session = entry_id.partition("-")
    return session if separator else entry_id
