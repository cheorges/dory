"""Renames and deletions the worker marks and dory carries out after a successful run."""

from pathlib import Path

from dory import vaultops
from dory.frontmatter import read_frontmatter
from dory.vaultops import apply_marks, current_marks

HUB, INFRA = "ai-assistant-hub", "ai-assistant-hub-infrastructure"


def write(vault: Path, relative: str, text: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def knowledge(vault: Path, relative: str, projects: list[str], extra: str = "") -> Path:
    links = ", ".join(f'"[[{name}]]"' for name in projects)
    return write(
        vault,
        relative,
        f"---\ntype: gotcha\nprojects: [{links}]\ndomain: work\nsummary: Loki port.\n"
        f"status: active\n{extra}created: 2026-10-01\nupdated: 2026-10-01\n---\n"
        "**Why:** Grafana took the port.\n",
    )


def overview(vault: Path, project: str, *knowledge_names: str) -> Path:
    entries = "".join(f"- [[{name}]]\n" for name in knowledge_names)
    return write(
        vault,
        f"projects/{project}/{project}.md",
        f"---\ntype: project\ndomain: work\nsummary: {project}\n---\n"
        f"## Knowledge\n{entries}\n## Sessions\n- [[2026-10-01-0900-{project}-abc-1]]\n",
    )


def test_rename_rewrites_every_link_form_and_nothing_else(tmp_path):
    vault = tmp_path
    old = knowledge(
        vault,
        f"projects/{HUB}/{HUB}-loki-port.md",
        [HUB],
        extra="rename_to: Loki läuft auf Port 3200\n",
    )
    overview(vault, HUB, f"{HUB}-loki-port", f"{HUB}-loki-port-history")
    session = write(
        vault,
        "sessions/2026/10/2026-10-16-1000-ai-assistant-hub-abc-1.md",
        f'---\ntype: session\nsuperseded_by: "[[{HUB}-loki-port]]"\n---\n## Insights\n'
        f"- [[{HUB}-loki-port|the port note]] (corrected)\n"
        f"- see [[{HUB}-loki-port#Why]] and [[{HUB}-loki-port-history]]\n"
        f"The text mentions {HUB}-loki-port without a link.\n",
    )

    changes = apply_marks(vault, HUB)

    new = vault / "projects" / HUB / "Loki läuft auf Port 3200.md"
    assert not old.exists() and new.is_file()
    assert "rename_to" not in new.read_text()
    assert read_frontmatter(new)["summary"] == "Loki port."
    text = session.read_text()
    assert '"[[Loki läuft auf Port 3200]]"' in text
    assert "[[Loki läuft auf Port 3200|the port note]]" in text
    assert "[[Loki läuft auf Port 3200#Why]]" in text
    assert f"[[{HUB}-loki-port-history]]" in text  # a longer name is a different note
    assert f"mentions {HUB}-loki-port without" in text
    assert (
        "- [[Loki läuft auf Port 3200]]\n" in (vault / "projects" / HUB / f"{HUB}.md").read_text()
    )
    assert any("Loki läuft auf Port 3200" in line for line in changes)


def test_a_taken_title_gets_the_project_in_brackets(tmp_path):
    knowledge(tmp_path, "general/Loki läuft auf Port 3200.md", [])
    knowledge(
        tmp_path,
        f"projects/{HUB}/{HUB}-loki-port.md",
        [HUB],
        extra="rename_to: loki läuft auf port 3200\n",
    )

    apply_marks(tmp_path, HUB)

    assert (tmp_path / "projects" / HUB / f"loki läuft auf port 3200 ({HUB}).md").is_file()
    assert (tmp_path / "general" / "Loki läuft auf Port 3200.md").is_file()


def test_forbidden_characters_are_stripped_and_the_title_is_capped(tmp_path):
    knowledge(
        tmp_path,
        f"projects/{HUB}/{HUB}-x.md",
        [HUB],
        extra='rename_to: "Loki: [[Port]] #3200 | a/b \\\\c ^d ' + "lang " * 30 + '"\n',
    )

    apply_marks(tmp_path, HUB)

    (renamed,) = (tmp_path / "projects" / HUB).glob("Loki*.md")
    assert not set(renamed.stem) & set('[]#^|\\/:*"<>?')
    assert len(renamed.stem) <= 100
    assert renamed.stem.startswith("Loki Port 3200 ab c d lang")
    assert not renamed.stem.endswith(" ")


def test_an_archived_note_is_deleted_and_every_link_to_it_goes(tmp_path):
    vault = tmp_path
    gone = knowledge(vault, f"projects/{HUB}/{HUB}-compactor.md", [HUB], extra="status: archived\n")
    gone.write_text(gone.read_text().replace("status: active\n", "", 1))
    overview(vault, HUB, f"{HUB}-compactor", f"{HUB}-retention")
    session = write(
        vault,
        "sessions/2026/10/2026-10-16-1000-ai-assistant-hub-abc-1.md",
        f"---\ntype: session\n---\n## Insights\n- [[{HUB}-compactor|Compactor folder]] (deleted)\n"
        f"- [[{HUB}-retention]] (new)\n",
    )

    changes = apply_marks(vault, HUB)

    assert not gone.exists()
    overview_text = (vault / "projects" / HUB / f"{HUB}.md").read_text()
    assert f"{HUB}-compactor" not in overview_text
    assert f"- [[{HUB}-retention]]" in overview_text
    assert "- Compactor folder (deleted)" in session.read_text()
    assert f"- [[{HUB}-retention]] (new)" in session.read_text()
    assert any(f"{HUB}-compactor" in line for line in changes)


def test_a_note_another_project_lists_is_kept_and_reactivated(tmp_path):
    shared = knowledge(tmp_path, f"projects/{HUB}/{HUB}-loki-compactor.md", [HUB, INFRA], extra="")
    shared.write_text(shared.read_text().replace("status: active", "status: archived"))

    changes = apply_marks(tmp_path, HUB)

    assert shared.is_file()
    assert read_frontmatter(shared)["status"] == "active"
    assert any("reset" in line and shared.stem in line for line in changes)


def test_marks_on_anything_but_a_knowledge_note_are_skipped(tmp_path):
    session = write(
        tmp_path,
        "sessions/2026/10/s-1.md",
        "---\ntype: session\nrename_to: Something else\nstatus: archived\n---\nLog.\n",
    )
    listing = write(
        tmp_path,
        "notes/shopping-list.md",
        "---\ntype: list\nrename_to: Einkauf\nstatus: archived\n---\n- [ ] Milk\n",
    )
    overview_path = overview(tmp_path, HUB)
    overview_path.write_text(
        overview_path.read_text().replace("type: project", "type: project\nstatus: archived")
    )
    before = {path: path.read_text() for path in (session, listing, overview_path)}

    changes = apply_marks(tmp_path, HUB)

    for path, text in before.items():
        assert path.read_text() == text
    assert sum("skipped" in line for line in changes) == 3


def test_a_note_linked_in_from_outside_the_vault_is_never_touched(tmp_path):
    vault, outside = tmp_path / "vault", tmp_path / "outside"
    target = knowledge(outside, "secret.md", [HUB], extra="status: archived\n")
    (vault / "projects" / HUB).mkdir(parents=True)
    (vault / "projects" / HUB / "link.md").symlink_to(target)

    changes = apply_marks(vault, HUB)

    assert target.is_file()
    assert (vault / "projects" / HUB / "link.md").is_symlink()
    assert any("skipped" in line for line in changes)


def test_a_vault_without_marks_stays_unchanged(tmp_path):
    note = knowledge(tmp_path, f"projects/{HUB}/{HUB}-loki.md", [HUB])
    before = note.read_text()

    assert apply_marks(tmp_path, HUB) == []
    assert note.read_text() == before


def test_a_step_that_fails_changes_nothing_and_resets_the_mark(tmp_path):
    marked = knowledge(
        tmp_path, f"projects/{HUB}/{HUB}-port.md", [HUB], extra="rename_to: Loki auf Port 3200\n"
    )
    archived = knowledge(tmp_path, f"projects/{HUB}/{HUB}-compactor.md", [HUB])
    archived.write_text(archived.read_text().replace("status: active", "status: archived"))
    first = write(tmp_path, "notes/a.md", f"[[{HUB}-port]] [[{HUB}-compactor]]\n")
    locked = write(tmp_path, "notes/b.md", f"[[{HUB}-port]] [[{HUB}-compactor]]\n")
    before = {path: path.read_text() for path in (first, locked)}
    locked.chmod(0o444)  # readable, so the change is planned, but the write fails
    try:
        changes = apply_marks(tmp_path, HUB)
    finally:
        locked.chmod(0o644)

    assert [line.split(":")[0] for line in changes] == [
        f"failed projects/{HUB}/{HUB}-compactor.md",
        f"failed projects/{HUB}/{HUB}-port.md",
    ], changes
    assert all("b.md" in line and "reset" in line for line in changes)
    assert {path: path.read_text() for path in (first, locked)} == before
    assert marked.is_file() and "rename_to" not in marked.read_text()
    assert archived.is_file() and read_frontmatter(archived)["status"] == "active"


def test_a_new_mark_on_another_projects_note_is_reset(tmp_path):
    other = knowledge(tmp_path, f"projects/{INFRA}/{INFRA}-x.md", [INFRA])

    for project in (HUB, None):
        other.write_text(other.read_text().replace("status: active", "status: archived"))

        changes = apply_marks(tmp_path, project)

        assert other.is_file() and read_frontmatter(other)["status"] == "active"
        assert changes == [f"reset projects/{INFRA}/{INFRA}-x.md: not a note of this project alone"]


def test_an_embed_of_a_deleted_note_goes_too(tmp_path):
    gone = knowledge(tmp_path, f"projects/{HUB}/{HUB}-x.md", [HUB])
    gone.write_text(gone.read_text().replace("status: active", "status: archived"))
    page = write(tmp_path, "notes/page.md", f"Before ![[{HUB}-x]] after.\n- ![[{HUB}-x]]\n- kept\n")

    apply_marks(tmp_path, HUB)

    assert page.read_text() == f"Before {HUB}-x after.\n- kept\n"


def test_a_mark_on_a_name_two_notes_share_is_skipped(tmp_path):
    decoy = knowledge(tmp_path, f"projects/{HUB}/Loki port.md", [HUB])
    decoy.write_text(decoy.read_text().replace("status: active", "status: archived"))
    real = knowledge(tmp_path, f"projects/{INFRA}/Loki port.md", [INFRA])
    infra_overview = overview(tmp_path, INFRA, "Loki port")
    before = infra_overview.read_text()

    changes = apply_marks(tmp_path, HUB)

    assert decoy.is_file() and real.is_file()
    assert infra_overview.read_text() == before
    assert changes == [f"skipped projects/{HUB}/Loki port.md: another note has the same name"]


def test_control_characters_and_broken_encoding_do_not_block_other_marks(tmp_path):
    nul = knowledge(tmp_path, f"projects/{HUB}/{HUB}-a.md", [HUB], extra="rename_to: Bad\x00Name\n")
    broken = tmp_path / "projects" / HUB / f"{HUB}-b.md"
    header = f'---\ntype: fact\nprojects: ["[[{HUB}]]"]\nstatus: archived\n---\n'
    broken.write_bytes(header.encode() + b"\xff\xfe\n")
    linking = tmp_path / "notes" / "raw.md"
    linking.parent.mkdir(parents=True)
    linking.write_bytes(f"[[{HUB}-a]] \xff\n".encode("latin-1"))

    changes = apply_marks(tmp_path, HUB)

    assert not nul.exists() and (tmp_path / "projects" / HUB / "BadName.md").is_file()
    assert not broken.exists()
    assert linking.read_bytes() == b"[[BadName]] \xff\n"
    assert not any(line.startswith("failed") for line in changes), changes


def test_a_rename_never_replaces_a_symlink_or_a_case_variant(tmp_path):
    folder = tmp_path / "projects" / HUB
    first = knowledge(tmp_path, f"projects/{HUB}/{HUB}-a.md", [HUB], extra="rename_to: Target\n")
    (folder / "Target.md").symlink_to(tmp_path / "elsewhere.md")
    second = knowledge(tmp_path, f"projects/{HUB}/{HUB}-b.md", [HUB], extra="rename_to: Other\n")
    (folder / "Other.MD").write_text("the user's own file\n")

    apply_marks(tmp_path, HUB)

    assert (folder / "Target.md").is_symlink()
    assert (folder / "Other.MD").read_text() == "the user's own file\n"
    assert not first.exists() and not second.exists()
    assert {p.name for p in folder.glob("*.md") if not p.is_symlink()} == {
        f"Target ({HUB}).md",
        f"Other ({HUB}).md",
    }


def test_the_project_in_brackets_is_cleaned_and_never_read_as_a_pattern(tmp_path):
    for project in ("c#-tools", "x\\9"):
        knowledge(tmp_path, f"general/Loki {len(project)}.md", [])
        knowledge(
            tmp_path,
            f"projects/{project}/loki-{len(project)}.md",
            [project],
            extra=f"rename_to: Loki {len(project)}\n",
        )
        page = write(tmp_path, f"notes/{len(project)}.md", f"[[loki-{len(project)}]]\n")

        changes = apply_marks(tmp_path, project)

        cleaned = project.replace("#", "").replace("\\", "")
        assert page.read_text() == f"[[Loki {len(project)} ({cleaned})]]\n", changes


def test_links_with_an_escaped_pipe_in_a_table_follow_too(tmp_path):
    knowledge(tmp_path, f"projects/{HUB}/{HUB}-old.md", [HUB], extra="rename_to: New\n")
    gone = knowledge(tmp_path, f"projects/{HUB}/{HUB}-gone.md", [HUB])
    gone.write_text(gone.read_text().replace("status: active", "status: archived"))
    table = write(
        tmp_path,
        "notes/table.md",
        f"| a | b |\n|---|---|\n| [[{HUB}-old\\|Old]] | [[{HUB}-gone\\|Gone]] |\n",
    )

    apply_marks(tmp_path, HUB)

    assert table.read_text().endswith("| [[New\\|Old]] | Gone |\n")


def test_a_mark_left_by_a_failed_run_is_reset_not_carried_out(tmp_path):
    marked = knowledge(
        tmp_path, f"projects/{HUB}/{HUB}-a.md", [HUB], extra="rename_to: Neuer Titel\n"
    )
    archived = knowledge(tmp_path, f"projects/{HUB}/{HUB}-b.md", [HUB])
    archived.write_text(archived.read_text().replace("status: active", "status: archived"))
    earlier = current_marks(tmp_path)

    changes = apply_marks(tmp_path, HUB, earlier=earlier)

    assert marked.is_file() and "rename_to" not in marked.read_text()
    assert archived.is_file() and read_frontmatter(archived)["status"] == "active"
    assert all(line.startswith("reset") for line in changes) and len(changes) == 2


def test_names_that_only_regex_case_folding_equates_stay_apart(tmp_path):
    decoy = knowledge(tmp_path, f"projects/{HUB}/Lokı port.md", [HUB])
    decoy.write_text(decoy.read_text().replace("status: active", "status: archived"))
    renamed = knowledge(tmp_path, f"projects/{HUB}/İnfra.md", [HUB], extra="rename_to: Evil\n")
    knowledge(tmp_path, f"projects/{INFRA}/Loki port.md", [INFRA])
    knowledge(tmp_path, f"projects/{INFRA}/infra.md", [INFRA])
    infra_overview = overview(tmp_path, INFRA, "Loki port", "infra")
    before = infra_overview.read_text()

    apply_marks(tmp_path, HUB)

    assert not decoy.exists() and not renamed.exists()
    assert infra_overview.read_text() == before


def test_an_old_deletion_mark_does_not_travel_with_a_rename(tmp_path):
    note = knowledge(tmp_path, f"projects/{HUB}/Old title.md", [HUB])
    note.write_text(note.read_text().replace("status: active", "status: archived"))
    earlier = current_marks(tmp_path)
    note.write_text(
        note.read_text().replace("status: archived", "status: archived\nrename_to: New title")
    )

    apply_marks(tmp_path, HUB, earlier=earlier)

    renamed = tmp_path / "projects" / HUB / "New title.md"
    assert renamed.is_file() and read_frontmatter(renamed)["status"] == "active"


def test_a_reset_that_cannot_be_written_is_logged_and_tried_again(tmp_path):
    hub_note = knowledge(tmp_path, f"projects/{HUB}/Hub note.md", [HUB])
    hub_note.write_text(hub_note.read_text().replace("status: active", "status: archived"))
    hub_note.chmod(0o444)
    try:
        changes = apply_marks(tmp_path, INFRA)
    finally:
        hub_note.chmod(0o644)

    assert changes[0].startswith("failed") and hub_note.is_file()
    apply_marks(tmp_path, HUB, earlier=current_marks(tmp_path))
    assert hub_note.is_file() and read_frontmatter(hub_note)["status"] == "active"


def test_a_rename_to_the_current_title_only_removes_the_field(tmp_path):
    note = knowledge(
        tmp_path, f"projects/{HUB}/Loki port.md", [HUB], extra="rename_to: Loki port\n"
    )

    assert apply_marks(tmp_path, HUB) == []
    assert note.is_file() and "rename_to" not in note.read_text()


def test_a_write_that_breaks_off_midway_is_rolled_back_too(tmp_path, monkeypatch):
    knowledge(tmp_path, f"projects/{HUB}/{HUB}-port.md", [HUB], extra="rename_to: Neu\n")
    first = write(tmp_path, "notes/a.md", f"A: [[{HUB}-port]]\n")
    second = write(tmp_path, "notes/b.md", f"B: [[{HUB}-port]]\n")
    before = {path: path.read_text() for path in (first, second)}
    real_write = vaultops._write
    failures = [second]

    def disk_full_once(path, text):
        if path in failures:
            failures.remove(path)
            path.write_text(text[:3])
            raise OSError(28, "No space left on device")
        real_write(path, text)

    monkeypatch.setattr(vaultops, "_write", disk_full_once)
    changes = apply_marks(tmp_path, HUB)
    monkeypatch.setattr(vaultops, "_write", real_write)

    assert changes[0].startswith("failed")
    assert {path: path.read_text() for path in (first, second)} == before


def test_a_multi_line_mark_is_removed_with_its_continuation_lines(tmp_path):
    renamed = knowledge(
        tmp_path,
        f"projects/{HUB}/{HUB}-port.md",
        [HUB],
        extra="rename_to: >-\n  Loki läuft auf Port 3200\n",
    )
    other = knowledge(tmp_path, f"projects/{INFRA}/{INFRA}-x.md", [INFRA])
    other.write_text(other.read_text().replace("status: active", "status:\n  archived"))

    apply_marks(tmp_path, HUB)

    new = tmp_path / "projects" / HUB / "Loki läuft auf Port 3200.md"
    assert not renamed.exists() and read_frontmatter(new)["status"] == "active"
    assert "Loki läuft auf Port 3200\n" not in new.read_text().split("---")[1]
    assert read_frontmatter(other)["status"] == "active"
    assert "archived" not in other.read_text()
