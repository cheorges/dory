# Record 004: Notes as Files and One Folder Without a Project

## Status

In Progress: all stories built on `feat/notes-as-files` (2026-10-21), not committed

---

## Problem

0.4.0 keeps one `knowledge.md` and one `notes.md` per scope: per project, in `general/` (work) and in `private/` (Record 003). A day after the release, `general/` and `private/` hold an empty `knowledge.md` each, no `notes.md` exists anywhere, and five worker runs have added no entry outside the projects (`runs.log`, 2026-10-20 to 2026-10-21). The problems below come from the structure, not from an observed loss.

1. **`general/` has no common subject.** A project's file is about one project, so sections by kind (pitfalls, decisions, facts) carry it. In `general/`, a fact about the Outlook connector would stand under `## Facts` next to a Notion pitfall, and the file grows with every project that adds to it. Every work session loads it, in full or inside a summary, whether the session touches any of its subjects or not.
2. **A note is one dated line.** `/dory:note` appends the user's words as a bullet to a `notes.md`. A note has no title and no room beyond a sentence; to find one, the user scans a list.
3. **Private knowledge is written by a model.** The worker writes `private/knowledge.md` from transcripts: family, health, money, the home network. The user wants that content in their own hands only, written in Obsidian, and read by dory when they point to it.
4. **Search hides what the user asks for.** In a work project, `/dory:search` shows nothing from `private/` (`search.py`), although a search is the user's own request.

**If nothing changes,** `general/knowledge.md` becomes one long file that every work session carries, notes stay one-line bullets, and private knowledge keeps coming from transcripts.

**Goal.** Notes become files with a meaningful title, in projects and without a project; everything without a project lives in `notes/`, one file per topic next to the lists, and the session start lists only their titles; `private/` belongs to the user; search covers the whole vault.

## Options Considered

All decisions were made by the user on 2026-10-21, in the session that started this record.

### Decision 1: The user's notes in a project

#### Option A: `notes.md` (0.4.0)
- **Approach:** One dated line per note in `projects/<project>/notes.md`.
- **Pros:** Exists; one file to load.
- **Cons:** No title, no room for content (problem 2).

#### Option B: One file per note
- **Approach:** Each note is a file with a meaningful title and its content.
- **Pros:** A note reads as a document; Obsidian lists the notes by title.
- **Cons:** More files to load and to protect.

#### Decision

Option B. The worker reads these files and never changes them: notes are not organized automatically, so Record 003 decision 3 stays for projects. A variant in which the worker may delete a note that a session refutes was considered and dropped with it. Accepted consequence: an outdated note keeps loading next to the entry that corrects it, until the user deletes it.

### Decision 2: Who writes a note's content

#### Option A: The user's text as written
- **Approach:** Claude picks the title; the content is exactly what the user wrote after `/dory:note`.
- **Pros:** The user's words stay as they are.
- **Cons:** A note is as short as the command line it was typed into.

#### Option B: Claude writes title and content
- **Approach:** The user says what to record ("/dory:note how we solved the Loki port"); Claude writes title and content from that request and the session, in the note language.
- **Pros:** A note can carry what the session worked out, not only one sentence.
- **Cons:** The content is Claude's wording.

#### Decision

Option B. The note is written inside the user's session, where the user sees it at once and can correct it.

### Decision 3: Knowledge without a project

#### Option A: One file pair in `general/` (0.4.0)
- **Approach:** `general/knowledge.md` by the worker, `general/notes.md` by `/dory:note`.
- **Pros:** Exists; one fixed path.
- **Cons:** Problem 1.

#### Option B: One file per topic, maintained by the worker
- **Approach:** `general/<topic>.md` with several entries; the worker maintains every file in `general/`, including the ones `/dory:note` created.
- **Pros:** Readable by subject; the session start can list topics instead of loading them.
- **Cons:** The worker has to find the matching file; two files on one topic are possible.

#### Option C: Only the user's notes
- **Approach:** `general/` holds notes the user writes; the worker writes nothing there.
- **Pros:** No model writes outside a project.
- **Cons:** A pitfall found in one project (Notion deletes embedded databases when a page is overwritten) stays in that project's file and never reaches another.

#### Decision

Option B. A file holds one topic with several entries (`Notion`), not one statement: a title that states something has to change when the statement does, and renaming with link rewriting is the machinery 0.4.0 removed (`vaultops.py`, Record 003). Unlike a project, `general/` makes no difference between the user's notes and the worker's knowledge.

### Decision 4: `/dory:note` in `general/`

