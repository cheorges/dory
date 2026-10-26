# Record 008: Capture Knowledge Reliably

## Status

In Progress (2026-10-24): built and ready as 0.11.0 on `feat/knowledge-capture`; the merge and the tag `v0.11.0` are the author's. The comparison run (Story 2) led to one more rule: a working rule the user sets is a preference, also when the session calls it a decision.

---

## Problem

dory 0.9.0 processed 7 sessions between 2026-10-22 and 2026-10-23 in three repositories (dory, box-cheorges, ai-assistant-hub) into the new iCloud vault. They left 8 entries: 3 in project knowledge files, 5 in topic files in `notes/`. All 8 are correct and concrete. The user finds this too sparse, and a review of the 7 session notes against the entries confirms it: about 4 to 5 insights that a later session needs are missing.

### What was missed

| Session | Insight | Where it should be |
|---|---|---|
| box-cheorges, 2026-10-22 | The user wants Mermaid diagrams only when they are really needed | A topic file, `## Preferences` |
| ai-assistant-hub, 2026-10-23 08:48 | Foundry throttles at 6 parallel calls and answers break off, so the quality tests run through a separate Anthropic workspace | ai-assistant-hub, `## Pitfalls` |
| ai-assistant-hub, 2026-10-23 12:35 | A new version of a document uploaded without deleting the old one adds its values to the existing product, and the comparison agent sees both; the old file has to be deleted | ai-assistant-hub, `## Facts` |
| ai-assistant-hub, 2026-10-23 08:48 | The comparison repository is now developed directly on `main` | ai-assistant-hub, `## Decisions` |

Each of them is in the session note under `## Log`, which the session start never loads.

### Why the rules leave them out

The rules in `plugin/skills/rules/SKILL.md` were tightened in Record 002 after 15 of 15 sessions had left notes and a third of them described what the code does. They now hold the worker back at three points:

1. **The test asks about the repository only.** "Would someone working in this repository tomorrow, reading the CLAUDE.md and the code, make a mistake or lose time without it?" A preference the user states in passing, such as the one on Mermaid diagrams, concerns no repository and fails the test, although the section on topic files asks for "ways of working the user states without reference to a project".
2. **The rules push towards leaving out.** "Most sessions add nothing to a knowledge file, and that is a normal result" stands in bold. A pitfall that changed how the session worked (the Foundry throttling) reads like an intermediate state of the session and goes to the log.
3. **What the CLAUDE.md states never becomes an entry, and an entry the CLAUDE.md now states is removed.** The CLAUDE.md is copied when the session is queued. When the session ran `/kolibee:wrapup`, its decisions are in the copy and the worker skips them. The CLAUDE.md is not a durable store, though: `Recent Decisions` keeps at most 20 rows, status rows and the next step are rewritten, and an insight that leaves it is then nowhere. When the session ended with `/clear` instead, the copy does not hold the insight, so point 3 does not block it, but points 1 and 2 do.

### Smaller finding

The rules count "the user's own devices and home infrastructure (NAS, home network, private servers ...)" as private content that becomes no entry anywhere. In box-cheorges the NAS is the project itself; the worker wrote the entry into its `knowledge.md` anyway, against the letter of the rule. The rule needs to say which one wins.

### If nothing changes

Knowledge that the user considers important for the future stays in session notes that never load. The user cannot rely on dory and keeps writing it into the CLAUDE.md by hand, which is the work dory was built to take over.

## Options Considered

### Decision 1: What counts as knowledge

#### Option A: Widen the test
- **Approach:** The test asks whether someone working in this repository, **or the user in any later session**, would make a mistake or lose time without the entry. The bold "Most sessions add nothing to a knowledge file" goes. Examples are added for what the strict test lost: a limit or throttling that changed how the work was done, a preference stated in passing, how an external system or a process behaves.
- **Pros:** One change to the rules text; the missed insights of the problem pass the test.
- **Cons:** The rules may swing back to the state before Record 002, when a third of the notes described what the code does.

#### Option B: Make rejected candidates visible
- **Approach:** The test stays; the worker lists every insight it considered and left out, with the reason, in the session note (`## Candidates`).
- **Pros:** A review sees what the worker dropped and why.
- **Cons:** Nothing more is captured; session notes grow.

#### Option C: A and B
- **Approach:** Both.
- **Pros:** A becomes checkable through B.
- **Cons:** The most work; session notes grow.

#### Decision

Option A, decided by the user on 2026-10-23. The comparison run against the old bundles (see Solution) shows what the widened test adds, without a permanent list in every session note.

### Decision 2: Knowledge the CLAUDE.md already states

#### Option A: As today
- **Approach:** What the CLAUDE.md states never becomes an entry, and an entry the CLAUDE.md now states is removed.
- **Pros:** No duplicates in the session start of that repository.
- **Cons:** An insight is lost once the CLAUDE.md drops it (`Recent Decisions` keeps 20 rows; status rows and the next step are rewritten).

