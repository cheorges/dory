# Record 009: Better Proposals in /dory:library

## Status

In Progress (2026-10-24): built and ready with 0.11.0 on `feat/knowledge-capture`; the merge and the tag `v0.11.0` are the author's.

---

## Problem

`/dory:library` (Record 006, dialog since 0.10.0) files knowledge deliberately and keeps the user's library apart from what the worker writes. A research on filing tools in October 2026 (`docs/notes/reports/Wissensablage Skills für dory library.md`, gitignored) found that this separation has no equal among the tools it looked at, and that the dialog's form (draft everything, propose compactly, the user picks, one controlled write path) matches the four tools with a filing command. It found three weaknesses:

- **Few fitting links.** `dory library-context` lists only the current project's notes and the topic files, each as a bare path, without heading, description, aliases or tags. Other projects' notes are missing although `dory link` accepts them, so knowledge that belongs to another project, or a request outside a project, gets no candidates there. The skill then greps for two or three key terms the model picks, in one spelling and one direction. The tools whose link proposals users trust find candidates in code (title and alias matches, mentions without a link, a catalog of one-liners) and let the model choose among them, with a reason per candidate.
- **Silent replacement and duplicates.** `library-write` replaces an existing entry without being told to as soon as folder and title match: a title typed under "Other" that happens to exist overwrites that entry, without the model having read it; only the snapshot brings it back. The same subject under a slightly different title or in another folder silently becomes a second entry, because `_existing` compares only the exact name in the same folder.
- **Coarse questions.** The `Links` question offers sets of files, without a reason per file; picking one of three proposed files needs typing. The `Write` question offers `Shorter` and `More detail` for a text the user does not see. An entry cannot get aliases (which Obsidian uses for link completion and unlinked mentions) or a source, and a request holding two subjects, or one already filed, has no answer but one new entry.

If nothing changes, library entries stay poorly linked and so do not load where they are needed, duplicates accumulate across folders, and a typo in a title can replace an entry.

By the user's call of 2026-10-24 the work joins release 0.11.0 (Record 008), on the same branch, including the candidate command. Remembering rejected links (the research's item 9) stays out.

## Options Considered

### Decision 1: Where link candidates come from

- **A. Code ranks candidates, the model chooses** (chosen): a new command takes the draft and prints the best 15 to 25 linkable files and library entries, each with its score and the reason it was found. Pure Python over the Markdown files, no index, no dependency. Separates recall (cheap, deterministic, testable) from precision (the model, which writes a reason per proposed link).
- **B. Obsidian CLI or Local REST API** (`backlinks`, `unresolved`, `aliases`): needs the running app; dory works on the files without Obsidian. Rejected.
- **C. Embeddings:** no finding in the research justifies them at a few hundred files; an index would be a second copy of confidential library content outside the vault. Rejected.

### Decision 2: What the comparison measures (the user, 2026-10-24)

The user's vault holds 23 files (2 library entries, 3 topic files, no project notes), too few for a before-and-after comparison to show anything.

- **A. A test vault with expected links:** a fixture of about 150 files with 8 to 10 requests and the files each should link; measured as a unit test, without `claude -p`.
- **B. The user's vault, later:** fixed weights now, the comparison once the vault has grown.
- **C. Both** (chosen): A now, B as a row in the Future table. Only A measures anything in 0.11.0; B later checks whether the expected links of A were realistic.

## Solution

All of it lands on `feat/knowledge-capture` and ships as 0.11.0 together with Record 008.

