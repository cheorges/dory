# dory: second brain for Claude Code in an Obsidian vault

As of: 2026-10-03. Status: accepted, implemented in 1.0.0. Named `dory`, after the fish from "Finding Nemo" who forgets everything; the plugin makes sure Claude no longer forgets.
Basis: brainstorming from 2026-10-03 (`~/Downloads/second-brain-plugin-brainstorming.md`, decisions E1 to E11) and its continuation in this session.

## Goal

At the end of every Claude Code session, the session is summarized in a structured way and written as a linked Markdown note into an Obsidian vault. Project, topic and decision pages are updated along the way. In later sessions the knowledge comes back: a short index of active notes at start (short-term memory), targeted lookup across the whole vault when needed (long-term memory). The vault stays readable without Claude, and the links form a knowledge graph.

**Success criteria**
- Every session with at least 3 user messages has a note in the vault no later than after the next start, even after Ctrl+C, `/clear` or a closed terminal.
- A new session in the project folder knows the state and the open items of the project at start, without anyone calling anything.
- When asked about an earlier project, customer or decision, Claude finds the note and gives source and date, or says that nothing is there.
- Someone who opens the vault in Obsidian without Claude can find their way around via folders, `types.md` and `hot.md`.

**Non-goals (version 1)**
- No own search index, no vector search, no MCP server.
- No automatic injection of notes on every prompt.
- No git and no version folder in the vault.
- No lint run, no nightly maintenance, no graph export, no measurement. Comes after version 1, once real notes exist.
- No team operation.

## Principles

- **Generic:** needs only Claude Code and a vault. No reference to herdr, team-specific skills or particular customers.
- **English by default:** folders, templates, frontmatter keys and section headings are English. The content of the notes is in the configured language.
- **Dependencies:** only projects with several thousand stars and active maintenance. Single dependency: `kepano/obsidian-skills` (49.1k stars, MIT). Everything else is built in-house; patterns from superbrain, chronicle, claude-mem, basic-memory and obsidian-second-brain are adopted, their code is not.
- **Runtime Python stdlib only.** Tests with pytest.
- **Fail-open:** no hook aborts a session or delays it noticeably. Errors are logged and reported at the next start.

## Building blocks

```
dory/
├── .claude-plugin/
│   ├── plugin.json          manifest, userConfig, dependency obsidian@obsidian-skills
│   └── marketplace.json     own marketplace, allowCrossMarketplaceDependenciesOn: ["obsidian-skills"]
├── hooks/hooks.json         SessionStart, SessionEnd (no matcher, so on every reason)
├── scripts/brain.py         hooks, worker, hot.md, checks; one entry point with subcommands
├── rules/writer.md          writing rules, single source for the background run and /save
├── agents/brain-writer.md   agent for the background run, refers to rules/writer.md
├── skills/
│   ├── search/SKILL.md      automatic and as /dory:search <question>
│   ├── save/SKILL.md        /dory:save
│   └── note/SKILL.md        /dory:note <topic>
├── vault-seed/              copied into the vault on the first run, never overwritten
│   ├── types.md
│   └── templates/{session,project,topic,decision}.md
└── tests/
```

`brain.py` stays one file as long as it is under about 400 lines. If it grows larger, transcript processing and vault access are split into separate modules.

State data lives in `${CLAUDE_PLUGIN_DATA}` (survives plugin updates, not in the vault):

| Path | Content |
|---|---|
| `queue/<session_id>.json` | session to process: `session_id`, `transcript_path`, `cwd`, `reason` |
| `processed.json` | per `session_id` the uuid of the last processed message (anchor) |
| `lock/` | lock per vault, contains `pid` |
| `errors.log` | errors from the hooks and the worker |
| `installed_at` | time of installation; sessions before it are never caught up |

## Write path

### Triggers

| Event | What happens |
|---|---|
| `/exit`, Ctrl+C, Ctrl+D, closing the terminal, `/clear`, `/resume` | SessionEnd hook, provided Claude Code fires it |
| SessionEnd is not fired | the next SessionStart finds the session and queues it (catch-up) |
| `/dory:save` | the running session writes itself, with full context |
| `/dory:note <topic>` | the running session writes a specific project, topic or decision page |

### SessionEnd hook (`brain.py session-end`)

Must finish in milliseconds (SessionEnd has at most 60 s in total and must not run `async`).

