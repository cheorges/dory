---
name: save
description: Write the current state of this Claude Code session into the dory second brain now, with full context. Use when the user says /dory:save, "save this to the brain", "write the session to Obsidian", or before /clear when the work continues.
allowed-tools: Bash(python3 *scripts/brain.py*), Read, Grep, Glob
---
# Save this session

You have the full context of this session, so you write the notes yourself.

1. Run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" begin --session '${CLAUDE_SESSION_ID}' --vault "${user_config.vault_path}" --data "${CLAUDE_PLUGIN_DATA}"`
2. Look into the vault only with Glob, Grep and Read, never with Bash: the Bash sandbox may not see the vault, and a note that looks missing gets created twice. Read `${CLAUDE_PLUGIN_ROOT}/rules/writer.md` and `${user_config.vault_path}/types.md` and follow them exactly. Note language: ${user_config.note_language}. Session id: ${CLAUDE_SESSION_ID}. If a session note with this id already exists in `sessions/`, append to it.
3. Write the session note and update the affected project, topic and decision notes.
   Before step 4, check what you wrote and fix it:
   - The session note keeps the `# ` title and exactly the sections `## Summary`, `## Decisions`, `## Open`, `## Touched` from `templates/session.md`.
   - Every decision that names an alternative or a reason that is not obvious has its own note in `decisions/`.
   - No open point is ticked that was only decided or planned in this session.
4. Run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" finish --session '${CLAUDE_SESSION_ID}' --written-by save --vault "${user_config.vault_path}" --data "${CLAUDE_PLUGIN_DATA}" --active-days ${user_config.active_days}`
5. Tell the user in one line which notes were written (from the finish output). If finish reports that the background run is writing, wait a minute and run step 4 again.
