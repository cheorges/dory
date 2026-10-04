---
name: note
description: Write or update one note in the dory second brain about a specific subject from this conversation (project, topic or decision), without a session note. Use when the user says /dory:note <subject>, "note this in the brain", "make a note about X".
argument-hint: "<subject>"
allowed-tools: Bash(python3 *scripts/brain.py*), Read, Grep, Glob
---
# Note a subject

Subject: $ARGUMENTS

1. Run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" begin --vault "${user_config.vault_path}" --data "${CLAUDE_PLUGIN_DATA}"`
2. Look into the vault only with Glob, Grep and Read, never with Bash: the Bash sandbox may not see the vault, and a note that looks missing gets created twice. Read `${CLAUDE_PLUGIN_ROOT}/rules/writer.md` and `${user_config.vault_path}/types.md` and follow them, except: write no session note. Note language: ${user_config.note_language}.
3. Decide whether the subject is a project, topic or decision (see types.md), search the vault for an existing note, then create or update it from what this conversation established. History line: `- YYYY-MM-DD /dory:note: <what changed>`.
4. Run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" finish --written-by note --vault "${user_config.vault_path}" --data "${CLAUDE_PLUGIN_DATA}" --active-days ${user_config.active_days}`
5. Tell the user in one line which note was written.
