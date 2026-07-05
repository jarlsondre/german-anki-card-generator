"""CLI: turn a list of German words into a rich Anki deck (.apkg).

Usage:
    uv run python generate_cards.py Mann fahren schnell
    uv run python generate_cards.py --file words.txt --output mydeck.apkg
    uv run python generate_cards.py schnell:adv      # pin a POS for ambiguous words

Words come from positional args, from --file (one per line), or both.
A line/arg containing ":" is read as "word:pos" so you can disambiguate
homographs (e.g. schnell:adj vs schnell:adv). Lines beginning with "#"
and blank lines in the words file are ignored.
"""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from deck_builder import build_deck, write_deck
from extract_fields import JUNK_POS, extract, form_of_lemma, is_form_of_stub

HERE = Path(__file__).parent
DEFAULT_DB = HERE / "dictionary.db"

# A spec is (word, pos_filter_or_None).
WordSpec = Tuple[str, "str | None"]

# When no POS is pinned, pick the entry with the highest-priority POS.
POS_PRIORITY: List[str] = [
    "noun",
    "verb",
    "adj",
    "adv",
    "name",
    "num",
    "pron",
    "prep",
    "conj",
    "det",
    "intj",
    "phrase",
    "prep_phrase",
    "proverb",
]


def _pos_rank(pos: str) -> int:
    try:
        return POS_PRIORITY.index(pos)
    except ValueError:
        return len(POS_PRIORITY)


def _describe_variant(entry: Dict[str, Any]) -> str:
    """Short tag for an alternate entry, e.g. 'noun#2' or 'adv'."""
    pos = entry.get("pos", "?")
    etym = entry.get("etymology_number")
    return f"{pos}#{etym}" if etym else pos


_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]


def _assign_disambiguations(group_fields: List[Dict[str, str]]) -> None:
    """Mutate `group_fields` to fill each note's `disambiguation` value.

    Used for true homographs — multiple entries sharing the same word and POS
    but different etymologies (e.g. Bank → bench / financial institution).
    Prefers the plural form when it differs across the group (clean and
    pedagogically useful); falls back to Roman numerals otherwise.
    """
    plurals = [f.get("plural", "") for f in group_fields]
    plurals_distinguish = all(plurals) and len(set(plurals)) == len(plurals)
    if plurals_distinguish:
        for fields, plural in zip(group_fields, plurals, strict=True):
            fields["disambiguation"] = f"pl. {plural}"
        return
    for i, fields in enumerate(group_fields, start=1):
        fields["disambiguation"] = _ROMAN[i] if i < len(_ROMAN) else str(i)


def parse_word_token(token: str) -> "WordSpec | None":
    """Parse a single token into (word, optional pos).

    Returns None for blank tokens and comment lines (starting with '#').
    """
    token = token.strip()
    if not token or token.startswith("#"):
        return None
    if ":" in token:
        word, _, pos = token.partition(":")
        return word.strip(), (pos.strip() or None)
    return token, None


def read_words_file(path: Path) -> List[WordSpec]:
    """Read a words file: one word (optionally `word:pos`) per line."""
    specs: List[WordSpec] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_word_token(raw)
        if parsed is not None:
            specs.append(parsed)
    return specs


def lookup_entries(
    cur: sqlite3.Cursor,
    word: str,
    pos_filter: "str | None",
) -> List[Dict[str, Any]]:
    """Return all kaikki entries for a word, optionally filtered by POS.

    When no POS filter is given, junk POS values (prefix, suffix, character…)
    are dropped so they don't pollute the deck. Results are sorted by POS
    priority so the first entry is the "best" pick for an unspecified lookup.
    """
    if pos_filter:
        rows = cur.execute(
            "SELECT data FROM entries WHERE word = ? AND pos = ? ORDER BY id",
            (word, pos_filter),
        ).fetchall()
    else:
        rows = cur.execute(
            "SELECT data FROM entries WHERE word = ? ORDER BY id",
            (word,),
        ).fetchall()
    entries: List[Dict[str, Any]] = [json.loads(r[0]) for r in rows]
    if not pos_filter:
        entries = [e for e in entries if e.get("pos") not in JUNK_POS]
    entries.sort(key=lambda e: _pos_rank(e.get("pos", "")))
    return entries


