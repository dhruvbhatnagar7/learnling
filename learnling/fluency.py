"""Oral reading fluency, reported against published norms.

Words correct per minute against Hasbrouck & Tindal is the instrument
intervention teachers already use. Reporting against it means an educator can
interpret learnling's output on sight, with no explanation and no trust in a
scale we invented. An invented scale means nothing to anyone.

    Hasbrouck, J. & Tindal, G. (2017). An update to compiled ORF norms
    (Technical Report No. 1702). Eugene, OR: Behavioral Research and
    Teaching, University of Oregon.

Counting rules
--------------
    wcpm = (total words read - uncorrected errors) / elapsed minutes

Errors: mispronunciations, substitutions, omissions, hesitations beyond about
three seconds, and words supplied by the system.

Not errors: self-corrections, repetitions, insertions, and variation
attributable to accent or dialect. Nor is a proper noun the learner has not
met before, on first encounter — a child who has never seen "Siobhan" has not
made a decoding error, they have met an unfamiliar name.

That last group matters more than it looks. Counting a dialect variation as an
error tells a child their own speech is wrong, which is both false and a
reliable way to lose them.

Reporting
---------
Results are banded against the grade level of the *passage* — the skill
grade — never the learner's own grade. A twelve-year-old reading grade-2
material is measured against grade-2 norms, because that is what tells an
educator whether the reading is improving.

Three presentation rules hold everywhere downstream of this module:

  - Never show a percentile to a learner. Bands are for the educator report.
    To the learner: growth over time, never rank.
  - Never celebrate speed. A child who learns that reading should be fast
    concludes they are bad at it the moment it isn't.
  - Always report accuracy alongside rate. High rate with low accuracy is
    not fluency, and reporting rate alone hides exactly the reader who is
    guessing their way through a page at speed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

_NORMS_PATH = Path(__file__).parent / "data" / "orf_norms_hasbrouck_tindal_2017.json"

#: Hasbrouck & Tindal's own published guidance: a learner scoring this many
#: words or more below the 50th percentile needs a fluency-building program.
FLUENCY_SUPPORT_THRESHOLD_WCPM = 10

#: The rule above is defined over the average of two unpracticed readings.
#: One reading is a measurement of a day, not of a reader.
UNPRACTICED_READINGS_REQUIRED = 2

PERCENTILES = (90, 75, 50, 25, 10)


class Season(str, Enum):
    FALL = "fall"
    WINTER = "winter"
    SPRING = "spring"


class NormsUnavailable(LookupError):
    """No published norm exists for this grade and season.

    Raised rather than defaulted. The most common case is grade 1 in the
    fall, which has no norm because grade 1 students are not reading
    connected text yet — substituting a neighbouring column there would
    manufacture a number the source does not contain.
    """


@dataclass
class FluencyResult:
    wcpm: int
    accuracy_pct: float
    #: The grade level of the PASSAGE, not the learner's grade.
    skill_grade: int
    season: Season
    percentile_band: str
    needs_fluency_support: bool
    #: How many unpracticed readings the support judgment is based on.
    #: Below UNPRACTICED_READINGS_REQUIRED, `needs_fluency_support` is False
    #: because the question has not yet been answered, not because the answer
    #: is no — see `readings_note`.
    readings_counted: int = 1
    readings_note: str = ""


@lru_cache(maxsize=1)
def _load_norms() -> dict:
    return json.loads(_NORMS_PATH.read_text(encoding="utf-8"))


def citation() -> str:
    """The source, formatted for display in a report."""
    source = _load_norms()["citation"]
    return (
        f"{source['authors']} ({source['year']}). {source['title']} "
        f"({source['series']}). {source['location']}: {source['publisher']}."
    )


def norms_for(skill_grade: int, season: Season) -> dict[int, int]:
    """Percentile -> WCPM cutoffs for one grade and season."""
    norms = _load_norms()["norms"]
    grade_key = str(skill_grade)
    if grade_key not in norms:
        raise NormsUnavailable(
            f"no ORF norms published for grade {skill_grade} "
            f"(the table covers grades 1-6)"
        )

    table = norms[grade_key][season.value]
    if table is None:
        raise NormsUnavailable(
            f"no ORF norm for grade {skill_grade} in {season.value} — grade 1 "
            "students are not reading connected text at that point in the year"
        )
    return {int(percentile): wcpm for percentile, wcpm in table.items()}


def compute_wcpm(
    total_words_read: int, uncorrected_errors: int, elapsed_seconds: float
) -> int:
    """Words correct per minute, rounded to a whole word.

    Fractional WCPM implies a precision a one-minute sample does not have.
    """
    if elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be positive to compute a rate")
    words_correct = max(0, total_words_read - uncorrected_errors)
    return round(words_correct / (elapsed_seconds / 60.0))


def percentile_band(wcpm: int, skill_grade: int, season: Season) -> str:
    """Which published band `wcpm` falls into for this grade and season."""
    cutoffs = norms_for(skill_grade, season)
    if wcpm < cutoffs[10]:
        return "below 10th"
    if wcpm < cutoffs[25]:
        return "10th-25th"
    if wcpm < cutoffs[50]:
        return "25th-50th"
    if wcpm < cutoffs[75]:
        return "50th-75th"
    if wcpm < cutoffs[90]:
        return "75th-90th"
    return "above 90th"


def needs_fluency_support(
    wcpm_readings: list[int], skill_grade: int, season: Season
) -> tuple[bool, str]:
    """Hasbrouck & Tindal's own rule, applied exactly as published.

    A learner scoring ten or more words below the 50th percentile — averaged
    over two unpracticed readings of grade-level material — needs a
    fluency-building program.

    Returns (verdict, note). With fewer than two readings the verdict is False
    and the note says why: one reading is a measurement of a day. A learner
    who slept badly, or met an unfamiliar topic, reads like a learner with a
    fluency problem, and enrolling them in an intervention on that basis is a
    real cost to a real child.
    """
    if len(wcpm_readings) < UNPRACTICED_READINGS_REQUIRED:
        return False, (
            f"{len(wcpm_readings)} unpracticed reading(s) on record; "
            f"{UNPRACTICED_READINGS_REQUIRED} required before judging fluency support"
        )

    cutoffs = norms_for(skill_grade, season)
    average = sum(wcpm_readings) / len(wcpm_readings)
    shortfall = cutoffs[50] - average

    if shortfall >= FLUENCY_SUPPORT_THRESHOLD_WCPM:
        return True, (
            f"average {average:.0f} WCPM over {len(wcpm_readings)} unpracticed "
            f"readings is {shortfall:.0f} below the grade {skill_grade} "
            f"{season.value} 50th percentile ({cutoffs[50]})"
        )
    return False, (
        f"average {average:.0f} WCPM over {len(wcpm_readings)} unpracticed "
        f"readings is within {FLUENCY_SUPPORT_THRESHOLD_WCPM} words of the "
        f"grade {skill_grade} {season.value} 50th percentile ({cutoffs[50]})"
    )


def assess_fluency(
    total_words_read: int,
    uncorrected_errors: int,
    elapsed_seconds: float,
    skill_grade: int,
    season: Season,
    prior_unpracticed_wcpm: list[int] | None = None,
) -> FluencyResult:
    """Score one reading and band it against the published norms.

    `prior_unpracticed_wcpm` carries earlier unpracticed readings so the
    support judgment can be made over the average the rule requires. learnling
    keeps no cross-session store by design, so today a caller can only supply
    readings from the session in hand.
    """
    wcpm = compute_wcpm(total_words_read, uncorrected_errors, elapsed_seconds)
    accuracy_pct = (
        100.0 * max(0, total_words_read - uncorrected_errors) / total_words_read
        if total_words_read
        else 0.0
    )

    readings = list(prior_unpracticed_wcpm or []) + [wcpm]
    support, note = needs_fluency_support(readings, skill_grade, season)

    return FluencyResult(
        wcpm=wcpm,
        accuracy_pct=round(accuracy_pct, 1),
        skill_grade=skill_grade,
        season=season,
        percentile_band=percentile_band(wcpm, skill_grade, season),
        needs_fluency_support=support,
        readings_counted=len(readings),
        readings_note=note,
    )
