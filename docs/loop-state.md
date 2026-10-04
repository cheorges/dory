# Loop state: dory v1

Working state of the build loop that produced dory 1.0.0. Kept as a record; the project is finished.

## Brake

free

## Context cut

not due

## Next task

## Mode

lean: a personal plugin without customers and without external target values; the bar is the tests from the plan (60 in Task 2 to 8, plus seed and skill tests) and the user's judgment of real notes in Task 11.

## Workplace

| What | Where |
|---|---|
| Repo | `<repo>` |
| Branch | `feat/dory-v1` |
| Return point | `8928c09` on `main` (local; there is no remote yet), everything after that is loop |
| Quick round | `python3 -m pytest -q`: the whole suite runs in about 2 s, a selection is not worth it |
| The full proof | `python3 -m pytest -q && claude plugin validate .`: before every cut and as the first step of the fresh session. Before Task 8 there is no `.claude-plugin/` yet; until then only the pytest part |
| Plan | `docs/superpowers/plans/2026-10-03-dory.md` (code and tests for each task are there in full) |
| Spec | `docs/superpowers/specs/2026-10-03-dory-design.md` |
| Scratch | `<scratchpad>` of the running session |

## Goals

1. Every interactive session with at least 3 user messages ends up as a linked note in the Obsidian vault, also after Ctrl+C, `/clear` or a closed terminal.
2. A new session in the project folder knows the state and open points of the project at startup.
3. Claude answers questions about earlier projects, customers or decisions with source and date, or says that nothing is there.
4. The vault stays readable without Claude: English folders, `types.md`, `hot.md`.
5. No hook breaks or delays a session; only the Python stdlib at runtime.

## Queue

| Story | Content | Status |
|---|---|---|
| Task 1a | Spike without the user: probe plugin, child process isolation, cost, `entrypoint` | done `9076bcf` |
| Task 2 | Scaffold and frontmatter parser | done `c910399` |
| Task 3 | Shorten transcript and mask credentials | done `ac30c7d` |
| Task 4 | State: config, queue, anchor, lock | done `c7cdcf7` |
| Task 5 | Vault: notes, project, active rule, `hot.md` | done `cd39b9f` |
| Task 6 | Start block and catch-up | done `5c0cb68` |
| Task 7 | Writer and cleanup step | done `2c11e1c` |
| Task 8 | `brain.py`, hooks, manifest, marketplace | done `8500d18` |
| Task 9 | Templates, `types.md`, writing rules | done `fd3ecd4` |
| Task 10 | Skills `search`, `save`, `note` | done `f49b591` |
| Review | `/do-review` over Task 2 to 10 | done `9bd164d`, `1b41abe` |
| Task 1b | Spike with the user: exit paths, worker survives, skill substitution, Obsidian graph, vault access | done `d899d15`; point 5 (backlinks and graph in Obsidian) deliberately open, the user will look when there is a chance |
| Task 11 | Installation, 3 real sessions, judge notes, tighten rules, README | done `5d98041`, `4ba4898`, `3656bca`; the look in Obsidian from Step 4 depends on spike point 5, deliberately open |

Task 1b and Task 11 run in one joint stop: all questions to the user in one round of questions.

## History

