# Changelog

All notable changes to dory are listed here. Versions follow [Semantic Versioning](https://semver.org/); the version lives in `pyproject.toml`, `plugin/.claude-plugin/plugin.json` and `plugin/dory/__init__.py`, and a test keeps them in sync.

## 0.9.0 (2026-10-22)

- **The note language is a choice list** in `/config`, English by default, with 16 common languages.
- **Any note language.** The list ends with `Other (config.toml)`. Choose it, and dory takes `language` from `~/.config/dory-brain/config.toml`, e.g. `language = "Catalan"`.
- **Versions.** While dory is at 0.x, every release raises the minor version; there are no patch releases.

## 0.8.0 (2026-10-22)

dory's main settings are in Claude Code's `/config` ([Record 007](docs/records/007-settings-in-claude-code.md)).

- **Settings in `/config`.** Vault folder, note language, worker model, context at session start and context window appear as rows of dory in `/config` and in `/plugin configure dory@brain`. Claude Code checks a value when you save it and applies it at the next start or after `/reload-plugins`.
- **opus as worker model.** The worker model can be `sonnet`, `haiku` or `opus`.
- **config.toml still works.** A value set in Claude Code wins; `~/.config/dory-brain/config.toml` decides what you have not set there, and keeps the rarer settings.

## 0.7.0 (2026-10-22)

`private/` becomes `library/`, and `/dory:library` files knowledge there in a dialog ([Record 006](docs/records/006-library.md)).

- **The library.** `library/` holds the knowledge you file deliberately, in folders you choose. `/dory:library "..."` proposes the folder, the title, the content with wikilinks to the notes it mentions, and the files to link it from, and writes after your yes, through `dory library-write` and `dory link`.
- **Links load entries.** A project note links a library entry in its text or in its `library` property, and the entry loads in that project's sessions. A topic file in `notes/` links one in its `library` property only, and the entry loads in every session, right after the topic. The worker gets copies of the entries its session could load and does not write them again; the checks after a run put back a `library` property the run changed.
- **`/dory:note` cannot write into the library.** A hook of the skill blocks Write and Edit under `library/` for the rest of the session. The scope `general` is now `notes` (`dory add-note --scope notes`), and "remember in general" is gone.
- **Rename `private/` yourself.** dory does not move the folder, since links to it would break. Rename it to `library` in Obsidian, which updates the links; until then the session start says that `private/` still holds files.
- **A short README.** It shows the idea and the commands; the details are in [docs/guide.md](docs/guide.md).

## 0.6.0 (2026-10-22)

The session start may take a share of the context window you choose, instead of a fixed 1,500 tokens, and topics in `notes/` load in full when there is room.

- **Three levels.** `context = "lean"` (5 % of the window, the default), `"balanced"` (10 %) or `"rich"` (15 %). The window comes from `context_window`, 200,000 tokens by default: Claude Code does not tell a hook which model a session uses. Set it to the smallest window you work with, e.g. `context_window = 1000000`. `recall_budget_tokens` still sets an exact limit and then wins. With the defaults the start may take 10,000 tokens, more than six times as much as before.
- **Topics in full.** After the project's files, each topic file in `notes/` loads whole, most recently updated first, as long as it fits; the rest, and every list and register, stays a title line.
- **Summaries are capped.** A project still gets a summary once its files exceed 80 % of the limit, but a summary is at most 10,000 tokens. A change of level or window makes existing summaries stale; the worker rebuilds them.

## 0.5.0 (2026-10-21)

Your notes become files with a title, everything without a project moves into `notes/`, and `private/` becomes your own folder that dory reads only through your links. The update does not migrate notes 0.4.0 wrote; see the last points.

- **A note is a file.** `/dory:note` in a project creates a file in `projects/<project>/notes/`, named by a title that says what it is about. Claude writes title and content from what you ask for and from the session, in the note language. The worker reads these notes in full and never changes them; when a session shows one to be wrong, it corrects the project's `knowledge.md` and links the note under `## Open` in the session note.
- **Everything without a project in `notes/`.** Knowledge that applies beyond a project lives in one file per topic in `notes/` (`Notion`, `Outlook connector`), next to the lists and registers. The worker extends the matching topic or creates one for a new subject; `/dory:note "remember in general: ..."` does the same. A topic file has the form of `knowledge.md`. `general/` is gone.
- **`private/` is yours.** dory creates the folder and never writes into it, and the worker can neither read nor write it (the deny rules of its run, checked live). Private knowledge from sessions is no longer kept; at most the session note mentions it. Write private notes into `private/` in Obsidian; a link from one of a project's notes (`[[private/Employment contract]]` or `[[Employment contract]]`) loads the private note at that project's session start. `/dory:note` no longer has a private scope.
- **Session start.** In a project it loads your notes, each followed by the private notes it links, then `knowledge.md`, and lists every file in `notes/` by title, most recently updated first, so Claude reads a topic when the session touches it. Outside a project only the titles load. When the project's files do not fit `recall_budget_tokens`, their summary loads; it is used only while the same private notes are linked.
- **Search covers the whole vault.** `/dory:search` finds entries of the knowledge and topic files and whole notes, lists, registers and session notes, `private/` included, in every session.
- **Checks after every run.** A change to one of your notes or to a file in `private/` is listed in `runs.log` and `dory status` and no longer undone, so an edit you save in Obsidian while a run is going stays. The snapshot is the way back. A topic file the worker creates gets `type: topic` if it lacks one, and a name that breaks the naming rules is reported.
- **Files 0.4.0 wrote.** `general/knowledge.md` and `general/notes.md` and a project's `notes.md` are no longer loaded, searched or written: move what you want to keep into topic files in `notes/` or into note files in the project's `notes/`, then delete them. `private/knowledge.md` and `private/notes.md` stay as your private notes and load when a project note links them.
- **Sessions started before the update** still run the 0.4.0 hooks until you restart them or run `/reload-plugins` in them, and their worker writes into `general/`, `private/` and `notes.md`.

## 0.4.0 (2026-10-19)

Each project's knowledge lives in one file instead of one note per insight, your own notes get a file of their own, and every worker run is checked against the vault as it was before. The update does not migrate existing notes; see the last two points.

- **One knowledge file per scope.** The worker keeps `projects/<project>/knowledge.md`, `general/knowledge.md` (knowledge without a project) and `private/knowledge.md` (the private domain). An entry is a bullet that opens with its statement in bold, under the sections `## Pitfalls`, `## Decisions`, `## Facts`, `## How-to` and `## Preferences`. The worker extends or corrects an entry in place and removes one the project's `CLAUDE.md` now states. There is no size limit and no renaming of files any more.
- **Your notes in `notes.md`.** `/dory:note` now writes into `projects/<project>/notes.md` in a project, into `general/notes.md` when you say it applies in general or it has nothing to do with the project, and into `private/notes.md` when it is private, also from a work project. The note is kept in your words with the date; the worker reads these files and never changes them. Lists such as the shopping list stay under `notes/`. The new command `dory add-note --scope project|general|private` does the writing; the skill only chooses where.
- **Session start.** It loads the project's `notes.md` and `knowledge.md`, then those of `general/`, and those of `private/` for a private project or outside a repository, each under its path. A project is private when its `knowledge.md` says `domain: private`.
- **A summary over the limit.** When these files exceed 80 % of `recall_budget_tokens`, the worker writes a summary of them in the background (a short `claude -p` run of the worker model, without tools). When the whole text of a session start no longer fits the limit, it loads that summary with the paths of the full files. Until the summary exists, or after the files changed, the session start loads the files cut at the limit or the previous summary with a note, and asks the worker for a new one. It never waits for a model.
- **Checks after every run.** dory compares the knowledge files with their state before the run: a removed entry, a rewritten lead, a restored `notes.md` or frontmatter and an unexpected file are listed in `runs.log`, and `dory status` shows today's counts. A run cannot change your notes: dory restores them. A note you add with `/dory:note` during a run is kept; an edit you make to a `notes.md` by hand while a run is in progress is undone with them.
- **Search finds entries.** `/dory:search` shows the matching entry with its section and file instead of a whole note, besides session notes and lists.
- **Sibling projects.** Knowledge about another repository that came up in a session now stays in the session's project; a session writes only its own project's file, `general/` and `private/`.
- **Notes of 0.3.0.** Knowledge notes and project overviews from earlier versions stay in your vault untouched, but they are no longer loaded at session start, searched or changed. A project you had marked `domain: private` in its overview stays private: the worker gives its `knowledge.md` that domain when it creates the file after the project's first session under 0.4.0. Keep the overview of such a project until then, or set `domain: private` in its `knowledge.md` yourself; without either, the project becomes work. Delete the other old files when you no longer need them, or keep them to read in Obsidian.
- **Sessions started before the update** still run the 0.3.0 hooks until you restart them or run `/reload-plugins` in them. When one of them ends, it starts the 0.3.0 worker, which processes every session waiting in the queue at that time the 0.3.0 way, into knowledge notes that 0.4.0 does not load.

## 0.3.0 (2026-10-16)

The session start carries knowledge only, and the vault keeps fewer, current notes named after what they say. The update does not rewrite existing notes; it applies to what the worker writes from then on.

- When a session ends, redacted copies of the repository's `CLAUDE.md` and `docs/records/*.md` are captured with it, from the checkout the session ran in (a worktree on its branch included) plus records only the main repository has. Before every knowledge note the worker searches them instead of seeing only the first 8,000 characters of the `CLAUDE.md`. The copies are removed when the session leaves the queue.
- The session start no longer injects open items, and the project overview no longer keeps an `## Open` section; the worker removes a leftover one. A session note still lists what that session left open.
- The session start no longer injects summaries of recent sessions, and the setting `short_term_sessions` is gone. Config files that still set it load as before.
- Knowledge notes only for what really matters: the worker asks whether someone working in the repository tomorrow, reading the `CLAUDE.md` and the code, would make a mistake or lose time without the note. What was built, how the code works and the steps of a session stay in the session note. Most sessions now yield no knowledge note.
- New knowledge notes are named after their core statement, in the note language and without the project prefix: `Loki startet nur, wenn UID 10001 das Datenverzeichnis besitzt.md` instead of `ai-assistant-hub-loki-uid-10001.md`. Existing names stay until a note is corrected.
- Stale notes are corrected instead of superseded: when a session shows that a note no longer holds, the worker corrects it in place and gives it a new title, and dory renames the file after the run and rewrites every link to it. A note whose content the `CLAUDE.md` now states is deleted and leaves the project overview, unless another project lists it too. This happens only when a session brings up the subject, and only for marks of a run that succeeded; the snapshot before each run is the way back. `runs.log` lists each rename and deletion, and `dory status` shows a step that failed.
- New writing rules:
  - The worker turns nothing the `CLAUDE.md` states into a knowledge note, wherever in the file it stands. What a record states becomes a note only if it matters beyond the record's own feature, as a pointer of three sentences that names the record; 0.2.0 wrote no note on a subject that matched a record title. `/dory:note` skips this check and writes the note the user asked for.
  - A note always describes the current state: when it is extended, its `summary` and `when` are rewritten instead of adding "as of" sections.
  - Knowledge notes hold no project status (progress, effort, costs, commit hashes, pull request numbers, branches) and keep their body under 1,200 characters.
  - Step, ticket and pull request numbers appear only next to what they name; the user is "the user" in the note language, never a role name such as "the engineer".
  - The repository documents are data, like the transcript: what they say about the language, form or place of notes does not apply.
- The `SessionEnd` hook has a timeout of 10 seconds, so the copies fit in. Queue entries keep their format: 0.2.0 and 0.3.0 read each other's entries. A session queued by 0.2.0, or one whose copies the hook did not finish, is processed without the documents: the worker then skips the check against the `CLAUDE.md` and the records. So is an entry moved back with `dory retry`: its copies are removed when it is parked in `failed/`.

## 0.2.0 (2026-10-12)

- README: the configuration shows the three settings a user chooses (`vault`, `language`, `model`); the six tuning settings are documented under "Advanced settings" with what each one guards against. Behaviour and defaults are unchanged.
- README: updating an installed plugin takes `claude plugin update dory@brain`; `claude plugin install` does not pick up a new version.
- The marketplace is now called `brain`: install with `claude plugin install dory@brain`. If you installed 0.1.0, remove the old marketplace first: `claude plugin uninstall dory@dory-brain && claude plugin marketplace remove dory-brain`.

## 0.1.0 (2026-10-12)

First release.

- Sessions are queued when they end (`SessionEnd` hook) and processed in the background by a worker running `claude -p` with the shared writing rules: session note, knowledge notes (merged, superseded instead of duplicated), project overview, lists and registers.
- Session start (`SessionStart` hook) injects the project, open items, recent sessions, ranked knowledge notes and a catalog within a token budget, with a boundary between work and private notes.
- `/dory:save` queues the running session without ending it; the rest becomes part 2.
- `/dory:note "..."` writes a note straight into the vault after a snapshot.
- `/dory:search` finds notes by summary, when, tags, file name and text.
- `dory status` and `dory retry` for operations; costs shown as API equivalent, the worker always runs on the Claude subscription.
- Configurable note language (`language`, default English).
