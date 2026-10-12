# Changelog

All notable changes to dory are listed here. Versions follow [Semantic Versioning](https://semver.org/); the version lives in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py`, and a test keeps them in sync.

## 0.2.0 (2026-10-12)

- README: the configuration shows the three settings a user chooses (`vault`, `language`, `model`); the six tuning settings are documented under "Advanced settings" with what each one guards against. Behaviour and defaults are unchanged.
- README: updating an installed plugin takes `claude plugin update dory@brain`; `claude plugin install` does not pick up a new version.

## 0.1.1 (2026-10-12)

- The marketplace is now called `brain`: install with `claude plugin install dory@brain`. If you installed 0.1.0, remove the old marketplace first: `claude plugin uninstall dory@dory-brain && claude plugin marketplace remove dory-brain`.

## 0.1.0 (2026-10-12)

First release.

- Sessions are queued when they end (`SessionEnd` hook) and processed in the background by a worker running `claude -p` with the shared writing rules: session note, knowledge notes (merged, superseded instead of duplicated), project overview, lists and registers.
- Session start (`SessionStart` hook) injects the project, open items, recent sessions, ranked knowledge notes and a catalog within a token budget, with a boundary between work and private notes.
- `/dory:save` queues the running session without ending it; the rest becomes part 2.
- `/dory:note "..."` writes a note straight into the vault after a snapshot.
- `/dory:search` finds notes by summary, when, tags, file name and text.
- `dory status` and `dory retry` for operations; costs shown as API equivalent, the worker always runs on the Claude subscription.
- Configurable note language (`language`, default English).
