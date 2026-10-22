# Record 005: Context Levels for the Session Start

## Status

Done (2026-10-22): released as 0.6.0

---

## Problem

The session start injects at most `recall_budget_tokens` (1,500 tokens, about 6,000 characters). That limit was chosen when a context window held 200,000 tokens and every token of the start weighed on every session. Today many sessions run with a window of 1,000,000 tokens. At 1,500 tokens a project with a real body of knowledge falls back to its summary early, and Record 004 lists the topics in `notes/` by title only, so a pitfall about a tool reaches a session only when Claude judges its title relevant.

The user wants the share of the window that dory may take to be a choice, in three levels.

## Options Considered

All decisions were made by the user on 2026-10-22.

### Decision 1: How the limit is set

- **Option A:** keep `recall_budget_tokens`, a number of tokens.
- **Option B:** three levels that each take a share of the context window: 5 %, 10 %, 15 %.

**Decision:** B. The levels are named `lean` (5 %), `balanced` (10 %) and `rich` (15 %); `lean` is the default. `recall_budget_tokens` stays as an advanced override for an exact number.

### Decision 2: Where the window size comes from

- **Option A:** from the hook: Claude Code could tell the `SessionStart` hook the session's model.
- **Option B:** from the configuration: `context_window`, default 200,000 tokens.

**Decision:** A if the hook gets the model, else B. A live probe on 2026-10-22 showed that it does not: the hook receives `session_id`, `transcript_path`, `cwd`, `hook_event_name` and `source`, with Haiku and with Sonnet at 1M alike. So the window comes from `context_window`; a user with 1M windows sets `context_window = 1000000`.

### Decision 3: The length of a summary

A summary was made to 80 % of the limit. At 15 % of 1,000,000 tokens that would be 120,000 tokens, far beyond what one `claude -p` run writes. **Decision:** a summary is at most 10,000 tokens, the `lean` limit of a 200k window. It is still made only when a project's files exceed 80 % of the limit.

### Decision 4: The topics in `notes/`

With a limit of 10,000 tokens and more, the topic files can load as they are instead of by title. **Decision:** after the project's files, the topic files load in full, most recently updated first, as long as each fits whole; the rest, and every list and register, stay a title line. This changes Record 004 decision 5 for the case that the room is there; the principle of 2026-10-15 (the start brings what one would not know to ask for) holds again as far as the level allows.

## Solution

- **Configuration.** `context` (`lean`, `balanced`, `rich`; an unknown value counts as `lean`) and `context_window` (tokens, default 200,000) give the limit: share times window. `recall_budget_tokens`, when set, replaces that product.
- **Summary.** Made when a project's files exceed 80 % of the limit, as before; its target length is that 80 % but at most 10,000 tokens (40,000 characters). The hash covers the limit in tokens, so a change of level or window makes summaries stale.
- **Session start.** Front, project files (or their summary) as before. Then each topic file in full under `## notes/<title>.md`, most recently updated first, while it fits whole; a topic that does not fit and every list and register is a title line in the section of the titles, which still ends with the line that counts what did not fit.
- **Docs.** README (configuration, session start), CHANGELOG 0.6.0, project CLAUDE.md.

| Level | Share | 200k window | 1M window |
|---|---|---|---|
| `lean` | 5 % | 10,000 tokens | 50,000 tokens |
| `balanced` | 10 % | 20,000 tokens | 100,000 tokens |
| `rich` | 15 % | 30,000 tokens | 150,000 tokens |

### Risks

- **A wrong `context_window`.** A user with 200k windows who sets 1M lets dory take five times the share they chose. The README says to set it to the smallest window the user works with.
- **Every token counts against the usage limit.** A `rich` start at 1M can put 150,000 tokens into every session; the levels are maxima, and a vault reaches them only with a lot of knowledge.

## User Stories

### Story S1: Levels set the limit, summaries are capped

**As a** user with a large context window
**I want** to choose how much of it dory's session start may take
**So that** a project's knowledge loads in full instead of being cut or summarized early

**Acceptance Criteria (unit tests):**
- [ ] Given no setting, when the limit is computed, then it is 5 % of 200,000 tokens; given `balanced` and `rich` with a window of 1,000,000, then 100,000 and 150,000 tokens; given an unknown level, then `lean`; given `recall_budget_tokens`, then that number.
- [ ] Given a limit of 150,000 tokens, when a summary is made, then its target is 10,000 tokens; given a limit of 1,500 tokens, then 80 % of it.
- [ ] Given another level, when a summary's hash is computed, then it differs.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S2: Topics load in full while they fit

**As a** user who keeps knowledge about tools in `notes/`
**I want** the topic files to load in full when the level leaves room
**So that** a pitfall arrives without Claude asking for it

**Acceptance Criteria (unit tests):**
- [ ] Given room for everything, when a session starts, then every topic file loads in full under its path after the project's files, most recently updated first, and lists and registers stay title lines.
- [ ] Given room for one topic only, when a session starts, then the most recent topic loads in full and the other topics are title lines, followed by the closing line when titles do not fit either.
- [ ] Given a session outside a repository, when it starts, then the topics load in full there too.

**Priority:** High
**Status:** Done (2026-10-22)

### Story S3: Release 0.6.0 prepared

**Acceptance Criteria:** version 0.6.0 in the three files; CHANGELOG, README and CLAUDE.md describe the levels, `context_window`, the summary cap and the topics in full; nothing tagged or pushed beyond the branch.

**Priority:** Medium
**Status:** Done (2026-10-22)
