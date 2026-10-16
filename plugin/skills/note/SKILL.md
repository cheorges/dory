---
name: note
description: Writes a note straight into the dory-brain vault without processing a session. Only when invoked explicitly as /dory:note "...".
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
   The output names the vault, the snapshot, today's date, the note language, the project with its domain and overview, the known projects, and below that the writing rules. The rules apply to everything that follows, in the case "without a task file". If the command fails, write nothing and report the error.
2. Place the text according to the rules: a knowledge note (in the session's project or under `general/`) or an entry in a list or register under `notes/`. Search the vault with Glob and Grep for an existing active note on the same topic first, and extend it instead of creating a second one. A new knowledge note is named after its core statement, as the rules say. Do not rename or delete notes, and do not set `rename_to` or `status: archived`.
3. Write only into the vault, using absolute paths under the vault from step 1. No session note. In the project overview, only the entry under `## Knowledge` for a new knowledge note; if the overview is missing (step 1 says so), create it according to the rules, without `## Sessions`.
4. Reply with one line: which file you created or extended, relative to the vault.
