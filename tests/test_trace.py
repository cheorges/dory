from dory import entries, trace

BEFORE = (
    "---\ntype: topic\n---\n## Pitfalls\n"
    "- **Loki listens on port 3100.** Grafana takes 3000.\n"
    "- **The probe needs bash 5.** macOS ships 3.2.\n"
    "- **Redis needs allkeys-lru.** Otherwise sessions fail.\n"
)


def test_diff_keeps_the_previous_text_of_changed_and_removed_entries():
    after = (
        "---\ntype: topic\n---\n## Pitfalls\n"
        "- **Loki listens on port 3200.** Grafana takes 3000.\n"  # re-led
        "- **Redis needs allkeys-lru.** Otherwise KoliChat sessions fail.\n"  # changed
        "- **Chrony must run on every VM.** Loki rejects old samples.\n"  # added
    )
    changes = {c.lead: c for c in entries.diff(entries.parse(BEFORE), entries.parse(after))}

    assert changes["Loki listens on port 3200."].before.endswith("Grafana takes 3000.")
    assert "Otherwise sessions fail." in changes["Redis needs allkeys-lru."].before
    assert changes["The probe needs bash 5."].before.startswith("- **The probe needs bash 5.**")
    assert changes["Chrony must run on every VM."].before == ""


def test_the_section_holds_each_previous_text_in_a_folded_callout():
    replaced = [
        ("projects/hub/knowledge.md", "changed", "- **Loki listens on port 3100.** Old.\n  More."),
        ("notes/GitHub.md", "removed", "- **Push needs a scope.** Use SSH."),
    ]

    text = trace.section(replaced)

    assert text.startswith("## Replaced\n")
    assert (
        "> [!quote]- [[projects/hub/knowledge|hub]] (changed): Loki listens on port 3100." in text
    )
    assert "> - **Loki listens on port 3100.** Old.\n>   More." in text
    assert "> [!quote]- [[notes/GitHub|GitHub]] (removed): Push needs a scope." in text


def test_append_adds_the_section_once_and_nothing_without_changes(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\ntype: session\n---\n## Log\n- Did things.\n")
    replaced = [("notes/GitHub.md", "removed", "- **Push needs a scope.** Use SSH.")]

    trace.append(note, [])
    assert "## Replaced" not in note.read_text()

    trace.append(note, replaced)
    trace.append(note, replaced)  # a repeated check replaces the section
    text = note.read_text()
    assert text.count("## Replaced") == 1
    assert text.index("## Log") < text.index("## Replaced")
    assert text.endswith("> - **Push needs a scope.** Use SSH.\n")


def test_an_entry_with_paragraphs_stays_in_one_callout_and_later_sections_survive(tmp_path):
    text = trace.section([("notes/X.md", "changed", "- **Lead.** First.\n\n  Second paragraph.")])
    assert "> - **Lead.** First.\n>\n>   Second paragraph." in text

    note = tmp_path / "note.md"
    note.write_text("## Log\n- a\n\n## Replaced\n\n> old\n\n## Later\n- keep me\n")
    trace.append(note, [("notes/X.md", "removed", "- **New.** x")])
    result = note.read_text()
    assert "- keep me" in result and "> old" not in result
    assert result.count("## Replaced") == 1


def test_an_unclosed_bold_lead_keeps_the_title_on_one_line():
    text = trace.section([("notes/X.md", "removed", "- **foo\nbar **baz** end")])
    title = next(line for line in text.splitlines() if line.startswith("> [!quote]-"))
    assert "\n" not in title and title.endswith("foo bar **baz** end")


def test_a_failed_attempts_trace_waits_for_the_attempt_that_finishes(tmp_path):
    from dory.state import StateDir

    state = StateDir(tmp_path).ensure()
    first = [("notes/X.md", "changed", "- **Old.** x")]
    trace.keep(state, "e1", first)
    trace.keep(state, "e1", [("notes/Y.md", "removed", "- **Gone.** y")])

    assert trace.take(state, "e1") == [*first, ("notes/Y.md", "removed", "- **Gone.** y")]
    assert trace.take(state, "e1") == []
