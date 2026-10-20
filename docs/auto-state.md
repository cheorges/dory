# Auto state: One knowledge file per project (Record 003, release 0.4.0)

## Brake

off

## Cut

not due

## Next task

## Review

each iteration

## Where

| What | Where |
|---|---|
| Repo | `~/Development/cheorges/dory` |
| Branch | `feat/knowledge-file` |
| Return point | `603eea3` on `origin/main`; everything after it is the loop and unpushed |
| Quick round | `uv run pytest -q tests/<file the iteration touches>` |
| Full proof | `uv run pytest -q && uv run ruff check .` (164 tests at setup, live checks deselected). Runs before every cut and as the first step of a fresh session |
| Live checks | `DORY_LIVE=1 uv run pytest -m live` in iterations that change the worker, the rules or `/dory:note` (S1, S3, S4). Real `claude -p` runs with Haiku in throwaway vaults; they count against the usage limit |
| Design | `docs/records/003-project-knowledge-file.md` |
| Implementation log | `docs/implementation-log.md`, the repository's English counterpart of the `umsetzungs-log` |
| Calibration journal | `docs/calibration-journal.md` |
| Actual times | herdr journal `~/.herdr-journal/dory/dory.jsonl` |

## Queue

Acceptance criteria per story are in Record 003, `## User Stories`. Order by risk: the worker change with live checks first, then the session start, the summary, the note command, search, release. Estimates follow the actual times of Record 002 (S1 there: 3 h estimated, 25 min agent time).

| Step | Est. (h) | Acceptance criterion | State |
|---|---|---|---|
| D: design review | 0.3 | Architect review of Record 003 against the code; findings worked in or put to the user; ok by the user | fertig |
| S1: entries and post-run checks | 1 | Record 003, Story S1: entry parser, baseline, diff with pairing, frontmatter and `notes.md` restored, unexpected files logged, `dory status` counts; unit tests | fertig |
| S2: the worker keeps one knowledge file per scope | 1.5 | Record 003, Story S2: permission probe first; `knowledge.md` created, extended, corrected and pruned; no entry lost at about 15,000 characters; `notes.md` untouched; placement in project, `general/`, `private/`; 0.3.0 files left alone; `vaultops.py` and the project overview gone | fertig |
| S3: the session start loads the files | 0.5 | Record 003, Story S3: fixed paths, notes before knowledge, `private/` only outside work projects, cut with paths over the limit, the limit covers the whole text, 0.3.0 files ignored | fertig |
| S4: a summary over the limit | 1.5 | Record 003, Story S4: live probe for the summary command first; one text function for both sides, summary per context by the worker, marks, stale and missing cases, failure handling | fertig |
| S5: `/dory:note` writes the user's notes | 0.5 | Record 003, Story S5: `dory add-note --scope`, project `notes.md`, `general/` on request, `private/` by content, lists from any session | fertig |
| S6: search finds single entries | 0.3 | Record 003, Story S6: entries scored on their own, domain boundary by folder and project, 0.3.0 files not shown | fertig |
| S7: release 0.4.0 prepared | 0.3 | Record 003, Story S7: version 0.4.0 in three files, CHANGELOG, README and CLAUDE.md; committed, not tagged, not pushed. Then halt: the author merges, tags, pushes and installs | fertig |

## History

