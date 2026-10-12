---
name: save
description: Saves the running session to dory-brain now, without ending it. Only when invoked explicitly as /dory:save.
disable-model-invocation: true
allowed-tools: Bash
---
Run exactly this command with the Bash tool and report its output in one sentence:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/dory" enqueue --session "${CLAUDE_SESSION_ID}"
```

Nothing else: no summary of the session, no further command. Processing runs in the background; afterwards work continues as usual.
