# dory

## About

Second brain for Claude Code: sessions go into a queue when they end, a background process distills insights from them into Obsidian notes, and new sessions load the relevant knowledge through a hook. Plus manual commands for `save`, `note` and `search`. Public repository: https://github.com/cheorges/dory

## Tech Stack

Python 3.12+ as uv scripts (PEP 723), pytest; Claude Code plugin `dory` (hooks, skills); `claude -p` for processing; state as files under `~/.local/state/dory-brain/`; Obsidian vault without git; macOS (APFS clones).

---

## Current Status

| Story | Status | Notes |
|-------|--------|-------|
| Vault cleanup to the 0.3.0 rules | Open | [Record 002](docs/records/002-note-quality.md), Story S5; task and loop state in `docs/auto-state.md`; can start, 0.3.0 is installed |

**Legend:** Open | In Progress | Done

Second Brain (Record 001) and Note quality (Record 002, all but the vault cleanup) are released; versions are in [CHANGELOG.md](CHANGELOG.md), currently 0.3.0.

**Next Step:** Vault cleanup in a fresh session: `/kolibee:catchup`, tell the loop to start, `/auto-run on`; it snapshots the vault first and halts for review. Then watch what 0.3.0 writes in daily use: fewer notes, names after their statement, renames and deletions in `runs.log`. Releasing: bump the version in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py` (a test keeps them equal), add a CHANGELOG entry, merge through a pull request, tag `vX.Y.Z` on `main` and push the tag; locally `claude plugin marketplace update brain && claude plugin update dory@brain`, then restart.

### Future

| Todo | Priority | Problem | Solution |
|------|----------|---------|----------|
| Narrow the Bash grant in save/note | Medium | `/dory:save` and `/dory:note` allow any Bash command; note reads vault content | `allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/dory <command>:*)` as in search, live probe as in `tests/test_live_note.py` |
| Configurable records folder | Low | The worker checks notes against `docs/records/` only (Record 002); public users keep decision records elsewhere, such as `docs/adr/` | A setting with the folders to capture, default `docs/records` |
| Prune `work/` | Low | Every entry's `bundle.md`, with its condensed transcript, stays under `~/.local/state/dory-brain/work/` indefinitely | Keep the last N bundle directories, as the snapshots do |
| Merge vault project `dory-brain` into `dory` | Low | Renaming the repository created a second project; the old notes stay under `projects/dory-brain/` and no longer load | Merge the folders, fix links and `paths`, point `projects.json` at the new path |

---

## Recent Decisions

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-11 | Worker model stays `sonnet` (Haiku as a config option) | Haiku passed all 7 live checks at 1/15 of the cost; the user keeps a quality margin for complex sessions |
| 2026-10-11 | Repository public and in English; note language configurable (`language`, default English), note headings always English | Public use; the recall reads the frontmatter keys, and the worker finds existing sections by their English names, so neither can depend on the language |
| 2026-10-12 | Apache 2.0 with a NOTICE file | Free use, also commercial; redistributions must credit the author |
| 2026-10-12 | Public history starts fresh with the 0.1.0 commits; the old history exists only on local `backup/*` branches | The old commits carried German text and customer names |
| 2026-10-12 | Marketplace named `brain`, plugin installed as `dory@brain`, also on the author's machine from GitHub | Short install command; the author runs exactly what users get, so changes need a push and `plugin update` |
| 2026-10-15 | Session start injects knowledge only: no open items, no recent sessions ([Record 002](docs/records/002-note-quality.md)) | Both repeat what the CLAUDE.md, `git log` and handover notes already say, and open items go stale because the worker only sees transcripts; the start should bring what one would not know to ask for |
| 2026-10-16 | Knowledge notes only when they really matter, named after their core statement; a stale note is corrected and renamed, a note the CLAUDE.md covers is deleted ([Record 002](docs/records/002-note-quality.md), decision 6) | The vault is a living second brain: the project view shows only what holds now; history lives in the session logs and the snapshots. 15 of 15 sessions had produced notes, a third of them describing the code |

The design decisions of 2026-10-09 (one global memory, Obsidian, vault without git, project = git repo, one rules skill) are in [Record 001](docs/records/001-second-brain.md).

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
- **Processing:** a background worker drains the queue, assigns the session to a project, writes and cleans up notes; renames and deletions the run marks are carried out by dory's code afterwards (`vaultops.py`)
- **Recall:** the `SessionStart` hook loads the project line and ranked knowledge notes within a token budget, plus a pointer to sessions still in the queue
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
