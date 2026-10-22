"""Keep every test, and every dory subprocess it starts, away from the user's real config.

No test starts a background worker either: one started from a test would run with the default
state directory, which is the user's real one. A test that needs the start patches
`spawn.spawn_worker` or sets DORY_NO_SPAWN in its own environment. Claude Code's settings and
plugin options are read from an empty file, never from the user's; CLAUDE_CONFIG_DIR itself stays,
so `claude` in the live checks keeps its login.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.getbasetemp()
    monkeypatch.setenv("DORY_CONFIG", str(base / "no-config.toml"))
    monkeypatch.setenv("DORY_CLAUDE_SETTINGS", str(base / "no-claude-settings.json"))
    monkeypatch.setenv("DORY_NO_SPAWN", "1")
    for name in [name for name in os.environ if name.startswith("CLAUDE_PLUGIN_OPTION_")]:
        monkeypatch.delenv(name)
