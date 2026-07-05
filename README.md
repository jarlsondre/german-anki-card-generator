# German Anki Card Generator

Generate rich [Anki](https://apps.ankiweb.net/) flashcards for German vocabulary
from a [kaikki.org](https://kaikki.org/) Wiktionary dump. Give it a list of
words and it produces an `.apkg` deck with definitions, inflections, examples,
and gender/POS info pulled from Wiktionary.

## Setup

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```sh
# 1. Install dependencies
uv sync

# 2. Download the source dictionary (~1 GB, from kaikki.org)
uv run download_dictionary.py

# 3. Build the local SQLite index (dictionary.db, ~1 GB)
uv run build_index.py
```

> **Why the download step?** The dictionary dump and the index built from it are
> each around 1 GB — too large to ship in a git repo. `download_dictionary.py`
> fetches the current dump straight from kaikki.org (resumable if interrupted),
> and `build_index.py` turns it into a fast local lookup index. Both files are
> git-ignored and live only on your machine.

## Usage

```sh
# A few words on the command line
uv run generate_cards.py schnell Haus laufen -o my_deck.apkg

# Or from a word list (one word per line; see sample.txt)
uv run generate_cards.py --file sample.txt -o my_deck.apkg
```

Then import the resulting `.apkg` into Anki (File → Import).

Pin a part of speech with `word:pos` (e.g. `schnell:adv`) when a word has
several. Inflected forms are resolved to their lemma automatically.

Options: `-o/--output` deck path, `-d/--deck` deck name, `--file/-f` word list,
`--db` index path. Run `uv run generate_cards.py --help` for details.

## Data source

Vocabulary data comes from the German
[machine-readable Wiktionary extract](https://kaikki.org/dictionary/German/)
by Tatu Ylonen (kaikki.org), derived from Wiktionary and licensed under
CC BY-SA. The dump is updated periodically, so a fresh download may contain more
entries than an older one.
