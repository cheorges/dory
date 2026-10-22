# Record 006: The Library

## Status

Done (2026-10-22): released as part of 0.6.0, before its release was merged.

---

## Problem

Record 004 made `private/` the user's folder: dory creates it, never writes into it, and a note in it loads at session start only when one of the user's project notes links it. In use two things are missing.

1. **Knowledge the user wants to keep deliberately has no way in.** `/dory:note` is for what the next session must know: catchups, and points the user does not want to leave to the worker. Knowledge the user wants to file with care (where it belongs, how detailed, what it relates to) has to be written by hand in Obsidian, and linked by hand from a project note so that it loads.
2. **"Private" says the wrong thing.** The folder is meant for knowledge the user curates. Confidential content (family, health, money) is one kind of it, not the definition.

Two smaller gaps sit next to it:

- `/dory:note` is told not to write into `private/`, but nothing enforces it: the skill allows Write and Edit on any path.
- `/dory:note` still names the scope for topic files `general` and reacts to "remember in general: ...", although Record 004 removed `general/`.

**If nothing changes,** curated knowledge stays manual work in Obsidian, or ends up as notes in `notes/` and `projects/<p>/notes/` that the user did not want there, and a model could still write into the user's folder through `/dory:note`.

## Options Considered

All decisions were made by the user on 2026-10-22, after the challenge in the same session.

### Decision 1: The folder

- **Option A:** keep `private/`, add a skill that may write into it.
- **Option B:** rename it to `library/`: the user's curated knowledge, confidential content included.

**Decision:** B. The name says what the folder holds. `domain: private` on a project's `knowledge.md` is a different thing and stays.

### Decision 2: Who writes into the library

- **Option A:** `/dory:note` gets a target `library`.
- **Option B:** a separate skill, `/dory:library`, that works in a dialog; `/dory:note` never writes there.

**Decision:** B. `/dory:note` stays quick and writes without asking, into `projects/<p>/notes/` or `notes/`. `/dory:library` asks before it writes: the folder (an existing one or a new one), the title, how detailed, and which project notes and topic files to link it from. The name `remember` was dropped because "remember ..." already reads like a note.

### Decision 3: How a library entry reaches a session

- **Option A:** a property in the library entry names its projects (`projects: [dory]`); the session start scans the library.
- **Option B:** the linking file says so: a project note or a topic file in `notes/` links the entry, and the session start follows that link.

**Decision:** B. Project notes and topic files are already what the session start loads; a link from them is the one rule for "this belongs here". `/dory:library` proposes the files that fit ("this could belong to Python and to dory's deploy note, link it?") and, on yes, adds the link.

### Decision 4: Where the link sits in the linking file

- **Option A:** in the text of the file.
- **Option B:** in a frontmatter property `library`, a list of wikilinks.

**Decision:** B. The worker rewrites the entries of topic files and could drop a link in the text, and the entry would stop loading without anyone noticing. The post-run checks already restore the frontmatter keys that place a file (`baseline.py`); `library` joins them. Obsidian shows the property as links, and the entry's backlinks show who links it.

```yaml
library:
  - "[[library/Python/Package management|Package management]]"
```

### Decision 5: Links in the text

The user wants matching words linked the way Obsidian does it (a word that names an existing note becomes a link).

- **Option A:** in the new library entry only: its words that name a project, a topic file, a project note or another library entry become wikilinks.
- **Option B:** also in the linking files: `/dory:library` edits the text of project notes and topic files.

**Decision:** A (confirmed by the user on 2026-10-22). A link from the library entry outward costs nothing: dory does not follow it (one level, as in Record 004), and Obsidian shows it as a backlink in the target. Editing the text of the user's project notes is a larger step than adding a property, and in topic files the worker can rewrite the text. The property of Decision 4 is what makes an entry load; a link in the text never has to.

### Decision 6: Which links load

