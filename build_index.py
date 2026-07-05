"""Build a SQLite index of the kaikki German dictionary JSONL.

One row per entry. (word, pos) is not unique — homographs with the same POS
but different etymologies appear more than once, distinguished by
`etymology_number` inside the JSON blob.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import List, Tuple

HERE = Path(__file__).parent
JSONL_PATH = HERE / "kaikki.org-dictionary-German-words.jsonl"
DB_PATH = HERE / "dictionary.db"

BATCH_SIZE = 10_000


def build_index() -> None:
    if not JSONL_PATH.exists():
        sys.exit(f"Missing source file: {JSONL_PATH}")

    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA journal_mode = OFF")
    cur.execute("PRAGMA synchronous = OFF")
    cur.execute("PRAGMA temp_store = MEMORY")

    cur.execute(
        """
        CREATE TABLE entries (
            id   INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            pos  TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """
    )

    start = time.time()
    batch: List[Tuple[str, str, str]] = []
    total = 0

    with JSONL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            batch.append((d["word"], d["pos"], line.rstrip("\n")))
            if len(batch) >= BATCH_SIZE:
                cur.executemany(
                    "INSERT INTO entries (word, pos, data) VALUES (?, ?, ?)",
                    batch,
                )
                total += len(batch)
                batch.clear()
                if total % 100_000 == 0:
                    elapsed = time.time() - start
                    print(f"  {total:>7,} rows  ({elapsed:5.1f}s)", file=sys.stderr)

    if batch:
        cur.executemany(
            "INSERT INTO entries (word, pos, data) VALUES (?, ?, ?)",
            batch,
        )
        total += len(batch)

    print("Creating indexes…", file=sys.stderr)
    cur.execute("CREATE INDEX idx_word ON entries(word)")
    cur.execute("CREATE INDEX idx_word_pos ON entries(word, pos)")

    conn.commit()
    conn.close()

    elapsed = time.time() - start
    size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"Done. {total:,} entries in {elapsed:.1f}s. DB: {size_mb:.1f} MB at {DB_PATH}")


if __name__ == "__main__":
    build_index()
