"""`dory library-candidates`: the files that should link a new library entry, and the entries
that may already cover it (Record 009, Story 4)."""

import io
import subprocess
from pathlib import Path

import pytest

from dory.candidates import Draft, candidates, parse_draft, render
from dory.cli import main
from dory.config import Config
from dory.project import Project, project_for_root
from dory.state import StateDir

DORY = Project("dory", Path("/code/dory"))


def write(vault: Path, relative: str, text: str) -> None:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def note(text: str) -> str:
    return f"---\ntype: note\n---\n{text}"


def topic(text: str) -> str:
    return f"---\ntype: topic\n---\n{text}"


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    write(root, "projects/dory/knowledge.md", "---\ntype: knowledge\ndomain: work\n---\n")
    write(root, "projects/dory/notes/Release steps.md", note("Tag on main after the merge.\n"))
    write(root, "projects/dory/notes/Packaging.md", note("We install with [[uv]] only.\n"))
    write(root, "projects/dory/notes/Unrelated.md", note("Nothing about packages at all.\n"))
    write(
        root, "notes/Python.md", topic("## Facts\n- **uv locks the versions of every package.**\n")
    )
    write(root, "notes/Shopping list.md", "---\ntype: list\n---\n- [ ] uv lamp\n")
    write(
        root, "library/Python/Package management.md", "---\ntype: library\naliases: [uv]\n---\nx\n"
    )
    write(root, "library/Tools/uv package manager.md", "---\ntype: library\n---\nx\n")
    return root


def paths(found) -> list[str]:
    return [candidate.path.as_posix() for candidate in found]


def test_a_file_with_an_unresolved_link_to_the_title_ranks_first(vault):
    links, _ = candidates(vault, DORY, Draft("uv", [], "uv locks the versions."))

    assert paths(links)[0] == "projects/dory/notes/Packaging.md"
    assert "links [[uv]]" in "; ".join(links[0].reasons)


def test_a_mention_of_an_alias_counts_and_lists_and_unrelated_files_do_not(vault):
    links, _ = candidates(vault, DORY, Draft("Lock files", ["uv"], "Reproducible installs."))

    assert "notes/Python.md" in paths(links)
    assert "notes/Shopping list.md" not in paths(links)
    assert "projects/dory/notes/Unrelated.md" not in paths(links)


def test_an_entry_with_the_same_title_in_another_folder_or_a_shared_alias_is_a_duplicate(vault):
    _, by_title = candidates(vault, DORY, Draft("uv package manager", [], "x"))
    _, by_alias = candidates(vault, DORY, Draft("Lock files", ["UV"], "x"))

    assert "library/Tools/uv package manager.md" in paths(by_title)
    assert paths(by_alias) == ["library/Python/Package management.md"]


def test_code_and_existing_links_are_no_mentions(vault):
    write(vault, "notes/Shell.md", topic("```bash\nrestic backup\n```\nUse `restic` here.\n"))
    write(vault, "notes/Links.md", topic("See [[library/Backups/restic|restic]].\n"))

    links, _ = candidates(vault, DORY, Draft("restic", [], "Backups."))

    assert not [
        c
        for c in links
        if c.path.name in ("Shell.md", "Links.md") and "mentions" in " ".join(c.reasons)
    ]


def test_a_short_file_name_in_the_draft_is_no_hit_but_a_short_alias_is(vault):
    write(vault, "notes/Go.md", topic("## Facts\n- **Go builds static binaries.**\n"))

    links, _ = candidates(vault, DORY, Draft("Lock files", ["uv"], "We go with it."))

    reasons = {c.path.as_posix(): c.reasons for c in links}
    assert not [r for r in reasons.get("notes/Go.md", []) if r.startswith("its name")]
    assert 'mentions "uv"' in reasons["notes/Python.md"]


def test_a_files_title_in_the_draft_counts(vault):
    links, _ = candidates(vault, DORY, Draft("Tags", [], "The release steps tag main."))

    assert "projects/dory/notes/Release steps.md" in paths(links)


def test_a_private_project_is_left_out_of_another_projects_session(vault):
    write(vault, "projects/home/knowledge.md", "---\ntype: knowledge\ndomain: private\n---\n")
    write(vault, "projects/home/notes/Taxes.md", note("uv and [[uv]].\n"))

    links, _ = candidates(vault, DORY, Draft("uv", [], "x"))

    assert not [p for p in paths(links) if p.startswith("projects/home/")]


