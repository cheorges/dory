"""Keep every test, and every dory subprocess it starts, away from the user's real config.

No test starts a background worker either: one started from a test would run with the default
state directory, which is the user's real one. A test that needs the start patches
`spawn.spawn_worker` or sets DORY_NO_SPAWN in its own environment.
"""

import pytest


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("DORY_CONFIG", str(tmp_path_factory.getbasetemp() / "no-config.toml"))
    monkeypatch.setenv("DORY_NO_SPAWN", "1")
