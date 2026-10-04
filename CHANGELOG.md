# Changelog

## 1.0.0

- Background run after each interactive session writes a session note and updates the project, topic and decision notes it touched (`claude -p`, limited to reading and writing inside the vault).
- Session start block with the state and open points of the current project and the notes active in the last 14 days.
- Catch-up at session start for sessions that ended without a session end event, once their transcript has been idle for 2 hours.
- Skills `/dory:search`, `/dory:save` and `/dory:note`.
- Vault seed with `types.md`, `hot.md`, `log.md` and templates for session, project, topic and decision notes.
- Transcript reduction with masking of credentials before anything reaches the writer.
- `events.log` with one line per session start and end, `errors.log` for failed runs.
