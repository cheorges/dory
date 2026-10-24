---
type: note
created: 2026-10-01
---
# Live checks
They run `claude -p` headless in a throwaway vault. A Bash command on a path outside the session's working directory is refused there, so the skills must not rely on `grep` over the vault.
