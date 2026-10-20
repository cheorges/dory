from dory.entries import Change, diff, parse

KNOWLEDGE = """---
type: knowledge
domain: work
---
A loose paragraph before any section.

## Pitfalls
- **Loki only starts if UID 10001 owns the data directory.** The container exits otherwise.
  Run `chown -R 10001` on it first.
- **Loki only starts if UID 10001 owns the data directory!** Written twice by mistake.
- A plain bullet without a bold lead, long enough that its key is cut at eighty characters.

## Facts
- **The proxy is on port 3128.** Every VM reaches the internet only through it.
"""


def test_entries_are_bullets_and_loose_text_with_a_normalized_key():
    entries = parse(KNOWLEDGE)

    assert [entry.key for entry in entries] == [
        "a loose paragraph before any section",
        "loki only starts if uid 10001 owns the data directory",
        "loki only starts if uid 10001 owns the data directory #2",
        "a plain bullet without a bold lead, long enough that its key is cut at eighty ch",
        "the proxy is on port 3128",
    ]
    assert [entry.section for entry in entries] == ["", "Pitfalls", "Pitfalls", "Pitfalls", "Facts"]
    assert entries[1].lead == "Loki only starts if UID 10001 owns the data directory."
    assert entries[1].text.endswith("Run `chown -R 10001` on it first.")
    assert "type: knowledge" not in entries[0].text


def test_an_empty_file_or_frontmatter_alone_has_no_entries():
    assert parse("") == []
    assert parse("---\ntype: knowledge\n---\n\n## Pitfalls\n\n") == []


BEFORE = """## Pitfalls
- **Loki listens on port 3100.** It clashes with Grafana on the VMs, so Grafana moves to 3001.
- **The probe script needs bash 5.** macOS ships bash 3.2; install it with brew.
- **Backups run at 02:00.** They lock the database for ten minutes.

## Facts
- **The proxy is on port 3128.** Every VM reaches the internet only through it.
- **Customer care reaches the CRM through its facade.** The facade token is its only protection.
"""

AFTER = """## Pitfalls
- **Loki listens on port 3200.** It clashes with Grafana on the VMs, so Grafana moves to 3001.
- **The probe script needs bash 5.** macOS ships bash 3.2; install it with brew before the probe.

## Facts
- **The proxy is on port 3128.** Every VM reaches the internet only through it.
- **Backups run at 02:00.** They lock the database for ten minutes.
- **Obsidian hides files whose name starts with a dot.** Name notes without one.
"""


def test_diff_pairs_a_corrected_lead_and_counts_a_move_as_a_change():
    changes = diff(parse(BEFORE), parse(AFTER))

    assert sorted(changes, key=lambda change: (change.change, change.lead)) == [
        Change("added", "Obsidian hides files whose name starts with a dot."),
        Change("changed", "Backups run at 02:00."),
        Change("changed", "Loki listens on port 3200.", was="Loki listens on port 3100."),
        Change("changed", "The probe script needs bash 5."),
        Change("removed", "Customer care reaches the CRM through its facade."),
    ]


def test_an_unchanged_file_has_no_changes_and_new_text_is_added():
    assert diff(parse(BEFORE), parse(BEFORE)) == []
    assert diff([], parse(BEFORE))[0] == Change("added", "Loki listens on port 3100.")


def test_a_long_corrected_entry_is_still_paired():
    before = (
        "- **Loki only starts if UID 10001 owns its data directory.** The container runs as UID"
        " 10001 and exits at start when the directory belongs to root. Run `chown -R 10001` on"
        " the data directory before `docker compose up`, also after restoring a backup.\n"
    )
    after = (
        "- **Loki starts only when UID 10001 owns the data directory.** The container runs as"
        " UID 10001 and stops at start when root owns the directory. Run `chown -R 10001` on the"
        " data directory before `docker compose up`, and again after a backup is restored.\n"
    )

    [change] = diff(parse(before), parse(after))

    assert change.change == "changed"
    assert change.was == "Loki only starts if UID 10001 owns its data directory."


def test_a_short_entry_corrected_into_a_longer_one_is_still_paired():
    before = "- **Loki runs on port 3100.** Port 3100 is the default.\n"
    after = (
        "- **Loki runs on port 3200, because Grafana takes port 3100.** This holds on all VMs, "
        "so the configuration of every VM uses 3200 for Loki.\n"
    )

    [change] = diff(parse(before), parse(after))

    assert change == Change(
        "changed",
        "Loki runs on port 3200, because Grafana takes port 3100.",
        was="Loki runs on port 3100.",
    )


def test_a_lead_that_drops_the_old_leads_words_does_not_pair():
    before = "- **Loki runs on port 3100.** Grafana reads the customer logs from there.\n"
    after = "- **Loki needs chrony on every VM.** Without it, pushes are rejected as too old.\n"

    changes = diff(parse(before), parse(after))

    assert sorted(change.change for change in changes) == ["added", "removed"]
