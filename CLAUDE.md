# dory

## About

Second brain for Claude Code: sessions go into a queue when they end, a background process distills insights from them into one knowledge file per project in Obsidian, and new sessions load that knowledge, or a summary of it, through a hook. Plus manual commands for `save`, `note` and `search`. Public repository: https://github.com/cheorges/dory

## Tech Stack

Python 3.12+ as uv scripts (PEP 723), pytest; Claude Code plugin `dory` (hooks, skills); `claude -p` for processing; state as files under `~/.local/state/dory-brain/`; Obsidian vault without git; macOS (APFS clones).

---

## Current Status

| Story | Status | Notes |
|-------|--------|-------|
| One knowledge file per project (0.4.0) | Done | [Record 003](docs/records/003-project-knowledge-file.md): released as 0.4.0 on 2026-10-20 (pull request #2, tag `v0.4.0`) |
| Test 0.4.0 in daily use | In Progress | Installed 2026-10-20. The 0.3.0 knowledge notes and overviews were deleted without migration (copy in `~/.local/state/dory-brain/manual-snapshots/20261020T122851Z-before-0.4.0-cleanup`). Windows started before the update kept their 0.3.0 hooks, and their workers wrote seven 0.3.0 files afterwards; deleted on 2026-10-21 without a copy. Now the vault holds only the 32 session notes, and 0.4.0 has not yet written a `knowledge.md`. Every window started before 2026-10-20 13:59 needs `/reload-plugins`. Watch `dory status` (removed entries, rewritten leads, restored notes) and the summaries under `~/.local/state/dory-brain/summaries/` |

**Legend:** Open | In Progress | Done

Second Brain (Record 001), Note quality (Record 002) and One knowledge file per project (Record 003) are released; versions are in [CHANGELOG.md](CHANGELOG.md), currently 0.4.0.

**Next Step:** Watch what 0.4.0 writes into the vault: one `knowledge.md` per project with few entries, `runs.log` and `dory status` for removed entries and restored notes, a summary once a project's files pass 80 % of the limit. Releasing: bump the version in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py` (a test keeps them equal), add a CHANGELOG entry, merge through a pull request, tag `vX.Y.Z` on `main` and push the tag; locally `claude plugin marketplace update brain && claude plugin update dory@brain`, then restart or `/reload-plugins` in every running session.

### Future

| Todo | Priority | Problem | Solution |
|------|----------|---------|----------|
| Narrow the Bash grant in save/note | Medium | `/dory:save` and `/dory:note` allow any Bash command; note reads vault content | `allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/dory <command>:*)` as in search, live probe as in `tests/test_live_note.py` |
| Configurable records folder | Low | The worker checks notes against `docs/records/` only (Record 002); public users keep decision records elsewhere, such as `docs/adr/` | A setting with the folders to capture, default `docs/records` |
| Prune `work/` | Low | Every entry's `bundle.md`, with its condensed transcript, stays under `~/.local/state/dory-brain/work/` indefinitely | Keep the last N bundle directories, as the snapshots do |

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
| 2026-10-19 | One `knowledge.md` per scope (project, `general/`, `private/`) kept by the worker, the user's notes in `notes.md`, a summary by the worker over the limit ([Record 003](docs/records/003-project-knowledge-file.md)); replaces single knowledge notes and their renaming of 2026-10-16 | Single notes grew to 13 files and 15,470 characters in two days in one project, beyond the session start's 6,000 characters; one file reads as one text, and the post-run checks make a lost entry visible |
| 2026-10-19 | Every test runs with `DORY_NO_SPAWN=1` (`tests/conftest.py`); a test that needs the start patches `spawn.spawn_worker` | A worker started from a test reads the default state directory, the user's real one; in Record 003 S4 a test-started worker ran against it (nothing was processed) |
| 2026-10-20 | The 0.3.0 knowledge notes and project overviews were deleted from the vault at the 0.4.0 release, not migrated; the session notes stay | The author's choice: three days of knowledge come back as sessions bring them up, and a vault 0.4.0 writes alone shows what it does. The copy before the deletion is a manual snapshot |
| 2026-10-21 | No person files (`people/<person>/`) with feedback and values per person; considered and dropped by the author | The worker only sees what the user writes about a person, so values would be inferred from single remarks; names that appear once would fill the folder as the 0.3.0 notes did; the session start cannot know who comes up |
| 2026-10-17 | Fresh vault instead of cleaning up the old one; only what 0.3.0 wrote stays ([Record 002](docs/records/002-note-quality.md), decision 4) | The old content had vanished from the vault on 2026-10-16 (cause unknown, not dory), and what two pre-update sessions wrote followed the 0.2.0 rules; a vault 0.3.0 writes alone shows what it does. The old vault stays as a manual snapshot |

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
- **Processing:** a background worker drains the queue, assigns the session to a project and edits the entries of the knowledge files; dory's code checks every run against a baseline of the vault (`baseline.py`), and after the queue the worker writes a summary of every context over the limit (`summarize.py`)
- **Recall:** the `SessionStart` hook loads the project line, the `notes.md` and `knowledge.md` of the session's context (or their summary over the limit), the paths of lists, and a pointer to sessions still in the queue; a project is private only when the user sets `domain: private` in its `knowledge.md` (before that file exists, a 0.3.0 overview's `domain: private` decides)
- **Commands:** `/dory:save`, `/dory:note "..."` (writes through `dory add-note`), `/dory:search` (single entries)

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
