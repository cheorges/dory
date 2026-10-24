from pathlib import Path

from dory import catalog
from dory.project import Project


def write(vault: Path, relative: str, text: str) -> None:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def knowledge(domain: str = "work", body: str = "") -> str:
    return f"---\ntype: knowledge\ndomain: {domain}\nupdated: 2026-10-20\n---\n{body}"


def project(name: str) -> Project:
    return Project(name=name, root=Path(f"/code/{name}"))


def test_lists_every_knowledge_and_topic_entry_grouped_by_file(tmp_path):
    write(
        tmp_path,
        "projects/hub/knowledge.md",
        knowledge(body="## Pitfalls\n- **Loki logs go to port 3100.** Query the API.\n"),
    )
    write(
        tmp_path,
        "projects/box/knowledge.md",
        knowledge(body="## Facts\n- **The box runs docker-compose 1.28.5.** Old.\n"),
    )
    write(
        tmp_path,
        "notes/GitHub.md",
        "---\ntype: topic\nupdated: 2026-10-23\n---\n## Pitfalls\n"
        "- **Pushing workflows needs the workflow scope.** Use SSH.\n",
    )

    text = catalog.build(tmp_path, project("hub"), private=False)

    assert "## projects/hub/knowledge.md\n" in text
    assert "- Pitfalls: Loki logs go to port 3100." in text
    assert "## projects/box/knowledge.md" in text
    assert "- Facts: The box runs docker-compose 1.28.5." in text
    assert "## notes/GitHub.md\n" in text
    assert text.index("projects/hub/") < text.index("projects/box/")  # the session's own first
    assert "Query the API" not in text  # leads only


def test_leaves_out_the_library_the_users_notes_lists_and_registers(tmp_path):
    write(tmp_path, "projects/hub/knowledge.md", knowledge())
    write(tmp_path, "library/Finance/Taxes.md", "## Facts\n- **Secret tax fact.** x\n")
    write(
        tmp_path,
        "projects/hub/notes/Release steps.md",
        "---\ntype: note\n---\n## How-to\n- **Users note lead.** x\n",
    )
    write(tmp_path, "notes/Shopping.md", "---\ntype: list\n---\n- [ ] **Milk**\n")
    write(tmp_path, "notes/Invoices.md", "---\ntype: register\n---\n- **Invoice 12** paid\n")

    text = catalog.build(tmp_path, project("hub"), private=False)

    for leaked in ("Secret tax", "Users note", "Milk", "Invoice"):
        assert leaked not in text


def test_a_private_session_sees_no_other_project(tmp_path):
    write(tmp_path, "projects/home/knowledge.md", knowledge("private", "## Facts\n- **Own.** x\n"))
    write(tmp_path, "projects/hub/knowledge.md", knowledge(body="## Facts\n- **Work.** x\n"))

    text = catalog.build(tmp_path, project("home"), private=True)

    assert "Own." in text
    assert "Work." not in text


def test_a_private_project_stays_out_of_other_sessions(tmp_path):
    write(tmp_path, "projects/home/knowledge.md", knowledge("private", "## Facts\n- **Own.** x\n"))
    write(tmp_path, "projects/hub/knowledge.md", knowledge(body="## Facts\n- **Work.** x\n"))

    assert "Own." not in catalog.build(tmp_path, project("hub"), private=False)
    assert "Own." not in catalog.build(tmp_path, None, private=False)


def test_long_leads_are_cut_and_a_hundred_entries_stay_small(tmp_path):
    lead = "A very long lead " * 20
    body = "## Facts\n" + "".join(f"- **{index} {lead}.** x\n" for index in range(100))
    write(tmp_path, "projects/hub/knowledge.md", knowledge(body=body))

    text = catalog.build(tmp_path, project("hub"), private=False)

    assert max(len(line) for line in text.splitlines() if line.startswith("- ")) <= 120
    assert "…" in text
    assert len(text) <= 13_000


def test_an_empty_vault_says_so(tmp_path):
    assert "No entries yet." in catalog.build(tmp_path, None, private=False)


def test_an_unreadable_file_is_skipped(tmp_path):
    (tmp_path / "projects" / "odd" / "knowledge.md").mkdir(parents=True)  # a folder, not a file
    write(tmp_path, "projects/hub/knowledge.md", knowledge(body="## Facts\n- **Work.** x\n"))

    assert "Work." in catalog.build(tmp_path, project("hub"), private=False)


def test_flags_stand_next_to_their_entry(tmp_path):
    write(tmp_path, "notes/GitHub.md", "---\ntype: topic\n---\n- **Push needs a scope.** x\n")
    flags = {"notes/GitHub.md": {"push needs a scope": ["unchanged since 2026-06-01"]}}

    text = catalog.build(tmp_path, None, private=False, flags=flags)

    assert "- Push needs a scope. [unchanged since 2026-06-01]" in text
