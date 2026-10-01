"""Presentation rules: what a learner may and may not be told.

Bands, percentiles and grade levels are educator-facing. A learner hears
about growth, never rank. These are separate from the fluency computation
itself — the numbers can be right and the delivery still be harmful.
"""

from __future__ import annotations

import re

from learnling.agents.reading import ReadingAgent, _feedback_for
from learnling.models import LearnerProfile, Miscue, Utterance
from learnling.orchestrator import Orchestrator
from learnling.report import generate_report

PASSAGE = "the cat sat on the mat and the dog ran to the park"

#: Anything that ranks a learner against other learners, or names a level.
_RANK_LANGUAGE = re.compile(
    r"percentile|\bth percentile\b|\bgrade \d|\bbelow (the )?\d+th\b|"
    r"\b\d+th-\d+th\b|\bwcpm\b|\bpercentile band\b",
    re.I,
)


def _spoken_responses(transcripts: list[str]) -> list[str]:
    orchestrator = Orchestrator(LearnerProfile(age_years=12))
    orchestrator.load_passage(PASSAGE)
    return [
        orchestrator.handle_utterance(Utterance(text=text)) for text in transcripts
    ]


def test_no_rank_language_reaches_the_learner():
    spoken = _spoken_responses(
        [
            PASSAGE,  # clean
            "the cat sat on the hat and the dog ran to the park",  # substitution
            "cat sat mat dog ran park",  # heavy omissions
            "the cat sat on the mat and the dog ran to the park quickly",  # insertion
        ]
    )
    for response in spoken:
        assert not _RANK_LANGUAGE.search(response), f"rank language spoken: {response!r}"


def test_feedback_templates_never_mention_speed():
    """Never celebrate speed: a child who learns reading should be fast
    concludes they are bad at it the moment it isn't."""
    templates = [
        _feedback_for([]),
        _feedback_for([Miscue("substitution", "mat", "hat", 5)]),
        _feedback_for([Miscue("omission", "the", None, 0)]),
        _feedback_for([Miscue("insertion", None, "quickly", 11)]),
    ]
    for text in templates:
        assert not re.search(r"\bfast(er)?\b|\bspeed\b|\bquick(ly|er)?\b", text, re.I), (
            f"speed praised in: {text!r}"
        )


def test_the_educator_report_may_carry_what_the_learner_may_not():
    """The split is the point: stats for the adult, encouragement for the child."""
    orchestrator = Orchestrator(LearnerProfile(age_years=12))
    orchestrator.load_passage(PASSAGE)
    orchestrator.handle_utterance(
        Utterance(text="the cat sat on the hat and the dog ran to the park")
    )
    report = generate_report(orchestrator.session)
    assert "Accuracy" in report
    assert "Assessment" in report


def test_accuracy_is_always_reported_alongside_rate():
    """High rate with low accuracy is not fluency; rate alone hides that reader."""
    orchestrator = Orchestrator(LearnerProfile(age_years=12))
    orchestrator.load_passage(PASSAGE)
    orchestrator.handle_utterance(Utterance(text=PASSAGE, duration_seconds=20.0))
    report = generate_report(orchestrator.session)
    assert "Accuracy" in report and "WPM" in report


def test_suppressed_miscues_are_visible_to_the_adult():
    """An adult should be able to see that the system chose to stay quiet."""
    orchestrator = Orchestrator(LearnerProfile(age_years=12))
    orchestrator.load_passage(PASSAGE)
    orchestrator.handle_utterance(
        Utterance(
            text="the cat sat on the hat and the dog ran to the park",
            confidence=0.2,
        )
    )
    report = generate_report(orchestrator.session)
    assert "Not raised" in report


def test_a_clean_read_is_praised_for_accuracy_not_pace():
    agent = ReadingAgent()
    response = agent.handle(
        Utterance(text=PASSAGE, duration_seconds=5.0), {"passage_text": PASSAGE}
    )
    assert not re.search(r"\bfast\b|\bspeed\b", response.spoken_text, re.I)
