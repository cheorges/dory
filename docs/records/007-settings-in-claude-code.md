# Record 007: Settings in Claude Code

## Status

Done (2026-10-22): released as 0.8.0; the language list in 0.8.1 and 0.9.0.

---

## Problem

dory's settings live in `~/.config/dory-brain/config.toml`. The user looks for them where Claude Code keeps its own, in `/config`, and does not find them there: a file they have to know about, with names they have to look up, and no check of a value before dory runs with it. The user also wants `opus` as a worker model next to `sonnet` and `haiku`.

## Options Considered

All decisions were made by the user on 2026-10-22.

### Decision 1: Where the settings are edited

- **Option A:** a skill `/dory:config` that shows the file and changes it in a dialog.
- **Option B:** the plugin's `userConfig` in `plugin.json`. Claude Code shows each option as a row in `/config` and in `/plugin configure dory@brain`, checks the value on save (a choice list, a number with a minimum), and stores it under `pluginConfigs` in its `settings.json`.

**Decision:** B. The settings appear where Claude Code's own are, and Claude Code validates them.

### Decision 2: Which settings move

The five a user changes: `vault`, `language`, `model`, `context`, `context_window`. The rest (`recall_budget_tokens`, `min_user_messages`, `condense_max_tokens`, `worker_timeout_minutes`, `snapshots_keep`) stays in config.toml: few people need it, and every row in `/config` costs attention. `model` offers `sonnet`, `haiku` and `opus`.

### Decision 3: How every part of dory reads them

A live probe on 2026-10-22 (Claude Code 2.1.308, an isolated `CLAUDE_CONFIG_DIR`, a throwaway plugin):

| Case | Result |
|---|---|
| Option never set, with or without `default` in the manifest | not in the hook's environment, not in `settings.json` |
| Option set | `CLAUDE_PLUGIN_OPTION_<NAME>` in every hook, and `pluginConfigs["<plugin>@<marketplace>"].options` in `settings.json` |
| A value outside the choice list | refused when saving |
| After a change | Claude Code says "Restart Claude Code to apply it" |

Only hooks get the variables. `/dory:note` and `/dory:save` run `dory` through Bash from a skill, and the worker they start inherits that environment, so they would run with other values than the hooks.

- **Option A:** the `SessionStart` hook copies the variables into the state directory, and everything reads that copy.
- **Option B:** dory reads `pluginConfigs` from Claude Code's `settings.json` itself and takes the variables only for an option the file lacks.

**Decision:** B. No copy that can be stale, and a part that runs before any session start sees the values too. The storage place is documented by Claude Code (plugin manifest reference, "Where values are stored").

### Decision 4: Order and defaults

`/config` wins over config.toml, config.toml over dory's defaults; `DORY_VAULT` and `DORY_STATE_DIR` override all. A choice list must have a default (the validator refuses one without), so `model`, `context` and, since 0.8.1, `language` show `sonnet`, `lean` and `English`; the probe shows such a default is display only, so a value in config.toml still applies until the user sets the option. `vault` and `context_window` declare no default: `/config` would show `~/Obsidian/dory-brain` to a user whose config.toml names another vault.

### Decision 5: The note language as a list (0.8.1)

The user asked for a choice list instead of free text, with English as default. The list holds 16 common languages. A language not on it goes into config.toml, which at first applied only while the option was not set; once set in `/config`, a value cannot be emptied again (`claude plugin configure` reports no change for an empty value). Since 0.9.0 the list ends with `Other (config.toml)`: dory treats it as not set, so config.toml decides (`config.OTHER_LANGUAGE`).

## Solution

- `plugin.json`: `userConfig` with the five options; `model` and `context` as choice lists, `context_window` a number of at least 10,000, `vault` a directory.
- `config.py`: `plugin_options` reads `pluginConfigs["dory@brain"]` (another marketplace's `dory@...` if that is the one installed) from `$CLAUDE_CONFIG_DIR/settings.json`, else `~/.claude/settings.json`, then `CLAUDE_PLUGIN_OPTION_*` for what the file lacks; an empty value or a window that is no number counts as not set. `load_config` puts them over config.toml.
- Tests read Claude Code's settings from an empty file (`DORY_CLAUDE_SETTINGS` in `tests/conftest.py`) and drop every `CLAUDE_PLUGIN_OPTION_*`, so no test sees the user's options. `CLAUDE_CONFIG_DIR` stays, so `claude` in the live checks keeps its login.
- The hook commands quote `${CLAUDE_PLUGIN_ROOT}`, which the validator asks for.
- README, guide, CHANGELOG.

### Risks

- **The storage place changes.** If Claude Code moves `pluginConfigs`, the skills and the worker fall back to config.toml while the hooks still see the variables. `test_the_manifest_declares_exactly_the_options_dory_reads` keeps the manifest and the code together; the place itself is not checked by a test.
- **opus costs the most.** The worker runs on the user's subscription; opus uses the usage limit fastest.

## User Stories

### Story S1: The settings in `/config`

**As a** user
**I want** dory's main settings in Claude Code's `/config`
**So that** I find and change them where Claude Code's own are, with the values checked

**Acceptance Criteria:**
- [x] (unit) An option set in Claude Code wins over config.toml; config.toml decides what is not set; `DORY_VAULT` wins over both.
- [x] (unit) The hook variables count only where `settings.json` has no value; an empty value, an unreadable file or a window that is no number leaves the default.
- [x] (unit) The manifest declares exactly the options dory reads; `model` offers sonnet, haiku and opus.
- [x] (live, isolated config) After `claude plugin configure dory@brain` with vault, opus, rich, 1000000 and French, dory reads those values and the start's limit is 150,000 tokens; `model = bogus` is refused by Claude Code.
- [x] `claude plugin validate plugin` passes.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S2: Release 0.8.0

**Acceptance Criteria:** version 0.8.0 in the three files; CHANGELOG, README, guide and CLAUDE.md describe `/config`; committed on `main`, tagged `v0.8.0`.

**Priority:** Medium
**Status:** Done (2026-10-22)
