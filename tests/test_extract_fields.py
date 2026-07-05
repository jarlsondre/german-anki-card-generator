"""Unit tests for extract_fields.py — one assertion per test."""

from extract_fields import (
    _all_glosses,
    _build_verb_principal_parts,
    _examples,
    _first_form,
    _noun_gender,
    _perfect_aux_form,
    _verb_auxiliary,
    form_of_lemma,
    is_form_of_stub,
)

# ── _first_form ─────────────────────────────────────────────────


def test_first_form_returns_empty_when_no_forms_key():
    assert _first_form({}, {"plural"}) == ""


def test_first_form_returns_empty_when_no_match():
    entry = {"forms": [{"form": "Mann", "tags": ["singular"]}]}
    assert _first_form(entry, {"plural"}) == ""


def test_first_form_finds_matching_form():
    entry = {"forms": [{"form": "Männer", "tags": ["nominative", "plural"]}]}
    assert _first_form(entry, {"nominative", "plural"}) == "Männer"


def test_first_form_requires_all_tags_to_match():
    entry = {"forms": [{"form": "Mann", "tags": ["nominative"]}]}
    assert _first_form(entry, {"nominative", "plural"}) == ""


def test_first_form_tolerates_extra_tags_on_the_form():
    entry = {"forms": [{"form": "Mannes", "tags": ["genitive", "singular", "strong"]}]}
    assert _first_form(entry, {"genitive", "singular"}) == "Mannes"


def test_first_form_returns_first_match_when_multiple():
    entry = {
        "forms": [
            {"form": "Männer", "tags": ["nominative", "plural"]},
            {"form": "Mannen", "tags": ["nominative", "plural"]},
        ]
    }
    assert _first_form(entry, {"nominative", "plural"}) == "Männer"


# ── _all_glosses ────────────────────────────────────────────────


def test_all_glosses_collects_across_senses():
    entry = {"senses": [{"glosses": ["man"]}, {"glosses": ["husband"]}]}
    assert _all_glosses(entry) == ["man", "husband"]


def test_all_glosses_preserves_order():
    entry = {"senses": [{"glosses": ["b", "a", "c"]}]}
    assert _all_glosses(entry) == ["b", "a", "c"]


def test_all_glosses_deduplicates():
    entry = {"senses": [{"glosses": ["good"]}, {"glosses": ["good"]}]}
    assert _all_glosses(entry) == ["good"]


def test_all_glosses_empty_when_no_senses():
    assert _all_glosses({}) == []


# ── _examples ───────────────────────────────────────────────────


def test_examples_prefers_roman_over_text():
    """When both are present, `roman` is the actual German quote and
    `text` is the citation header."""
    entry = {
        "senses": [
            {
                "examples": [
                    {
                        "text": "1925, Citation, page 1",
                        "roman": "Das ist ein Beispiel.",
                        "english": "This is an example.",
                        "type": "quotation",
                    }
                ]
            }
        ]
    }
    assert _examples(entry)[0]["de"] == "Das ist ein Beispiel."


def test_examples_falls_back_to_text_when_no_roman():
    entry = {"senses": [{"examples": [{"text": "Das Auto ist rot.", "english": "The car is red."}]}]}
    assert _examples(entry)[0]["de"] == "Das Auto ist rot."


def test_examples_skips_when_english_missing():
    entry = {"senses": [{"examples": [{"text": "Hallo."}]}]}
    assert _examples(entry) == []


def test_examples_uses_english_field_first():
    """`english` takes priority over `translation` when both are present."""
    entry = {"senses": [{"examples": [{"text": "x", "english": "good", "translation": "wrong"}]}]}
    assert _examples(entry)[0]["en"] == "good"


def test_examples_falls_back_to_translation_field():
    entry = {"senses": [{"examples": [{"text": "x", "translation": "fallback"}]}]}
    assert _examples(entry)[0]["en"] == "fallback"


def test_examples_plain_sorted_before_quotations():
    entry = {
        "senses": [
            {
                "examples": [
                    {"text": "Quote.", "english": "Q.", "type": "quotation"},
                    {"text": "Plain.", "english": "P."},
                ]
            }
        ]
    }
    assert _examples(entry)[0]["de"] == "Plain."


def test_examples_respects_limit():
    entry = {
        "senses": [
            {
                "examples": [
                    {"text": "a", "english": "x"},
                    {"text": "b", "english": "y"},
                    {"text": "c", "english": "z"},
                ]
            }
        ]
    }
    assert len(_examples(entry, limit=2)) == 2


# ── _noun_gender ────────────────────────────────────────────────