#### Option A: A new file per note
- **Approach:** Every note with scope `general` creates a file.
- **Pros:** Simple for the note skill.
- **Cons:** With the worker maintaining every file, a topic splits into two files (`Brave Search` from the worker, `Brave API key in the keychain` from the user), and merging them needs a deletion the worker cannot make.

#### Option B: The worker's rule
- **Approach:** Extend the matching topic file; create one only for a new topic.
- **Pros:** One file per topic, whoever writes.
- **Cons:** The note skill has to find the matching file.

#### Decision

Option B.

### Decision 5: What the session start loads from `general/`

#### Option A: Every topic file in full
- **Approach:** As `general/knowledge.md` today; the summary over the limit.
- **Pros:** A pitfall reaches the session without being asked for.
- **Cons:** Every work session carries every topic.

#### Option B: The titles only
- **Approach:** The session start lists the titles with their paths; Claude reads a file when the session touches its subject.
- **Pros:** Small, and Claude knows which topics exist.
- **Cons:** A pitfall reaches a session only if Claude judges its title relevant.

#### Decision

Option B. For `general/` this replaces the decision of 2026-10-15 that the session start brings what one would not know to ask for; it still holds for the project's files.

### Decision 6: What the session start loads from the project's note files

#### Option A: In full
- **Approach:** As `notes.md` today; the summary over the limit.
- **Pros:** A rule the user noted for the project ("always pnpm here") holds from the first answer.
- **Cons:** More context per project session.

#### Option B: The titles only
- **Approach:** As in `general/`.
- **Pros:** Less context.
- **Cons:** A rule holds only once Claude reads its file; no fully loaded file of the user's could bring a private note along (decision 7).

#### Decision

Option A.

### Decision 7: `private/`

#### Option A: Written by dory (0.4.0)
- **Approach:** The worker keeps `private/knowledge.md`, `/dory:note` writes `private/notes.md`; both load in private contexts.
- **Pros:** Private insights from sessions are kept.
- **Cons:** Problem 3.

#### Option B: Written by the user only
- **Approach:** dory creates the folder and never writes into it; the user writes private notes in Obsidian.
- **Pros:** Private content is only what the user put there.
- **Cons:** Private insights from sessions are no longer kept.

#### Decision

Option B. For loading, three ways were considered: titles only, everything in private contexts, or only what is linked. Chosen: a private note loads at session start only when a loaded file links it, one level deep, in a work project too. Only links in files the user writes count, which in practice are the project's note files; the worker never links into `private/`. A private insight from a session is mentioned only in the session note's `## Log`. `/dory:note` loses the scope `private`; lists and registers under `notes/` stay as they are.

### Decision 8: Search

#### Option A: The domain boundary (0.4.0)
- **Approach:** In a work project nothing private is shown.
- **Pros:** Same boundary as the session start.
- **Cons:** Problem 4.

#### Option B: The whole vault
- **Approach:** `/dory:search` searches every scope in every session.
- **Pros:** Finds what the user asks for.
- **Cons:** Private hits can appear in a work session, at the user's request.

#### Decision

Option B. Claude can also run `/dory:search` on its own when the user asks about earlier knowledge; private hits then appear too. The boundary of the session start filters what is injected, it was never access control: Claude can read `private/` in any session.

### Decision 9: Existing vaults

No migration. In the author's vault no `notes.md` exists, and `general/knowledge.md` and `private/knowledge.md` are empty. Record 003 decision 5 holds: dory is at 0.x and may change incompatibly.

### Decision 10: One folder for everything without a project

Raised by the user after decisions 1 to 9, which were made with the folder named `general/`.

#### Option A: Two folders
- **Approach:** `general/` for topic files, `notes/` for lists and registers (0.4.0).
- **Pros:** Lists stay apart from knowledge.
- **Cons:** Two folders for the same kind of file: a file with a title that belongs to no project.

#### Option B: `notes/` for both
- **Approach:** Topic files, lists and registers live in `notes/`; `general/` goes away.
- **Pros:** One place; the name matches `projects/<project>/notes/` (the notes of a project there, the notes without a project here); lists stay where they are.
- **Cons:** Lists appear by title in work sessions too; the post-run diff has to tell topics from lists.

#### Option C: `general/` for both
- **Approach:** Lists and registers move to `general/`.
- **Pros:** The name of decisions 3 to 7 stays.
- **Cons:** "General" fits a shopping list badly; every list moves.

#### Decision

