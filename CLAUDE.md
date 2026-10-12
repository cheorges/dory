# dory

## About

Second brain for Claude Code: sessions go into a queue when they end, a background process distills insights from them into Obsidian notes, and new sessions load the relevant short- and long-term memory through a hook. Plus manual commands for `save`, `note` and `search`. Public repository: https://github.com/cheorges/dory

## Tech Stack

Python 3.12+ as uv scripts (PEP 723), pytest; Claude Code plugin `dory` (hooks, skills); `claude -p` for processing; state as files under `~/.local/state/dory-brain/`; Obsidian vault without git; macOS (APFS clones).

---

## Current Status

| Story | Status | Notes |
|-------|--------|-------|
| Second Brain | Done | [Record 001](docs/records/001-second-brain.md), 10 stories built, installed from GitHub since 2026-10-12 (`dory@brain`) |

**Legend:** Open | In Progress | Done

**Next Step:** Watch it in daily use: read the first real notes in the vault, check `dory status`. The plugin is installed from the GitHub marketplace like any user's: changes reach this machine only after a push and `claude plugin marketplace update brain && claude plugin install dory@brain`.

### Future

| Todo | Priority | Problem | Solution |
|------|----------|---------|----------|
| Narrow the Bash grant in save/note | Medium | `/dory:save` and `/dory:note` allow any Bash command; note reads vault content | `allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/dory <command>:*)` as in search, live probe as in `tests/test_live_note.py` |

---

## Recent Decisions

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-09 | One global memory across all projects, not one per project | Knowledge should be findable across projects; assignment to a project or note topic happens automatically on write |
| 2026-10-09 | Obsidian as storage and viewer | Memory stays readable and navigable for the human (graph, backlinks, bases) |
| 2026-10-09 | Vault separate, without git, path configurable; undo through APFS snapshots | Code and data stay apart; no git wanted in the vault |
| 2026-10-09 | A project only comes from a git repo (main path, worktrees included) | Assignment as a fact instead of an LLM judgement; no throwaway projects |
| 2026-10-09 | One skill `dory:rules` for worker, save and note | The writing rules exist exactly once |
| 2026-10-11 | Worker model stays `sonnet` (Haiku as a config option) | Haiku passed all 7 live checks at 1/15 of the cost; the user keeps a quality margin for complex sessions |
| 2026-10-12 | Marketplace named `brain`, plugin installed as `dory@brain` | Short install command; repo is `cheorges/dory` |
| 2026-10-11 | Repository public and in English; note language configurable (`language`, default English), note headings always English | Public use; the recall parses the headings, so they cannot depend on the language |

---

## Project Instructions

<!-- PROJECT INSTRUCTIONS START -->
- Everything in the repository is in English: code, comments, skills, program output, docs and commit messages. The repository is public.
- All notes in the vault follow Obsidian Flavored Markdown (properties in the frontmatter, `[[wikilinks]]`, tags, callouts).
- When writing new notes or sessions, existing content is cleaned up at the same time (merge instead of duplicate, replace outdated content).
<!-- PROJECT INSTRUCTIONS END -->

---

## Architecture

See [Record 001](docs/records/001-second-brain.md) and the README.

- **Capture:** the `SessionEnd` hook puts a transcript copy into a queue; manually also with `/dory:save`
- **Processing:** a background worker drains the queue, assigns the session to a project, writes and cleans up notes
- **Recall:** the `SessionStart` hook loads the project, open items, recent sessions and ranked knowledge notes within a token budget
- **Commands:** `/dory:save`, `/dory:note "..."`, `/dory:search`

---

## Files

Key directories:
- `plugin/` — the Claude Code plugin (`dory/` Python package, `skills/`, `hooks/`, `bin/dory`)
- `docs/records/` — design decisions and feature specs
- `docs/implementation-log.md` — what was built and checked per story
- `docs/notes/` — private notes, gitignored
- `spike/` — the Story 1 spike (hook and `claude -p` experiments)

---

## Development

```bash
uv run pytest -q && uv run ruff check .          # tests and linter (live checks deselected)
DORY_LIVE=1 uv run pytest -m live                # live checks against real claude -p (count against the usage limit)
plugin/bin/dory status                           # queue, failures, API equivalent cost
```
