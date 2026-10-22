from pathlib import Path

from dory.config import load_config


def test_settings_no_longer_known_are_ignored(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('language = "German"\nshort_term_sessions = 3\n')

    config = load_config({"DORY_CONFIG": str(config_file), "DORY_VAULT": str(tmp_path / "v")})

    assert config.language == "German"
    assert config.vault == Path(tmp_path / "v")
    assert not hasattr(config, "short_term_sessions")


def config_from(tmp_path: Path, toml: str):
    path = tmp_path / "config.toml"
    path.write_text(toml)
    return load_config({"DORY_CONFIG": str(path), "DORY_VAULT": str(tmp_path / "vault")})


def test_the_level_and_the_window_set_the_limit_of_the_session_start(tmp_path):
    from dory.summary import limit_tokens

    assert limit_tokens(config_from(tmp_path, "")) == 10_000  # lean, 5 % of 200,000
    big = 'context_window = 1000000\ncontext = "{}"\n'
    assert limit_tokens(config_from(tmp_path, big.format("balanced"))) == 100_000
    assert limit_tokens(config_from(tmp_path, big.format("rich"))) == 150_000
    assert limit_tokens(config_from(tmp_path, big.format("huge"))) == 50_000  # unknown is lean
    assert limit_tokens(config_from(tmp_path, "recall_budget_tokens = 1500\n")) == 1500


def test_a_summary_is_at_most_10000_tokens_and_80_percent_of_a_small_limit(tmp_path):
    from dory.summary import digest, target_chars, threshold_chars

    rich = config_from(tmp_path, 'context_window = 1000000\ncontext = "rich"\n')
    small = config_from(tmp_path, "recall_budget_tokens = 1500\n")

    assert target_chars(rich) == 40_000
    assert threshold_chars(rich) == 480_000
    assert target_chars(small) == threshold_chars(small) == 4800
    lean = config_from(tmp_path, "")
    assert digest("text", "work", lean) != digest("text", "work", rich)