- **`dory library-context`, complete.** The notes of every project, the current one first, then the topic files; per file its first heading or `description`, its `aliases` and `tags`, and the entries it links; per library entry its aliases. A private project's notes appear only in that project's sessions (the same rule as the catalog of Record 008).
- **`dory library-candidates`.** Reads the draft (title, aliases and content) on standard input and prints up to 25 candidates in two groups: files to link from (project notes, topic files) and existing library entries that may be the same subject. Signals, strongest first: an unresolved link `[[X]]` whose target is the draft's title or an alias; a file that mentions the title, an alias or a distinctive phrase of a multi-word title without a link; a title or alias of an existing file that occurs in the draft; BM25 over the linkable files with the whole draft as the query; neighbourhood (files that already link entries of the same library folder, or that the draft links). Code and links are skipped, matching ignores case and phrases of three characters or less. Each line: path, where a link loads the entry, score, and the reasons in words.
- **Duplicates across folders.** The same command lists library entries whose title has a token overlap (Jaccard) of at least 0.75 with the draft's title, that share an alias, or whose title or alias stands in the draft's title as whole words (`uv` in "uv sync and the lock file", added in Story 5), in any folder. The skill then proposes `Extend <folder>/<title>` first and says why.
- **No silent replacement.** `library-write` fails on an existing entry unless it gets `--replace` together with `--expect <sha256>` of the entry as the skill read it; a changed entry fails with the current hash, and the skill reads it again. A new entry is written as today.
- **Aliases and source.** `library-write --alias <a>` (repeatable) and `--source <URL or [[...]]>` write the `aliases` and `source` properties, links quoted; on replace, given values replace the old ones, absent ones are kept. The skill proposes two or three aliases (an abbreviation, a synonym, the term in the other language) and names a source only when the user or the session gave one, never invented.
- **The dialog.** Step 2 runs `library-candidates` on the draft instead of grepping for key terms. The `Links` question becomes a multi-select with one option per proposed file (up to four), its description saying where the entry then loads and the reason ("both cover the deploy of dory"); further files under "Other". A request with two subjects gets two entries proposed, one per run; a subject already filed gets "nothing to write" as an option. The summary before the questions states the rough length; the `Write` question offers `Write it`, `Show the text first` and `Shorter`.
- **Measurement.** A fixture vault under `tests/fixtures/library-vault/` with about 150 files (several projects with notes, topic files, library folders, German and English mixed) and 8 to 10 requests with their expected links. A test computes recall among the first 10 candidates for `library-candidates` and for the old way (the files `library-context` listed that contain one of three key terms per request, as the skill's grep did), and prints both.

## User Stories

Order: the safety fix first (it guards the user's entries and is small), then the context, then the measurement before the candidate command it measures, then the dialog that uses all of it. Stories 1 to 3 change code only; Story 5 changes the skill and needs live checks.

### Story 1: No silent replacement, aliases and source
**As a** user filing into my library
**I want** an existing entry replaced only when the dialog read it and chose to extend it, and an entry to carry aliases and its source
**So that** a typed title never overwrites an entry, and an entry is found under its other names and says where it came from

**Acceptance Criteria:**
- [x] Given an entry `library/Python/uv.md`, when `library-write --folder Python --title uv` runs without `--replace`, then it fails with a message naming the entry and its current hash, and the file is unchanged
- [x] Given the same entry, when `--replace --expect <hash of the file as read>` is given, then the content is replaced and `created` stays; with a stale hash it fails and the file is unchanged
- [x] Given `--alias "Package management" --alias Paketverwaltung --source "https://docs.astral.sh/uv/"`, then the entry's frontmatter holds both aliases and the source; a source link `[[...]]` is written quoted
- [x] Given a replace without `--alias` or `--source`, then the existing aliases, tags and source stay
- [x] Unit tests for each case; the live check of `/dory:library` that files a new entry still passes

**Priority:** High
**Status:** Done (2026-10-24)

### Story 2: The whole vault in the library context
**As a** user filing knowledge that belongs to another project, or filing outside a project
**I want** the context to list every project's notes, with what each file is about
**So that** the dialog can propose any file that should link the entry

**Acceptance Criteria:**
- [x] Given notes in the projects `dory` and `hub` and a session in `dory`, when `dory library-context` runs, then the notes of both appear, `dory` first, each with its first heading or `description`, its `aliases` and `tags`, and the entries it links
- [x] Given a library entry with aliases, then its line names them, and every entry's line carries its sha256, so that an extend sends the hash of the entry as it was read (found in the review of Story 1); the skill uses it instead of the refusal's
- [x] Given a project with `domain: private`, then its notes appear only in a session of that project
- [x] Given a session outside any project, then every work project's notes appear
- [x] Unit tests; the output stays within 20,000 characters for the fixture vault of Story 3 (a cap per project with a count of the rest)

**Priority:** High
**Status:** Done (2026-10-24)

### Story 3: A test vault that measures link proposals
**As a** developer of dory
**I want** a realistic vault with requests and the links each should get
**So that** the candidate command is measured against the way the skill finds links today

**Acceptance Criteria:**
- [x] `tests/fixtures/library-vault/` holds about 150 files: at least four projects with notes, topic files in `notes/`, library entries in several folders, German and English text mixed, some aliases, some unresolved links and mentions without a link
- [x] 8 to 10 requests, each with a draft, its expected links (files to link from) and, where one exists, the library entry that is the same subject
- [x] A test computes recall among the first 10 for the old way (the files `library-context` of 0.10.0 listed that contain one of three key terms per request) and prints it; it passes as long as the fixture parses
- [x] The requests and expected links appear in the review package so that the user can correct them

**Priority:** High
**Status:** Done (2026-10-24)

### Story 4: Candidates computed in code
**As a** user filing into my library
**I want** dory to find the files that should link the new entry, and the entries that may already cover it, with a reason for each
**So that** the dialog proposes the right links and extends instead of duplicating

**Acceptance Criteria:**
- [x] Given a draft on standard input, when `dory library-candidates` runs, then it prints at most 25 candidates in two groups (files to link from, possible duplicates), each with path, where a link loads the entry, score and its reasons in words
- [x] Given a file with an unresolved link `[[uv]]` and a draft titled `uv`, then that file ranks first among the files to link from
- [x] Given an entry `library/Tools/uv package manager.md` and a draft titled `uv package manager` in another folder, or sharing an alias, then it appears under possible duplicates
- [x] Code blocks and existing links do not count as mentions; a phrase of the title or another file's name of three characters or less counts as no hit, while the draft's own title and aliases count at any length as whole words (`uv`)
- [x] On the fixture vault of Story 3, recall among the first 10 is at least 0.8 and higher than the old way's (0.72), all five expected duplicates appear, and no candidate of the work session about taxes lies in the private project; the test prints both through `report`
- [x] The whole run on the fixture vault takes under one second

**Priority:** High
**Status:** Done (2026-10-24)

### Story 5: The dialog uses the candidates
**As a** user filing into my library
**I want** to pick each proposed link on its own, see why it is proposed, and be offered extending or nothing when the subject is already filed
**So that** I decide link by link and never get a duplicate by accident

**Acceptance Criteria:**
- [x] The skill runs `library-candidates` on its draft instead of grepping for key terms; its `allowed-tools` allow the command
- [x] The `Links` question is a multi-select with one option per proposed file (up to four), each description naming where the entry then loads and the reason
- [x] Given a possible duplicate, then `Extend <folder>/<title>` is the recommended folder option and the summary says why; extending reads the entry and writes with `--replace --expect`
- [x] Given a request whose subject is already filed, then "nothing to write" is an option; given two subjects, the skill says so and files one per run
- [x] The summary states the rough length; the `Write` question offers `Write it`, `Show the text first` and `Shorter`
- [x] The skill proposes two or three aliases in the summary and passes a source only when the user or the session gave one
- [x] `test_library_asks_before_it_writes` passes 5 of 5: on 0.10.0's step 2 it failed about 1 run in 3, because a `grep` on the vault, which lies outside the session's working directory, was refused in a headless run (found in Story 1)
- [x] Live checks in `tests/test_live_note.py`: a link proposed from another project's note; an existing entry under another title extended, not duplicated; no invented source; the two existing library checks still pass

**Priority:** High
**Status:** Done (2026-10-24); the AskUserQuestion dialog itself is not live-checked, since it cannot run headless

### Story 6: Release text
**As a** user of dory
**I want** the 0.11.0 entry and the guide to describe the new dialog
**So that** I know what `/dory:library` now asks and what it refuses

**Acceptance Criteria:**
- [x] CHANGELOG 0.11.0 and the guide's `/dory:library` row and library section describe the candidates, the multi-select links, `--replace`, aliases and source
- [x] The Future table holds the comparison on the user's own vault (decision 2, B)
- [x] Record 009 and Record 008 are In Progress until merge and tag

**Priority:** Medium
**Status:** Done (2026-10-24)
