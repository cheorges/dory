from pathlib import Path

import pytest

from dory.links import private_notes


@pytest.fixture
def vault(tmp_path) -> Path:
    vault = tmp_path / "vault"
    for relative in (
        "private/Employment contract.md",
        "private/family/Holidays.md",
        "private/family/Second.md",
        "notes/Notion.md",
        "outside.md",
    ):
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n")
    return vault


CONTRACT = Path("private/Employment contract.md")
HOLIDAYS = Path("private/family/Holidays.md")


def test_a_path_from_the_vault_root_and_a_bare_name_both_find_the_note(vault):
    text = "See [[private/Employment contract]] and [[Holidays]]."

    assert private_notes(vault, text) == [CONTRACT, HOLIDAYS]


def test_case_alias_heading_embed_and_suffix_do_not_matter(vault):
    text = (
        "![[employment CONTRACT.md|the contract]]\n"
        "[[private/family/holidays#Summer]]\n"
        "[[Private/Employment contract]]\n"
    )

    assert private_notes(vault, text) == [CONTRACT, HOLIDAYS]


def test_markdown_links_with_encoded_or_bracketed_targets_count(vault):
    text = "[contract](private/Employment%20contract.md) and [h](<private/family/Holidays.md>)"

    assert private_notes(vault, text) == [CONTRACT, HOLIDAYS]


def test_each_note_counts_once_in_the_order_of_its_first_link(vault):
    text = "[[Holidays]] then [[private/Employment contract]] then [[holidays]] again"

    assert private_notes(vault, text) == [HOLIDAYS, CONTRACT]


def test_links_inside_code_are_ignored(vault):
    text = "```\n[[private/Employment contract]]\n```\nInline `[[Holidays]]` too.\n"

    assert private_notes(vault, text) == []


def test_targets_outside_private_never_load(vault, tmp_path):
    secret = tmp_path / "secret.md"
    secret.write_text("outside the vault\n")
    (vault / "private" / "escape.md").symlink_to(secret)
    (vault / "private" / "family" / "Second.md").unlink()
    (vault / "private" / "family" / "Second.md").symlink_to(vault / "outside.md")
    text = (
        "[[notes/Notion]] [[private/../notes/Notion]] [[private/../outside]] "
        "[[private/escape]] [[Second]] [[outside]]"
    )

    assert private_notes(vault, text) == []


def test_a_missing_target_or_an_empty_link_is_ignored(vault):
    assert private_notes(vault, "[[private/Gone]] [[Gone]] [[]] [x]()") == []


def test_a_vault_without_a_private_folder_has_no_private_notes(tmp_path):
    assert private_notes(tmp_path / "vault", "[[Holidays]] [[private/Holidays]]") == []


def test_a_private_folder_that_is_itself_a_link_still_works(tmp_path):
    elsewhere = tmp_path / "encrypted" / "private"
    elsewhere.mkdir(parents=True)
    (elsewhere / "Taxes.md").write_text("taxes\n")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "private").symlink_to(elsewhere)

    assert private_notes(vault, "[[Taxes]] [[private/taxes]]") == [Path("private/Taxes.md")]


def test_an_alias_escaped_for_a_table_still_finds_the_note(vault):
    text = "| Contract | [[private/Employment contract\\|contract]] |\n| [[Holidays\\|h]] | x |\n"

    assert private_notes(vault, text) == [CONTRACT, HOLIDAYS]


def test_indented_and_unclosed_code_blocks_hide_their_links(vault):
    text = (
        "- An example:\n  ```\n  [[private/Employment contract]]\n  ```\n"
        "[[Holidays]]\n```\n[[private/family/Second]] runs to the end\n"
    )

    assert private_notes(vault, text) == [HOLIDAYS]