| Date | Story | What moved |
|---|---|---|
| 03.10. | Setup | Branch `feat/dory-v1` from `8928c09`, state file created, mode lean |
| 03.10. | Task 1a | Child process needs `--setting-sources ""` (otherwise global CLAUDE.md, output style and third-party plugin hooks are included); `acceptEdits` allowed writing outside the vault, replaced by the rule `Edit(//<vault>/**)`. Plan Task 7 adjusted. Sonnet run 18 s, 0.23 USD for 100k characters. `entrypoint` `sdk-cli` vs `cli` confirmed. Text pass without changes |
| 03.10. | Task 2 to 10 | Code and tests taken over from the plan (by script from the plan blocks, not typed by hand), each task red (missing module) and then green with the plan count: 8, 17, 27, 37, 43, 49, 60, 63, 66. `claude plugin validate .` green; the only warning (marketplace without description) fixed with `metadata.description`. Against real material: the transcript of this session runs through `reduce` and `is_interactive`; `brain.py` with empty, broken and real hook input exits with 0, without traceback |
| 03.10. | Findings for Task 11 | (1) `count_user_messages` counts `/clear` and slash commands as user messages; the threshold of 3 can thus be reached by a session without real input. (2) `session-start` outputs the start block with the current directory on empty stdin; plan focus 5 says "without output", the test only checks exit and traceback. Kept, because this way the start block still delivers project context if the hook format changes (goal 2) |
| 03.10. | Review at the seam | First round with three agents (architecture, code quality, security): 8 findings after merging, 2 of them P1. (1) The writer was allowed to read any file on disk, so an instruction in the transcript could have copied credentials into the vault; now reading, searching and writing are restricted to the vault and `.obsidian` is blocked, measured with a `claude -p` probe. (2) With an overlapping `/dory:save` and background run, the note of the other session got stamped; now the writer sets `session_id` itself. Plus 6 P2/P3 (masking, permanently failed sessions, re-queueing, broken frontmatter, placeholders, non-UTF-8). All fixed in `9bd164d`. Second round: verdict correct, 3 findings in the masking pattern (values with spaces leaked, "basic functionality" and `key=lambda` were destroyed), fixed in `1b41abe`. 77 tests green, plugin validated. Text pass skipped: each changed `.md` is read by a test |
| 04.10. | Vault access | `/bin/ls` on the cloud-synced vault from the session under herdr: `Operation not permitted`, also without the Claude Code sandbox. So the block comes from macOS (privacy permission), not from Claude Code. Hooks inherit it because they are child processes of Claude Code; dory reports this in the start block as "Vault not writable" |
| 04.10. | Spike point 7 | After the user's macOS permission: reading and writing in the cloud-synced vault work without the sandbox. Vault empty except for `.obsidian`. Added to the spike results |
| 04.10. | Task 11, installation | The user installed `obsidian-skills`, the marketplace `dory` and `dory@dory`; options set (`vault_path` cloud-synced vault, `note_language` German). At 13:21 the background run wrote the running build session into the vault without errors: session note with correct frontmatter (`session_id`, `written_by: background`), project `projects/dory/dory.md` with `path`, a decision note, `hot.md`, `log.md`, templates and `types.md`. No `errors.log`, queue empty. Trigger unclear: the session kept running, so the queueing probably came from a session end when the plugins were reloaded; dory does not log hook events. Good in content; one outdated open point ("set `vault_path` and `note_language`"), because the setting was not visible in the transcript |
| 04.10. | Task 11, test run | Drove six test sessions myself (Haiku, herdr workspace `dory-test`, closed since). All normal exit paths fire the session end, note after 7 to 20 s; `herdr pane close` does not, the catch-up covers it. `/dory:save` works, with 5 prompts; a later background run writes nothing twice. No `errors.log`, no check messages. The notes of the background run (Sonnet) follow the template, set "(as of ...)", add `## History` and mark contradictions with `replaced:`. Weaknesses: the note written with Haiku via `/dory:save` deviates from the template (no title, "What happened" instead of `## Summary`, no decision note despite an alternative) and ticks off an open point in the project note that is only decided, not implemented. After `finish` the `begin` file stays in the data folder |
| 04.10. | Findings 1 to 5 from the test run | Slash commands no longer count (`94d7035`); `events.log` per session start and end (`6a91c9e`); the helper file of `/dory:save` is deleted after a successful `finish` (`9b59971`, fixed up); writing rules and `/dory:save` with checklist, search in the vault only with Glob, Grep and Read, `brain.py` allowed in advance (`5d98041`). Measured with Haiku in herdr: notes now with title and the four sections, decision as its own note; `/dory:save` with vault rule 0 prompts, without it 6, because placeholders in the skill header are not substituted. README written (`4ba4898`). Review: verdict correct, 2 findings (helper file deleted too early, decision rule with "and" and "or"), both fixed. Text pass: README three places, spike results unchanged. 83 tests green |
| 04.10. | Answers from the user | Permission rule `Edit(~/Obsidian/Vault/**)` added to `~/.claude/settings.json` on the user's yes. Ran the memory test myself (Haiku, new session in the dory folder): "Where do we stand with dory?" answered from the start block, with source, without search; state partly outdated because the running build session was not in the vault yet. Question about the decision on rotating `events.log`: correct, with reason, source and date, from the start block (active note) and Claude's memory. Spike point 5 needs Obsidian itself, no command line available; deliberately open |
| 04.10. | Acceptance round (lean) | (1) Full proof green: 83 passed, plugin validated. (2) Queue ticked off, only the look in Obsidian (backlinks and graph) open, deliberately. (3) Last review over `1b41abe..3656bca` without open findings; since then only `docs/loop-state.md` changed. (4) Everything committed locally; there is no separate implementation log, in lean mode the history here plays that role. Result: done, merge question to the user |
| 04.10. | Wrap-up | The user: yes to the merge. `feat/dory-v1` merged locally into `main` by fast-forward, no push. Project finished |

## Open questions for the user

- When there is a chance, nothing is blocked: open the note `dory` in Obsidian and check whether the session notes appear under "Backlinks" (spike point 5).

## Last cut

**04.10., after the findings from the test run.** Second cut in the project. The session before it built Task 2 to 10 after the first cut, worked in two review rounds, unlocked the cloud-synced vault (macOS permission by the user), installed the plugin with the user, drove six plus two test sessions itself via herdr and fixed the five findings from them. README is done.

Taken over on 04.10. by the fresh session: proof green (83 passed, plugin validated), cut marker reset, acceptance round run (`8eaa64b`).

### State at the cut

| | |
|---|---|
| Green | `python3 -m pytest -q` 83 passed, `claude plugin validate .` passed |
| Review | last round over `1b41abe..3656bca`: verdict correct, 2 findings, both fixed in `3656bca` |
| Text pass | README three places changed, spike results unchanged |
| Committed | everything, most recently the commit of this handover. Nothing pushed, no remote |
| Live | the plugin is installed from this repo (directory marketplace); every change in the working tree applies immediately in all of the user's sessions |

### What the next session starts with

1. `## Context cut` to `not due`.
2. Full proof: `python3 -m pytest -q && claude plugin validate .`.
3. The user has answered (History 04.10., "Answers from the user"); the permission rule is added.
4. Acceptance round according to "Next task".

### What is not in the plan and still applies

- Vault: `~/Obsidian/Vault`. Invisible or blocked from the Bash sandbox; checks there with `dangerouslyDisableSandbox`. Data folder: `~/.claude/plugins/data/dory-dory/` (`events.log`, `processed.json`, `queue/`).
- Test sessions: scripts `drive.sh` and `waitlog.sh` were in the scratchpad of the old session (gone after restart). Pattern: `herdr workspace create --cwd <repo> --label dory-test --no-focus`, `herdr agent start <name> --kind claude --pane <pane> -- --model haiku`, `herdr agent prompt <name> "<text>" --wait`, slash commands via `herdr pane send-text` plus `send-keys Enter`, Ctrl+D is `ctrl+d`. Confirm prompts of the test session with `send-keys <pane> 1`. Close test workspaces afterwards.
- The test sessions write real notes into the vault and into the project's Claude memory; only feed them real dory content.
- Commits: `<type>(<scope>): <description>`, no `Co-Authored-By` lines.
