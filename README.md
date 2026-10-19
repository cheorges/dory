# 🐠 Dory

A memory for Claude Code. When a session ends, a background process writes what was learned in it into an Obsidian vault, one knowledge file per project. When a new session starts, Claude gets back what is already known: the pitfalls, decisions and facts of the project, the ones that apply everywhere, and the notes you wrote yourself.

The notes are plain Markdown, so you can browse them in Obsidian. They are written in the language you configure, English by default.

## What you get

### Automatically

- **When a session ends** (`/exit`, `/clear`, closing the tab, Ctrl+C), it goes into a queue. A worker processes it in the background with `claude -p` and writes:
  - a session note: what was done, which knowledge entries came out of it, what is still open
  - entries in the project's `knowledge.md`, only for what really matters: a pitfall, a decision the repository does not record, a fact about a system outside the code, a how-to, a preference. Most sessions add none. An entry opens with its statement in bold (`**Loki only starts if UID 10001 owns the data directory.**`) followed by at most three sentences, and states the current state without progress, effort or commit hashes. What the project's CLAUDE.md already says does not become an entry, and what a record says becomes at most a short pointer to the record.
  - entries kept current: an entry on the same subject is extended rather than duplicated; when a session shows it is wrong, it is corrected in place; an entry the CLAUDE.md now states is removed
  - knowledge without a project into `general/knowledge.md`, private knowledge into `private/knowledge.md`
  - changes to lists such as the shopping list, if the session touched them
- **After every run**, dory compares the knowledge files with their state before it. A removed entry, a rewritten lead, a change to your notes (undone) and a file the run had no business writing are listed in `runs.log`, and `dory status` shows today's counts.
- **When a session starts**, a hook injects the project's notes and knowledge, then the general ones, as the files are. When they no longer fit the limit, it loads a summary the worker made of them in the background, with the paths of the full files. Sessions of the project still waiting in the queue are listed with the path to their transcript. What happened in recent sessions is not injected: you know it, and `/dory:search` finds it.

### Commands in Claude Code

| Command | What it does |
|---|---|
| `/dory:save` | Queues the running session right away without ending it. When it ends later, only the rest is processed, as part 2. |
| `/dory:note "Loki port 3100 clashes with Grafana"` | Adds the note, in your words and dated, to the project's `notes.md`. "remember in general: ..." goes to `general/notes.md`, something private to `private/notes.md`, "buy milk" onto the shopping list. The worker reads your notes and never changes them. |
| `/dory:search loki deploy` | Searches the vault and shows each matching entry with its section and file, besides session notes and lists. Claude also uses it on its own when you ask about earlier knowledge. |

### In the terminal

```bash
dory status   # queue, failed entries with reason, last error, API equivalent cost, today's checks
dory retry    # move failed entries back into the queue
dory add-note --scope general "uv instead of pip"   # what /dory:note runs: project, general or private
```

`dory` is in the installed plugin: `~/.claude/plugins/cache/brain/dory/<version>/bin/dory`.

## Requirements

