import json
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


def claude_settings(tmp_path: Path, configs: dict) -> Path:
    path = tmp_path / "claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"theme": "dark", "pluginConfigs": configs}))
    return path


def test_options_set_in_claude_code_win_over_config_toml(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('vault = "~/old"\nlanguage = "German"\ncontext = "rich"\nsnapshots_keep = 7\n')
    settings = claude_settings(
        tmp_path,
        {
            "dory@brain": {"options": {"vault": "/v", "model": "opus", "context_window": 1000000}},
            "other@brain": {"options": {"model": "haiku"}},
        },
    )

    config = load_config({"DORY_CONFIG": str(toml), "DORY_CLAUDE_SETTINGS": str(settings)})

    assert config.vault == Path("/v") and config.model == "opus"
    assert config.context_window == 1_000_000
    assert (config.language, config.context, config.snapshots_keep) == ("German", "rich", 7)


def test_hook_variables_count_where_settings_have_no_value(tmp_path):
    settings = claude_settings(tmp_path, {"dory@elsewhere": {"options": {"language": "French"}}})

    config = load_config(
        {
            "DORY_CONFIG": str(tmp_path / "none.toml"),
            "DORY_CLAUDE_SETTINGS": str(settings),
            "CLAUDE_PLUGIN_OPTION_LANGUAGE": "Italian",
            "CLAUDE_PLUGIN_OPTION_CONTEXT": "balanced",
            "CLAUDE_PLUGIN_OPTION_CONTEXT_WINDOW": "not a number",
        }
    )

    assert config.language == "French"  # the file is current, the variables date from the start
    assert config.context == "balanced"
    assert config.context_window == 200_000


def test_dory_vault_still_overrides_everything(tmp_path):
    settings = claude_settings(tmp_path, {"dory@brain": {"options": {"vault": "/v"}}})

    config = load_config(
        {
            "DORY_CONFIG": str(tmp_path / "none.toml"),
            "DORY_CLAUDE_SETTINGS": str(settings),
            "DORY_VAULT": "/w",
        }
    )

    assert config.vault == Path("/w")


def test_unreadable_settings_or_empty_options_leave_the_defaults(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    empty = claude_settings(tmp_path, {"dory@brain": {"options": {"language": ""}}})

    for path in (broken, empty, tmp_path / "missing.json"):
        config = load_config(
            {"DORY_CONFIG": str(tmp_path / "none.toml"), "DORY_CLAUDE_SETTINGS": str(path)}
        )
        assert (config.language, config.model) == ("English", "sonnet")


def test_the_manifest_declares_exactly_the_options_dory_reads():
    from dory.config import OTHER_LANGUAGE, PLUGIN_OPTIONS

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "plugin/.claude-plugin/plugin.json").read_text()
    )
    options = manifest["userConfig"]
    assert tuple(options) == PLUGIN_OPTIONS
    assert options["model"]["options"] == ["sonnet", "haiku", "opus"]
    assert options["context"]["options"] == ["lean", "balanced", "rich"]
    assert options["model"]["default"] == "sonnet" and options["context"]["default"] == "lean"
    assert (
        options["language"]["default"] == "English" and "German" in options["language"]["options"]
    )
    assert options["language"]["options"][-1] == OTHER_LANGUAGE
    assert all("default" not in options[name] for name in ("vault", "context_window"))


def test_other_in_the_language_list_hands_the_language_to_config_toml(tmp_path):
    from dory.config import OTHER_LANGUAGE

    toml = tmp_path / "config.toml"
    toml.write_text('language = "Catalan"\n')
    other = claude_settings(tmp_path, {"dory@brain": {"options": {"language": OTHER_LANGUAGE}}})

    config = load_config({"DORY_CONFIG": str(toml), "DORY_CLAUDE_SETTINGS": str(other)})
    bare = load_config(
        {
            "DORY_CONFIG": str(tmp_path / "none.toml"),
            "DORY_CLAUDE_SETTINGS": str(tmp_path / "none.json"),
            "CLAUDE_PLUGIN_OPTION_LANGUAGE": OTHER_LANGUAGE,
        }
    )

    assert config.language == "Catalan"
    assert bare.language == "English"