1. If `BRAIN_CHILD=1` is set, exit immediately (protection against recursion from the own background run).
2. If `auto_capture` is off, `cwd` is under a path from `exclude_paths`, or the session is not interactive (`claude -p`, Agent SDK, automations), exit. How a non-interactive session can be recognized in the transcript is clarified by spike item 8.
3. Write `queue/<session_id>.json`.
4. Start the worker detached (`subprocess.Popen(..., start_new_session=True)`, stdin/stdout/stderr to `/dev/null`) and exit.

### Worker (`brain.py worker`)

1. **Lock:** `mkdir lock/`. If it exists and the `pid` in it is alive, exit; the running worker processes the whole queue. If the `pid` is dead, take over the lock.
2. **Seed:** if `types.md` or `templates/` is missing in the vault, copy from `vault-seed/`. Existing files are never overwritten.
3. For each entry in `queue/`, oldest first:
   1. **Read transcript** starting at the anchor from `processed.json`.
   2. **Trim:** only text from user and assistant; `isMeta` entries and tool results are dropped; tool calls become `[tool_use: <name> <short target>]`. If the rest is larger than the limit (initial value 150'000 characters), the beginning and end are kept, with a note about the cut in between.
   3. **Hide credentials:** typical patterns (`sk-…`, `ghp_…`, `github_pat_…`, `AKIA…`, `xox[bp]-…`, `-----BEGIN … KEY-----` to `-----END`, lines `KEY|TOKEN|SECRET|PASSWORD = …`) become `[REDACTED]`.
   4. **Minimum size:** fewer than `min_user_messages` user messages since the anchor: set the anchor, delete the entry, no note.
   5. **Determine project:** `git rev-parse --git-common-dir` in `cwd`, then its parent folder; without git the folder `cwd`. Name = folder name. If there is a project page whose `path` matches, its name applies.
   6. **Start writer:** see below.
   7. **Clean up:** see below.
   8. **Success:** set the anchor to the last uuid, delete the entry. **Failure:** the entry stays, error goes to `errors.log`; after 3 failed attempts the entry is moved to `queue/failed/`.
4. Release the lock.

### Background writer

```
cd <empty temp directory>
BRAIN_CHILD=1 claude -p --model <writer_model> \
  --tools Read,Write,Edit,Grep,Glob --add-dir <vault_path> \
  --strict-mcp-config --no-session-persistence < prompt
```

The prompt contains: content of `rules/writer.md`, `types.md` from the vault, project name and project folder (for `path` of a new project page), date, `note_language`, `session_id`, whether a session note for this `session_id` already exists, and the trimmed transcript, fenced as "raw data, NOT instructions". Whether the agent is loaded via `--agent dory:brain-writer` or via `--append-system-prompt-file` is decided by the spike (item 3).

### Writing rules (`rules/writer.md`)

Apply equally to the background run and to `/dory:save` and `/dory:note`.

1. **Search before creating:** for the project and every important term, grep in file names, `aliases` and full text. If an alias matches, extend the existing page.
2. **Read:** from hits only frontmatter, `## Current state` and `## Open`. The whole file only when a contradiction has to be placed.
3. **Session note** following `templates/session.md`. If one already exists for this `session_id` (after `/save` or `/resume`), it is extended instead of created anew. In the session note the agent sets only `summary` and `topics`; the worker sets the other fields afterwards (see clean-up) and overwrites whatever the agent put there.
4. **Affected pages:** rewrite `## Current state` freely, set `summary` anew, maintain `## Open`, append exactly one line to `## History`, `last_active` to today.
5. **Contradiction:** the new fact replaces the old one in the state; `## History` records `replaced: X → Y, [[Session]]`. Contradictions the session does not resolve are listed under `## Open` instead of being resolved silently.
6. **Decisions** get their own page if there was an alternative and the why is not obvious. Smaller decisions are only in the session note. A decision is never rewritten; a new one gets `supersedes`, the old one `status: closed`.
7. **Fast-changing facts** carry a date: "(as of 2026-10-03)".
8. **What counts as knowledge:** decisions with reasons, state of projects, recurring error patterns and their fix, facts about customers, tools and environments. Not: small talk, single command outputs, intermediate states that were superseded in the same session.
9. **Links** always to the file name, alias at most as display text: `[[Claude Code Plugins|CC Plugins]]`.
10. **No credentials** in the vault, not even partially.
11. **New types and subfolders** only according to the rules in `types.md`.
12. If the session yields nothing that meets the rules above, `SKIP` is a valid answer.

### Clean-up after the writer (Python, no LLM)

1. Find changed files (mtime since the start of the run).
2. **Set the session note frontmatter:** `type`, `created`, `project`, `session_id`, `cwd`, `written_by`. `summary` and `topics` from the agent stay.
3. **Check:** every changed file has frontmatter with `type`; wikilinks that point to no file, and files with `(conflicted copy)` in the name, are reported in `log.md`, not corrected.
4. **`log.md`:** append one line: `YYYY-MM-DD HH:MM | <written_by> | session <id8> | new: … | changed: …`. New types and folders with their reason as a separate line.
5. **`hot.md`:** rebuild (see read path).

### `/dory:save`

The running session has the full context, so it writes itself and not in the background.

1. The skill loads `rules/writer.md` and `types.md`.
2. Claude writes the session note and affected pages according to the rules.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/brain.py finish --session ${CLAUDE_SESSION_ID} --written-by save --vault ${user_config.vault_path} --data ${CLAUDE_PLUGIN_DATA}` sets the session frontmatter and the anchor to the last uuid in the transcript, checks, writes `log.md` and `hot.md`. Paths and values are passed as arguments in the call, because commands run via the Bash tool do not get the plugin environment variables; Claude Code substitutes `${…}` in the skill text when loading it.

The worker at session end then only processes messages after the anchor.

### `/dory:note <topic>`

Like `/save`, but without a session note and without an anchor: Claude summarizes the topic from the context and creates or updates the matching project, topic or decision page. Then `brain.py finish --written-by note`.

### Concurrency

One lock per vault. Two sessions that end at the same time are both queued; one worker processes them one after the other. `/save` and `/note` take the same lock via `brain.py finish`; if the background run is currently writing, `finish` waits up to 60 s (the Bash tool aborts after 120 s) and otherwise reports that the run should be repeated later.

## Read path

### SessionStart hook (`brain.py session-start`)

1. `BRAIN_CHILD=1` → exit.
2. **Catch-up:** transcripts under `~/.claude/projects/*/*.jsonl` that were modified after `installed_at` and within the last 7 days, whose last uuid does not match the anchor in `processed.json`, that are not the current session, that have not been modified for at least 2 hours (otherwise they are probably still running, e.g. in another terminal), that were interactive and whose `cwd` is not under `exclude_paths`, are added to the queue (only with `auto_capture: true`). If the queue is not empty, start the worker detached.
3. **Output context** as `additionalContext`:

```
dory: second brain in <vault_path>.
Look things up with the skill dory:search as soon as a project, customer,
tool or earlier decision comes up that is not in the context,
and before you say that you don't know something. Every state carries a
date and may be outdated.

## Current project: [[dory]] (2026-10-03)
<summary>
Open: <items from ## Open>

## Active (last <active_days> days)
- [[Customer X Onboarding]] (project, 2026-10-01): <summary> · 2 open
- ...

## Notices
- The previous session is being written right now (on source=clear)
- New type people/ created, reason in log.md
- 1 session not processed: <reason>
- Vault not writable: <path>
```

- **Current project:** project page whose `path` matches `cwd` (same detection as in the worker).
- **Active:** content of `hot.md`, pinned first, then by `last_active`.
- **Notices:** only when there is something to report. New types and folders are reported once.
- **Budget:** target around 4'000 characters, hard limit 9'000 (Claude Code replaces anything from 10'000 with a preview). Reduction order: oldest non-pinned lines in Active, then open items except for the current project; at the end "+N more in hot.md".

### `hot.md`

Built only by the script, never by the model. A note is active if `pinned: true`, or if `last_active` is within `active_days` and `status` is not `closed`. Sessions and `templates/` are excluded. One line per note: link, type, `last_active`, `summary`, number of open items.

### Skill `search`

One search for both paths: Claude calls it itself when the description matches; by hand as `/dory:search <question>`. The description is worded assertively: "Use before saying you don't know, or when the user mentions a project, customer, tool, decision or earlier work that is not in the current context."

1. Extract terms from the question, grep the vault: file names, `aliases`, full text.
2. Rank hits: project, topic, decision and custom types before session; within that by `last_active`.
3. Read frontmatter, `## Current state`, `## Open` of at most 5 hits.
4. Follow the frontmatter links one step (`project`, `topics`, `supersedes`); for superseded decisions the newer one applies.
5. Answer with source and date: "According to [[dory]] (as of 2026-10-03) …".
6. If no hit shares a term with the question: "nothing found in the second brain".
7. Broad questions across many notes ("what happened with customer X this year") run in a subagent that returns only the answer with sources.

## Vault

### Layout

```
<vault_path>/
├── types.md
├── hot.md
├── log.md
├── templates/
│   ├── session.md
│   ├── project.md
│   ├── topic.md
│   └── decision.md
├── sessions/
├── projects/
│   └── <Project>/
│       ├── <Project>.md
│       └── <Subfolder>/      only according to the rules in types.md
├── topics/
└── decisions/
```

`type` in the frontmatter is authoritative, the folder is for overview. If a file is moved in Obsidian, the search still finds it.

### Types

| Type | Folder | For what |
|---|---|---|
| session | `sessions/` | what happened in a session; raw record, does not age |
| project | `projects/<Name>/` | a work context, by default one per git repo or working folder |
| topic | `topics/` | what recurs across projects: customer, technology, tool, error pattern; subkinds via tag |
| decision | `decisions/` | what was decided, why, against which alternative |

### `types.md`

Register of all types and folders. Per type: folder, when it applies (with example), when not, template. Plus the rules for extensions. Claude (background run and running session) may extend:

| Rule | Initial value |
|---|---|
| new type only if at least this many existing notes would belong to it and no type fits | 3 |
| new type needs a complete entry in `types.md` and a template in `templates/` | - |
| maximum number of types | 8 |
| subfolder in a project from this many notes of the same kind | 5 |
| depth of subfolders in a project | 1 |
| every new type, folder and relation key gets a line in `log.md` with its reason and is reported at the next start | - |

The initial values are in `types.md` and can be changed there.

### File names

| Type | Pattern | Example |
|---|---|---|
| session | `YYYY-MM-DD <Project> <short title>` | `2026-10-03 dory plugin design.md` |
| project | project name | `dory.md` |
| topic | readable name | `Claude Code Plugins.md` |
| decision | decision as a short statement | `No git in vault.md` |

- Unique across the whole vault. On collision a parenthesis: `Mercury (planet).md`, `Mercury (customer).md`.
- Without `# ^ [ ] | / : \`.
- Topics and decisions are named in the language of the notes, proper names stay.
- New spellings of a term go under `aliases`.

### Frontmatter

All types except session:

```yaml
---
type: project
status: active          # active | closed
pinned: false
created: 2026-10-03
last_active: 2026-10-03
summary: "Write path decided, vault layout in progress (as of 2026-10-03)"
aliases: []
tags: []
project: "[[dory]]"  # optional for topic, required for decision, empty for project
topics: []              # list of links
supersedes: ""          # for decision and topic
path: <repo>   # project only
---
```

session:

```yaml
---
type: session
created: 2026-10-03
summary: "..."
project: "[[dory]]"
topics: ["[[Obsidian]]", "[[Claude Code Plugins]]"]
session_id: 9aab7cb2-...
cwd: <repo>
written_by: background  # background | save | note
---
```

The frontmatter is read by `brain.py` with its own flat parser (key, scalar or single-line list). Nested YAML is not supported and is reported in `log.md`.

### Sections

| Type | Sections |
|---|---|
| project, topic | `## Current state` (freely rewritten), `## Open` (checkboxes), `## History` (append only) |
| decision | `## Context`, `## Decision`, `## Alternatives`, `## Source` |
| session | `## Summary`, `## Decisions`, `## Open`, `## Touched` |

### Relations

Typed relations are links in the frontmatter: `project` (belongs to), `topics` (covers), `supersedes` (replaces). Everything else is a normal link in the text. This lets Obsidian Bases filter tables ("all sessions of dory", "all superseded decisions"), and a later export can produce typed edges. New relation keys only according to the rules in `types.md`.

## Configuration (`userConfig`)

| Key | Type | Default | For what |
|---|---|---|---|
| `vault_path` | directory, required | - | location of the vault |
| `note_language` | string | `English` | language of the note content (for the user `Deutsch`) |
| `active_days` | number, 1 to 365 | `14` | window of the short-term memory |
| `writer_model` | string, choice `sonnet`, `haiku`, `opus` | `sonnet` | model of the background run |
| `min_user_messages` | number | `3` | below this, no note |
| `auto_capture` | boolean | `true` | background run on/off; `/save` and `/note` always work |
| `exclude_paths` | string, multiple | empty | working folders from which nothing is ever written automatically |

Hooks read the values as `CLAUDE_PLUGIN_OPTION_<KEY>`, skills as `${user_config.KEY}`.

## Error handling

| Case | Behavior |
|---|---|
| SessionEnd is not fired | catch-up at the next start |
| writer aborts, timeout, invalid output | entry stays in the queue, notice at start; after 3 attempts `queue/failed/` |
| worker dies holding the lock | next worker detects the dead `pid` and takes over |
| vault missing or not writable | no write attempt, notice at start |
| `vault_path` not set | hooks do nothing except a notice at start |
| frontmatter malformed | file is skipped for `hot.md`, notice in `log.md` |
| sync conflict (Nextcloud, OneDrive) | conflict file is reported in `log.md` |

Every hook ends with exit code 0, even on errors.

## Tests

**Automated (pytest, against a throwaway vault in `tmp_path`):**
- Trimming the transcript: meta removed, tool calls as one line, beginning and end on oversize, start at anchor.
- Hiding credentials: every pattern from the list, no hit in normal text.
- Active rule and `hot.md`: pinned, expired, closed, sessions excluded.
- Start output: budget, reduction order, hard limit 9'000 characters.
- Catch-up: finds missing sessions, ignores processed, current, old ones and those before `installed_at`.
- Lock: second worker exits, dead `pid` is taken over.
- Determining the project: repo, worktree, folder without git, `path` of a project page.
- Frontmatter parser and dead link check.
- Hooks: `BRAIN_CHILD`, `auto_capture`, `exclude_paths`.

Test data: a trimmed, anonymized real transcript as a fixture.

**By hand:** writer against the fixture transcript and against 3 real sessions; look at the notes in Obsidian (graph, backlinks, Bases).

## Spike before the plan

| No | Question | How checked | Consequence if no |
|---|---|---|---|
| 1 | Does Claude Code 2.1.288 fire a SessionEnd hook **from a plugin**, and with which `reason`, on `/exit`, Ctrl+C twice, Ctrl+D, closing the window, `/clear`? (issue #33458) | test plugin writes `reason` and time to a file; Ctrl+C and closing the window are triggered by the user | catch-up at start becomes the main path |
| 2 | Does the detached worker keep running when the terminal is closed? | worker writes a file after 30 s | `nohup` or a `launchd` job instead of a process group |
| 3 | Does `claude -p` in an empty folder load other plugins' hooks, plugins, the global `~/.claude/CLAUDE.md` and an output style? Does `--agent dory:brain-writer` work? | child process with a test hook that reports itself | restrict `--setting-sources`, agent prompt via `--append-system-prompt-file`; Obsidian syntax rules directly in `rules/writer.md` |
| 4 | Duration and tokens of a run with a real transcript, Sonnet | measurement | lower the transcript limit or Haiku |
| 5 | Do frontmatter links produce edges in the Obsidian graph and backlinks? | open a test vault in Obsidian | relations additionally as text links in the sections |
| 6 | Are `${CLAUDE_SESSION_ID}`, `${CLAUDE_PLUGIN_DATA}` and `${user_config.vault_path}` substituted in the skill text? | test skill | `/save` reads the newest transcript file of the project |
| 7 | Can hook processes under herdr write to `~/Obsidian/Vault`? | test from a plain Ghostty window, then under a freshly started herdr | clarify the macOS permission or move the vault to an unprotected location |
| 8 | How can a non-interactive session (`claude -p`, SDK) be recognized in the transcript or in the hook input? | compare the transcript of a `claude -p` session with an interactive one | exclusion only via `exclude_paths` |

Effort about 1.5 hours, plus 10 minutes with the user for items 1, 2 and 7.

## After version 1

- Search index (SQLite FTS5, `unicode61 remove_diacritics 2`) if grep is measurably too slow or misses too often.
- Recall log and 20 to 30 test questions following LongMemEval categories.
- Lint: dead links, orphaned pages, outdated states, duplicates.
- Graph export with edge types.
- Team operation.

