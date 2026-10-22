import unicodedata

import pytest

from dory.names import MAX_BYTES, MAX_CHARACTERS, TitleError, file_stem, is_clean, name_key


def test_characters_that_break_links_or_paths_are_removed():
    assert file_stem("Deploy [only] #fridays ^1 | a/b \\ c: d") == "Deploy only fridays 1 a b c d"


def test_leading_dots_and_trailing_dots_and_spaces_are_removed():
    assert file_stem("..hidden title... ") == "hidden title"


def test_line_breaks_and_runs_of_spaces_become_one_space():
    assert file_stem("Loki\nport \t 3200") == "Loki port 3200"


def test_a_decomposed_umlaut_becomes_its_composed_form():
    decomposed = unicodedata.normalize("NFD", "Prüfung")

    assert file_stem(decomposed) == "Prüfung"
    assert file_stem(decomposed) == unicodedata.normalize("NFC", "Prüfung")


def test_a_long_title_is_cut_at_80_characters():
    stem = file_stem("a" * 120)

    assert len(stem) == MAX_CHARACTERS


def test_a_title_of_wide_characters_is_cut_at_200_bytes():
    four_bytes = "\U0001d11e"  # the G clef, four bytes in UTF-8
    stem = file_stem("ü" * 79)  # 158 bytes, within both limits
    wide = file_stem(four_bytes * 79)

    assert stem == "ü" * 79
    assert len(wide.encode()) <= MAX_BYTES
    assert wide == four_bytes * (MAX_BYTES // 4)


def test_a_cut_does_not_leave_a_trailing_space_or_dot():
    assert file_stem("a" * 79 + " b") == "a" * 79


@pytest.mark.parametrize("title", ["", "   ", "...", "[[]]", "#|^"])
def test_a_title_that_leaves_no_name_is_refused(title):
    with pytest.raises(TitleError):
        file_stem(title)


def test_names_compare_without_case_and_in_their_composed_form():
    assert name_key("Notion") == name_key("notion")
    assert name_key(unicodedata.normalize("NFD", "Prüfung")) == name_key("prüfung")
    assert name_key("Notion") != name_key("Notion API")


def test_a_name_is_clean_when_the_title_rules_leave_it_as_it_is():
    assert is_clean("Notion")
    assert is_clean(unicodedata.normalize("NFD", "Prüfung"))
    assert not is_clean("Notion: API")
    assert not is_clean(".hidden")
    assert not is_clean("")
