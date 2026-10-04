# Types

This file is the register of note types and folders in this vault. dory reads it on every write and may extend it under the limits below. You can edit it; your changes are respected.

The `type` field in a note's frontmatter is authoritative. Folders are for orientation only.

## Limits

min_notes_for_new_type: 3
max_types: 8
min_notes_for_subfolder: 5
max_subfolder_depth: 1

- A new type is only created when at least `min_notes_for_new_type` existing notes would belong to it and no existing type fits.
- A new type needs a complete entry in this file (folder, when it applies with an example, when it does not, template) and a template in `templates/`.
- At most `max_types` types. Beyond that, extend an existing type instead.
- A subfolder inside a project only once it would hold `min_notes_for_subfolder` notes of the same kind, at most `max_subfolder_depth` level deep.
- New relation keys in frontmatter follow the same rules as new types.
- Every new type, folder and relation key gets a line in `log.md` with the reason.

## session

- Folder: `sessions/`
- Applies to: what happened in one Claude Code session. Raw record, never rewritten except to append when the same session continues. Example: `2026-10-03 dory plugin design`.
- Does not apply to: knowledge that outlives the session. That goes into a project, topic or decision.
- Template: `templates/session.md`

## project

- Folder: `projects/<name>/`, main page `projects/<name>/<name>.md`
- Applies to: a working context, by default one per git repository or working folder. Example: `dory`.
- Does not apply to: something that recurs across projects. That is a topic.
- Template: `templates/project.md`

## topic

- Folder: `topics/`
- Applies to: something that comes up in more than one project: a customer, technology, tool or recurring error. Sub-kinds are tags (`kunde`, `werkzeug`, `fehler`). Example: `Obsidian`.
- Does not apply to: a term used in one project only. That belongs on the project page.
- Template: `templates/topic.md`

## decision

- Folder: `decisions/`
- Applies to: a choice between real alternatives whose reason is not obvious. Example: `No git in vault`.
- Does not apply to: small implementation choices. Those stay in the session note under `## Decisions`.
- Template: `templates/decision.md`

## Relations

- `project`: the note belongs to this project
- `topics`: the note deals with these topics (list)
- `supersedes`: the note replaces this older note