#### Option B: Importance decides
- **Approach:** The CLAUDE.md blocks nothing; descriptions of the code stay excluded.
- **Pros:** Nothing is lost when the CLAUDE.md is pruned.
- **Cons:** Decisions are copied too, although the CLAUDE.md and the records are where they belong.

#### Option C: By CLAUDE.md section
- **Approach:** Status, next step and `Recent Decisions` count as transient and block nothing; architecture and instructions block.
- **Pros:** Duplicates only what may disappear.
- **Cons:** Depends on the section names of one template; public users keep other CLAUDE.md files.

#### Decision

A variant of B, decided by the user on 2026-10-23: **what the CLAUDE.md states becomes an entry if it is important behaviour, not a decision and not a description of the code.** Behaviour means how a system, a service, a tool or a process behaves when one works with it: a pitfall, a limit, what a process does with an input (the comparison service adds a new document version to the existing product), the steps of a procedure the user follows. Decisions stay in the CLAUDE.md and the records; the code stays in the repository. An entry is no longer removed because the CLAUDE.md now states it, unless it is a decision.

### Decision 3: Home infrastructure that is the project itself

When the session's project is the user's own device or home infrastructure (box-cheorges manages the user's NAS), its insights go into that project's `knowledge.md` like in any project, never into topic files in `notes/`. Decided by the user on 2026-10-23; this is what the worker already did.

### Decision 4: No references to documents outside the vault

Raised at the review of Story 1, decided by the user on 2026-10-23: **the vault stands on its own.** An entry never points to a record or another document outside the vault ("Details: `044-budget-conversion.md`"); when an insight belongs in the vault, its substance is written into the entry, briefly and completely. This replaces the pointer entries of Record 002 (decision 3). Paths and commands one uses to do something (`compose-deploy.sh check`) stay; they are not references that explain the subject elsewhere. Behaviour that a record describes becomes such a self-contained entry when it passes the test; the record's decisions and the design of its code do not.

### Decision 5: A trace for every rewritten entry, a signal for stale ones

Asked by the user on 2026-10-23 after the research on other memory systems (`docs/notes/reports/Second Brains für Coding Agenten.md`, gitignored): the field moves to replacing with a trace instead of overwriting silently (mem0, Zep, agentcairn), and GitHub Copilot checks remembered facts against the current code. dory keeps its own strengths (repository documents in the bundle, `library/` closed to the worker, the deterministic check of every run against a baseline, nothing deleted automatically, entries in their current state for a lean session start) and adds both in dory's code, from the baseline diff it already computes:

- **Trace in the session note** (chosen over a history file per knowledge file): after each run, dory appends `## Replaced` to the session note with the full previous text of every changed or removed entry, as a folded callout. Session notes never load at session start.
- **Stale signal, shown to the worker and in `dory status`; at session start only for a missing path** (chosen over no start marker and over an age marker at start): dory keeps per entry when it was added and last changed, in the state directory. An entry is flagged when a path it names in backticks no longer exists in the project's repository, or when it is unchanged for more than 90 days. Flags appear in the worker's catalog and as a count in `dory status`; at session start, only an entry whose path is missing gets a short marker. Nothing is deleted.

## Solution

All three decisions change the rules text in `plugin/skills/rules/SKILL.md`; no code changes in the worker. The ingest skill's step 5 ("Many sessions have none") is aligned. The comparison run is a script under `spike/`, not part of the plugin.

### Rules text

- **What counts as knowledge.** The test becomes: would someone working in this repository, or the user in any later session, make a mistake or lose time without it? The bold "Most sessions add nothing to a knowledge file, and that is a normal result" is replaced by one plain sentence that a session without insights writes only its session note. A short list of what the old test lost: a limit, throttling or failure that changed how the work was done; a preference the user stated in passing, also without reference to a project; how an external system, service or process behaves with an input. The list of what is not knowledge stays: what was built, how the code works, the steps of the session, intermediate states, guesses, textbook knowledge.
- **What the repository already documents.** The section is rewritten after decision 2. What the CLAUDE.md or a record states becomes an entry when it is important behaviour (pitfall, limit, how a system or process behaves, a procedure the user follows), and not when it is a decision or a description of the code. The rule "remove what the CLAUDE.md now states" applies to decisions only. The Grep over the repository documents stays: it now decides whether a statement is a decision already recorded, and it gives the record name for a pointer.
- **Private content.** One sentence: when the session's project is itself the user's device or home infrastructure, its insights go into that project's `knowledge.md`, never into topic files.

### Checks

- **Live checks** in `tests/test_live_rules.py`, each a small transcript against a real `claude -p`:
  1. A preference the user states in passing without a project ends up in a topic file under `## Preferences`.
  2. A throttling that made the session switch providers ends up as a pitfall.
  3. A pitfall the CLAUDE.md copy already states ends up as an entry anyway.
  4. A decision the CLAUDE.md copy states does not become an entry.
  5. A session that only explains what a script does leaves no entry (guards against the swing back to before Record 002).
- **Comparison run** (`spike/replay.py`): replays the bundles under `~/.local/state/dory-brain/work/` from 2026-10-22 and 2026-10-23 in their order into an empty copy of the vault, once with the released rules and once with the new ones, and prints the entries of both runs side by side. The repository documents of a bundle were deleted after its run, so the script copies the repositories' current CLAUDE.md and records; they have moved on since, which the comparison accepts. Expected: the four missed insights of the problem appear with the new rules, and no entry describes code. Costs about 5 to 10 USD API equivalent on the subscription.

### Release

0.11.0 (0.10.0 is the open library dialog), CHANGELOG entry, the guide's section on what the worker writes.

## User Stories

### Story 1: Rules that capture behaviour and preferences
**As a** user who often ends a session with `/clear` instead of a wrapup
**I want** the worker to write important behaviour, limits and my preferences into the knowledge and topic files, even when the CLAUDE.md states them
**So that** a later session gets them although the CLAUDE.md drops them or never had them

**Acceptance Criteria:**
- [x] Given a transcript in which the user states a preference without reference to a project, when the worker runs, then a topic file in `notes/` holds it under `## Preferences`
- [x] Given a transcript in which throttling made the session switch providers, when the worker runs, then the project's `knowledge.md` holds it under `## Pitfalls`
- [x] Given a pitfall the CLAUDE.md copy already states, when the worker runs, then it becomes an entry anyway
- [x] Given a decision the CLAUDE.md copy states, when the worker runs, then it becomes no entry
- [x] Given a session that only explains what a script does, when the worker runs, then no knowledge or topic file changes
- [x] Given a session in a project that is the user's home infrastructure, when the worker runs, then its insights go into that project's `knowledge.md` and no topic file
- [x] `uv run pytest -q`, `ruff check .` and the live checks in `tests/test_live_rules.py` pass

**Priority:** High
**Status:** Done (2026-10-24)

### Story 2: Comparison run against the real bundles
**As a** maintainer
**I want** the bundles of 2026-10-22 and 2026-10-23 replayed with the old and the new rules
**So that** I see what the new rules add before they reach the real vault

**Acceptance Criteria:**
- [x] Given the bundles under `~/.local/state/dory-brain/work/`, when `spike/replay.py` runs, then it writes into empty vault copies only, never into the real vault or the real state directory (it replays the transcript copies, see the result)
- [x] The output lists the entries of both runs side by side, per file
- [x] With the new rules, the four missed insights of the problem appear (Mermaid preference, Foundry throttling, new document versions, development on `main`): three of four; development on `main` is a decision and stays out by decision 2
- [x] No new entry describes what the code does or restates a decision from the CLAUDE.md
- [x] The result is noted in this record with the cost of the run

**Priority:** High
**Status:** Done (2026-10-24)

### Story 5: A trace of every changed or removed entry
**As a** user who reads the vault in Obsidian
**I want** the previous text of every entry a run changed or removed kept in that run's session note
**So that** I can see what an entry said before and restore it, without the session start loading it

**Acceptance Criteria:**
- [x] Given a run that changes an entry (also with a new lead) or removes one, when the post-run checks finish, then the session note ends with `## Replaced` holding, per entry, its file and its full previous text in a folded callout (`> [!quote]- ...`)
- [x] Given a run that only adds entries, then the session note has no `## Replaced`
- [x] Changes the post-run checks attribute to the user (the user's notes, `library/`) are not traced there; they stay in the run log as today
- [x] Recall never loads `## Replaced` (session notes do not load); search finds the old text only as part of the session note
- [x] Unit tests for changed, re-led, removed and added-only; full proof green

**Priority:** High
**Status:** Done (2026-10-24)

### Story 6: A signal for stale entries
**As a** user who relies on the session start
**I want** entries flagged whose named path is gone or that nobody touched for a long time
**So that** a session checks them before relying on them, and the worker corrects them when a session touches their subject

**Acceptance Criteria:**
- [x] dory keeps per entry (file and key) the date it was added and last changed, in the state directory, updated from the baseline diff of every run; an entry seen for the first time counts from that run. Added at the review: a hash of the entry's text detects edits in Obsidian under the same lead; entries of a file seen for the first time have no change date, so they never count as `changed after this session`. The ordering rule dropped in Story 4 returns as the flag `changed after this session`, with a run's own changes exempt
- [x] An entry of a project's `knowledge.md` is flagged `missing path` when a path it names in backticks does not exist below the project's repository; topic files are not path-checked. Changed at the build: a candidate needs a `/` and a first part that exists in the repository, and it counts as missing only when git does not list it and it is not on disk; bare file names (`SKILL.md.orig`) and paths elsewhere (`cheorges/other-repo`, `notes/GitHub.md`) would give false flags
- [x] Any entry is flagged `unchanged since <date>` when its last change is more than 90 days old
- [x] The worker's catalog (Story 4) shows the flags next to the leads
- [x] `dory status` shows the number of flagged entries per kind
- [x] At session start, an entry flagged `missing path` carries a short marker naming the path; no other start text changes
- [x] Nothing is deleted or rewritten by the flags; unit tests for each flag and for the start marker; full proof green

**Priority:** Medium
**Status:** Done (2026-10-24)

**Result (2026-10-24).** `spike/replay.py` replayed the seven reviewed sessions through the full pipeline of `main` and of this branch, each into an empty throwaway vault with its own state directory, with the configured worker model (opus). It replays the transcript copies through `enqueue` instead of the bundles, because the bundles no longer hold repository documents; each version builds its own bundle, catalog and checks. The real vault and state were only read (no file in the vault changed, the 14 transcript copies are still there).

| | `main` | branch |
|---|---|---|
| Entries in knowledge and topic files | 11 | 25 |
| API equivalent (subscription) | 3.54 USD | 3.87 USD |
| Transcript copies left in its state | 7 | 0 |

- **The missed insights:** the Mermaid preference, the Foundry limit and the behaviour of a new document version appear with the branch. With `main`, this run also caught the Mermaid preference and the Foundry limit, which the real run of 2026-10-23 had missed; one run per version cannot separate the rules from the model's variance. The new document version appears only with the branch.
- **Not written, as decision 2 says:** "the comparison repository is developed directly on `main`" and the `known-issues.md` rule; both are decisions the user made in the session, and the branch leaves decisions to the CLAUDE.md. `main` wrote the `known-issues.md` rule as a preference.
- **The 14 added entries** are behaviour and procedures the old rules dropped: seven pitfalls of the box (reachable only from the home network, Postgres 18 data directory, the Debian base of a Postgres tag, the Nextcloud maintenance mode not stopping every database access), two how-tos of the comparison service, `claude -p` without `AskUserQuestion`, the vault's location. By vir's rubric each is concrete enough to be wrong and none narrates the session; none describes code or restates a decision of a CLAUDE.md; no secret appears in either vault.
- **Not exercised:** no run changed or removed an entry (empty vaults), so the trace and the `changed after this session` flag did not show; the unit and live checks cover them.

### Story 3: Release 0.11.0
**As a** user of dory
**I want** the new rules released with a guide that says what the worker writes
**So that** I know what to expect in my vault

**Acceptance Criteria:**
- [x] Version 0.11.0 in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py`
- [x] CHANGELOG entry and the guide's section on what the worker writes are updated
- [ ] Merged through a pull request with a merge commit, tag `v0.11.0` pushed (the author)

**Priority:** Medium
**Status:** In Progress (ready to merge)

### Story 4: A catalog of every entry in the bundle
**As a** user whose sessions now leave more entries
**I want** the worker to check each insight against every entry already in the vault
**So that** the wider test of Story 1 extends existing entries instead of adding duplicates, also across projects

Added on 2026-10-23 after the research on filing tools (Karpathy's `index.md`, mem0's retrieve-then-decide): the worker today sees the project's own `knowledge.md` in full and greps the topic files, but never the other projects' files.

**Acceptance Criteria:**
- [x] Given a vault with knowledge files in several projects and topic files in `notes/`, when the bundle is built, then it holds a catalog with every entry's bold lead and its file, grouped by file, the session's own `knowledge.md` included
- [x] The catalog leaves out `library/`, the user's notes in `projects/<p>/notes/`, lists and registers, and in a private project's session the other projects' files
- [x] The rules tell the worker to check each insight against the catalog and to extend the matching entry in the session's project file or the topic file; the worker never writes into another project's file. Changed at the review of Story 4: each session loads only its own project's file and `notes/`, so an insight another project's file already states goes into this project's file when it concerns this project's own setup, or into the topic file of its subject when it holds for any project using the tool, with the other project's entry named under `## Open`. When unsure whether an insight matches, it is a new subject. The rule that a file updated after the session's date is not rewritten was dropped: `updated` changes with every write of dory, so it says nothing about the user; ordering waits for the per-entry dates of Story 6
- [x] Given a session whose insight matches an entry in a topic file under another wording, when the worker runs (live check), then that entry is extended and no new one is added
- [x] `uv run pytest -q` and `ruff check .` pass; leads are cut at 100 characters, so 100 entries take about 12,000 characters (the first estimate of 4,000 did not fit real leads)

**Priority:** High
**Status:** Done (2026-10-24)