- **Project notes:** the `library` property and links in the text, as today for `private/`. The project notes are the user's files.
- **Topic files in `notes/`:** the `library` property only. The worker writes their text; a link it put there would carry library content into every session.

A topic file loads in every session, in every project, while it fits. A library entry linked from it loads everywhere too. `/dory:library` says so when it proposes the link: "linked from `notes/Python.md`: loads in every session" against "linked from `projects/dory/notes/Deploy.md`: loads in dory only".

### Decision 7: What the worker sees

- **Option A:** nothing in the library, as today with `private/`.
- **Option B:** the library entries the session start loads for the session's project, copied into the bundle.

**Decision:** B. The worker then knows what the user already filed and does not write it again into `knowledge.md` or a topic file. It sees nothing the session did not have. The `--settings` keep denying Read, Edit and Write on `library/**`; the copies lie in `work/<id>/library/`, as the repository's records lie in `work/<id>/repo/`.

### Decision 8: The guard of `/dory:note`

A live probe on 2026-10-22 (Claude Code 2.1.308, Haiku, a throwaway plugin and vault) showed:

| Case | Result |
|---|---|
| A `PreToolUse` hook in the skill's frontmatter, Write to `vault/private/x.md` | blocked, no file, listed in `permission_denials` |
| Same skill, Write to `vault/notes/y.md` | written |
| Same session, a later request without the skill, Write into `private/` | **blocked**: the hook stays active until the session ends |
| A new process (`--continue`) | the hook is gone |

The guard must compare paths relative to the vault: on macOS `/tmp` is `/private/tmp`, and a text match on `/private/` blocked everything in the probe.

**Decision:** `/dory:note` gets a skill-scoped `PreToolUse` hook on `Write|Edit` that runs `dory guard` and blocks every path under `<vault>/library/`. Since it stays active for the rest of the session, `/dory:library` writes only through dory commands (Bash), never with Write or Edit, so the guard never meets it. Bash stays open in `/dory:note` (it needs `dory prepare-note` and `dory add-note`); the skill's text forbids the library, the guard does not cover it.

### Decision 9: Renaming and migration

dory is at 0.x and may change incompatibly (Record 003 decision 5). dory does not move `private/`: links written as `[[private/...]]` would break, and Obsidian rewrites them only when the folder is renamed inside Obsidian. When `private/` exists and holds files, the session start prints one line asking the user to rename it to `library` in Obsidian. In the author's vault `private/` is empty.

## Solution

```
/dory:library "Python packages with uv instead of pip, because ..."
  1  dory library-context     the library's folders and titles, project notes,
                              topic files, the note language, the rules
  2  dialog                   folder, title, detail, links to propose
  3  dory library-write       library/<folder>/<title>.md from stdin
  4  dory link                adds the entry to `library:` of each chosen file
        │
        ▼
session start in dory  ──►  projects/dory/notes/*.md + notes/*.md
                            └─► their `library:` entries, one level
```

