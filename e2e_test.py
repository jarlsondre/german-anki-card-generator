"""End-to-end smoke test: build a tiny dict, run the CLI, verify the deck.

Run with:  uv run python e2e_test.py
Exits 0 on success, 1 on failure. Not picked up by pytest (intentional —
the filename doesn't start with `test_`).
"""

import json
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List

from extract_fields import FIELD_NAMES
from generate_cards import main as cards_main

SAMPLE_ENTRIES: List[Dict] = [
    {
        "word": "Mann",
        "pos": "noun",
        "head_templates": [{"expansion": "Mann m (genitive Mannes, plural Männer)"}],
        "senses": [
            {
                "glosses": ["man"],
                "examples": [
                    {"text": "Der Mann ist da.", "english": "The man is there."},
                ],
            }
        ],
        "forms": [
            {"form": "Männer", "tags": ["nominative", "plural"]},
            {"form": "Mannes", "tags": ["genitive", "singular"]},
        ],
        "sounds": [{"ipa": "/man/"}],
    },
    {
        "word": "fahren",
        "pos": "verb",
        "head_templates": [{"expansion": "fahren (..., auxiliary haben or sein)"}],
        "senses": [{"glosses": ["to go"]}],
        "forms": [
            {"form": "fährt", "tags": ["third-person", "singular", "present"]},
            {"form": "fuhr", "tags": ["first-person", "singular", "preterite"]},
            {"form": "gefahren", "tags": ["participle", "past"]},
        ],
        "sounds": [{"ipa": "/ˈfaːʁən/"}],
    },
    {
        "word": "schnell",
        "pos": "adj",
        "head_templates": [{"expansion": "schnell"}],
        "senses": [{"glosses": ["fast"]}],
        "forms": [
            {"form": "schneller", "tags": ["comparative"]},
            {"form": "am schnellsten", "tags": ["superlative"]},
        ],
    },
]


def _seed_db(path: Path) -> None:
    """Create the same schema build_index.py produces, populated with samples."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, word TEXT, pos TEXT, data TEXT)")
    for entry in SAMPLE_ENTRIES:
        cur.execute(
            "INSERT INTO entries (word, pos, data) VALUES (?, ?, ?)",
            (entry["word"], entry["pos"], json.dumps(entry)),
        )
    conn.commit()
    conn.close()


def _read_notes(apkg_path: Path, work_dir: Path) -> List[Dict[str, str]]:
    """Unzip an apkg and return its notes as field-name → value dicts."""
    with zipfile.ZipFile(apkg_path) as z:
        z.extract("collection.anki2", path=work_dir)
    coll = work_dir / "collection.anki2"
    conn = sqlite3.connect(coll)
    notes = []
    for (flds,) in conn.execute("SELECT flds FROM notes"):
        values = flds.split("\x1f")
        notes.append(dict(zip(FIELD_NAMES, values, strict=True)))
    conn.close()
    return notes


def run() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "test.db"
        words_path = tmp_path / "words.txt"
        apkg_path = tmp_path / "test.apkg"

        _seed_db(db_path)
        words_path.write_text("Mann\nfahren\nschnell\n", encoding="utf-8")

        exit_code = cards_main(
            [
                "--file",
                str(words_path),
                "--output",
                str(apkg_path),
                "--db",
                str(db_path),
            ]
        )
        assert exit_code == 0, f"cards.main returned {exit_code}"
        assert apkg_path.exists(), "deck file was not written"

        notes = _read_notes(apkg_path, tmp_path)
        assert len(notes) == 3, f"expected 3 notes, got {len(notes)}"

        by_word = {n["word"]: n for n in notes}

        mann = by_word["Mann"]
        assert mann["gender"] == "m"
        assert mann["article"] == "der"
        assert mann["plural"] == "Männer"
        assert mann["genitive"] == "Mannes"
        assert mann["translation_primary"] == "man"
        assert mann["ex1_de"] == "Der Mann ist da."

        fahren = by_word["fahren"]
        assert fahren["third_singular_present"] == "fährt"
        assert fahren["preterite"] == "fuhr"
        assert fahren["past_participle"] == "gefahren"
        assert fahren["auxiliary"] == "haben or sein"

        schnell = by_word["schnell"]
        assert schnell["comparative"] == "schneller"
        assert schnell["superlative"] == "am schnellsten"
        assert schnell["pos_display"] == "adjective"

    print("e2e: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
