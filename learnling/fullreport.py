"""The full report: each read scored again after the session, by a better recogniser.

The stand's live recogniser is there to time hints. It is quick, but too
unreliable to say which words were read wrong. So the stand keeps the audio of
the two reads in memory, and once the session is over it scores them again
with a slower, more careful model (Whisper, or a children's fine-tune of it),
on the stand itself. The audio is written to a temporary file only for that,
and deleted straight after. Nothing is sent anywhere except the finished
report, by email, to the adult.

Even this model gets words wrong, so the report says so, and it is meant as a
pointer for the adult, a hint of what to listen for, not a score.
"""

from __future__ import annotations

import os
import re
import tempfile

from learnling.agents.reading import ReadingAgent, normalize_words
from learnling.patterns import PATTERN_NAMES
from learnling.record import write_wav
from learnling.report import _NOT_MISTAKES, _describe, _pattern_summary, _words_to_look_at

#: Lower than the live threshold: the full report is for an adult, who can
#: weigh a doubtful word, and catching more slips matters more here than in
#: what the child hears. Tune it on the pilot recordings.
FULL_REPORT_CONFIDENCE = 0.5

CAVEAT = (
    "learnling can get words wrong, especially with children's voices. Use this as a pointer to\n"
    "what to listen for next time, not as a score."
)


class ReadKeeper:
    """`on_read` for the stand: keeps each read's audio in memory until it is scored."""

    def __init__(self, also=None):
        self.reads: list[tuple[int, bool, bytes, str]] = []
        self._also = also

    def __call__(self, number: int, hints: bool, pcm: bytes, passage: str | None = None) -> None:
        if pcm and passage:
            self.reads.append((number, hints, pcm, passage))
        if self._also is not None:
            self._also(number, hints, pcm, passage=passage)

    def clear(self) -> None:
        self.reads = []


def score_reads(reads, asr, confidence: float = FULL_REPORT_CONFIDENCE, story_prompt: bool = False):
    """Each read's `ReadingResult`, from `asr.transcribe(wav_path)`. Audio is deleted after.

    With `story_prompt`, `asr` must have `with_prompt` (WhisperASR does): each read
    is transcribed with its passage as the prompt.
    """
    agent = ReadingAgent()
    results = []
    for number, hints, pcm, passage in reads:
        handle, path = tempfile.mkstemp(suffix=".wav")
        os.close(handle)
        try:
            write_wav(path, pcm)
            # A Whisper scorer hears unclear words better when it is told the page.
            utterance = (asr.with_prompt(passage) if story_prompt else asr).transcribe(path)
        finally:
            os.remove(path)
        results.append((number, hints, agent.assess(passage, utterance, confidence)))
    return results


def hard_page_words(passage: str) -> set[str]:
    """Page words no recogniser reads reliably: abbreviations (IEPs, DIBELS) and numbers."""
    hard = set()
    for raw in passage.split():
        if re.search(r"\d", raw) or sum(c.isupper() for c in raw) >= 2:
            hard.update(normalize_words(raw))
    return hard


def _worth_listing(entry: dict, hard: set[str]) -> bool:
    # An "added" word is nearly always the recogniser filling a pause, and an
    # adult can't act on it, so the full report leaves those out.
    if entry["kind"] == "insertion":
        return False
    return entry["word"] not in hard


def full_report_text(scored, words_helped: list[str]) -> str:
    """Plain-text full report from `score_reads` output."""
    stats = []
    for _, _, result in scored:
        hard = hard_page_words(result.passage)
        entries = _words_to_look_at({"reading_result": result})
        stats.append({"words_to_look_at": [e for e in entries if _worth_listing(e, hard)]})
    lines = ["learnling full report", ""]
    for (number, hints, result), stat in zip(scored, stats):
        label = "First read (with hints)" if hints else "Second read (on their own)"
        numbers = f"{result.accuracy:.0%} of words matched the page"
        if result.wcpm is not None:
            numbers += f", {result.wcpm} words correct per minute"
        lines.append(f"{label}: {numbers}.")
        if hints and words_helped:
            lines.append("  Hints given for: " + ", ".join(words_helped) + ".")
        mistakes = [e for e in stat["words_to_look_at"] if e["sure"] and e["kind"] not in _NOT_MISTAKES]
        fixed = [e for e in stat["words_to_look_at"] if e["kind"] in _NOT_MISTAKES]
        if mistakes:
            lines.append("  Words to look at:")
            lines += [f"  - {_describe(e)}" for e in mistakes]
        else:
            lines.append("  No words stood out.")
        if fixed:
            lines.append("  Fixed or repeated (not mistakes): " + "; ".join(_describe(e) for e in fixed) + ".")
        lines.append("")
    patterns = _pattern_summary(stats)
    if patterns:
        lines.append("Patterns that came up more than once:")
        lines += [f"- {PATTERN_NAMES[p].capitalize()}: {', '.join(words)}" for p, words in patterns]
        lines.append("")
    lines.append(CAVEAT)
    return "\n".join(lines) + "\n"
