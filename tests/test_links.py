from pathlib import Path

import pytest

from dory.links import library_entries


@pytest.fixture
def vault(tmp_path) -> Path:
    vault = tmp_path / "vault"
    for relative in (
        "library/Employment contract.md",
        "library/family/Holidays.md",
        "library/family/Second.md",
        "notes/Notion.md",
        "outside.md",
    ):
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n")
    return vault


CONTRACT = Path("library/Employment contract.md")
HOLIDAYS = Path("library/family/Holidays.md")


def test_a_path_from_the_vault_root_and_a_bare_name_both_find_the_note(vault):
    text = "See [[library/Employment contract]] and [[Holidays]]."

    assert library_entries(vault, text) == [CONTRACT, HOLIDAYS]


def test_case_alias_heading_embed_and_suffix_do_not_matter(vault):
    text = (
        "![[employment CONTRACT.md|the contract]]\n"
        "[[library/family/holidays#Summer]]\n"
        "[[Library/Employment contract]]\n"
    )

    assert library_entries(vault, text) == [CONTRACT, HOLIDAYS]


def test_markdown_links_with_encoded_or_bracketed_targets_count(vault):
    text = "[contract](library/Employment%20contract.md) and [h](<library/family/Holidays.md>)"

    assert library_entries(vault, text) == [CONTRACT, HOLIDAYS]


def test_each_note_counts_once_in_the_order_of_its_first_link(vault):
    text = "[[Holidays]] then [[library/Employment contract]] then [[holidays]] again"

    assert library_entries(vault, text) == [HOLIDAYS, CONTRACT]


def test_links_inside_code_are_ignored(vault):
    text = "```\n[[library/Employment contract]]\n```\nInline `[[Holidays]]` too.\n"

    assert library_entries(vault, text) == []


def test_targets_outside_the_library_never_load(vault, tmp_path):
    secret = tmp_path / "secret.md"
    secret.write_text("outside the vault\n")
    (vault / "library" / "escape.md").symlink_to(secret)
    (vault / "library" / "family" / "Second.md").unlink()
    (vault / "library" / "family" / "Second.md").symlink_to(vault / "outside.md")
    text = (
        "[[notes/Notion]] [[library/../notes/Notion]] [[library/../outside]] "
        "[[library/escape]] [[Second]] [[outside]]"
    )

    assert library_entries(vault, text) == []


def test_a_missing_target_or_an_empty_link_is_ignored(vault):
    assert library_entries(vault, "[[library/Gone]] [[Gone]] [[]] [x]()") == []


def test_a_vault_without_a_library_has_no_entries(tmp_path):
    assert library_entries(tmp_path / "vault", "[[Holidays]] [[library/Holidays]]") == []


def test_a_library_folder_that_is_itself_a_link_still_works(tmp_path):
    elsewhere = tmp_path / "encrypted" / "library"
    elsewhere.mkdir(parents=True)
    (elsewhere / "Taxes.md").write_text("taxes\n")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "library").symlink_to(elsewhere)

    assert library_entries(vault, "[[Taxes]] [[library/taxes]]") == [Path("library/Taxes.md")]


def test_an_alias_escaped_for_a_table_still_finds_the_note(vault):
    text = "| Contract | [[library/Employment contract\\|contract]] |\n| [[Holidays\\|h]] | x |\n"

    assert library_entries(vault, text) == [CONTRACT, HOLIDAYS]


def test_indented_and_unclosed_code_blocks_hide_their_links(vault):
    text = (
        "- An example:\n  ```\n  [[library/Employment contract]]\n  ```\n"
        "[[Holidays]]\n```\n[[library/family/Second]] runs to the end\n"
    )

    assert library_entries(vault, text) == [HOLIDAYS]
