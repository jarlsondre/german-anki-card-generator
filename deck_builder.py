"""Build a genanki deck from extract_fields.py field dicts.

A single note type carries every possible field; the card template uses
{{#field}}...{{/field}} conditionals so empty fields disappear. Two card
templates per note give you DE→EN and EN→DE in one shot.
"""

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List

import genanki

from extract_fields import FIELD_NAMES

MODEL_NAME = "Anki Card Generator"
MODEL_VERSION_TAG = b"kaikki-de-v1"


def _stable_id(seed: bytes) -> int:
    """Derive a stable 32-bit positive int ID from a seed string."""
    return int(hashlib.md5(seed).hexdigest()[:8], 16)


MODEL_ID = _stable_id(MODEL_VERSION_TAG)

# Anki uses snake_case field names directly as template variables ({{word}}).
ANKI_FIELDS: List[Dict[str, str]] = [{"name": n} for n in FIELD_NAMES]

# ── CSS shared across all card faces ─────────────────────────────
CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
  font-size: 22px;
  text-align: center;
  color: #222;
  background: #fafafa;
  padding: 20px;
}
.pos {
  color: #888;
  font-style: italic;
  font-size: 14px;
  margin-bottom: 6px;
}
.word {
  font-size: 32px;
  font-weight: 600;
  margin: 4px 0;
}
.principal-parts {
  font-size: 24px;
  letter-spacing: 0.2px;
}
.article {
  color: #888;
  font-weight: 400;
}
.disambig {
  color: #888;
  font-weight: 400;
  font-size: 0.6em;
  margin-left: 4px;
}
.translation {
  font-size: 22px;
  margin: 10px 0;
}
.alt-trans {
  color: #555;
  font-size: 15px;
  font-style: italic;
  margin: 6px 0;
}
.ipa {
  color: #666;
  font-family: "Lucida Sans Unicode", "Charis SIL", sans-serif;
  font-size: 15px;
  margin: 4px 0;
}
.forms {
  font-size: 14px;
  color: #333;
  background: #eef1f5;
  padding: 5px 10px;
  border-radius: 4px;
  display: inline-block;
  margin: 5px 4px;
}
.forms .label {
  color: #888;
  margin-right: 2px;
}
.examples {
  margin-top: 14px;
  text-align: left;
}
.example {
  margin: 10px auto;
  max-width: 520px;
  padding: 6px 10px;
  border-left: 3px solid #ccc;
}
.ex-de {
  font-size: 16px;
}
.ex-en {
  font-size: 14px;
  color: #666;
}
hr {
  border: none;
  border-top: 1px solid #ddd;
  margin: 12px 0;
}
"""

# ── Reusable template fragments ─────────────────────────────────
_GERMAN_HEADWORD = """
<div class="pos">{{pos_display}}</div>
<div class="word">
  {{#article}}<span class="article">{{article}}</span> {{/article}}{{word}}
  {{#disambiguation}}<span class="disambig">({{disambiguation}})</span>{{/disambiguation}}
</div>
"""

# Back-side headword used on EN→DE: leads with the verb principal parts
# ("fahren, fährt, fuhr, ist gefahren") when present, falling back to the
# regular article+word display for non-verbs.
_BACK_HEADWORD = """
<div class="pos">{{pos_display}}</div>
{{#principal_parts}}
<div class="word principal-parts">{{principal_parts}}</div>
{{/principal_parts}}
{{^principal_parts}}
<div class="word">
  {{#article}}<span class="article">{{article}}</span> {{/article}}{{word}}
  {{#disambiguation}}<span class="disambig">({{disambiguation}})</span>{{/disambiguation}}
</div>
{{/principal_parts}}
"""

_FORMS_BLOCK = """
{{#plural}}
<div class="forms">
  <span class="label">plural:</span> {{plural}}
  {{#genitive}} · <span class="label">gen:</span> {{genitive}}{{/genitive}}
</div>
{{/plural}}
{{#third_singular_present}}
<div class="forms">
  <span class="label">3sg:</span> {{third_singular_present}}
  · <span class="label">pret:</span> {{preterite}}
  · <span class="label">part:</span> {{past_participle}}
  {{#auxiliary}} · <span class="label">aux:</span> {{auxiliary}}{{/auxiliary}}
</div>
{{/third_singular_present}}
{{#comparative}}
<div class="forms">
  <span class="label">comp:</span> {{comparative}}
  · <span class="label">sup:</span> {{superlative}}
</div>
{{/comparative}}
"""

_EXAMPLES_BLOCK = """
{{#ex1_de}}
<div class="examples">
  <div class="example">
    <div class="ex-de">{{ex1_de}}</div>
    <div class="ex-en">{{ex1_en}}</div>
  </div>
  {{#ex2_de}}
  <div class="example">
    <div class="ex-de">{{ex2_de}}</div>
    <div class="ex-en">{{ex2_en}}</div>
  </div>
  {{/ex2_de}}
  {{#ex3_de}}
  <div class="example">
    <div class="ex-de">{{ex3_de}}</div>
    <div class="ex-en">{{ex3_en}}</div>
  </div>
  {{/ex3_de}}
</div>
{{/ex1_de}}
"""

_ALT_TRANS = '{{#translations_alt}}<div class="alt-trans">also: {{translations_alt}}</div>{{/translations_alt}}'
_IPA = '{{#ipa}}<div class="ipa">{{ipa}}</div>{{/ipa}}'

# ── Card templates ─────────────────────────────────────────────
DE_EN_FRONT = _GERMAN_HEADWORD
DE_EN_BACK = (
    "{{FrontSide}}\n<hr>\n"
    f"{_IPA}\n"
    '<div class="translation">{{translation_primary}}</div>\n'
    f"{_ALT_TRANS}\n"
    f"{_FORMS_BLOCK}\n"
    f"{_EXAMPLES_BLOCK}"
)

EN_DE_FRONT = """
<div class="pos">{{pos_display}}</div>
<div class="translation">{{translation_primary}}</div>
"""
EN_DE_BACK = f"{{{{FrontSide}}}}\n<hr>\n{_BACK_HEADWORD}\n{_IPA}\n{_ALT_TRANS}\n{_FORMS_BLOCK}\n{_EXAMPLES_BLOCK}"

TEMPLATES: List[Dict[str, str]] = [
    {"name": "DE → EN", "qfmt": DE_EN_FRONT, "afmt": DE_EN_BACK},
    {"name": "EN → DE", "qfmt": EN_DE_FRONT, "afmt": EN_DE_BACK},
]

GERMAN_MODEL = genanki.Model(
    model_id=MODEL_ID,
    name=MODEL_NAME,
    fields=ANKI_FIELDS,
    templates=TEMPLATES,
    css=CSS,
)


def build_deck(notes_fields: Iterable[Dict[str, str]], deck_name: str) -> genanki.Deck:
    """Build a genanki Deck from an iterable of field dicts (output of extract())."""
    deck = genanki.Deck(deck_id=_stable_id(deck_name.encode()), name=deck_name)
    for fields in notes_fields:
        note = genanki.Note(
            model=GERMAN_MODEL,
            fields=[fields.get(k, "") for k in FIELD_NAMES],
            guid=genanki.guid_for(
                fields.get("word", ""),
                fields.get("pos", ""),
                fields.get("etym_num", ""),
            ),
        )
        deck.add_note(note)
    return deck


def write_deck(deck: genanki.Deck, output_path: Path) -> None:
    """Write a deck to a .apkg file."""
    genanki.Package(deck).write_to_file(str(output_path))
