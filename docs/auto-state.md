# Auto state: Note quality and recall value (Record 002)

## Brake

Entscheid: merge the pull request, tag v0.3.0, push the tag and install 0.3.0

## Cut

not due

## Next task

Iteration S5: clean up the existing vault. Acceptance criteria: Record 002 (`docs/records/002-note-quality.md`), `### Story S5`, six criteria; the plan is under `### Cleaning up the existing vault (decision 4)`, the note rules under `### Living notes (decision 6)`.

Precondition, checked first: `claude plugin list` shows dory 0.3.0. If it does not, stop with `Frage:` under `## Brake`: the 0.2.0 worker would keep writing `## Open` sections, long notes and prefixed names, also for this session.

This is the one iteration that writes into the real vault `~/Documents/dory` (note language German, from the real config). By hand, following `plugin/skills/rules/SKILL.md`; no worker run. Renames and deletions go through `dory.vaultops` (`rename_note`, `delete_note`, run with `uv run python` from the repository), so every link follows; never move or delete a note with the shell.

1. Snapshot first: `cp -cR ~/Documents/dory ~/.local/state/dory-brain/manual-snapshots/<UTC timestamp>`; name it in the implementation log.
2. Every project overview under `projects/*/` loses its `## Open` section.
3. Every knowledge note of ai-assistant-hub and ai-assistant-hub-infrastructure is checked against both CLAUDE.md files (`~/Development/kolibee/ai-assistant-hub/CLAUDE.md` and `~/Development/kolibee/ai-assistant-hub/ai-assistant-hub-infrastructure/CLAUDE.md`, a repository nested inside the hub folder), their `docs/records/` and the bar of decision 6. Outcomes: deleted (stated in the CLAUDE.md of every project the note lists; held by a record and relevant only to its feature; only describes the code; superseded); shortened to a pointer note (held by a record, relevant beyond it); corrected (contradicting notes merged into one, e.g. the two on how the quota warning mail is sent); kept. Every remaining note: current state, no project status, no bare identifiers, body under 1,200 characters, and its core statement in German as file name (`rename_note`). The matrix design note `ai-assistant-hub-leistungsmatrix-design.md` becomes the current decision in a few sentences with a pointer to records 041 and 042.
4. The implementation log lists each note with its outcome (kept, renamed, shortened to a pointer, corrected, deleted).
5. Checks: no `## Open` in the overviews; no knowledge note name starting with a project name; every `[[link]]` in the vault resolves to a file; a simulated session start for both hub repositories has no bare identifier (the judge `bare_identifiers` in `tests/test_live_rules.py`):
   `echo '{"session_id":"sim","transcript_path":"/x/sim.jsonl","cwd":"<repo path>","source":"startup"}' | plugin/bin/dory recall`

Then the full proof, `/kolibee:do-review` on the vault changes (`diff -r` against the snapshot), review package, halt. Not part of this iteration: the old project `dory-brain` next to `dory`. The vault has no git: the snapshot is the way back.

## Review

each iteration

## Where

| What | Where |
|---|---|
| Repo | `~/Development/cheorges/dory` |
| Branch | `feat/note-quality` |
| Return point | `57d5eda` on `origin/main`; the loop's work is on `feat/note-quality`, squashed into three commits and pushed for a pull request |
| Quick round | `uv run pytest -q tests/<file the iteration touches>` |
| Full proof | `uv run pytest -q && uv run ruff check .` (120 tests at setup, live checks deselected). Runs before every cut and as the first step of a fresh session |
| Live checks | `DORY_LIVE=1 uv run pytest -m live` in iterations that change the worker or the rules (S1, S2). Real `claude -p` runs with Haiku in throwaway vaults; they count against the usage limit |
| Design | `docs/records/002-note-quality.md` |
| Implementation log | `docs/implementation-log.md`, the repository's English counterpart of the `umsetzungs-log` |
| Calibration journal | `docs/calibration-journal.md` |
| Actual times | herdr journal `~/.herdr-journal/dory/dory.jsonl` |

## Queue

Acceptance criteria per story are in Record 002, `## User Stories`. Order by risk and value (design review, 2026-10-15): the deterministic session-start changes first, the worker changes after, the vault cleanup only once 0.3.0 is installed.

