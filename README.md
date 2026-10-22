# 🐠 Dory

A memory for Claude Code. Claude forgets everything when a session ends; dory keeps what was learned and gives it back at the next start.

- **When a session ends**, a background worker reads it and writes what matters later into an Obsidian vault: pitfalls, decisions, facts, how-tos. One `knowledge.md` per project, one file per topic for what applies everywhere, and a short note per session.
- **When a session starts**, Claude gets the project's knowledge and your notes for it, plus the topics that fit.
- **In between**, you write down what must not get lost, file knowledge you want to keep, and search everything.

All of it is plain Markdown you can read and edit in Obsidian.

```mermaid
flowchart LR
    End[Session ends] --> Worker[Worker with claude -p]
    Worker --> Vault[(Obsidian vault)]
    Note[/dory:note/] --> Vault
    Library[/dory:library/] --> Vault
    Vault --> Start[Next session starts]
    Vault --> Search[/dory:search/]
```

## Install

Needs macOS, [Claude Code](https://claude.com/claude-code) with your Claude subscription, and [uv](https://docs.astral.sh/uv/).

```bash
claude plugin marketplace add cheorges/dory
claude plugin install dory@brain
```

Restart Claude Code. The vault is `~/Obsidian/dory-brain`; open it in Obsidian with *Open folder as vault*.

## Use

Work as usual: ending a session (`/exit`, `/clear`, closing the tab) is enough. On top of that:

| Command | When |
|---|---|
| `/dory:note "Loki runs on 3200 because Grafana takes 3100"` | Something the next session must know. Claude writes it as a note in the project, or into the matching topic, without asking. |
| `/dory:library "uv instead of pip, because ..."` | Knowledge you want to keep for good. Claude proposes folder, title, content and which notes link it, and writes after your yes. |
| `/dory:search loki deploy` | Find earlier knowledge, notes and sessions in the whole vault. |
| `/dory:save` | Process the running session now, without ending it. |

`dory status` in the terminal shows the queue, failed runs and their cost.

## The vault

```text
projects/<project>/knowledge.md     the project's knowledge, kept by the worker
projects/<project>/notes/           your notes for the project
notes/                              topics, lists and registers without a project
library/                            knowledge you filed; loads where a note links it
sessions/                           one note per session
```

The worker never changes your notes or the library, and dory snapshots the vault before every write.

## Configure

Optional, in `~/.config/dory-brain/config.toml`:

```toml
vault = "~/Obsidian/dory-brain"  # not in iCloud Drive, which offloads files
language = "English"             # language the notes are written in
context = "lean"                 # share of the context window the start may take: lean 5 %, balanced 10 %, rich 15 %
context_window = 200000          # the smallest window you work with, e.g. 1000000
```

## More

- [Guide](docs/guide.md): what happens when, all commands and settings, the files in the vault, undoing a change, upgrading, cost
- [Records](docs/records/): the design decisions; [changelog](CHANGELOG.md)
- Development: `uv run pytest -q && uv run ruff check .`; live checks against real `claude -p` with `DORY_LIVE=1 uv run pytest -m live`

## License

[Apache License 2.0](LICENSE). Redistributions must include the [NOTICE](NOTICE) file, which credits the author.
