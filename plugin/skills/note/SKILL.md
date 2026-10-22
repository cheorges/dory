---
name: note
description: Writes a note into the dory-brain vault without processing a session. Only when invoked explicitly as /dory:note "...".
argument-hint: "<what to record>"
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---
# dory:note

To record, as the user asks: $ARGUMENTS

1. Run with the Bash tool:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/bin/dory" prepare-note
   ```
   The output names the vault, the snapshot, today's date, the note language, the project with its domain, the scopes with their folders, the titles of the project's notes and of the files in `notes/` with their types, and below that the writing rules. The rules apply to everything that follows, in the case "without a task file". If the command fails, write nothing and report the error.
2. An item for a list or register (a shopping list, open invoices, things to take along): change that list in `notes/` as the rules say for lists and registers, from any session, inside a project too. Go on with step 6.
3. Private content that is no list item (the user's family, health, money, home, own devices and home network): write nothing. Tell the user in one sentence that dory keeps no private notes, and that a note they write into `private/` in Obsidian reaches a project's sessions when one of the project's notes links it. Stop here.
4. Anything else is a note. Choose its scope from the output of step 1:
   - `project`: in a project, by default.
   - `general`: when the user says it applies in general ("remember in general: ..."), or when the text clearly has nothing to do with the project. Outside a project, always.
5. Write it:
   - **project**: write a title and the content. The title names the subject in a short phrase in the note language, not a statement, and is none of the project's note titles from step 1. The content is what the user asked to record, written out from the request and from what this session worked out: complete enough that a later session understands it without this one, in the note language. Leave out words that only say where to put it ("remember in general:"). Link nothing in `private/` unless the user's request asks for that link. Then create the file, the content on standard input between the quoted heredoc markers, exactly as below:
     ```bash
     "${CLAUDE_PLUGIN_ROOT}/bin/dory" add-note --scope project --title "<title>" <<'DORY_NOTE'
     <the content>
     DORY_NOTE
     ```
   - **general**: write entries in the form the rules give for topic files. Find the matching topic among the titles from step 1 and Grep the topic files in `notes/` for the key terms. When a topic file on the subject exists, change it with Edit as the rules say: extend or correct the entry on the same subject in place, add an entry only for a new subject, and set `updated` to today. Otherwise create a topic file whose title names the subject, exactly as below:
     ```bash
     "${CLAUDE_PLUGIN_ROOT}/bin/dory" add-note --scope general --title "<topic>" <<'DORY_NOTE'
     ## <Section>
     - **<bold lead>** <at most three sentences>
     DORY_NOTE
     ```
   A title holds no quote, `$` or backtick. Never change a project's note, its `knowledge.md` or anything in `private/`. If the command fails, read its message: a project note title that exists needs another title; for a topic that exists, change that file with Edit.
6. Reply with one line: the file you wrote or changed, relative to the vault.