| Step | Est. (h) | Acceptance criterion | State |
|---|---|---|---|
| D: finalize Record 002 | 0.5 | Record 002 has a decision for each of the four questions, a solution and six stories with Given-When-Then; status `Designed`; a row in the CLAUDE.md status table | fertig |
| S3: remove open items | 0.5 | Record 002, Story S3: no open items in the session start (unit test), no `## Open` in project overviews, session notes keep theirs (live checks), docs updated | fertig |
| S4: remove recent sessions | 0.5 | Record 002, Story S4: no session summaries in the session start, in a project or outside; the queue line stays; `short_term_sessions` removed, old configs still load; docs updated (unit tests) | fertig |
| S1: repository documents for the worker | 3 | Record 002, Story S1: Grep live probe first; CLAUDE.md and records captured redacted at session end into `work/<entry>/repo/` (worktree first, union with the main repository's records); edge cases; cleanup when the entry leaves the queue plus a sweep; live check that a CLAUDE.md fact after character 8,000 yields no note while a new insight does | fertig |
| S2: writing rules | 2 | Record 002, Story S2: eight live checks, each three of three runs with a positive control, plus the unit test that archived notes are skipped by recall and search | fertig |
| S7: living notes with telling names | 3 | Record 002, Story S7: no knowledge note from a plain build session, file names as core statement, correction renames in place, covered notes deleted; dory renames, deletes and rewrites links after the run; eight criteria | fertig |
| S6: release 0.3.0 prepared | 0.2 | Record 002, Story S6: version 0.3.0 in three files, CHANGELOG entry; committed, not tagged, not pushed. Then halt: the author merges, tags, pushes and installs 0.3.0 | fertig |
| S5: clean up the existing vault | 0.5 | Record 002, Story S5: only after 0.3.0 is installed; manual snapshot outside the rotation; matrix note rewritten, no `## Open` in overviews, hub notes checked and archived or shortened, no bare identifiers in a simulated session start | offen |

## History

| Date | Step | What moved |
|---|---|---|
| 2026-10-15 | setup | Branch `feat/note-quality` from `57d5eda`, full proof green (120 tests), Record 002 with problem and options, state file and calibration journal created |
| 2026-10-15 | setup | User decision: open items are removed completely, from the session start and from the project overview (decision 2, replaces the recommended 2A and 2B); S3 rewritten, estimate 1 h to 0.5 h |
| 2026-10-15 | D | Record 002 designed: four decisions, solution, six stories; architect review with 13 findings (5 P1) worked in; queue reordered to S3, S4, S1, S2, S6, S5; review ok by the user |
| 2026-10-15 | S3 | Open items removed from the session start, the rules and the docs; 120 unit tests, new live checks 3 of 3, other rule checks green; review correct, one P3 (stated reason for English headings) fixed; ok by the user |
| 2026-10-15 | S4 | User decision 5: the session start drops recent sessions and the setting `short_term_sessions`; S4 rewritten from the `0` fix to the removal, estimate 0.2 h to 0.5 h |
| 2026-10-15 | S4 | Recent sessions and `short_term_sessions` removed; infrastructure session start now loads 10 of 11 knowledge notes instead of 4; 120 tests; review correct, one P3 (README queue sentence) fixed; ok by the user |
| 2026-10-15 | S1 | CLAUDE.md and records captured redacted at session end into `work/<entry>/repo/`, bundle holds an index; the new live check fails on the old code and passes 3 of 3 on the new; 135 unit tests, 17 of 17 live; three reviewers, 5 findings (2 P2: quadratic redaction pattern, queue format skew with 0.2.0) fixed; ok by the user |
| 2026-10-15 | S2 | Writing rules: repository documents checked per insight, pointer notes for records, `status: archived` (skipped by recall and search, never for a shared note), current-state summaries, no project status, identifiers with their subject, no role names; ten live checks 3 of 3, whole live suite 27 of 27, 137 unit tests; control runs show three checks fail on the old rules; three reviewers plus a second pass, 4 P2 and 3 P3 fixed, Record 002 got the shared-note exception; ok by the user |
| 2026-10-16 | S6 | Version 0.3.0 in the three version files and `uv.lock`, CHANGELOG entry checked against the branch code; two reviewers, 1 P2 and 3 P3 in the CHANGELOG text fixed, second pass clean; ok by the user; halt for merge, tag, push and install |
| 2026-10-16 | decision 6 | User decisions before the release: knowledge notes only when they really matter, names after the core statement without project prefix (way B), stale notes corrected in place and renamed, notes the CLAUDE.md covers deleted (option 2: "the second brain lives"); all in 0.3.0. Record 002 got decision 6, the solution and Story S7; S5 adapted. Release halt moved behind S7 |
| 2026-10-16 | S7 | Living notes: knowledge notes only when they really matter (a build session yields none), names after the core statement, correction renames in place, covered notes deleted; dory's `vaultops` carries out the marks after a successful run, all or nothing, only marks the run wrote; the task file opens with the note language. 164 unit tests, live suite 28 of 28, language check 12 of 12; five review passes, the retry mechanism built and removed again; ok by the user |

## Open questions

- **Release 0.3.0 (decision for the author, 2026-10-16).** The branch `feat/note-quality` is squashed into three commits and pushed, with a pull request to `main`; nothing tagged. The author merges the pull request, tags `v0.3.0` on `main`, pushes the tag, runs `claude plugin marketplace update brain && claude plugin update dory@brain` and restarts Claude Code. Once `claude plugin list` shows dory 0.3.0, the answer goes here and `## Brake` goes to `off`; the vault cleanup (S5, `## Next task`) then starts.

## Last cut

Cut done 2026-10-15.

**2026-10-15, after S1.** Context at 52 % when the task for S2 arrived. The seam is clean: S1 reviewed by three agents (all `correct`, five findings fixed), ok by the user, committed as `ba06780`; S2 not started.

### State at the cut

| | |
|---|---|
| Green | `uv run pytest -q && uv run ruff check .`: 135 tests; whole live suite 17 of 17 during S1 |
| Review | S1: architect, code-reviewer and security-auditor `correct`; P2 quadratic redaction pattern and P2 queue format skew with 0.2.0 fixed, three P3 fixed; ok by the user |
| Committed | everything, last `ba06780`. Nothing pushed. Return point `57d5eda` on `origin/main` |
| Done | D (design), S3 (open items removed), S4 (recent sessions removed), S1 (repository documents) |
| Open | S2, see `## Next task`; then S6 (release prepared, then halt for the author to merge, tag, push and install); then S5 (vault cleanup, only once 0.3.0 is installed) |

### How the next session starts

1. `## Cut` back to `not due`, a line "Cut done <date>" here.
2. The full proof: green before anything is touched. It is also the check that the cut was clean.
3. S2 as written under `## Next task`.

### What is not in the plan and still holds

- Decisions by the user so far (all in Record 002): decision 2 = D (open items removed completely, also from the project overview; the session note keeps its `## Open`), decision 5 = B (recent sessions and the setting `short_term_sessions` removed); decisions 1, 3 and 4 as recommended (1B, 3B, 4A), confirmed with "ok" at the design review. Also in the CLAUDE.md under Recent Decisions.
- Still open with the user and not part of this work: whether the old vault project `dory-brain` moves to `dory` after the repository rename.
- The rules live in `plugin/skills/rules/SKILL.md`; `/dory:note` reads them too (through `dory prepare-note`, "without a task file"), so a rule that needs the bundle must say it applies with a task file. The principle to replace is "Nothing that duplicates CLAUDE.md or records" in `## Principles`.
- Live checks: `DORY_LIVE=1 uv run pytest -m live -q -p no:cacheprovider -k <name> tests/test_live_rules.py`, about 25 s per worker run with Haiku. `--basetemp=<scratchpad dir>` keeps each test's `state/runs.log` with `cost_usd` for reading costs. `World.session` queues with `cwd` = `world.hub` (a `git init` repository without commits), so `world.hub / "CLAUDE.md"` and `world.hub / "docs" / "records" / *.md` reach the worker as captured documents.
- Reviews: write `git diff HEAD` (after `git add -N` for new files) to a file in the scratchpad and give the agents its path; paste the reviewer contract from `/kolibee:do-review` verbatim; add the security-auditor when secrets, customer content or the hook path are touched.
- Actual times: agent and human minutes from the `agent_start`/`agent_stop` pairs in `~/.herdr-journal/dory/dory.jsonl`.
- Commit messages carry no `Co-Authored-By` or other trailers (the user's global rule; the history has none). The `Stand` values in `## Queue` are the auto skill's German words (`offen`, `läuft`, `fertig`, `bewusst offen`).
- The Bash tool runs zsh: an unquoted `$VAR` holding several paths is not split into words. Write paths out or use an array.
- Tests never touch the real vault or config: `tests/conftest.py` points `DORY_CONFIG` at a throwaway file. The real config has `language = "German"`; the real vault is `~/Documents/dory`. Only S5 writes into the real vault, and only after a snapshot.
- Facts behind the problem section: the bundles of past runs are under `~/.local/state/dory-brain/work/<entry>/bundle.md`; the hub CLAUDE.md files are `~/Development/kolibee/ai-assistant-hub/CLAUDE.md` (41,450 characters, status table at 8,735) and `.../ai-assistant-hub-infrastructure/CLAUDE.md` (Future table at 8,969).
