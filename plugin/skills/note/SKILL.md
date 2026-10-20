---
name: note
description: Writes a note of the user's into the dory-brain vault without processing a session. Only when invoked explicitly as /dory:note "...".
argument-hint: "<what to record>"
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---
# dory:note

To record, in the user's own words: $ARGUMENTS

1. Run with the Bash tool:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/bin/dory" prepare-note
   ```
   The output names the vault, the snapshot, today's date, the note language, the project with its domain, the scopes with their `notes.md`, and below that the writing rules. The rules apply to everything that follows, in the case "without a task file". If the command fails, write nothing and report the error.
2. An item for a list or register (a shopping list, open invoices, things to take along): edit that list under `notes/` as the rules say for lists and registers, from any session, inside a project too. No `notes.md` changes. Go on with step 5.
3. Anything else is a note. Choose its scope from the output of step 1:
   - `project`: in a project, by default.
   - `general`: when the user says it applies in general ("remember in general: ..."), or when the text clearly has nothing to do with the project. Outside a project, this is the default.
   - `private`: when the content belongs to the private domain (the user's family, health, money, home, own devices and home network), also from within a work project.
4. Write it with the Bash tool, the note on standard input between the quoted heredoc markers, exactly as below:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/bin/dory" add-note --scope <scope> <<'DORY_NOTE'
   <the note>
   DORY_NOTE
   ```
   The note is the user's text as written: not translated, not reworded, not completed. Leave out only words that tell you where to put it ("remember in general:"). Never edit a `notes.md` or a `knowledge.md` yourself. If the command fails, report its message.
5. Reply with one line: the file you wrote, relative to the vault.
