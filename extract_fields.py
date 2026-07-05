"""Normalize a raw kaikki entry into a flat dict of Anki note fields.

The output dict always contains every field key; irrelevant fields are empty
strings. The Anki card template uses conditional blocks ({{#Field}}...{{/Field}})
to decide what to render, so empty strings are skipped automatically.
"""

import re
from typing import Any, Dict, List, Set

POS_DISPLAY: Dict[str, str] = {
    "noun": "noun",
    "verb": "verb",
    "adj": "adjective",
    "adv": "adverb",
    "name": "proper noun",
    "num": "numeral",
    "pron": "pronoun",
    "prep": "preposition",
    "conj": "conjunction",
    "det": "determiner",
    "intj": "interjection",
    "phrase": "phrase",
    "prep_phrase": "prepositional phrase",
    "proverb": "proverb",
}

# POS values that aren't useful as vocabulary cards.
JUNK_POS: Set[str] = {"character", "symbol", "prefix", "suffix", "article", "contraction"}

GENDER_ARTICLE: Dict[str, str] = {"m": "der", "f": "die", "n": "das"}
GENDER_FULL: Dict[str, str] = {"m": "masculine", "f": "feminine", "n": "neuter"}

MAX_EXAMPLES = 3
MAX_ALT_TRANSLATIONS = 4


def _first_form(entry: Dict[str, Any], required_tags: Set[str]) -> str:
    """Return the first inflected form whose tags are a superset of required_tags."""
    for f in entry.get("forms", []):
        form = f.get("form")
        if not form:
            continue
        if required_tags <= set(f.get("tags", [])):
            return form
    return ""


def _all_glosses(entry: Dict[str, Any]) -> List[str]:
    """Collect distinct English glosses across all senses, preserving order."""
    out: List[str] = []
    for sense in entry.get("senses", []):
        for g in sense.get("glosses", []) or []:
            if g and g not in out:
                out.append(g)
    return out


def _examples(entry: Dict[str, Any], limit: int = MAX_EXAMPLES) -> List[Dict[str, str]]:
    """Pull up to `limit` German/English example pairs across senses.

    For quotation-style entries kaikki sometimes stores the citation in `text`
    and the actual German quote in `roman` (a misnomer carried over from
    non-Latin-script languages), so prefer `roman` when present. Quotations
    are deprioritised behind plain examples because they're often archaic.
    """
    plain: List[Dict[str, str]] = []
    quotations: List[Dict[str, str]] = []
    for sense in entry.get("senses", []):
        for ex in sense.get("examples", []) or []:
            de = (ex.get("roman") or ex.get("text") or "").strip()
            en = (ex.get("english") or ex.get("translation") or "").strip()
            if not de or not en:
                continue
            bucket = quotations if ex.get("type") == "quotation" else plain
            bucket.append({"de": de, "en": en})
    return (plain + quotations)[:limit]


def _ipa(entry: Dict[str, Any]) -> str:
    """Return the first IPA pronunciation, if any."""
    for s in entry.get("sounds", []):
        if s.get("ipa"):
            return s["ipa"]
    return ""


def _head_expansion(entry: Dict[str, Any]) -> str:
    templates = entry.get("head_templates") or []
    return templates[0].get("expansion", "") if templates else ""


def is_form_of_stub(entry: Dict[str, Any]) -> bool:
    """True if this entry is a placeholder pointing at a lemma.

    Inflected forms (`manche`, `fährt`, `Männer`, ...) get their own
    kaikki entry whose only content is a `form_of` reference. Such entries
    aren't worth a card on their own — the real meaning lives in the lemma.
    """
    senses = entry.get("senses", [])
    return bool(senses) and bool(senses[0].get("form_of"))


def form_of_lemma(entry: Dict[str, Any]) -> str:
    """Return the lemma a form-of stub points at, or '' if there isn't one."""
    senses = entry.get("senses", [])
    if not senses:
        return ""
    form_of = senses[0].get("form_of") or []
    return form_of[0].get("word", "") if form_of else ""


def _noun_gender(entry: Dict[str, Any]) -> str:
    """Parse single-letter gender from the head expansion ('Mann m (...')."""
    expansion = _head_expansion(entry)
    word = entry.get("word", "")
    m = re.match(rf"^{re.escape(word)}\s+([mfn])\b", expansion)
    return m.group(1) if m else ""


