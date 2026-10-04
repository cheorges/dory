# dory 🐠

dory is a Claude Code plugin that gives Claude a second brain in an Obsidian vault. After every interactive session it writes a session note and updates the notes of the project, topics and decisions the session touched. When a new session starts in a project folder, Claude gets the current state and open points of that project, and it can search the vault for anything older.

The vault stays readable without Claude: plain Markdown, English folder names, a `types.md` that explains the structure, and a `hot.md` with the notes that are currently active.

## Requirements

- Claude Code with plugin support
- Python 3.9 or newer on the `PATH` as `python3`; dory uses only the standard library
- An Obsidian vault (any folder works; Obsidian itself is only needed to read the notes)

Tested on macOS.

## Installation

```
claude plugin marketplace add kepano/obsidian-skills
claude plugin marketplace add cheorges/dory
claude plugin install dory@dory
```

`obsidian@obsidian-skills` is installed as a dependency. The install dialog asks for the options below; they can be changed later under `/config`.

Two settings are needed once:

1. macOS access to the vault. A vault inside `~/Library/CloudStorage` (OneDrive, iCloud) or `~/Documents` is protected by macOS. Give your terminal (and herdr, if you use it) Full Disk Access under System Settings > Privacy & Security, then restart it. Without it dory reports "Vault not writable" in the start block and writes nothing.
2. An allow rule for writes from `/dory:save` and `/dory:note`. Add it for the vault to `~/.claude/settings.json`:

   ```json
   "permissions": { "allow": ["Edit(~/Obsidian/Vault/**)"] }
   ```

   Use your own vault path, starting with `~/` or with `//` for an absolute path. The rule covers Write and Edit and only inside the vault. Without it, each note written in-session asks for approval. The background run does not need it.

## Configuration

| Option | Default | Purpose |
|---|---|---|
| `vault_path` | (required) | Folder of the Obsidian vault |
| `note_language` | `English` | Language of the note content; folders, templates and headings stay English |
| `active_days` | `14` | Notes touched within this many days count as active |
| `writer_model` | `sonnet` | Model of the background run (`sonnet`, `haiku`, `opus`) |
| `min_user_messages` | `3` | Sessions with fewer of your messages get no note; slash commands do not count |
| `auto_capture` | `true` | Background run after each session; `/dory:save` and `/dory:note` always work |
| `exclude_paths` | empty | Working folders that are never written automatically |

## Commands

| Command | What it does |
|---|---|
| `/dory:search <question>` | Searches the vault and answers with source and date. Claude also uses it on its own when an earlier project, customer or decision comes up |
| `/dory:save` | Writes the current session now, with the full context of the running session. Useful before `/clear` when the work continues |
| `/dory:note <subject>` | Writes or updates one project, topic or decision note without a session note |

## Where things live

- Notes: in the vault, under `sessions/`, `projects/`, `topics/`, `decisions/`, plus `types.md`, `hot.md` and `log.md` (one line per write). dory never deletes anything in the vault and never runs git there.
- State: `~/.claude/plugins/data/dory-dory/` holds the queue, the processed sessions, `errors.log` and `events.log` (one line per session start and end, with its source or reason).

To pause the background run, set `auto_capture` to `false`. To keep a folder out of the vault, add it to `exclude_paths`.

## Known limits

- A note appears about 10 to 30 seconds after the session ends; the background run uses `claude -p` and counts against your plan limits (a long session with `sonnet` costs from about 0.25 USD, more when it touches many notes).
- A session that is killed hard (`herdr pane close`, `kill -9`) sends no session end. dory catches it up at the next session start once its transcript has been idle for 2 hours. Closing a terminal window normally is fine.
- Sessions from before the installation are not imported.
- Running sessions that sit idle for 2 hours are written by the catch-up; when they continue, only the new part is appended to the same note.

## License

MIT, see [LICENSE](LICENSE). Changes are listed in [CHANGELOG.md](CHANGELOG.md).
