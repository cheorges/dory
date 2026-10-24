# dory

## About

Second brain for Claude Code: sessions go into a queue when they end, a background process distills insights from them into one knowledge file per project and one topic file per subject in `notes/` of an Obsidian vault, and new sessions load the project's notes and knowledge, or a summary of them, plus the topic files in `notes/` and the `library/` entries that loaded files link, through a hook. Plus manual commands for `save`, `note`, `library` and `search`. Public repository: https://github.com/cheorges/dory

## Tech Stack

Python 3.12+ as uv scripts (PEP 723), pytest; Claude Code plugin `dory` (hooks, skills); `claude -p` for processing; state as files under `~/.local/state/dory-brain/`; Obsidian vault without git; macOS (APFS clones).

---

## Current Status

| Story | Status | Notes |
|-------|--------|-------|
| Test 0.9.0 in daily use | Open | Installed on the author's machine on 2026-10-22, the five options set in Claude Code (German, opus, lean, 200000; window 1000000 if the sessions run with 1M windows). The vault is a new, empty one in iCloud Drive (`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/dory`, "Keep Downloaded" in Finder), against the guide's advice, to see whether iCloud harms dory; the old `~/Documents/dory` stays untouched. Watch: sync conflict copies such as `knowledge 2.md` and unexpected changes reported by the checks, the dory rows in `/config`, topic files in `notes/` (title, one subject each, no duplicates), the user's notes untouched, `/dory:library` (proposals, links, entries loading where linked), `dory status`, and how much the session start loads |
| Release 0.11.0 | In Progress | [Record 008](docs/records/008-knowledge-capture.md) built on `feat/knowledge-capture` (branched from `feat/library-dialog` at `4c2e765`, unpushed): wider test for knowledge, working rules as preferences, catalog against duplicates, `## Replaced` trace, stale flags, transcript copies deleted. Release text written for Records 008 and 009; ready to merge; 0.10.0 is merged (pull request #6) but not yet tagged |
| Better proposals in /dory:library | In Progress | [Record 009](docs/records/009-library-candidates.md) built on the same branch: no silent replacement, aliases and source, the whole vault in the library context, a test vault, `dory library-candidates`, the dialog using it; ready with 0.11.0. The AskUserQuestion dialog itself is not live-checked (headless); try it once after installing |

**Legend:** Open | Designed | In Progress | Done

Records 001 to 007 are released, 008 and 009 are ready as 0.11.0; versions are in [CHANGELOG.md](CHANGELOG.md). A release tag sits on the commit on `main` that releases it (the merge commit of its pull request, or the release commit itself when it went directly on `main`, as 0.7.0 did).

**Next Step:** `git fetch origin` (local `main` is behind), then tag `v0.10.0` on the merge commit of pull request #6 (`3a82984`) and push the tag, then push `feat/knowledge-capture`, open its pull request against `main`, merge it with a merge commit and tag `v0.11.0`; update the plugin locally, then check what "Test 0.9.0 in daily use" lists, now with 0.11.0, and run `/dory:library` once by hand to see the dialog. Releasing: while dory is at 0.x, every release raises the minor version (0.9.0, 0.10.0), never the patch version; bump it in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py` (a test keeps them equal), add a CHANGELOG entry, merge through a pull request with a merge commit, tag `vX.Y.Z` and push the tag; locally `claude plugin marketplace update brain && claude plugin update dory@brain`, then restart or `/reload-plugins` in every running session.

### Future

| Todo | Priority | Problem | Solution |
|------|----------|---------|----------|
| Narrow the Bash grant in save/note | Medium | `/dory:save` and `/dory:note` allow any Bash command; note reads vault content | `allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/dory <command>:*)` as in search, live probe as in `tests/test_live_note.py` |
| Configurable records folder | Low | The worker checks notes against `docs/records/` only (Record 002); public users keep decision records elsewhere, such as `docs/adr/` | A setting with the folders to capture, default `docs/records` |
| Compare link proposals on the real vault | Low | The fixture of Record 009 is easy for any lexical ranker; whether the weights of `dory library-candidates` hold on a real vault is unmeasured (decision 2, B) | Once the vault has a few hundred files, rerun the requests of `tests/fixtures/library-requests.json` written against it, before and after |
| Snapshot fails on an unreadable file | Low | Every command that snapshots the vault first (`library-context`, the worker) fails when one file cannot be read, e.g. an iCloud file that cannot be fetched (found in Record 009, Story 2) | Skip and log unreadable files in the snapshot |
| Prune `work/` | Low | Every entry's `bundle.md`, with its condensed transcript, stays under `~/.local/state/dory-brain/work/` indefinitely | Keep the last N bundle directories, as the snapshots do |

---

## Recent Decisions

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-11 | Worker model stays `sonnet` by default (`haiku` and, since 0.8.0, `opus` selectable) | Haiku passed all 7 live checks at 1/15 of the cost; the user keeps a quality margin for complex sessions |
| 2026-10-11 | Repository public and in English; note language configurable (`language`, default English), note headings always English | Public use; the recall reads the frontmatter keys, and the worker finds existing sections by their English names, so neither can depend on the language |
| 2026-10-12 | Apache 2.0 with a NOTICE file | Free use, also commercial; redistributions must credit the author |
| 2026-10-12 | Public history starts fresh with the 0.1.0 commits; the old history exists only on local `backup/*` branches | The old commits carried German text and customer names |
| 2026-10-12 | Marketplace named `brain`, plugin installed as `dory@brain`, also on the author's machine from GitHub | Short install command; the author runs exactly what users get, so changes need a push and `plugin update` |
| 2026-10-15 | Session start injects knowledge only: no open items, no recent sessions ([Record 002](docs/records/002-note-quality.md)) | Both repeat what the CLAUDE.md, `git log` and handover notes already say, and open items go stale because the worker only sees transcripts; the start should bring what one would not know to ask for |
| 2026-10-21 | A project's notes are files in `projects/<p>/notes/`, everything without a project lives in `notes/` (topic files, lists, registers), `private/` is the user's and loads only through links from project notes (now `library/`, see 2026-10-22); the checks log changes to the user's files and never restore them ([Record 004](docs/records/004-notes-and-topic-files.md)) | One `general/knowledge.md` would grow into a grab bag; a note needs a title and room; private content should come only from the user; restoring notes undid the user's own edits during a run |
| 2026-10-22 | `private/` becomes `library/`, the knowledge the user files deliberately; `/dory:library` writes it in a dialog and links entries through a `library` property in project notes or topic files; `/dory:note` never writes there, enforced by a skill hook ([Record 006](docs/records/006-library.md)) | The folder holds curated knowledge, confidential content being one kind; a link from a file that loads is the one rule for what loads; the property survives the worker rewriting a topic's text |
| 2026-10-22 | While at 0.x, every release raises the minor version, no patch releases | The author's rule; 0.x may change incompatibly anyway (Record 003), so a patch number carries no information |
| 2026-10-22 | The five main settings are `userConfig` options in `/config`; dory reads them from Claude Code's `settings.json` (`pluginConfigs`), the hook variables only as a fallback, and config.toml for what is not set there ([Record 007](docs/records/007-settings-in-claude-code.md)) | The user looks for settings in `/config`; Claude Code validates the values; only hooks get the variables, skills and the worker do not |
| 2026-10-22 | The session start may take `lean` 5 %, `balanced` 10 % or `rich` 15 % of `context_window` (default `lean` and 200,000 tokens); topics in `notes/` load in full while they fit; a summary is at most 10,000 tokens ([Record 005](docs/records/005-context-levels.md)) | 1,500 tokens were too little for 1M windows; the `SessionStart` hook gets no model (probed), so the window is configured |
| 2026-10-23 | Behaviour, limits and the user's working rules become entries even when the CLAUDE.md states them; only decisions about the system stay out, and only decision entries are removed once the CLAUDE.md states them ([Record 008](docs/records/008-knowledge-capture.md)) | The CLAUDE.md is rewritten and pruned and many sessions never update it; 0.9.0 left 8 entries from 7 sessions, about half of what later sessions needed |
| 2026-10-23 | Entries never point to records or other documents outside the vault; they hold the substance ([Record 008](docs/records/008-knowledge-capture.md), decision 4) | The vault must be understood without the repository; a record bullet made a live check flip in 2 of 5 runs |
| 2026-10-23 | dory's code, not the worker, keeps a trace (`## Replaced` in the session note) and per-entry dates for stale flags; nothing is deleted automatically ([Record 008](docs/records/008-knowledge-capture.md), decision 5) | Holds for every run and costs nothing at session start; the model cannot forget it |
| 2026-10-24 | Link candidates for `/dory:library` come from code (`dory library-candidates`), the model only chooses; no index, no embeddings ([Record 009](docs/records/009-library-candidates.md)) | The model's own grep found few files and none in other projects; code finds them cheaply and testably, and an index would copy confidential library content out of the vault |
| 2026-10-19 | Every test runs with `DORY_NO_SPAWN=1` (`tests/conftest.py`); a test that needs the start patches `spawn.spawn_worker` | A worker started from a test reads the default state directory, the user's real one; in Record 003 S4 a test-started worker ran against it (nothing was processed) |
| 2026-10-21 | No person files (`people/<person>/`) with feedback and values per person; considered and dropped by the author | The worker only sees what the user writes about a person, so values would be inferred from single remarks; names that appear once would fill the folder as the 0.3.0 notes did; the session start cannot know who comes up |

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

See [Record 001](docs/records/001-second-brain.md) and [the guide](docs/guide.md).

- **Capture:** the `SessionEnd` hook puts a transcript copy into a queue; manually also with `/dory:save`
- **Processing:** a background worker drains the queue, assigns the session to a project and edits the entries of the project's `knowledge.md` and of the topic files in `notes/`; its settings deny it `library/` and the user's notes, and the library entries its session could load come as copies in the bundle; the bundle holds a catalog of every entry's lead (`catalog.py`) with stale flags from per-entry dates (`staleness.py`); dory's code checks every run against a baseline of the vault (`baseline.py`), appends the previous text of rewritten entries to the session note (`trace.py`) and deletes the transcript copy, and after the queue the worker writes a summary of every project over the limit (`summarize.py`)
- **Recall:** the `SessionStart` hook loads the project line, in a known project its notes (each followed by the library entries it links, `links.py`) and `knowledge.md`, or their summary over the limit, then the topic files in `notes/` that fit whole, each with the library entries its `library` property links, and the titles of the rest, and a pointer to sessions still in the queue; the limit is the level's share of `context_window` (`summary.limit_tokens`); a project is private only when the user sets `domain: private` in its `knowledge.md`
- **Settings:** `config.load_config` takes the plugin's `userConfig` options from Claude Code's `settings.json` (`pluginConfigs`), the `CLAUDE_PLUGIN_OPTION_*` variables where the file has none, then `~/.config/dory-brain/config.toml`, then the defaults
- **Commands:** `/dory:save`, `/dory:note "..."` (a note file or a topic entry; new files through `dory add-note`; a skill hook running `dory guard` blocks Write and Edit under `library/`), `/dory:library "..."` (a dialog; candidates and possible duplicates from `dory library-candidates`, `candidates.py`; writes only through `dory library-write`, which replaces an entry only with `--replace --expect <sha256>`, and `dory link`), `/dory:search` (the whole vault, `library/` included)

---

## Files

Key directories:
- `plugin/` — the Claude Code plugin (`dory/` Python package, `skills/`, `hooks/`, `bin/dory`)
- `docs/guide.md` — the user guide behind the short README
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