def collect_specs(args: argparse.Namespace) -> List[WordSpec]:
    """Combine specs from --file and positional args, preserving order."""
    specs: List[WordSpec] = []
    if args.file:
        specs.extend(read_words_file(args.file))
    for token in args.words:
        parsed = parse_word_token(token)
        if parsed is not None:
            specs.append(parsed)
    return specs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a rich Anki deck for German vocabulary from a kaikki index.",
    )
    parser.add_argument(
        "words",
        nargs="*",
        help="Words to include. Use `word:pos` to pin a POS (e.g. schnell:adv).",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Path to a .txt file with one word (optionally `word:pos`) per line.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("german.apkg"),
        help="Output .apkg path (default: german.apkg).",
    )
    parser.add_argument(
        "--deck",
        "-d",
        default="German Vocabulary",
        help="Deck name shown inside Anki (default: 'German Vocabulary').",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to the SQLite index (default: {DEFAULT_DB}).",
    )
    return parser


def main(argv: "List[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.db.exists():
        print(f"DB not found: {args.db}. Run build_index.py first.")
        return 1

    specs = collect_specs(args)
    if not specs:
        print("No words given. Pass words as args, or use --file PATH.")
        return 1

    conn = sqlite3.connect(args.db)
    try:
        cur = conn.cursor()
        notes: List[Dict[str, str]] = []
        seen: Set[Tuple[str, str, str]] = set()
        missing: List[WordSpec] = []
        extras: List[Tuple[str, List[str]]] = []
        redirects: List[Tuple[str, str]] = []
        for word, pos_filter in specs:
            entries = lookup_entries(cur, word, pos_filter)
            if not entries:
                missing.append((word, pos_filter))
                continue

            # If the word is purely an inflected form (e.g. `manche` → `manch`,
            # `fährt` → `fahren`), re-look-up the lemma and use that data.
            if all(is_form_of_stub(e) for e in entries):
                lemma = form_of_lemma(entries[0])
                if not lemma:
                    missing.append((word, pos_filter))
                    continue
                lemma_entries = lookup_entries(cur, lemma, pos_filter)
                if not lemma_entries:
                    missing.append((word, pos_filter))
                    continue
                redirects.append((word, lemma))
                entries = lemma_entries

            # Homographs sharing the top-priority POS each get their own note;
            # entries at lower-priority POS values are merely reported as
            # variants the user could pin explicitly.
            best_pos = entries[0]["pos"]
            homograph_group = [e for e in entries if e["pos"] == best_pos]
            other_pos_entries = [e for e in entries if e["pos"] != best_pos]

            group_fields = [extract(e) for e in homograph_group]
            if len(group_fields) > 1:
                _assign_disambiguations(group_fields)

            for fields in group_fields:
                key = (fields["word"], fields["pos"], fields["etym_num"])
                if key in seen:
                    continue
                seen.add(key)
                notes.append(fields)

            if other_pos_entries:
                extras.append((word, [_describe_variant(e) for e in other_pos_entries]))
    finally:
        conn.close()

    if missing:
        print(f"\nWarning: {len(missing)} word(s) not found:")
        for word, pos in missing:
            label = f"{word}:{pos}" if pos else word
            print(f"  - {label}")
        print("(German nouns are capitalized — make sure spelling matches.)")

    if redirects:
        print("\nNote: inflected forms were resolved to their lemma:")
        for original, lemma in redirects:
            print(f"  - {original} → {lemma}")

    if extras:
        print("\nNote: some words have additional variants not included.")
        print("To add them, pin the POS explicitly (e.g. word:adv):")
        for word, variants in extras:
            print(f"  - {word}: also has {', '.join(variants)}")

    if not notes:
        print("No notes generated. Aborting.")
        return 1

    deck = build_deck(notes, deck_name=args.deck)
    write_deck(deck, args.output)
    print(f"Wrote {len(notes)} notes to {args.output}")
    return 0


if __name__ == "__main__":
    main()
