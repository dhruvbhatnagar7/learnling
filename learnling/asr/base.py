"""The ASR adapter contract.

Every speech-recognition backend — simulated, generic Whisper, or a future
open child-speech model — implements this single method and returns an
`Utterance`. Nothing downstream (orchestrator, agents) needs to know which
backend produced the transcript.
"""

from __future__ import annotations

from typing import Protocol

from learnling.agents.reading import normalize_words
from learnling.models import Utterance


class ASRAdapter(Protocol):
    def transcribe(self, audio: str | bytes) -> Utterance:
        """Transcribe an audio file path or raw bytes into an Utterance."""
        ...


def utterance_from_words(words: list[tuple[str, float, float, float | None]]) -> Utterance:
    """Build an Utterance from (word, start, end, probability) tuples.

    The transcript is rebuilt from the words themselves so `word_confidences`
    lines up one to one with `normalize_words(utterance.text)`, which is what
    the reading agent indexes it by. Tokens that are only punctuation drop
    out, and a token that normalizes to two words keeps its score for both.

    `duration_seconds` is the time from the first word to the last, not the
    length of the file: silence before the child starts is not reading time.
    """
    kept = [
        (part, start, end, prob)
        for text, start, end, prob in words
        for part in normalize_words(text)
    ]
    if not kept:
        return Utterance(text="", confidence=None, duration_seconds=None)

    confidences = [prob for _, _, _, prob in kept]
    known = [c for c in confidences if c is not None]
    return Utterance(
        text=" ".join(text for text, _, _, _ in kept),
        confidence=sum(known) / len(known) if known else None,
        duration_seconds=max(kept[-1][2] - kept[0][1], 0.0) or None,
        word_timestamps=[
            {"word": text, "start": start, "end": end} for text, start, end, _ in kept
        ],
        word_confidences=confidences if len(known) == len(confidences) else None,
    )