def _verb_auxiliary(entry: Dict[str, Any]) -> str:
    """Extract 'haben' / 'sein' / 'haben or sein' from the head expansion."""
    expansion = _head_expansion(entry)
    m = re.search(r"auxiliary\s+([a-z]+(?:\s+or\s+[a-z]+)?)", expansion)
    return m.group(1) if m else ""


def _noun_fields(entry: Dict[str, Any]) -> Dict[str, str]:
    gender = _noun_gender(entry)
    return {
        "gender": gender,
        "gender_full": GENDER_FULL.get(gender, ""),
        "article": GENDER_ARTICLE.get(gender, ""),
        "plural": _first_form(entry, {"nominative", "plural"}),
        "genitive": _first_form(entry, {"genitive", "singular"}),
    }


def _verb_fields(entry: Dict[str, Any]) -> Dict[str, str]:
    return {
        "third_singular_present": _first_form(entry, {"third-person", "singular", "present"}),
        "preterite": _first_form(entry, {"first-person", "singular", "preterite"}),
        "past_participle": _first_form(entry, {"participle", "past"}),
        "auxiliary": _verb_auxiliary(entry),
    }


def _perfect_aux_form(auxiliary: str) -> str:
    """3rd-singular form of the perfect-tense auxiliary ('ist' / 'hat')."""
    if "sein" in auxiliary:
        return "ist"
    if "haben" in auxiliary:
        return "hat"
    return ""


def _build_verb_principal_parts(
    word: str,
    third: str,
    preterite: str,
    past_participle: str,
    auxiliary: str,
) -> str:
    """Compose 'fahren, fährt, fuhr, ist gefahren'.

    The auxiliary is folded into the participle slot ('ist gefahren') rather
    than printed separately. Returns "" if no conjugations are available so
    the card template can fall back to the plain headword.
    """
    parts: List[str] = [word]
    if third:
        parts.append(third)
    if preterite:
        parts.append(preterite)
    if past_participle:
        aux = _perfect_aux_form(auxiliary)
        parts.append(f"{aux} {past_participle}" if aux else past_participle)
    return ", ".join(parts) if len(parts) > 1 else ""


def _adj_fields(entry: Dict[str, Any]) -> Dict[str, str]:
    return {
        "comparative": _first_form(entry, {"comparative"}),
        "superlative": _first_form(entry, {"superlative"}),
    }


# Every field the Anki note type expects. Kept here so the note type and the
# extractor can't drift apart silently.
FIELD_NAMES: List[str] = [
    "word",
    "pos",
    "etym_num",
    "disambiguation",
    "pos_display",
    "ipa",
    "translation_primary",
    "translations_alt",
    "gender",
    "gender_full",
    "article",
    "plural",
    "genitive",
    "third_singular_present",
    "preterite",
    "past_participle",
    "auxiliary",
    "principal_parts",
    "comparative",
    "superlative",
    "ex1_de",
    "ex1_en",
    "ex2_de",
    "ex2_en",
    "ex3_de",
    "ex3_en",
]


def extract(entry: Dict[str, Any]) -> Dict[str, str]:
    """Flatten a kaikki entry into the field dict that Anki notes expect."""
    word: str = str(entry.get("word") or "")
    pos: str = str(entry.get("pos") or "")
    glosses = _all_glosses(entry)
    examples = _examples(entry)

    fields: Dict[str, str] = dict.fromkeys(FIELD_NAMES, "")
    fields["word"] = word
    fields["pos"] = pos
    fields["etym_num"] = str(entry.get("etymology_number") or "")
    fields["pos_display"] = POS_DISPLAY.get(pos, pos)
    fields["ipa"] = _ipa(entry)

    if glosses:
        fields["translation_primary"] = glosses[0]
        if len(glosses) > 1:
            fields["translations_alt"] = "; ".join(glosses[1 : 1 + MAX_ALT_TRANSLATIONS])

    for i, ex in enumerate(examples, start=1):
        fields[f"ex{i}_de"] = ex["de"]
        fields[f"ex{i}_en"] = ex["en"]

    if pos == "noun":
        fields.update(_noun_fields(entry))
    elif pos == "verb":
        fields.update(_verb_fields(entry))
        fields["principal_parts"] = _build_verb_principal_parts(
            word,
            fields["third_singular_present"],
            fields["preterite"],
            fields["past_participle"],
            fields["auxiliary"],
        )
    elif pos == "adj":
        fields.update(_adj_fields(entry))

    return fields
