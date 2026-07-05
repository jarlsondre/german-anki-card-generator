"""Unit tests for generate_cards.py — one assertion per test."""

from generate_cards import (
    POS_PRIORITY,
    _assign_disambiguations,
    _describe_variant,
    _pos_rank,
    lookup_entries,
    parse_word_token,
)

# ── parse_word_token ────────────────────────────────────────────


def test_parse_plain_word():
    assert parse_word_token("Mann") == ("Mann", None)


def test_parse_word_with_pos():
    assert parse_word_token("schnell:adv") == ("schnell", "adv")


def test_parse_empty_string_returns_none():
    assert parse_word_token("") is None


def test_parse_whitespace_only_returns_none():
    assert parse_word_token("   ") is None


def test_parse_comment_line_returns_none():
    assert parse_word_token("# this is a comment") is None


def test_parse_strips_whitespace_around_word():
    assert parse_word_token("  Mann  ") == ("Mann", None)


def test_parse_strips_whitespace_around_pos():
    assert parse_word_token("schnell : adv") == ("schnell", "adv")


def test_parse_empty_pos_treated_as_no_filter():
    """`Mann:` should mean `Mann` with no POS pinned (not POS == '')."""
    assert parse_word_token("Mann:") == ("Mann", None)


# ── _pos_rank ───────────────────────────────────────────────────
# Only the fallback branch is non-trivial logic; the happy path is just
# `list.index`, so testing known POS values would just exercise stdlib.


def test_pos_rank_unknown_pos_sorts_last():
    assert _pos_rank("nonsense") == len(POS_PRIORITY)


# ── _describe_variant ───────────────────────────────────────────


def test_describe_variant_without_etym():
    assert _describe_variant({"pos": "noun"}) == "noun"


def test_describe_variant_with_etym_includes_hash():
    assert _describe_variant({"pos": "noun", "etymology_number": 2}) == "noun#2"


def test_describe_variant_missing_pos_uses_placeholder():
    assert _describe_variant({}) == "?"


# ── lookup_entries ──────────────────────────────────────────────
# Only the parts that exercise my own logic are covered: the JUNK_POS
# filter, the rule that the filter is skipped when a POS is pinned, and
# the priority sort. Tests for "WHERE word=?", "WHERE pos=?", and ORDER
# BY would just exercise SQLite.


def test_lookup_without_pos_filter_skips_junk_pos(db_cursor):
    """`un-` is a prefix (in JUNK_POS) and should be filtered when no POS pinned."""
    assert lookup_entries(db_cursor, "un-", None) == []


def test_lookup_with_explicit_junk_pos_includes_it(db_cursor):
    """If the user explicitly pins a junk POS, they get the entry."""
    assert len(lookup_entries(db_cursor, "un-", "prefix")) == 1


def test_lookup_sorts_by_pos_priority(db_cursor):
    """`gut` has adj (rank 2) and adv (rank 3); adj should come first."""
    entries = lookup_entries(db_cursor, "gut", None)
    assert entries[0]["pos"] == "adj"


# ── _assign_disambiguations ─────────────────────────────────────


def test_disambiguate_distinct_plurals_first_gets_first_plural():
    fields = [{"plural": "Bänke"}, {"plural": "Banken"}]
    _assign_disambiguations(fields)
    assert fields[0]["disambiguation"] == "pl. Bänke"


def test_disambiguate_distinct_plurals_second_gets_second_plural():
    """Catches bugs where iteration uses index 0 for everything."""
    fields = [{"plural": "Bänke"}, {"plural": "Banken"}]
    _assign_disambiguations(fields)
    assert fields[1]["disambiguation"] == "pl. Banken"


def test_disambiguate_same_plurals_falls_back_to_roman():
    """When plurals don't distinguish, the Roman fallback fires."""
    fields = [{"plural": "X"}, {"plural": "X"}]
    _assign_disambiguations(fields)
    assert fields[0]["disambiguation"] == "I"


def test_disambiguate_empty_plural_falls_back_to_roman():
    """A missing plural fails `all(plurals)` → fallback, not 'pl. '."""
    fields = [{"plural": ""}, {"plural": "Banken"}]
    _assign_disambiguations(fields)
    assert fields[0]["disambiguation"] == "I"