- **Folder.** `library/` replaces `private/` in `scopes.py`, `links.py`, `baseline.py`, `search.py`, the worker's `--settings`, the rules, the skills, the README. The baseline hashes every `.md` under `library/`; a change by a worker run is logged, nothing is restored.
- **`dory library-context`.** Prints what the dialog needs: the vault, the note language, the tree of `library/` (folders and titles), the current project with the titles of its notes, the topic files in `notes/` with their types, and the rules for library entries.
- **`dory library-write --folder <f> --title <t>`.** Takes the content on stdin. Creates `library/<f>/<t>.md` with frontmatter (`type: library`, `created`, `updated`), or replaces the content of an existing entry and sets `updated`. Takes a snapshot first. Refuses a path outside `library/`, a title that breaks the naming rules, and a folder deeper than two levels.
- **`dory link --entry <library path> <file>...`.** Adds the entry, in path form with an alias, to the `library` property of each file, if it is not there yet. Accepts only project notes and topic files in `notes/`, never `knowledge.md`, a list, a register, or a file in `library/`. Takes a snapshot first.
- **`/dory:library` skill.** `allowed-tools: Read, Glob, Grep, Bash(grep:*), Bash(rg:*), Bash(ls:*)` and the three dory commands. Claude Code 2.1.308 offers no Grep or Glob tool in a normal session (they exist only when `--tools` names them, as the worker does), so the skill searches with `grep`, `rg` and `ls`; `find` is left out because `-delete` and `-exec` write. Steps: run `library-context`; read the library entries and topic files that look related; propose folder, title, the content written out in the note language with its matching words as wikilinks (Decision 5), and the files to link from, each with where it would load; ask; write after the user's yes; reply with the paths.
- **Session start.** `links.py` reads the `library` property besides the text. `recall.py` follows links from project notes (property and text) and from topic files in `notes/` (property only) into `library/`, one level, each entry once, within the budget of Record 005, after the files that link them.
- **Worker.** `ingest.py` copies the entries the session start would load for the project into `work/<id>/library/`; `task.md` names them as read-only reference. The checks restore `library` on topic files like `type`.
- **`/dory:note`.** The guard of Decision 8 (`dory guard`, reading the hook's JSON on stdin, exit 2 with a message that names `/dory:library`). The scope `general` becomes `notes` (`--scope notes`), and "remember in general" leaves the skill and the README.
- **`/dory:search`.** Covers `library/` as it covered `private/`.

### Risks

- **The dialog in a live check.** `claude -p` cannot answer questions. The live checks give the answers in the request ("file under Python, link it from the Python topic") and check what was written.
- **A library entry linked from a topic file loads in every session.** That is intended for knowledge about a tool, and visible in the dialog; for confidential content it is the wrong place, and the skill says so.
- **The guard holds for the rest of the session.** After `/dory:note`, a request to change a library entry with Write or Edit is blocked in that session. The message points to `/dory:library`.
- **Bash in `/dory:note`.** `cat > library/x.md` is not blocked. The Future item "Narrow the Bash grant in save/note" stays open.

## User Stories

### Story S1: `private/` becomes `library/`

**As a** user who curates knowledge in the vault
**I want** the folder to be called `library` everywhere in dory
**So that** its name says what it holds

**Acceptance Criteria (unit tests):**
- [ ] Given a project note that links `[[library/Python/Package management]]`, when a session starts, then the entry loads as `private/` notes did; a link into `private/` loads nothing.
- [ ] Given a worker run that changes a file in `library/`, when the checks run, then the change is logged and not restored.
- [ ] Given `/dory:search` for a word in a library entry, then the entry is a hit.
- [ ] Given a vault with files in `private/`, when a session starts, then one line asks to rename the folder to `library` in Obsidian; given an empty or no `private/`, then no line.
- [ ] The worker's `--settings` deny Read, Edit and Write on `library/**`.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S2: Library links load from project notes and topic files

**As a** user who linked a library entry from a project note or a topic file
**I want** the entry to load at session start
**So that** filed knowledge arrives where it belongs

**Acceptance Criteria (unit tests):**
- [ ] Given a project note with `library: ["[[library/a]]"]`, when a session starts in that project, then `library/a.md` loads after the note; in another project it does not.
- [ ] Given a topic file in `notes/` with the property, when a session starts in any project or outside one, then the entry loads; given a link to it in the topic file's text only, then it does not.
- [ ] Given two files linking the same entry, then it loads once; given a link in a library entry, then it is not followed.
- [ ] Given a worker run that removes `library` from a topic file, when the checks run, then the property is restored and the restore is logged.
- [ ] Given a session in a project whose notes link library entries, when the worker prepares the bundle, then the entries lie in `work/<id>/library/` and `task.md` names them as reference.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S3: `dory library-write` and `dory link`

**As** the `/dory:library` skill
**I want** commands that write the entry and the links
**So that** code, not the model, checks paths, names and the link form

**Acceptance Criteria (unit tests):**
- [ ] Given a folder, a title and content on stdin, when `library-write` runs, then `library/<folder>/<title>.md` exists with `type: library`, `created` and `updated`, and a snapshot was taken; given an existing entry, then its content is replaced and `updated` set, `created` kept.
- [ ] Given a title or folder with `..`, `/`, a quote, `$` or a backtick, or a folder three levels deep, then the command fails with a message and writes nothing.
- [ ] Given `link --entry library/Python/Package management.md notes/Python.md`, then the topic file's `library` list holds `"[[library/Python/Package management|Package management]]"` once, its text unchanged; a second run changes nothing.
- [ ] Given `knowledge.md`, a list, a register or a file in `library/` as target, then `link` fails and writes nothing.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S4: The `/dory:library` skill

**As a** user who wants to file knowledge deliberately
**I want** a skill that proposes where it goes and what it links to, and writes after my yes
**So that** the entry is in the right folder, linked, and loads where it is needed

**Acceptance Criteria (live checks, answers given in the request):**
- [ ] Given a vault with `notes/Python.md` and the request "file: Python packages with uv instead of pip; under Python; link it from the Python topic", then `library/Python/<title>.md` exists, its text links `[[notes/Python|Python]]` or similar, and `notes/Python.md` has the property and an unchanged text.
- [ ] Given a request without answers, then the skill asks and writes nothing in that turn.
- [ ] Given the skill's run, then no Write or Edit tool was used (only dory commands), and nothing outside `library/` and the chosen files changed.
- [ ] The proposal names, for each file to link from, where the entry would load.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S5: `/dory:note` guards the library and drops `general`

**As a** user
**I want** `/dory:note` to be unable to write into `library/` and to use the folder names I see in the vault
**So that** the library holds only what I filed through `/dory:library` or by hand

**Acceptance Criteria:**
- [ ] (unit) `dory guard` with a hook JSON whose `tool_input.file_path` lies under `<vault>/library/` exits 2 with a message naming `/dory:library`; a path in `notes/`, in a project, outside the vault, or under `/private/tmp/...` outside `library/` exits 0.
- [ ] (unit) `add-note --scope notes` creates a topic file; `--scope general` fails with a message naming `notes`.
- [ ] (live) `/dory:note` asked to write into `library/` leaves the library unchanged, and the denial is listed.
- [ ] The skill and the README no longer mention "remember in general" or the scope `general`.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S6: Part of release 0.6.0

**Acceptance Criteria:** version 0.6.0 stays in the three files; CHANGELOG, README (folders, `/dory:library`, the property, migration line) and CLAUDE.md updated; Record 004 points to this record for `private/`; nothing tagged or pushed beyond the branch.

**Priority:** Medium
**Status:** Done (2026-10-22)

## Implementation Notes

- **One release.** 0.6.0 was tagged but not merged, so the marketplace (which installs from `main`) had not shipped it. The library went into 0.6.0 in one commit, and the tag moves to the new release commit.
- **Where the topic files' link lives.** `dory link` writes the property as a block list (`frontmatter.add_list_item`); an inline list or a scalar under `library` becomes a block list with its values kept. While an entry waits in the queue, `baseline.record_dory_write` gives the baseline's copy of the topic file the new property, so its checks do not take the link back.
- **A run that adds a property.** A topic file the run created loses a `library` property, and one it changed gets the old one back; both are logged as `restored`.
- **The guard fails open.** A broken `dory guard` lets the call through and logs to `hook-errors.log`: it stays active for the rest of the session, and a guard that blocks every write would be worse than one that misses.
- **Dedupe at session start.** A library entry linked by the project's notes loads with them; one linked by several topics comes with the first of them in load order, and the topic block loads whole with its entries or not at all.
- **Checked.** Unit tests in `tests/test_library.py`. Live (Haiku): the three `/dory:library` and note checks three times in a row; a `/dory:note` asked to Edit a library entry was blocked by the guard (the denial listed, the file unchanged); the worker's deny probe on `library/**` and the two rule checks that touch the folder.