- macOS (snapshots and transcript copies use APFS clones)
- [Claude Code](https://claude.com/claude-code), signed in with your Claude subscription
- [uv](https://docs.astral.sh/uv/) on your `PATH`; it runs the plugin's Python scripts
- [Obsidian](https://obsidian.md) to browse the notes, optional

## Installation

```bash
claude plugin marketplace add cheorges/dory
claude plugin install dory@brain
```

Restart Claude Code. From the next session on, ended sessions land in `~/Obsidian/dory-brain`; to use another folder or language, see [Configuration](#configuration). In Obsidian, open the folder with *Open folder as vault*.

To update:

```bash
claude plugin marketplace update brain
claude plugin update dory@brain
```

To remove:

```bash
claude plugin uninstall dory@brain
```

The vault and the state directory stay where they are.

## Configuration

Create `~/.config/dory-brain/config.toml` if you want to change a default:

```toml
vault = "~/Obsidian/dory-brain"  # where the notes live; not in iCloud Drive, which offloads files
language = "English"             # language the notes are written in, e.g. "German"
model = "sonnet"                 # worker model; "haiku" uses far less of your usage limit
```

`DORY_VAULT` and `DORY_STATE_DIR` override the vault and the state directory.

### Advanced settings

Change these only if you have a reason.

| Setting | Default | Purpose |
|---|---|---|
| `recall_budget_tokens` | `1500` | The limit for what a session start injects; it sits in the context of every session. When the whole text exceeds it and a project's files alone exceed 80 % of it, a summary loads instead of the files. More costs every session; less means a summary sooner. |
| `min_user_messages` | `3` | Sessions with fewer messages from you are skipped, so a quick question does not cost a worker run. Counted over the whole session. |
| `condense_max_tokens` | `30000` | Upper limit for the condensed transcript the worker reads. Longer sessions keep their beginning and end; the middle is cut. |
| `worker_timeout_minutes` | `10` | Without a network, `claude -p` hangs instead of failing. The timeout stops it so the queue keeps moving. Real runs take 20 to 60 seconds. |
| `snapshots_keep` | `50` | How many vault snapshots are kept for undo. A snapshot is taken before every write; APFS clones cost almost no disk space. |

## How it works

```mermaid
flowchart LR
    End[Session ends] --> Queue[Queue]
    Save[/dory:save/] --> Queue
    Queue --> Worker[Worker with claude -p]
    Worker --> Vault[(Obsidian vault)]
    Worker --> Summary[Summary over the limit]
    Note[/dory:note/] --> Vault
    Summary --> Start[Session starts: recall]
    Vault --> Start
    Vault --> Search[/dory:search/]
```

### Queue

The `SessionEnd` hook clones the transcript to `~/.local/state/dory-brain/transcripts/`, queues an entry and starts the worker detached. Claude Code does not wait for it.

### Worker

One worker runs at a time (file lock). For each entry:

1. The transcript is condensed: only what you and Claude wrote is kept. Tool output, attachments and command wrappers are dropped because they carry foreign text and personal data. Secrets are redacted first. Lines processed before are skipped.
2. The vault is snapshotted (see [Undoing a change](#undoing-a-change)).
3. `claude -p` processes the bundle with the writing rules from `plugin/skills/rules/SKILL.md`. The run is restricted (`--restricted`): it sees only the vault and its own bundle, no CLAUDE.md, no settings, no other plugins.
4. A run only counts as a success if the session note exists. On a rate limit or network error the entry stays in the queue and is retried next time. After three real failures it moves to `failed/`, which `dory status` shows.
5. After every run that changed the vault, dory checks it against the state before: it restores the frontmatter keys that place a knowledge file (`type`, `domain`, `paths`) and every `notes.md` the run changed, lists other files the run wrote, and compares the entries of the knowledge files. `runs.log` lists each change.
6. After the queue, the worker writes a summary of every context whose knowledge and notes files exceed 80 % of `recall_budget_tokens`: the project of each session it processed, and every context a session start or `/dory:note` asked for. The run has no tools and gets the files as data; the summary is stored under `~/.local/state/dory-brain/summaries/` with the hash of the text it was made from.

### Projects

A project is a git repository. Worktrees belong to their main repository. Sessions outside a repository have no project; their knowledge goes to `general/`, `private/` or into lists under `notes/`.

### Work and private

`general/` holds work knowledge and `private/` private knowledge. A project is work unless its `knowledge.md` says `domain: private`; to mark one, change that line in its frontmatter. Before that file exists, a project overview from 0.3.0 that says `domain: private` decides, and the worker carries it into the new file. Session notes and lists carry their own `domain` (lists are private unless they say otherwise). In a session in a work project, the start injects nothing private, not even a path, and search does not show it. In a private project and outside a repository both are visible. The boundary only applies to what is loaded and searched; Claude can still read the vault directly.

### Session start

| Session in | Loads |
|---|---|
| a work project | the project's `notes.md` and `knowledge.md`, then `general/notes.md` and `general/knowledge.md` |
| a private project | the same, then `private/notes.md` and `private/knowledge.md` |
| no repository | `general/`, then `private/` |
| a repository dory does not know yet | `general/` |

While the whole text fits `recall_budget_tokens`, the files load as they are. Beyond that, if the files alone exceed 80 % of it, their summary loads, followed by their paths; otherwise the files load cut at the limit. If the files changed since the summary was made, the old summary loads with a line saying so, and the worker makes a new one. Until a first summary exists, the files load cut at the limit.

## The vault

```text
<vault>/
  projects/
    ai-assistant-hub/
      knowledge.md                           the project's knowledge, kept by the worker
      notes.md                               your notes for the project, from /dory:note
  general/
    knowledge.md                             knowledge without a project
    notes.md
  private/
    knowledge.md                             private knowledge
    notes.md
  notes/
    shopping-list.md                         list
    invoices.md                              register
  sessions/2026/10/
    2026-10-09-1432-ai-assistant-hub-abc12345-1.md
```

All files are Obsidian Flavored Markdown with properties in the frontmatter and `[[wikilinks]]`. Other files in `projects/`, `general/` and `private/` come from versions before 0.4.0 (single knowledge notes, project overviews): dory no longer loads, searches or changes them, and you can delete them. Keep the overview of a project you had marked `domain: private` until its `knowledge.md` exists, or set the domain there yourself.

### Undoing a change

The vault has no git. Before every write, dory takes a snapshot (an APFS clone, the last 50 are kept). It is also the way back for an entry a run removed: `runs.log` names the run. Restore a file from there:

```bash
ls ~/.local/state/dory-brain/snapshots/
cp ~/.local/state/dory-brain/snapshots/<timestamp>/projects/x/knowledge.md ~/Documents/dory/projects/x/
```

## Cost

The worker runs on your Claude subscription, not on the API. It removes `ANTHROPIC_API_KEY` from its environment so an API key is never used. The runs count against your usage limit like a normal session.

`dory status` shows an amount in USD anyway: the API equivalent that `claude -p` reports for each run. On 10 real sessions with `sonnet` it was 0.18 to 0.35 USD per session, 20 to 60 seconds each. `haiku` needs about a fifteenth of that.

## Development

```bash
uv run pytest -q && uv run ruff check .     # tests and linter
DORY_LIVE=1 uv run pytest -m live           # live checks against real claude -p (counts against your limit)
```

The live checks use Haiku (`DORY_LIVE_MODEL=sonnet` for another model) and throwaway vaults.

To run the plugin from a clone, add the clone as the marketplace instead: `claude plugin marketplace add ~/Development/dory`. Claude Code then loads the plugin in place, so changes take effect at the next session start or after `/reload-plugins`.

Design and decisions: [Record 001](docs/records/001-second-brain.md), [Record 002](docs/records/002-note-quality.md), [Record 003](docs/records/003-project-knowledge-file.md). What was built and checked per story: [implementation log](docs/implementation-log.md).

## License

[Apache License 2.0](LICENSE). You may use, change and redistribute dory, also commercially. Redistributions and products built on it must include the [NOTICE](NOTICE) file, which credits the author. Changes per version are in the [changelog](CHANGELOG.md).
