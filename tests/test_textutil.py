from rfpx.textutil import clean_cell, is_verbatim, locate, match_key, split_number, squash


def test_squash_folds_whitespace_quotes_and_dashes():
    assert squash("The  Proponent shall\n describe “its” plan – in detail") == 'The Proponent shall describe "its" plan - in detail'


def test_squash_expands_ligatures_and_drops_invisible_characters():
    assert squash("oﬃce​ hours­") == "office hours"


def test_is_verbatim_ignores_layout_but_not_wording():
    source = "3.1 The Proponent shall describe its\nimplementation approach and timeline."
    assert is_verbatim("The Proponent shall describe its implementation approach and timeline.", source)
    assert not is_verbatim("The Proponent must describe its implementation approach.", source)


def test_is_verbatim_tolerates_a_dropped_final_full_stop():
    source = "Describe your support model. Include hours of coverage."
    assert is_verbatim("Describe your support model", source)
    assert is_verbatim("Describe your support model.", source)


def test_is_verbatim_is_case_sensitive():
    assert not is_verbatim("describe your support model.", "Describe your support model.")


def test_locate_returns_start_offset_in_squashed_source():
    source = "Intro text. Describe your support model. More text."
    assert locate("Describe your support model.", source) == source.index("Describe")
    assert locate("Not there", source) == -1


def test_split_number_separates_printed_number_from_text():
    assert split_number("3.2.1 The Proponent shall provide references.") == ("3.2.1", "The Proponent shall provide references.")
    assert split_number("(a) Describe your backup process.") == ("(a)", "Describe your backup process.")
    assert split_number("Q12. Do you hold ISO 27001?") == ("Q12.", "Do you hold ISO 27001?")
    assert split_number("R-014 The system shall support SAML 2.0.") == ("R-014", "The system shall support SAML 2.0.")
    assert split_number("Describe your approach.") == (None, "Describe your approach.")


def test_split_number_does_not_eat_ordinary_words_or_years():
    assert split_number("2026 pricing must be held for 90 days.") == (None, "2026 pricing must be held for 90 days.")
    assert split_number("A single point of contact must be named.") == (None, "A single point of contact must be named.")
    assert split_number("I confirm the above.") == (None, "I confirm the above.")


def test_match_key_makes_near_identical_texts_equal():
    a = "Describe your approach to data backup."
    b = "describe  your approach to data backup"
    assert match_key(a) == match_key(b)
    assert match_key(a) != match_key("Describe your approach to data recovery.")


def test_clean_cell_strips_control_characters_but_keeps_text():
    assert clean_cell("a\x00b\x0bc\x1fd\te") == "abcd\te"
    assert clean_cell(None) == ""
    assert clean_cell(12.0) == "12"
