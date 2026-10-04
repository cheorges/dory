---
name: search
description: Look things up in the dory second brain (Obsidian vault). Use before saying you don't know something, and whenever the user mentions a project, customer, tool, decision or earlier work that is not in the current context. Also runs as /dory:search <question>.
argument-hint: "<question>"
---
# Search the second brain

Vault: `${user_config.vault_path}`. Question: $ARGUMENTS (if empty, use the topic of the current conversation).

1. Take the key terms from the question, including likely spellings and abbreviations.
2. Grep the vault for them: file names (Glob `**/*<term>*.md`), `aliases:` lines and full text. Ignore `templates/` and `.obsidian/`.
3. Rank hits: project, topic, decision and other non-session types before `sessions/`; within that, newer `last_active` first.
4. Read at most 5 hits: frontmatter, `## Current state` and `## Open` only.
5. Follow the frontmatter links `project`, `topics`, `supersedes` one step. If a decision is superseded, the newer one counts.
6. Answer with source and date for every statement: "According to [[dory]] (as of 2026-10-03) ...". Say when a state is old.
7. If no hit shares a term with the question, answer "Nothing found in the second brain" and do not guess.

For broad questions across many notes ("everything about customer X this year"), run the search in a subagent and have it return only the answer with its sources.
