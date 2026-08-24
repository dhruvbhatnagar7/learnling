"""The miscue confidence gate: bias toward silence over false accusation.

Child ASR still misrecognises correct productions, and the two failure modes
cost very different things. A missed error is recoverable — the next read
surfaces it. A false "you got that wrong" is not: it costs a child confidence
in their own reading and trust in the tool, and no later correction takes it
back. So the detector errs toward staying quiet.
"""

from __future__ import annotations

import pytest

from learnling.agents.reading import (
    MISCUE_CONFIDENCE_THRESHOLD,
    ReadingAgent,
    align,
    configured_confidence_threshold,
    surfaceable,
)
from learnling.models import Utterance

PASSAGE = "the cat sat on the mat"


def test_low_confidence_miscues_are_dropped_silently():
    agent = ReadingAgent()
    utterance = Utterance(
        text="the cat sat on the hat",
        word_confidences=[0.99, 0.99, 0.99, 0.99, 0.99, 0.20],
    )
    result = agent.assess(PASSAGE, utterance)
    assert result.miscues == []
    assert result.suppressed_miscues == 1


def test_high_confidence_miscues_are_surfaced():
    agent = ReadingAgent()
    utterance = Utterance(
        text="the cat sat on the hat",
        word_confidences=[0.99, 0.99, 0.99, 0.99, 0.99, 0.98],
    )
    result = agent.assess(PASSAGE, utterance)
    assert len(result.miscues) == 1
    assert result.miscues[0].heard == "hat"


def test_a_suppressed_miscue_does_not_count_against_accuracy():
    """We must not quietly score a child down for something we declined to raise."""
    agent = ReadingAgent()
    utterance = Utterance(
        text="the cat sat on the hat",
        word_confidences=[0.99, 0.99, 0.99, 0.99, 0.99, 0.10],
    )
    result = agent.assess(PASSAGE, utterance)
    assert result.accuracy == 1.0
    assert result.assessment == "clean"


def test_unknown_confidence_is_not_treated_as_low_confidence():
    """A typed or simulated transcript is exact; absence of a score is not doubt."""
    agent = ReadingAgent()
    result = agent.assess(PASSAGE, Utterance(text="the cat sat on the hat"))
    assert len(result.miscues) == 1


def test_utterance_level_confidence_is_used_when_word_level_is_absent():
    agent = ReadingAgent()
    result = agent.assess(
        PASSAGE, Utterance(text="the cat sat on the hat", confidence=0.3)
    )
    assert result.miscues == []
    assert result.suppressed_miscues == 1


def test_threshold_is_configurable_per_call():
    agent = ReadingAgent()
    utterance = Utterance(
        text="the cat sat on the hat",
        word_confidences=[0.99, 0.99, 0.99, 0.99, 0.99, 0.50],
    )
    assert agent.assess(PASSAGE, utterance, confidence_threshold=0.9).miscues == []
    assert len(agent.assess(PASSAGE, utterance, confidence_threshold=0.1).miscues) == 1


def test_threshold_is_configurable_by_environment(monkeypatch):
    monkeypatch.setenv("LEARNLING_MISCUE_CONFIDENCE", "0.4")
    assert configured_confidence_threshold() == 0.4


def test_a_malformed_environment_threshold_falls_back_to_the_default(monkeypatch):
    """A typo in configuration must not silently disable the gate."""
    monkeypatch.setenv("LEARNLING_MISCUE_CONFIDENCE", "not-a-number")
    assert configured_confidence_threshold() == MISCUE_CONFIDENCE_THRESHOLD


def test_the_default_errs_toward_silence():
    """A majority-confidence guess is still not confident enough to accuse."""
    assert MISCUE_CONFIDENCE_THRESHOLD > 0.5


def test_only_the_uncertain_miscue_is_dropped():
    """Suppression is per-miscue, not all-or-nothing for the utterance."""
    agent = ReadingAgent()
    utterance = Utterance(
        text="the bat sat on the hat",
        word_confidences=[0.99, 0.99, 0.99, 0.99, 0.99, 0.10],
    )
    result = agent.assess(PASSAGE, utterance)
    assert [m.heard for m in result.miscues] == ["bat"]
    assert result.suppressed_miscues == 1


def test_align_records_the_confidence_each_miscue_was_judged_at():
    miscues = align(
        ["the", "cat"], ["the", "hat"], word_confidences=[0.9, 0.42]
    )
    assert len(miscues) == 1
    assert miscues[0].confidence == pytest.approx(0.42)


def test_surfaceable_keeps_miscues_exactly_at_the_threshold():
    from learnling.models import Miscue

    at_threshold = Miscue("substitution", "cat", "hat", 1, confidence=0.75)
    assert surfaceable([at_threshold], 0.75) == [at_threshold]