def test_noun_gender_masculine():
    entry = {"word": "Mann", "head_templates": [{"expansion": "Mann m (genitive Mannes)"}]}
    assert _noun_gender(entry) == "m"


def test_noun_gender_feminine():
    entry = {"word": "Frau", "head_templates": [{"expansion": "Frau f (genitive Frau)"}]}
    assert _noun_gender(entry) == "f"


def test_noun_gender_neuter():
    entry = {"word": "Auto", "head_templates": [{"expansion": "Auto n (genitive Autos)"}]}
    assert _noun_gender(entry) == "n"


def test_noun_gender_empty_when_no_match():
    entry = {"word": "fahren", "head_templates": [{"expansion": "fahren (class 6 strong)"}]}
    assert _noun_gender(entry) == ""


def test_noun_gender_escapes_regex_special_chars_in_word():
    """A word containing a regex metachar shouldn't break the match."""
    entry = {"word": "a.b", "head_templates": [{"expansion": "a.b m (test)"}]}
    assert _noun_gender(entry) == "m"


# ── _verb_auxiliary ─────────────────────────────────────────────


def test_verb_auxiliary_haben():
    entry = {"head_templates": [{"expansion": "machen (..., auxiliary haben)"}]}
    assert _verb_auxiliary(entry) == "haben"


def test_verb_auxiliary_sein():
    entry = {"head_templates": [{"expansion": "gehen (..., auxiliary sein)"}]}
    assert _verb_auxiliary(entry) == "sein"


def test_verb_auxiliary_both_haben_or_sein():
    entry = {"head_templates": [{"expansion": "fahren (..., auxiliary haben or sein)"}]}
    assert _verb_auxiliary(entry) == "haben or sein"


def test_verb_auxiliary_empty_when_missing():
    entry = {"head_templates": [{"expansion": "Mann m (genitive Mannes)"}]}
    assert _verb_auxiliary(entry) == ""


# ── _perfect_aux_form ───────────────────────────────────────────


def test_perfect_aux_form_haben_becomes_hat():
    assert _perfect_aux_form("haben") == "hat"


def test_perfect_aux_form_sein_becomes_ist():
    assert _perfect_aux_form("sein") == "ist"


def test_perfect_aux_form_either_prefers_ist():
    """When a verb takes either, the sein check fires first → 'ist'."""
    assert _perfect_aux_form("haben or sein") == "ist"


def test_perfect_aux_form_empty_when_unknown():
    assert _perfect_aux_form("") == ""


# ── _build_verb_principal_parts ─────────────────────────────────


def test_principal_parts_embeds_aux_with_participle():
    """Auxiliary lives inside the participle slot, not on its own line."""
    result = _build_verb_principal_parts("machen", "macht", "machte", "gemacht", "haben")
    assert result.endswith("hat gemacht")


def test_principal_parts_drops_aux_when_unknown():
    """Empty auxiliary → bare participle, no leading whitespace."""
    result = _build_verb_principal_parts("x", "xt", "xte", "gext", "")
    assert result == "x, xt, xte, gext"


def test_principal_parts_empty_when_no_conjugations():
    """Bare word with no conjugations yields '' so the template falls back."""
    assert _build_verb_principal_parts("fahren", "", "", "", "") == ""


def test_principal_parts_skips_missing_parts():
    """Empty parts are skipped — `if third:` guards work."""
    assert _build_verb_principal_parts("fahren", "fährt", "", "", "") == "fahren, fährt"


# ── is_form_of_stub ─────────────────────────────────────────────


def test_is_form_of_stub_true_when_form_of_present():
    entry = {"senses": [{"form_of": [{"word": "manch"}]}]}
    assert is_form_of_stub(entry) is True


def test_is_form_of_stub_false_when_form_of_absent():
    entry = {"senses": [{"glosses": ["bench"]}]}
    assert is_form_of_stub(entry) is False


def test_is_form_of_stub_false_when_no_senses():
    """Entries without senses can't be stubs — guard against IndexError."""
    assert is_form_of_stub({}) is False


# ── form_of_lemma ───────────────────────────────────────────────


def test_form_of_lemma_returns_referenced_word():
    entry = {"senses": [{"form_of": [{"word": "manch"}]}]}
    assert form_of_lemma(entry) == "manch"


def test_form_of_lemma_empty_when_form_of_absent():
    entry = {"senses": [{"glosses": ["x"]}]}
    assert form_of_lemma(entry) == ""


def test_form_of_lemma_empty_when_no_senses():
    assert form_of_lemma({}) == ""