Option B. Decisions 3 to 7 keep the name `general/` they were made with; the folder is `notes/`. The scope of `/dory:note` stays `general` ("remember in general"), it writes into `notes/`.

### Decision 11: A changed project note after a run

Raised by the design review on 2026-10-21. In 0.4.0 the post-run checks restore a changed `notes.md` from the baseline; they cannot tell the run's writes from the user's, so an edit the user makes during a run (20 to 60 seconds) is undone. With notes as documents the user edits, renames and deletes in Obsidian, that hits the user's own work: a note saved during a run is reverted, and a note renamed during a run comes back under its old name next to the new one.

#### Option A: Restore every project's notes (0.4.0)
- **Approach:** A changed or deleted note in any project is restored from the baseline.
- **Pros:** A second net if the worker writes into a note despite the deny rule.
- **Cons:** Undoes the user's edits during any run; a rename leaves the note twice.

#### Option B: Restore only the notes of the session's project
- **Approach:** As A, limited to the project the run processes.
- **Pros:** Fewer notes at risk.
- **Cons:** The same loss for that project's notes.

#### Option C: Log only
- **Approach:** A created, changed or deleted note is logged as `unexpected`; nothing is restored, the snapshot is the way back.
- **Pros:** The user's edits stay; less code than today.
- **Cons:** A write by the worker despite the deny rule stays until the user notices it in `dory status`.

#### Decision

Option C, decided by the user on 2026-10-21. The deny rule held in three of three live probes for 0.4.0 (`docs/implementation-log.md`).

**Superseded:** Record 003 decision 4 (one file per domain), the `notes.md` files of its solution, and its restore of the user's notes after a run.

## Solution

A project keeps its `knowledge.md` and gets a folder of the user's notes, one file each; `notes/` holds every file without a project, topics the worker maintains as well as lists and registers, and the session start lists them by title; `private/` holds what the user writes there, and a note in it loads when one of the user's project notes links it. The worker, the post-run checks and the summaries of Record 003 stay; what they cover changes.

### The vault

| Path | Written by | Maintained by | Session start |
|---|---|---|---|
| `projects/<project>/knowledge.md` | worker | worker | in full |
| `projects/<project>/notes/<title>.md` | `/dory:note` | the user | in full |
| `notes/<title>.md`, `type: topic` | worker, `/dory:note` | worker | title and path |
| `notes/<title>.md`, `type: list` or `register` | worker, `/dory:note` | as today | title and path |
| `private/**/<title>.md` | the user, in Obsidian | the user | in full when a loaded project note links it |
| `sessions/<YYYY>/<MM>/<...>.md` | worker | worker | no |

