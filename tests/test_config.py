from pathlib import Path

from dory.config import load_config


def test_settings_no_longer_known_are_ignored(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('language = "German"\nshort_term_sessions = 3\n')

    config = load_config({"DORY_CONFIG": str(config_file), "DORY_VAULT": str(tmp_path / "v")})

    assert config.language == "German"
    assert config.vault == Path(tmp_path / "v")
    assert not hasattr(config, "short_term_sessions")
