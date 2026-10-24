# Auto state: Capture knowledge reliably (Record 008, release 0.11.0)

## Brake

Entscheid: release by the author (fetch, tag v0.10.0, push, pull request, merge commit, tag v0.11.0)

## Cut

not due

## Next task


## Review

each iteration

## Where

| What | Where |
|---|---|
| Repo | `~/Development/cheorges/dory` |
| Branch | `feat/knowledge-capture`, branched from `feat/library-dialog` at `4c2e765`; that branch is merged into `main` as 0.10.0 (pull request #6, `3a82984`), its tag `v0.10.0` is still missing |
| Return point | `4c2e765` on `origin/feat/library-dialog`; everything after it is the loop and unpushed |
| Quick round | `uv run pytest -q tests/<file the iteration touches>` |
| Full proof | `uv run pytest -q && uv run ruff check .` (294 tests at setup, live checks deselected). Runs before every cut and as the first step of a fresh session |
| Live checks | `DORY_LIVE=1 uv run pytest -m live tests/test_live_rules.py` in iterations that change the rules or the bundle (S1, S4). Real `claude -p` runs in throwaway vaults; they count against the usage limit |
| Design | `docs/records/008-knowledge-capture.md` |
| Research behind S4 | `docs/notes/reports/Wissensablage Skills für dory library.md` (gitignored) |
| Implementation log | `docs/implementation-log.md` |
| Calibration journal | `docs/calibration-journal.md` |
| Actual times | herdr journal `~/.herdr-journal/dory/dory.jsonl` |

## Queue

Order: the security fix first (three transcript copies hold a real Anthropic key), then the rules, then the catalog that keeps the wider rules from adding duplicates, then the comparison run that measures both, then the release text. Estimates follow the actual times of Records 003 and 004 (a rules or worker story took 20 to 30 min agent time).

| Step | Est. (h) | Acceptance criterion | State |
|---|---|---|---|
| T: transcript copies deleted after processing | 0.5 | The copy under `~/.local/state/dory-brain/transcripts/` is deleted when its entry is processed or skipped; an entry still queued or parked in `failed/` keeps its copy (`dory retry` moves parked entries back); copies without an entry are swept; `bundle.md` under `work/` stays (Story 2 replays it); unit tests for the three cases; guide and CHANGELOG say what is kept | fertig |
| S1: rules that capture behaviour and preferences | 1 | Record 008, Story 1 | fertig |
| S4: a catalog of every entry in the bundle | 1 | Record 008, Story 4 | fertig |
| S5: trace of changed or removed entries | 0.5 | Record 008, Story 5 | fertig |
| S6: signal for stale entries | 1 | Record 008, Story 6 | fertig |
| S2: comparison run against the real bundles | 1 | Record 008, Story 2; writes only into throwaway vault copies and a throwaway state directory | fertig |
| S1b: a rule the user sets is a preference | 0.3 | A working rule the user sets in a session (where something goes, how something is filed), also phrased as "the user decided", becomes a `## Preferences` entry; a decision no CLAUDE.md states still goes under `## Decisions`; a live check with the `known-issues.md` case passes; the whole live rules suite stays green | fertig |
| S3: release 0.11.0 prepared | 0.3 | Record 008, Story 3, without merge, tag and push: version in the three files, CHANGELOG, guide, CLAUDE.md, Record 008 Done; committed. Then halt: the author tags `v0.10.0`, then merges this branch, tags and pushes | fertig |
| L1: no silent replacement, aliases and source | 0.5 | Record 009, Story 1 | fertig |
| L2: the whole vault in the library context | 0.5 | Record 009, Story 2 | fertig |
| L3: a test vault that measures link proposals | 0.5 | Record 009, Story 3 | fertig |
| L4: candidates computed in code | 1 | Record 009, Story 4 | fertig |
| L5: the dialog uses the candidates | 1 | Record 009, Story 5; live checks in `tests/test_live_note.py` | fertig |
| L6: release text for Record 009, then halt for merge and tag | 0.2 | Record 009, Story 6; full proof green; committed. Then halt: the author tags `v0.10.0`, merges this branch, tags `v0.11.0` and pushes | fertig |

## History

| Date | Step | What moved |
|---|---|---|
| 2026-10-23 | setup | Record 008 designed with the user (decisions 1 to 3, solution, stories 1 to 3); story 4 (catalog) added after the research on filing tools, at the user's go. Branch `feat/knowledge-capture` from `4c2e765`, full proof green (294 tests). The state file of Record 003 replaced; that loop had finished on 2026-10-19 |
| 2026-10-24 | L6 | CHANGELOG 0.11.0, guide, CLAUDE.md, Record 009 for the library changes; review: two agents, one shared P3 (the 20,000-character claim) and the missing fetch; 375 tests. Ok by the user, who then asked for a review of the whole branch |
| 2026-10-24 | L5 | Skill: draft first, `library-candidates`, multi-select links with reasons, extend or nothing to write on a duplicate, show the text first, aliases and source, Read only; duplicate rule widened (an entry's name in the draft's title); 4 new live checks, library runs 44 of 45, asks-before 5 of 5; 375 tests. Review: two agents, 6 findings worked in. Ok by the user |
| 2026-10-24 | L4 | `candidates.py` and `dory library-candidates`: six signals with reasons, duplicates by title words or a shared name; `links.wiki_names`; fixture recall 1.00 (old 0.72), duplicates 5 of 5, no leaks, 26 ms; 374 tests. Review: two agents, 5 findings worked in, each with a test red on the old code. Ok by the user |
| 2026-10-24 | L3 | Fixture vault of 151 files with a generator and a drift test, 10 requests with 18 expected links, 5 duplicates and a privacy case; old way 0.72 among the first ten (0.83 without the cut); 356 tests. Review: two agents, 7 P3 worked in. Ok by the user, expected links unchanged |
| 2026-10-24 | L2 | `library-context` lists every visible project's notes with description or heading, aliases, tags and links, each entry with aliases and sha256; budget 20,000 characters; `scopes.visible_projects` shared with the catalog; `describe.py`; skill reads before extending with the context's hash; 352 tests, library live 12 of 12. Review: two agents, 6 findings worked in; snapshot on unreadable files into the Future table. Ok by the user |
| 2026-10-24 | L1 | `library-write` refuses an existing entry without `--replace --expect <sha256>`, writes `aliases` and `source`; skill step 5 extends only on purpose and keeps the entry's text; 345 tests, live extend checks 9 of 10. Found: a pre-existing flaky library check (grep outside the cwd refused), moved to Story 5. Review: two agents, 3 findings worked in. Ok by the user |
| 2026-10-24 | Record 009 | Designed with the user: decisions 1 (candidates in code) and 2 (test vault now, the user's vault later), six stories as L1 to L6, joining 0.11.0. Ok by the user |
| 2026-10-24 | S3 | Version 0.11.0, CHANGELOG, guide, CLAUDE.md, Record 008 In Progress; review: two agents, 2 findings (0.10.0 already merged as #6, only `v0.10.0` missing; statuses). Ok by the user, who also decided that Record 009 (library) joins 0.11.0 |
| 2026-10-24 | S1b | Rules: a working rule the user sets is a preference, also as "the user decided"; `## Decisions` only for decisions about the system; new live checks for the `known-issues.md` case (old rules 1 of 2, new 3 of 3) and for an unstated system decision (3 of 3); live suite 35 of 35, 334 tests. Review: two agents, 4 findings worked in. Ok by the user |
| 2026-10-24 | S2 | `spike/replay.py`: the seven reviewed sessions through main and the branch (opus): 11 against 25 entries, 3.54 against 3.87 USD; three of four missed insights back, development on `main` stays out as a decision; found that a user's working rule was taken for a decision. Review: one agent, one P3 worked in. Ok by the user, who also agreed to S1b before the release |
| 2026-10-24 | S6 | Per-entry dates and text hash in the state directory; flags missing path, unchanged since, changed after this session (the ordering rule back); catalog, rules, status, start marker; 334 tests, live 33 of 33. Review: two agents, 8 findings (one P1), 7 worked in. Ok by the user |
| 2026-10-24 | S5 | `## Replaced` in the session note with the previous text of every changed or removed entry, written by dory's code; failed attempts' traces held for the retry; 317 tests. Review: two agents, 4 findings worked in. Ok by the user |
| 2026-10-24 | S4 | Catalog of every entry's lead in the bundle, privacy filters, cross-project rule in the rules (own setup in this project, tool-wide in a topic file with an Open note); 307 tests, live 32 of 32, control without catalog red 2 of 2. Review: two agents, 6 findings worked in. Ok by the user |
| 2026-10-24 | S1 | Rules capture behaviour, limits and preferences; the CLAUDE.md blocks only decisions; no references outside the vault; home infrastructure as project. Live rules suite 30 of 30 (haiku), key checks 8 of 8. Review: two agents, 5 findings worked in. Ok by the user |
| 2026-10-23 | S1 decision | User: no references to documents outside the vault (decision 4); trace and stale signal added as Stories 5 and 6 (decision 5), queued after S4 |
| 2026-10-23 | T | Transcript copies deleted when their entry is processed or skipped, parked entries keep theirs for `dory retry`, a sweep clears the rest; 299 tests. Review: two agents, one shared finding (a clone kept the source's mtime, so the sweep's grace did not protect a fresh copy), fixed with a test. Ok by the user |

## Open questions

- None. (Answered 2026-10-23: no record pointers; the vault stands on its own, see Record 008 decision 4. Trace in the session note, stale signal to worker and status, at start only for a missing path: decision 5, Stories 5 and 6.)

## Last cut

**2026-10-24, after S2, before S1b.** Context at 50 %. The seam is clean: T, S1, S4, S5, S6 and S2 are reviewed, approved by the user and committed (last `7058788`, plus the journal fix in the cut commit). Nothing pushed; return point `4c2e765` on `origin/feat/library-dialog`.

Cut executed 2026-10-24.

### State at the cut

| | |
|---|---|
| Green | `uv run pytest -q && uv run ruff check .`: 334 tests; live rules suite 33 of 33 at S6 |
| Committed | everything; S1b not started |
| Open | S1b (see `## Next task`), then S3 (release text, no merge/tag/push) |

### What the next session starts with

1. The full proof: green before anything is touched.
2. S1b after `## Next task`: the live check first, against the current rules, then the rules.

### What the plan does not say and still holds

- Live checks run with haiku (`DORY_LIVE_MODEL` default); the user's worker runs opus. A whole live rules suite takes about 10 minutes; run it in the background and pull `Waiting:` meanwhile.
- After changing rules or code, an earlier background live run keeps the old modules loaded; its result does not count. Stop it (`pkill -f "pytest -m live tests/test_live_rules.py"`) and rerun.
- The user's global CLAUDE.md forbids `Co-Authored-By` lines; commits end with the `Claude-Session:` line only.
- Research reports (gitignored): `docs/notes/reports/Wissensablage Skills für dory library.md` (library, basis for a later Record 009) and `docs/notes/reports/Second Brains für Coding Agenten.md`.
- The comparison run's output stays in the scratchpad `replay/` of the earlier session and may be gone; `spike/replay.py --out <new dir>` reruns it (about 7.4 USD API equivalent with opus).
- For S3: the guide must say that entries never point to records (decision 4), that transcript copies are deleted (T), the trace in the session note (S5), the flags and `dory status` line (S6); CHANGELOG has an `Unreleased` section from T to fold into 0.11.0.