- **What counts.** In `notes/` and in `projects/<project>/notes/` only the `.md` files at the top level of the folder; subfolders and other files are left alone everywhere (session start, `task.md`, post-run checks, search). A file in `notes/` without `type`, or with a type other than `list` or `register`, counts as a topic: the user may create one in Obsidian.
- **The file name is the title**, in the note language: a phrase that names the subject (`Notion`, `Expenses and employment contract`, `Shopping list`), not a statement. One function in dory's code turns a title into a name: Unicode NFC; each character that breaks Obsidian links or paths (`[ ] # ^ | \ / :`) replaced by a space, runs of whitespace by one; leading dots and trailing dots and spaces removed; cut at 80 characters and at 200 bytes of UTF-8. A title that is empty after this is an error.
- **Names compare without case.** APFS ignores case by default, and Obsidian matches link targets without case, so every comparison of names (an existing title, the matching topic, a list's title, a link target) uses the NFC form, casefolded. dory's code creates a new file exclusively (open mode `x`), so it never overwrites an existing one, a case variant included.
- **Links.** Names are unique within a folder, not across the vault, so every link into `projects/`, `notes/` and `private/` uses the path form, with an alias where it reads better: `[[notes/Notion|Notion]]`, `[[projects/dory/knowledge|dory]]`. Session notes keep their vault-wide unique names.
- **`domain`** no longer matters in `notes/`: neither the session start nor search filters by it. Files dory creates there carry none; an existing `domain` key is left alone.

### Project note files

```markdown
---
type: note
created: 2026-10-21
---
<content Claude wrote from the user's request and the session>
```

- Free Markdown in the note language, no fixed sections. No `domain`: the project's `knowledge.md` decides it, as before.
- The user edits, renames and deletes them in Obsidian. The worker reads them in full and never changes them (decision 1); nothing a note says becomes an entry. When a session shows a note to be wrong, the worker writes the corrected entry into `knowledge.md` and links the note in path form under `## Open` in the session note.

### Topic files in `notes/`

```markdown
---
type: topic
updated: 2026-10-21
---
## Pitfalls
- **Overwriting a Notion page deletes the databases embedded in it.** The API replaces the page's blocks, inline databases included. Append blocks instead of replacing the page.
```

- The entry format and the sections of `knowledge.md` (Record 003): bold lead plus at most three sentences, sections `## Pitfalls`, `## Decisions`, `## Facts`, `## How-to`, `## Preferences`. The post-run diff and search parse them with the same parser.
- `type` belongs to dory's code; the worker sets `updated` when it changes an entry. A topic file has no `summary`: its title says what it is about.
- **Lists and registers** keep their format and rules: items added and removed as asked, registers one dated line per item. `type: list` or `type: register` tells them apart from topics. A new list is named by its title like any file; the list example in the rules loses its `domain`.

### `private/`

- The worker creates the empty folder before its run when it is missing and writes nothing else under it; no other part of dory writes there. The user writes any Markdown there, with any frontmatter and in subfolders.
- **Links that load a private note.** dory reads the links in a loaded project note file, outside fenced and inline code, in these forms: `[[target]]`, `![[target]]`, each with an optional `|alias` and `#heading`, and with or without `.md`; and Markdown links `[text](target)` whose target is percent-decoded. A target with a path is taken from the vault root (`private/Employment contract`); a bare name (`Employment contract`) matches a file of that name under `private/`, searched recursively and without case, the first by path if several. Each target is resolved to its real path, symlinks included, and loads only if that path lies inside `private/`, so `[[private/../notes/x]]` or a symlink out of the folder loads nothing. One level: links inside a private note are not followed. A note loads once, however many files link it. Links to anything outside `private/` are not followed; Claude can read those files itself.
- **Who writes such a link.** The worker never writes a link into `private/` and cannot read the folder (below); `/dory:note` writes one only when the user's request asks for it. Only project note files are searched for links, so private content reaches a session through a link the user wanted.

### `/dory:note`

- **`dory prepare-note`** prints the vault, the snapshot, the date, the note language, the project with its domain, the two scopes with their folders (`project` → `projects/<project>/notes/`, `general` → `notes/`), the titles of the project's notes and of the files in `notes/` with their type, and the rules.
- **The skill** handles a list or register item as today, in `notes/`. Anything else is a note: scope `project` in a repository, `general` when the user says it applies in general or the text clearly has nothing to do with the project, and outside a repository. The scope `private` is gone; a private item that is no list is answered with the hint to write it into `private/` in Obsidian. A note contains a link into `private/` only when the user's request asks for one.
  - `project`: Claude writes a title and the content from the user's request and the session, and writes the file through `dory add-note`.
  - `general`: Claude writes entries in the format of the rules. When a topic file on the subject exists, the skill changes it with Edit after the snapshot, as it does for lists: it extends or corrects the entry on the same subject in place and adds a new entry only for a new subject, as the rules say. For a new topic it writes the file through `dory add-note`.
- **`dory add-note --scope project|general --title "<title>"`**, the content on stdin, creates a file and nothing else:
  - `project` creates `projects/<project>/notes/<name>.md` with `type: note` and `created`; it writes the new note into the baselines of queued entries as well, so a running worker's checks do not report it, marks the project's context for a new summary and starts the worker.
  - `general` creates `notes/<name>.md` as a topic file with the given entries. A general note needs no summary mark: the session start lists titles only.
  - An existing name in the folder, in any case, is an error that names the file (for `general` the skill then edits that file); so are `project` outside a repository, an empty title or content, and a title that is empty after cleaning. Nothing is written then.

### The worker run

- **Task.** `task.md` names the session note; the files the run may change: the project's `knowledge.md`, every file in `notes/`, and new topic files in `notes/`; the project's note files to read; the titles and types of the files in `notes/`. It names no file in `private/`. A private project's session may update lists and registers but writes no topic file, since every session lists their titles; its task offers none.
- **Ingest skill and rules.** Read the project's `knowledge.md` and note files in full. An insight that applies beyond the project: Grep the topic files in `notes/` for its key terms, choose the matching topic by title and content, extend or correct an entry there with Edit, or create `notes/<title>.md` as a topic file for a new topic, its name following the naming rules (listed in the rules). Update lists and registers if the session touched them, as today. Private content (family, health, money, the user's own devices and home network) becomes no entry anywhere; the session note mentions it under `## Log`. Never a link into `private/`.
- **The command's `--settings`** deny `Read(private/**)`, `Edit(private/**)`, `Write(private/**)`, `Edit(projects/*/notes/**)` and `Write(projects/*/notes/**)`; patterns without a leading slash are relative to the run's working directory, the vault. Read rules also cover Grep and Glob. A live probe built first (S2) shows whether restricted mode honours each of them, for a path in different case too. If one does not hold, S2 stops there and the record goes back to the user: without a working read barrier the worker can carry private content into `notes/`.
- **Baseline.** A copy of the project's `knowledge.md` and of every file in `notes/`; a hash of every project note file of every project, of every `.md` under `private/` (no attachments) and of every other `.md` under `projects/`. A kept baseline whose captured files name `general/` or `private/` comes from 0.4.0: it is discarded, not checked, so no restore ever writes into `private/`.
- **Post-run checks** (Record 003, decision 2), changed where marked:
  1. **Frontmatter.** `type`, `domain` and `paths` of the project's `knowledge.md` as today. The `type` of a file in `notes/` is restored when the run changed it; a file the run created in `notes/` without `type` gets `type: topic`; both are logged as `restored`.
  2. **Project note files** (decision 11). A created, changed or deleted note is logged as `unexpected`; nothing is restored. `dory add-note` puts its own new notes into the baselines, so they are not reported.
  3. **Unexpected files.** A created, changed or deleted `.md` under `private/`, any other `.md` under `projects/` outside `knowledge.md` and `notes/`, and a file the run created in `notes/` whose name breaks the naming rules are logged. A private project's run that creates or changes a topic file is logged as well. Nothing is renamed or restored; the snapshot holds the old version.
  4. **Diff** of the project's `knowledge.md` and of every topic file in `notes/`; lists and registers are not compared entry by entry, or every bought item would count as a removed entry. A new topic file reports its entries as `added`, a deleted one its entries as `removed`.
