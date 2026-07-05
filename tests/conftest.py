"""Shared pytest fixtures."""

import json
import sqlite3
from typing import Iterator

import pytest


@pytest.fixture
def db_cursor() -> Iterator[sqlite3.Cursor]:
    """In-memory SQLite cursor with the same schema as build_index.py.

    Pre-populated with a multi-POS word (`gut` adj+adv) for the priority-
    sort test, and a junk-POS entry (`un-` prefix) for the filter tests.
    """
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, word TEXT, pos TEXT, data TEXT)")
    rows = [
        (
            "gut",
            "adj",
            {
                "word": "gut",
                "pos": "adj",
                "senses": [{"glosses": ["good"]}],
                "head_templates": [{"expansion": "gut"}],
            },
        ),
        (
            "gut",
            "adv",
            {
                "word": "gut",
                "pos": "adv",
                "senses": [{"glosses": ["well"]}],
                "head_templates": [{"expansion": "gut"}],
            },
        ),
        (
            "un-",
            "prefix",
            {
                "word": "un-",
                "pos": "prefix",
                "senses": [],
                "head_templates": [{"expansion": "un-"}],
            },
        ),
    ]
    for word, pos, data in rows:
        cur.execute(
            "INSERT INTO entries (word, pos, data) VALUES (?, ?, ?)",
            (word, pos, json.dumps(data)),
        )
    conn.commit()
    yield cur
    conn.close()
