"""Settings: the plugin's options in Claude Code's `/config`, then ~/.config/dory-brain/config.toml,
then the defaults; DORY_VAULT and DORY_STATE_DIR override both.

Claude Code keeps the options the user sets in `/config` or with `/plugin configure` under
`pluginConfigs["dory@<marketplace>"].options` in its `settings.json`, and gives them to hooks as
`CLAUDE_PLUGIN_OPTION_<NAME>`. A skill's Bash command and the worker it starts get no such
variables, so dory reads `settings.json` itself and takes the variables only where the file has
no value: every part of dory then sees the same settings. An option the user never set is in
neither place, whatever default the manifest shows, so config.toml still applies to it.
"""

import json
import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

DEFAULT_CONFIG = Path("~/.config/dory-brain/config.toml")
DEFAULT_STATE = Path("~/.local/state/dory-brain")
DEFAULT_VAULT = Path("~/Obsidian/dory-brain")
PLUGIN = "dory"
MARKETPLACE = "brain"
# The options `plugin.json` declares under `userConfig`; the rest stays in config.toml.
PLUGIN_OPTIONS = ("vault", "language", "model", "context", "context_window")


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
    values.update(plugin_options(env))
    values["vault"] = Path(env.get("DORY_VAULT", values.get("vault", DEFAULT_VAULT))).expanduser()
    values["state_dir"] = Path(
        env.get("DORY_STATE_DIR", values.get("state_dir", DEFAULT_STATE))
    ).expanduser()
    return Config(**values)


def plugin_options(env: dict[str, str]) -> dict[str, object]:
    """The options the user set for dory in Claude Code; an empty or invalid value counts as
    not set."""
    raw: dict[str, object] = {
        name: value
        for name in PLUGIN_OPTIONS
        if (value := env.get(f"CLAUDE_PLUGIN_OPTION_{name.upper()}"))
    }
    raw.update(_saved_options(env))
    found: dict[str, object] = {}
    for name, value in raw.items():
        if value in ("", None):
            continue
        if name == "context_window":
            try:
                found[name] = int(value)
            except (TypeError, ValueError):
                continue
        else:
            found[name] = str(value)
    return found


def claude_settings(env: dict[str, str]) -> Path:
    """Claude Code's user settings; DORY_CLAUDE_SETTINGS points elsewhere (the tests use it)."""
    override = env.get("DORY_CLAUDE_SETTINGS") or os.environ.get("DORY_CLAUDE_SETTINGS")
    if override:
        return Path(override).expanduser()
    return Path(env.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser() / "settings.json"


def _saved_options(env: dict[str, str]) -> dict[str, object]:
    try:
        configs = json.loads(claude_settings(env).read_text()).get("pluginConfigs") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    installed = sorted(key for key in configs if key.partition("@")[0] == PLUGIN)
    if not installed:
        return {}
    key = f"{PLUGIN}@{MARKETPLACE}" if f"{PLUGIN}@{MARKETPLACE}" in installed else installed[0]
    options = configs[key].get("options") if isinstance(configs[key], dict) else None
    if not isinstance(options, dict):
        return {}
    return {name: value for name, value in options.items() if name in PLUGIN_OPTIONS}