- **Session note.** `## Insights` links topic files in the path form: `- [[notes/Notion|Notion]]: **<lead>** (added)`.

### The session start

| Session in | In full | Listed |
|---|---|---|
| a known project, work or private | the project's note files, the private notes they link, the project's `knowledge.md` | every file in `notes/` |
| a repository dory does not know yet | nothing | every file in `notes/` |
| no repository | nothing | every file in `notes/` |

- **Order:** header, project line, queue lines, the project's note files by name, each linked private note right after the first note that links it, `knowledge.md`, then `## Notes without a project (read a file when the session touches its subject)` with one line `- <title>: notes/<title>.md` per file, `(list)` or `(register)` after the title of those, most recently `updated` first (file time without `updated`). Files load as today: without frontmatter, under `## <path>`, their headings one level down.
- **Limit.** Header, project line and queue lines take their room first, as today, and room for one closing line of the titles is kept. The project's files come next, in full or as their summary (below), followed by their paths when they are cut or summarized. The titles fill what is left; when not all fit, the closing line says how many are left out and that the folder `notes/` holds them.
- **Domain boundary.** A work project loads nothing from `private/` except the notes the user's own project notes link. The titles of lists and registers appear in every session, their content does not (decision 10).

### Summaries

- One context per known project: its note files, the private notes they link and its `knowledge.md`, as `context.text` builds them. Its domain is private when the project is private or a linked private note is part of it; a summary is usable only for the same domain and the same set of linked private notes, so after a link changes the files load cut until the worker has rebuilt it, and a removed private note's content never lingers in a stale summary.
- `_general` and `_outside` go away: outside a known project nothing loads in full; a mark with one of these names is removed without a run. A change in `notes/` no longer makes a project summary stale; a change in a linked private note makes its project's summary stale.
- The summary's system prompt names the project's note files, not `notes.md`, as the user's notes.
- `dory add-note --scope project` marks the project's context, as today.

### Search

- Candidates: every entry of each `knowledge.md` and each topic file (the post-run parser); each project note file, each `.md` under `private/` and each list or register as one candidate (title from the file name or `summary`, text from the body); session notes as today.
- No domain filter: every session searches the whole vault (decision 8).

### What goes away

`general/` with its `knowledge.md` and `notes.md`; `notes.md` in projects and in `private/`; `private/knowledge.md`; the knowledge skeletons outside projects; the restore of the user's notes after a run; the scope `private` of `dory add-note` and `prepare-note`; the summary contexts `_general` and `_outside`; the domain filter of search and of the list paths at session start.

### Vaults written by 0.4.0

