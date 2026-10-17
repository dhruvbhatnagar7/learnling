"""Which sound pattern a misread word points to, for the adult's report.

A teacher can't do much with "two wrong words". They can with "trouble with
vowel teams: read 'found' as 'fond' and 'beach' as 'bench'", because that
names the lesson to pick. This module takes one raised miscue and says which
spelling pattern of the page word the reader got wrong.

It works from spelling alone: it finds the letters where the heard word
differs from the page word, and names the pattern those letters belong to.
That is a guide to where to look, not a diagnosis. English spelling is not
sound, and the recogniser can be wrong about what was said, so the report
says so next to every grouping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from learnling.agents.reading import is_near_miss
from learnling.models import Miscue

#: Teacher-facing names, in the order the report lists them.
PATTERN_NAMES: dict[str, str] = {
    "short_vowel": "short vowels (a, e, i, o, u)",
    "silent_e": "silent e (a_e, i_e, o_e, u_e)",
    "vowel_team": "vowel teams (ai, ee, ea, oa, ou, igh...)",
    "r_controlled": "r-controlled vowels (ar, or, er, ir, ur)",
    "digraph": "digraphs (sh, ch, th, ck, ng...)",
    "blend": "consonant blends (fr, st, nd...)",
    "consonant": "single consonant sounds",
    "ending": "word endings (-s, -ed, -ing...)",
    "swap": "a different word read in its place",
    "skipped": "skipped words",
    "added": "added words",
}

_VOWELS = set("aeiou")

# Longest first, so "igh" is found before "ig" could be anything else.
_VOWEL_TEAMS = (
    "eigh", "igh", "augh", "ough",
    "ai", "ay", "ee", "ea", "ey", "oa", "oe", "oo", "ou", "ow", "oi", "oy",
    "au", "aw", "ew", "ie", "ue", "ui",
)
# Vowel-plus-r spellings first, so "heard" is r-controlled rather than "ea".
_R_CONTROLLED = ("ear", "eer", "air", "are", "ore", "oar", "our", "ire", "ar", "or", "er", "ir", "ur")
_DIGRAPHS = ("tch", "dge", "sh", "ch", "th", "wh", "ph", "ck", "ng", "nk", "kn", "wr", "gh")
_INITIAL_BLENDS = (
    "scr", "spl", "spr", "str", "squ", "thr", "shr",
    "bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "pl", "pr",
    "sc", "sk", "sl", "sm", "sn", "sp", "st", "sw", "tr", "tw",
)
_FINAL_BLENDS = ("nd", "nt", "mp", "st", "sk", "sp", "lk", "lt", "ld", "lf", "lp", "ft", "pt", "ct", "xt")
_SILENT_E = re.compile(r"[aeiou][^aeiou]e$")
_SUFFIXES = ("ing", "est", "ed", "er", "es", "ly", "s")


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    pattern: str


def _spans(word: str) -> list[_Span]:
    """Every spelling pattern in `word`, each letter claimed once."""
    claimed = [False] * len(word)
    spans: list[_Span] = []

    def claim(start: int, end: int, pattern: str) -> None:
        if any(claimed[start:end]):
            return
        for i in range(start, end):
            claimed[i] = True
        spans.append(_Span(start, end, pattern))

    def find_all(units, pattern):
        for unit in units:
            for match in re.finditer(re.escape(unit), word):
                claim(match.start(), match.end(), pattern)

    silent = _SILENT_E.search(word)
    if silent:
        # The vowel and the final e work together; the consonant between
        # them stays its own sound.
        claim(silent.start(), silent.start() + 1, "silent_e")
        claim(len(word) - 1, len(word), "silent_e")
    find_all(_R_CONTROLLED, "r_controlled")
    find_all(_VOWEL_TEAMS, "vowel_team")
    find_all(_DIGRAPHS, "digraph")
    for blend in _INITIAL_BLENDS:
        if word.startswith(blend):
            claim(0, len(blend), "blend")
            break
    for blend in _FINAL_BLENDS:
        if word.endswith(blend):
            claim(len(word) - len(blend), len(word), "blend")
            break
    for i, letter in enumerate(word):
        if not claimed[i]:
            claim(i, i + 1, "short_vowel" if letter in _VOWELS else "consonant")
    return spans


def _split_suffix(word: str) -> tuple[str, str]:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            return word[: -len(suffix)], suffix
    return word, ""


def _same_stem(a: str, b: str) -> bool:
    """'sit' and 'sitt', 'make' and 'mak': one root with spelling changes."""
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    if len(long) - len(short) != 1 or not long.startswith(short):
        return False
    extra = long[-1]
    return extra == "e" or extra == short[-1]


def _is_ending_slip(expected: str, heard: str) -> bool:
    """Right root, wrong or missing ending: 'sitting' read as 'sit'."""
    expected_stem, expected_suffix = _split_suffix(expected)
    heard_stem, heard_suffix = _split_suffix(heard)
    if expected_suffix == heard_suffix:
        return False
    return (
        _same_stem(expected_stem, heard_stem)
        or _same_stem(expected_stem, heard)
        or _same_stem(expected, heard_stem)
    )


def _differing_region(expected: str, heard: str) -> tuple[int, int]:
    """Letters of `expected` not shared with `heard` at either end."""
    prefix = 0
    while prefix < min(len(expected), len(heard)) and expected[prefix] == heard[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < min(len(expected), len(heard)) - prefix
        and expected[-1 - suffix] == heard[-1 - suffix]
    ):
        suffix += 1
    start, end = prefix, len(expected) - suffix
    if start >= end:
        # Letters were added, not changed: look at the letter before them.
        start, end = max(0, start - 1), max(1, start)
    return start, end


def patterns_for(miscue: Miscue) -> list[str]:
    """The pattern key (see `PATTERN_NAMES`) this miscue points to, if any."""
    if miscue.kind == "omission":
        return ["skipped"]
    if miscue.kind == "insertion":
        return ["added"]
    expected, heard = miscue.expected or "", miscue.heard or ""
    if not expected or not heard:
        return []
    if _is_ending_slip(expected, heard):
        return ["ending"]
    if not is_near_miss(expected, heard):
        # "a" for "the" is not about any one spelling pattern.
        return ["swap"]
    start, end = _differing_region(expected, heard)
    overlapping = [
        span for span in _spans(expected) if span.start < end and start < span.end
    ]
    if not overlapping:
        return []
    # One group per word, so a word is not counted twice. The pattern that
    # covers most of the changed letters wins, and a multi-letter pattern
    # wins a tie over a single letter.
    order = list(PATTERN_NAMES)
    best = max(
        overlapping,
        key=lambda span: (
            min(end, span.end) - max(start, span.start),
            span.end - span.start,
            -order.index(span.pattern),
        ),
    )
    return [best.pattern]


def is_self_correction(miscue: Miscue, next_page_word: str | None) -> bool:
    """An extra word that was a try at the next page word: "sell... shell".

    The reader fixed it themselves, so it is not something to practise.
    """
    return (
        miscue.kind == "insertion"
        and next_page_word is not None
        and miscue.heard != next_page_word
        and is_near_miss(next_page_word, miscue.heard)
    )
