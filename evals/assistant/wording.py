"""Wording counters for the eval report: English words and avoided phrases in Hungarian answers.

Plain text matching, no network and no settings. Every occurrence counts, in any case and with Hungarian suffixes.
"""
from __future__ import annotations

import re
import unicodedata

# Only words with a plain Hungarian equivalent; terms the athlete knows from Garmin (HRV, VO2max, Zone 2, RPE, TSB) are fine.
ENGLISH_WORDS = ("readiness", "taper", "insight", "recovery", "workout", "baseline", "deload", "cooldown", "cool-down", "warmup", "warm-up")
# From the copy rules in CLAUDE.md ("Szövegezés – természetes magyar").
AVOIDED_PHRASES = ("egy helyen", "egy pillantással", "közérthető", "átfogó", "személyre szabott élmény", "fontos, hogy", "érdemes megjegyezni",
                   "ez azt jelenti, hogy", "figyelembe vesszük", "lehetővé teszi", "segít abban, hogy", "-ként funkcionál")


def _pattern(term: str) -> str:
    """A term starts at a word start ("_" separates words too) and may take any suffix; a term starting with "-" is itself a suffix."""
    words = r"\s+".join(re.escape(word) for word in term.removeprefix("-").split())
    start = "" if term.startswith("-") else r"(?<![^\W_])"
    end = r"\b" if term.endswith("hogy") else ""  # "fontos, hogyan" is another sentence
    return start + words + end


def _matcher(terms: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(map(_pattern, terms)), re.IGNORECASE)


_ENGLISH, _AVOIDED = _matcher(ENGLISH_WORDS), _matcher(AVOIDED_PHRASES)


def _count(matcher: re.Pattern[str], text: str) -> int:
    # Bold marks would split a phrase ("**Fontos**, hogy"), decomposed accents would hide it.
    return len(matcher.findall(unicodedata.normalize("NFC", text).replace("*", "")))


def count_english_words(text: str) -> int:
    return _count(_ENGLISH, text)


def count_avoided_phrases(text: str) -> int:
    return _count(_AVOIDED, text)