- `general/` is no longer read, searched or written; the CHANGELOG tells the user to move its entries into topic files under `notes/`.
- A `projects/<project>/notes.md` is no longer loaded, searched or protected; the CHANGELOG tells the user to move its lines into note files.
- `private/knowledge.md` and `private/notes.md` are the user's private notes from then on, loaded when linked.
- Lists and registers under `notes/` stay as they are.
- In the author's vault, `general/` and the empty `private/knowledge.md` are deleted at the release.

### Risks

- **Two files on one topic.** The worker and `/dory:note` pick a topic by its title (`NAS`, `Synology`, `Home network`). Nothing merges files; the user merges them by hand in Obsidian. A live check shows that an insight on an existing topic extends that file.
- **A pitfall behind a title** reaches a session only when Claude judges the title relevant (decision 5).
- **A linked private note** loads in every session of the project that links it, in a work project too, and counts against the limit; it can push the project into its summary.
- **A write into a note despite the deny rule** stays until the user sees it in `dory status` (decision 11).
- **Noise in `dory status`.** The checks cannot tell the run's changes from the user's: the user's own edits in `private/` and in project notes during a run show as `unexpected`, and a general note `/dory:note` edits during a run shows as the run's `added` or `changed`.
- **The task grows with `notes/`:** it lists every title there.
- **Sessions started before the update** keep running the 0.4.0 worker until `/reload-plugins`, and it writes `general/`, `private/knowledge.md` and `notes.md`.

### Not part of this record

The narrower Bash grant for `/dory:save` and `/dory:note` (`dory add-note` keeps it possible), the configurable records folder and pruning `work/` stay in the Future table.

## User Stories

Order by risk and dependency: S1 builds the file names and the post-run checks for the new layout; they are deterministic, and S2's live checks read their results in `runs.log`. S2 changes what the worker writes and carries the highest risk; its first criterion, the probe of the deny rules, decides whether the design holds. S3 loads the new files, S4 narrows the summaries to S3's project context, S5 writes note files with S1's name function. S6 and S7 close. Between S2 and S5 the branch is not releasable: S2 rewrites the rules that `/dory:note` shares, so `tests/test_live_note.py` is skipped until S5. The installed 0.4.0 is not affected.

**Live checks** run against real `claude -p` with Haiku in throwaway vaults, as in Record 003: each new check passes in three of three runs before its story counts as done, and every negative check has a positive control in the same transcript where one is possible.

### Story S1: File names and post-run checks for the new layout

**As a** user whose notes and private files sit next to files a model edits
**I want** every worker run checked against the new layout
**So that** a touched note or private file shows up in `dory status` and every removed topic entry is reported

**Acceptance Criteria (unit tests, with a fake runner where a run is needed):**
- [ ] Given a title with `[ ] # ^ | \ / :`, a leading dot, trailing dots or spaces, a decomposed umlaut, more than 80 characters or more than 200 bytes, when it becomes a file name, then the characters are gone, the name is NFC and cut at both limits; given a title that is empty after this, then it is refused; given `Notion` and `notion`, then they compare equal.
- [ ] Given three project note files, when a run changes one, deletes one and creates a fourth, then each is logged as `unexpected` and none is restored.
- [ ] Given a `.md` under `private/` and one in a subfolder of it, when a run creates, changes or deletes them, then each is logged as `unexpected` and nothing under `private/` is written by dory; given a vault without `private/`, when a run is prepared, then the folder exists and is empty, and no file under `general/` or `private/` was created.
- [ ] Given a kept, unchecked baseline from 0.4.0 that lists `private/knowledge.md`, when the next attempt runs, then that baseline is discarded and nothing is restored into `private/`.
- [ ] Given topic files in `notes/` and a file there without `type`, when a run adds, changes and removes entries and creates a new topic file, then the diff reports them per file, the file without `type` included, and the new file's entries as `added`; given a list from which a run removes two items, then no entry change is reported for it; given a subfolder or a non-`.md` file in `notes/`, then it is ignored.
- [ ] Given a run that changed the `type` of a list, when the checks run, then it is restored and logged; given a file the run created in `notes/` without `type`, then it gets `type: topic`; given one whose name breaks the naming rules, then it is logged as `unexpected` and keeps its name; the frontmatter checks of the project's `knowledge.md` hold as in Record 003.
- [ ] Given a run of a private project, when it creates or changes a topic file in `notes/`, then the change is logged as `unexpected`.

**Priority:** High
**Status:** Done (2026-10-21), not committed

### Story S2: The worker keeps topic files in `notes/`

**As a** user who works in several projects
**I want** the worker to write what applies beyond a project into one file per topic in `notes/`, and to leave my notes and my private folder alone
**So that** a pitfall found in one project is there for every other, filed under its subject

