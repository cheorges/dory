"""Settings from ~/.config/dory-brain/config.toml, overridable by environment."""

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

DEFAULT_CONFIG = Path("~/.config/dory-brain/config.toml")
DEFAULT_STATE = Path("~/.local/state/dory-brain")
DEFAULT_VAULT = Path("~/Obsidian/dory-brain")


@dataclass(frozen=True)
class Config:
    vault: Path
    state_dir: Path
    model: str = "sonnet"
    language: str = "English"  # language the notes are written in
    context: str = "lean"  # share of the context window the session start may take
    context_window: int = 200_000  # tokens; the smallest window you work with
    recall_budget_tokens: int | None = None  # an exact limit in tokens instead of the level
    min_user_messages: int = 3
    condense_max_tokens: int = 30_000
    worker_timeout_minutes: int = 10
    snapshots_keep: int = 50


def load_config(env: dict[str, str] | None = None) -> Config:
    env = dict(os.environ) if env is None else env
    config_file = Path(env.get("DORY_CONFIG", DEFAULT_CONFIG)).expanduser()
    values: dict = {}
    if config_file.is_file():
        values = tomllib.loads(config_file.read_text())
    known = {f.name for f in fields(Config)}
    values = {key: value for key, value in values.items() if key in known}
    values["vault"] = Path(env.get("DORY_VAULT", values.get("vault", DEFAULT_VAULT))).expanduser()
    values["state_dir"] = Path(
        env.get("DORY_STATE_DIR", values.get("state_dir", DEFAULT_STATE))
    ).expanduser()
    return Config(**values)
