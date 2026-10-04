"""Plugin state outside the vault: config, queue, anchors, lock, errors, notices."""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

MAX_ATTEMPTS = 3
_OPT = "CLAUDE_PLUGIN_OPTION_"


def _list(value: str) -> list:
    value = (value or "").strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            return [str(v) for v in json.loads(value)]
        except json.JSONDecodeError:
            pass
    return [p.strip() for p in re.split(r"[,\n]", value.strip("[]")) if p.strip()]


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class Config:
    vault: Path = None
    data: Path = field(default_factory=lambda: Path.home() / ".claude" / "plugins" / "data" / "dory")
    language: str = "English"
    active_days: int = 14
    model: str = "sonnet"
    min_user_messages: int = 3
    auto_capture: bool = True
    exclude_paths: list = field(default_factory=list)
    projects_dir: Path = field(default_factory=lambda: Path.home() / ".claude" / "projects")

    @classmethod
    def from_env(cls, env: dict = None) -> "Config":
        env = os.environ if env is None else env
        opt = lambda k: env.get(_OPT + k, "")  # noqa: E731
        cfg = cls()
        if opt("VAULT_PATH"):
            cfg.vault = Path(opt("VAULT_PATH")).expanduser()
        if env.get("CLAUDE_PLUGIN_DATA"):
            cfg.data = Path(env["CLAUDE_PLUGIN_DATA"])
        cfg.language = opt("NOTE_LANGUAGE") or cfg.language
        cfg.active_days = _int(opt("ACTIVE_DAYS"), cfg.active_days)
        cfg.model = opt("WRITER_MODEL") or cfg.model
        cfg.min_user_messages = _int(opt("MIN_USER_MESSAGES"), cfg.min_user_messages)
        cfg.auto_capture = opt("AUTO_CAPTURE").lower() not in ("false", "0", "no")
        cfg.exclude_paths = _list(opt("EXCLUDE_PATHS"))
        return cfg

    def excluded(self, cwd: str) -> bool:
        if not cwd:
            return False
        here = Path(cwd).expanduser().resolve()
        for p in self.exclude_paths:
            base = Path(p).expanduser().resolve()
            if here == base or base in here.parents:
                return True
        return False


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _queue(cfg: Config) -> Path:
    return cfg.data / "queue"


def enqueue(cfg: Config, item: dict) -> Path:
    path = _queue(cfg) / f"{item['session_id']}.json"
    old = _read_json(path, {})
    _write_json(path, {**item, "attempts": old.get("attempts", 0)})
    return path


def queue_items(cfg: Config) -> list:
    paths = sorted(_queue(cfg).glob("*.json"), key=lambda p: p.stat().st_mtime) if _queue(cfg).is_dir() else []
    return [(p, _read_json(p, {})) for p in paths]


def record_failure(cfg: Config, path: Path, item: dict, error: str) -> None:
    item = {**item, "attempts": item.get("attempts", 0) + 1, "last_error": error[-500:]}
    log_error(cfg, f"session {item.get('session_id')}: {error}")
    if item["attempts"] >= MAX_ATTEMPTS:
        _write_json(_queue(cfg) / "failed" / path.name, item)
        path.unlink(missing_ok=True)
    else:
        _write_json(path, item)


def failed_ids(cfg: Config) -> set:
    return {p.stem for p in (_queue(cfg) / "failed").glob("*.json")}


def failed_count(cfg: Config) -> int:
    return len(failed_ids(cfg))


def load_anchors(cfg: Config) -> dict:
    return _read_json(cfg.data / "processed.json", {})


def set_anchor(cfg: Config, session_id: str, uuid) -> None:
    anchors = load_anchors(cfg)
    anchors[session_id] = {"uuid": uuid, "at": time.time()}
    _write_json(cfg.data / "processed.json", anchors)


def _alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock(cfg: Config, wait: float = 0.0) -> bool:
    lock = cfg.data / "lock"
    deadline = time.time() + wait
    while True:
        try:
            lock.mkdir(parents=True)
            (lock / "pid").write_text(str(os.getpid()))
            return True
        except FileExistsError:
            pid = _int(_read_text(lock / "pid"), 0)
            young = time.time() - _mtime(lock) < 5  # ponytail: pid file not written yet by a fresh holder
            if (not pid and not young) or (pid and not _alive(pid)):
                shutil.rmtree(lock, ignore_errors=True)
                continue
            if time.time() >= deadline:
                return False
            time.sleep(0.5)


def _read_text(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def release_lock(cfg: Config) -> None:
    shutil.rmtree(cfg.data / "lock", ignore_errors=True)


def log_error(cfg: Config, message: str) -> None:
    cfg.data.mkdir(parents=True, exist_ok=True)
    with open(cfg.data / "errors.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def log_event(cfg: Config, event: str, session_id, key: str, value) -> None:
    # ponytail: one line per hook call, never rotated; about 60 bytes, so years before it matters
    try:
        cfg.data.mkdir(parents=True, exist_ok=True)
        with open(cfg.data / "events.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {event} session {session_id or '-'} {key}={value or '-'}\n")
    except OSError:
        pass


def add_notice(cfg: Config, message: str) -> None:
    cfg.data.mkdir(parents=True, exist_ok=True)
    with open(cfg.data / "notices.txt", "a", encoding="utf-8") as f:
        f.write(message.replace("\n", " ") + "\n")


def pop_notices(cfg: Config) -> list:
    path = cfg.data / "notices.txt"
    lines = [l for l in _read_text(path).splitlines() if l.strip()]
    path.unlink(missing_ok=True)
    return lines


def ensure_installed_at(cfg: Config) -> float:
    path = cfg.data / "installed_at"
    try:
        return float(path.read_text())
    except (OSError, ValueError):
        now = time.time()
        cfg.data.mkdir(parents=True, exist_ok=True)
        path.write_text(str(now))
        return now


def save_begin(cfg: Config, key: str, started: float, before: list) -> None:
    _write_json(cfg.data / "begin" / f"{key}.json", {"started": started, "before": sorted(before)})


def load_begin(cfg: Config, key: str):
    data = _read_json(cfg.data / "begin" / f"{key}.json", None)
    return (data["started"], set(data["before"])) if data else None


def drop_begin(cfg: Config, key: str) -> None:
    (cfg.data / "begin" / f"{key}.json").unlink(missing_ok=True)