| Date | Step | What moved |
|---|---|---|
| 2026-10-19 | setup | Record 003 designed with the user: decisions 1 to 6, solution, six stories. Branch `feat/knowledge-file` from `603eea3`, full proof green (164 tests). The state file of Record 002 replaced; that loop had finished on 2026-10-17 |
| 2026-10-19 | D | Architect review of Record 003 against the code: 19 findings (3 P1: corrections counted as removals, the worker could flip a project's domain, 0.3.0 files in the project folder) worked in; story S1 split into the post-run checks (new S1) and the worker (S2), seven stories now. User decision: no guard that undoes large removals (decision 2 stays). Ok by the user |
| 2026-10-19 | S1 | Entry parser and diff (`entries.py`), skeletons, per-attempt baseline and post-run checks (`baseline.py`), wired into `ingest.py`, counts in `dory status`; 186 unit tests. Three review passes, 9 findings (one P1: a baseline kept across attempts undid the user's edits), all fixed with a failing-first test; Record 003 now says the baseline is per attempt. Ok by the user |
| 2026-10-19 | S2 | Worker writes one `knowledge.md` per scope: rules and ingest skill rewritten, task lists the files, `notes.md` denied by a permission rule (live probe 3 of 3), `scopes.py`, `vaultops.py` removed; live suite rewritten, 25 of 25, new checks 3 of 3, size check 40 entries without loss (Haiku 0.006 USD, Sonnet 0.088 USD); two review passes, 11 findings fixed (lead pairing restricted and rewritten leads counted, 0.3.0 private domain kept, no `general/` from private projects). Ok by the user |
| 2026-10-19 | S3 | Session start loads the files: `scopes.context_files` (load table), `context.py` (the text the worker will summarize in S4), `recall.py` rewritten (fixed paths, notes before knowledge, `private/` by the load table, lists by domain, cut in load order with marker and paths), `search.py` keeps its 0.3.0 helpers until S6; 168 unit tests. Review: three agents, then one; 5 findings fixed (P2: a list-valued `type` under `notes/` crashed the session start, found by all three); open for S4: one threshold for session start and worker. Ok by the user |
| 2026-10-19 | S4 | Summary over the limit: one threshold on both sides (context text against 80 % of the limit, in Record 003), `summary.py` (contexts `project-<name>`, `_general`, `_outside`, hash, store, marks), `summarize.py` (the `claude -p` run without tools or hooks, failure cap, `kind: summary` in `runs.log`), `spawn.py`, summary step in `worker.run`, `recall.py` loads or asks for the summary; 188 unit tests, live probe with control and length/language check 3 of 3 (about 0.0016 USD per summary with Haiku). Review: three agents, then one; P1 fixed (every test run started a real worker on the user's state; real state checked, nothing processed, two empty folders left), P2 reserved context names, five P3. Ok by the user |
| 2026-10-19 | S5 | `/dory:note` writes the user's notes: `dory add-note --scope project\|general\|private` (one dated bullet in the user's words, the line also into the baselines of queued entries, the context that loads the file marked, the worker started), `baseline.notes_lock` between add-note, capture and the notes restore, `prepare-note` with project, domain and scopes, the note skill only chooses; 203 unit tests, the live note suite back (7 checks, 3 of 3 with Haiku). Review: three agents, then one; P2 from all three (no lock between add-note and a running worker), two P3. Ok by the user |
| 2026-10-19 | S6 | Search finds single entries: `search.py` rewritten on `entries.parse` (entries of every `knowledge.md` and `notes.md`, session notes, lists), domain by folder, project and own `domain`, 0.3.0 files never read, a user note shown whole; 206 unit tests, live search checks 3 of 3. Review: three agents, all `correct`, three small findings fixed (ranking test, byte order mark, notes cut mid-word). Ok by the user |
| 2026-10-19 | S7 | Release 0.4.0 prepared: version in the three files, CHANGELOG, README and CLAUDE.md for the 0.4.0 model, Record 003 Done; documentation review against the code, six findings worked in (P2: keep a private project's 0.3.0 overview until its `knowledge.md` exists). Ok by the user; at the user's request the branch was squashed into one commit and opened as a pull request. Loop done |

## Open questions

- None.

## Last cut

**2026-10-19, after S2.** Context at 60 % when the task for S3 arrived. The seam is clean: S2 reviewed by three agents plus a second pass (11 findings, all fixed), ok by the user, committed as `0e768f9`; S3 not started.

Cut done 2026-10-19.

### State at the cut

| | |
|---|---|
| Green | `uv run pytest -q && uv run ruff check .`: 170 tests; whole live suite 25 of 25 on the S2 end state (the 6 checks of `tests/test_live_note.py` skipped) |
| Review | S2: architect, code-reviewer, security-auditor `correct`, second pass `correct`; ok by the user |
| Committed | everything, last `0e768f9`. Nothing pushed. Return point `603eea3` on `origin/main` |
| Done | D (design review), S1 (entries and post-run checks), S2 (the worker keeps one knowledge file per scope) |
| Open | S3, see `## Next task`; then S4 (summary over the limit), S5 (`/dory:note` writes notes), S6 (search by entry), S7 (release prepared, then halt for the author) |

### How the next session starts

1. `## Cut` back to `not due`, a line "Cut done <date>" here.
2. The full proof: green before anything is touched. It is also the check that the cut was clean.
3. S3 as written under `## Next task`.

### What is not in the plan and still holds

- User decisions so far (all in Record 003): 1 = no size limit on `knowledge.md`, 2 = fixed sections, edits and a diff after the run, without a guard that undoes large removals, 3 = the worker reads `notes.md` and never changes it, 4 = one pair of files per scope with `general/` (work) and `private/`, and `/dory:note` can write general notes from within a project, 5 = no migration, 0.3.0 notes are simply no longer loaded, 6 = the summary is made in the background by the worker, never at session start.
- The rules live in `plugin/skills/rules/SKILL.md`; `/dory:note` reads them too (through `dory prepare-note`, "without a task file"), so a rule that needs the bundle says it applies with a task file.
- Live checks: `DORY_LIVE=1 uv run pytest -m live -q -p no:cacheprovider -k <name> tests/test_live_rules.py`, about 25 s per worker run with Haiku. `--basetemp=<scratchpad dir>` keeps each test's `state/runs.log` with `cost_usd`. `World.session` queues with `cwd` = `world.hub` (a `git init` repository without commits), so `world.hub / "CLAUDE.md"` and `world.hub / "docs" / "records" / *.md` reach the worker as captured documents.
- Reviews: write `git diff HEAD` (after `git add -N` for new files) to a file in the scratchpad and give the agents its path; paste the reviewer contract from `/kolibee:do-review` verbatim; add the security-auditor when secrets, customer content or the hook path are touched.
- Actual times: agent and human minutes from the `agent_start`/`agent_stop` pairs in `~/.herdr-journal/dory/dory.jsonl`.
- Commit messages carry no `Co-Authored-By` or other trailers (the user's global rule; the history has none). The values in the `State` column are the auto skill's German words (`offen`, `läuft`, `fertig`, `bewusst offen`).
- The Bash tool runs zsh: an unquoted `$VAR` holding several paths is not split into words. `ls` is aliased to `eza`, which rejects `ls <dir>/` with an `--icons` error; use `/bin/ls`.
- Tests never touch the real vault or config: `tests/conftest.py` points `DORY_CONFIG` at a throwaway file. The real config has `language = "German"`; the real vault is `~/Documents/dory`, and the installed plugin there is 0.3.0 from GitHub.
- Where S1 and S2 put things: `plugin/dory/scopes.py` is the vault layout (`knowledge_files(project, domain)` leaves out `general/` for a private project; `project_domain` reads the project's `knowledge.md`, before it exists a 0.3.0 overview; `notes_files`). `plugin/dory/entries.py` parses entries and diffs them (S6 search reuses `parse`). `plugin/dory/baseline.py` holds skeletons, the per-attempt baseline under `<state>/baselines/` and the post-run checks. `recall.py` and `search.py` are still on the 0.3.0 model; `search.py` imports `Note`, `allowed`, `project_domain` and `scan` from `recall.py`.
- `tests/test_live_note.py` is skipped with a module-level mark until S5. `tests/test_live_rules.py` has the helpers `World.knowledge_file`, `user_notes`, `entries_about`, `changes` and `realistic_knowledge()` (40 entries, 14,095 characters).
- Live runs: about 0.005 USD and 25 s per worker run with Haiku. The whole live suite takes about 9 minutes, longer than one 10-minute tool call: run it in two halves with `-k`, each with its own `--basetemp=<scratchpad>/<name>`.
- macOS `sed` has no `\b`: a `sed 's/\bX\b/Y/g'` silently changes nothing (it hid a rename in S2). Use `perl -pi -e` for word boundaries, and grep after every scripted edit.
- Record 003 lists a known limit: a hand edit to a `notes.md` during a worker run is undone and logged as `restored`; S5's `dory add-note` must write into the baselines of queued entries (an S5 criterion).
- Facts behind the problem section: ai-assistant-hub held 13 knowledge notes with 15,470 characters on 2026-10-19 (7 of them written by the old 0.2.0 worker of sessions that started before the update); the recall budget of 1,500 tokens is about 6,000 characters.