def test_the_draft_has_a_title_line_aliases_and_content():
    draft = parse_draft("# uv lock files\naliases: uv, Lockfile\n\nuv writes uv.lock.\n")

    assert draft == Draft("uv lock files", ["uv", "Lockfile"], "uv writes uv.lock.")
    with pytest.raises(ValueError):
        parse_draft("no title line\n")


def test_the_output_has_two_groups_with_load_place_score_and_reasons(vault):
    links, duplicates = candidates(vault, DORY, Draft("uv", ["Package management"], "x"))

    text = render(vault, links, duplicates)

    assert text.startswith("Files to link from, best first:")
    assert "- projects/dory/notes/Packaging.md (loads in dory's sessions; score " in text
    assert "- notes/Python.md (loads in every session; score " in text
    assert "Library entries that may cover the same subject:" in text
    assert "- library/Python/Package management.md (" in text


def test_the_command_reads_the_draft_and_prints_the_groups(vault, tmp_path, monkeypatch, capsys):
    config = Config(vault=vault, state_dir=tmp_path / "state")
    repo = (tmp_path / "code" / "dory").resolve()
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    project_for_root(repo, StateDir(config.state_dir).projects_file)
    monkeypatch.setattr("dory.cli.load_config", lambda: config)
    monkeypatch.chdir(repo)
    monkeypatch.setattr("sys.stdin", io.StringIO("# uv\n\nuv locks.\n"))

    code = main(["library-candidates"])

    out = capsys.readouterr().out
    assert code == 0 and "projects/dory/notes/Packaging.md" in out


def test_a_file_named_with_sharp_s_counts_when_the_draft_holds_the_word(vault):
    write(vault, "notes/Straße.md", topic("## Facts\n- **Streets.**\n"))

    links, _ = candidates(vault, DORY, Draft("Umzug", [], "Die neue Straße hat keine Parkplätze."))

    street = next(c for c in links if c.path.name == "Straße.md")
    assert 'its name "Straße" occurs in the draft' in street.reasons


@pytest.mark.parametrize("link", ["[[uv\\|uv]]", "[[uv.md]]", "[[tools/uv#install|uv]]"])
def test_a_link_in_any_spelling_obsidian_reads_counts(vault, link):
    write(vault, "notes/Table.md", topic(f"| tool | note |\n|---|---|\n| x | {link} |\n"))

    links, _ = candidates(vault, DORY, Draft("uv", [], "x"))

    table = next(c for c in links if c.path.name == "Table.md")
    assert any(r.startswith("links [[uv]]") for r in table.reasons)


def test_a_dotted_name_the_draft_links_is_a_neighbour(vault):
    write(vault, "notes/Node.js.md", topic("## Facts\n- **Runtime.**\n"))

    links, _ = candidates(vault, DORY, Draft("Bundlers", [], "Built with [[Node.js]]."))

    node = next(c for c in links if c.path.name == "Node.js.md")
    assert "the draft links it" in node.reasons


def test_a_common_word_of_the_title_is_no_reason(vault):
    for index in range(12):
        write(vault, f"notes/Filler {index}.md", topic("## Facts\n- **Works with everything.**\n"))

    links, _ = candidates(vault, DORY, Draft("Working with uv", [], "x"))

    assert not [c for c in links if 'mentions "with"' in c.reasons]


def test_a_project_note_linking_a_duplicate_in_its_text_is_a_neighbour(vault):
    write(
        vault,
        "projects/dory/notes/Install.md",
        note("See [[library/Python/Package management|package management]].\n"),
    )

    links, _ = candidates(vault, DORY, Draft("Lock files", ["uv"], "x"))

    install = next(c for c in links if c.path.name == "Install.md")
    assert "links library/Python/Package management" in install.reasons


def test_an_entry_whose_alias_stands_in_the_drafts_title_may_be_a_duplicate(vault):
    _, duplicates = candidates(vault, DORY, Draft("uv sync and the lock file", ["lock file"], "x"))

    assert "library/Python/Package management.md" in paths(duplicates)
