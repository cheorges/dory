"""Keep every test, and every dory subprocess it starts, away from the user's real config."""

import pytest


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("DORY_CONFIG", str(tmp_path_factory.getbasetemp() / "no-config.toml"))