**Acceptance Criteria:**
- [ ] Given a restricted worker run whose `--settings` deny `Read`, `Edit` and `Write` on `private/**` and `Edit` and `Write` on `projects/*/notes/**`, when the model tries to Read, Grep and Glob in `private/` and to change a project note, also through a path in different case, then it gets no content and the files are unchanged (live probe, built first); if any rule does not hold, the story stops and the record goes back to the user.
- [ ] Given a project session that yields a fact about a tool unrelated to the project, a fact about the project's own stack and a fact about the user's home NAS, when the worker runs, then the first is an entry in a topic file in `notes/` whose title names the tool, the second is in the project's `knowledge.md`, and the third is in no file but the session note's `## Log` (live check).
- [ ] Given a topic file `Notion` with one entry and a transcript with another Notion insight, when the worker runs, then the insight is an entry in `notes/Notion.md` and no new topic file exists (live check).
- [ ] Given a private note that names a tool and a transcript with an insight about the same tool, when the worker runs, then the insight is an entry in a topic file and nothing of the private note's content appears in `notes/` (live check).
- [ ] Given a project note file that the transcript repeats and a second, new insight, when the worker runs, then the note is byte-identical, no entry repeats it, and the second insight is an entry (live check).
- [ ] Given a project note that the transcript shows to be wrong, when the worker runs, then `knowledge.md` holds the corrected statement, the note is unchanged, and the session note links it under `## Open` (live check).
- [ ] Given a session in a private project with an insight about a tool, when the worker runs, then no topic file is written and the session note exists (live check; the session's own project insight is the positive control).
- [ ] Given a shopping list in `notes/` and a session in which milk was bought, when the worker runs, then the list is updated as before (live check, ported).
- [ ] Given a run, when `task.md` is written, then it names the project's `knowledge.md`, its note files to read, the titles and types of the files in `notes/`, and nothing under `private/`; given a private project, then it offers no new topic file (unit test).

**Priority:** High
**Status:** Done (2026-10-21), not committed

### Story S3: The session start loads note files and lists `notes/`

**As a** user starting a session
**I want** my project notes and the project's knowledge in full, the private notes I linked, and the titles of everything in `notes/`
**So that** Claude follows my notes from the first answer and knows which topics and lists exist without carrying them all

**Acceptance Criteria (unit tests):**
- [ ] Given a work project with two note files, `knowledge.md`, two topic files, a file without `type` and a list in `notes/` and an unlinked private note, all under the limit, when a session starts, then the text holds the project line, the note files by name in full, `knowledge.md`, and a section listing the four files of `notes/` with `(list)` after the list's title, most recently `updated` first, and nothing from `private/`.
- [ ] Given note files that link the same private note as `[[private/Employment contract]]`, `![[employment contract.md|contract]]` and `[contract](private/Employment%20contract.md)`, and that private note linking a second one, when a session starts, then the first private note loads once, right after the first note that links it, and the second does not.
- [ ] Given a link inside a code block, `[[private/../notes/x]]`, a symlink under `private/` that points outside it, and a link to `notes/Notion`, when a session starts, then none of these targets loads.
- [ ] Given a session outside a repository, or in a repository dory does not know yet, when it starts, then only the titles of `notes/` appear besides header and queue lines.
- [ ] Given titles that do not all fit after the project's files, when a session starts, then the list stops with a line that names how many are left out and the folder `notes/`; given project files cut at the limit without a summary, then their paths come before the titles and the closing line still appears.
- [ ] Given files from 0.4.0 (`general/`, a project's `notes.md`, an unlinked `private/knowledge.md`), when a session starts, then none of their text or paths appear.

**Priority:** High
**Status:** Done (2026-10-21), not committed

### Story S4: Summaries per project only

**As a** user with a lot in one project
**I want** the summary to cover exactly what the session start loads in full for the project
**So that** it stays within the limit, a change outside the project does not make it stale, and no private content outlives its link

**Acceptance Criteria (unit tests):**
- [ ] Given a project whose note files, linked private notes and `knowledge.md` exceed the summary's target, when the session start and the worker build the context's text, then both texts are identical and contain exactly these files.
- [ ] Given a work project whose note links a private note, or a private project without links, when its summary is made, then its domain is private.
- [ ] Given a summary made while a note linked one private note, when the link is replaced by another, then the session start loads the files cut instead of the old summary, marks the context and starts the worker.
- [ ] Given a change in `notes/`, when a session starts in a project with a summary, then the summary is still fresh.
- [ ] Given marks `_general` or `_outside` left by 0.4.0, when the worker's summary pass runs, then no summary run happens and the marks are gone.
- [ ] Given the summary's system prompt, when it is built, then it names the project's note files as the user's notes and no longer `notes.md`.

**Priority:** Medium
**Status:** Done (2026-10-21), not committed

### Story S5: `/dory:note` writes note files

**As a** user who wants something remembered right now
**I want** `/dory:note` to write a note with a meaningful title, in the project or in the matching topic in `notes/`
**So that** I find it by its title in Obsidian and later sessions load it

**Acceptance Criteria:**
- [ ] Given `dory add-note --scope project --title "<title>"` with content in a project, when it runs, then `projects/<project>/notes/<name>.md` exists with `type: note` and `created`, the context is marked, the worker starts and the path is printed; given the title of an existing note in another case, `project` outside a repository, an empty title or content, or the scope `private`, then it fails with a message and writes nothing (unit tests).
- [ ] Given a worker run in progress, when `dory add-note --scope project` creates a note file, then the run's checks do not report it (unit test).
- [ ] Given `dory add-note --scope general --title "<title>"` with entries, when no file of that name exists, then `notes/<name>.md` is created as a topic file with the entries; given `notion` while `Notion.md` exists, or the title of a list, then it fails, names the existing file and writes nothing (unit tests).
- [ ] Given `dory prepare-note` in a project, when it runs, then it names both scopes with their folders and the titles of the project's notes and of `notes/` with their types (unit test).
- [ ] Given a session that solved the Loki port clash, when the user runs `/dory:note "how we solved the Loki port"`, then a new file in the project's `notes/` has a title that names the subject and content that describes the solution, in the note language, and `knowledge.md` is unchanged (live check).
- [ ] Given a topic file `Python` with an entry on package managers, when the user runs `/dory:note "remember in general: Python packages with uv instead of pip"` in a project, then that entry now says uv, `notes/Python.md` has no second entry on package managers, and no new file exists (live check).
- [ ] Given a session that read a private note, when the user runs `/dory:note` on the session's result without asking for a link, then the note is written and contains no link into `private/` (live check; the written note is the positive control).
- [ ] Given a note about the user's health, when the user runs `/dory:note`, then nothing is written and the reply points to `private/` in Obsidian; given "add milk to the shopping list", then the list in `notes/` gains the item as before (live check).

**Priority:** Medium
**Status:** Done (2026-10-21), not committed

### Story S6: Search covers the whole vault

**As a** user looking for something I or dory wrote down
**I want** `/dory:search` to search every folder in every session
**So that** I find a private note from a work project without changing directory

**Acceptance Criteria (unit tests):**
- [ ] Given a session in a work project and a private note in a subfolder of `private/` that mentions the tax return, when the user searches "tax", then the private note is a hit with its path.
- [ ] Given a topic file with two entries, when the user searches a word of one, then that entry is a hit and the other is not; given a file in `notes/` without `type`, then its entries are searched like a topic's.
- [ ] Given a project note file and a list that match, when the user searches, then each is one hit with its title.
- [ ] Given `general/`, a project's `notes.md` from 0.4.0, a subfolder of `notes/` and a non-`.md` file that match, when the user searches, then none of them is shown.

**Priority:** Medium
**Status:** Done (2026-10-21), not committed

### Story S7: Release 0.5.0 prepared

**As a** user of the public plugin
**I want** these changes as version 0.5.0 with a changelog entry
**So that** `claude plugin update dory@brain` brings them and I know what happens to the files 0.4.0 wrote

**Acceptance Criteria:**
- [ ] Given the three version files, when the version test runs, then all of them say 0.5.0 and the test is green.
- [ ] Given the CHANGELOG, when a user reads the 0.5.0 entry, then it names note files per project, `notes/` for topics, lists and registers, titles only at session start, `private/` as the user's folder loaded through links and closed to the worker, that changed notes are logged and no longer restored, search over the whole vault, what happens to `general/`, a project's `notes.md` and the files in `private/`, and that sessions started before the update need `/reload-plugins`.
- [ ] Given the README and the project CLAUDE.md, when they describe the vault, the session start and the commands, then they no longer mention `general/` or `notes.md` (review).
- [ ] Given the release commit on the feature branch, when the branch is inspected, then nothing is tagged or pushed; merging, tagging, pushing and installing stay with the author.

**Priority:** Medium
**Status:** Done (2026-10-21), not committed
