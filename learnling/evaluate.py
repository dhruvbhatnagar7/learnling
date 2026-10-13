"""Measure how well an ASR adapter plus the reading agent judge real readings.

A test set is a folder of recordings, each with a small JSON label file next
to it:

    reading-01.wav
    reading-01.json   {"passage": "The cat sat on the mat.",
                       "said": "the cat sat on the hat"}

`said` is what the reader actually said, typed out by a person who listened
to the recording: misread words as they were said ("hat"), skipped words
left out, sounded-out attempts written however they sounded ("mmm-at").
`passage` may instead be `passage_file`, a path relative to the JSON file.

Typing what was said is much easier to label than marking word positions,
and it lets the same alignment code that judges the child produce the
answer key, so the two can be compared word by word.

The number that matters most is the false-accusation rate: of the words the
reader got right, how many did learnling say were wrong. See
`MISCUE_CONFIDENCE_THRESHOLD` in `agents/reading.py` for why.

Recordings of children are sensitive. Keep test sets out of the repository
(`*.wav` is already ignored) and record a child only with a parent's written
consent. See `docs/audio-evaluation.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from learnling.agents.reading import ReadingAgent, align, normalize_words
from learnling.asr.base import ASRAdapter

#: Miscue kinds that count as a word read wrong. Insertions are not errors
#: under the fluency counting rules (see `fluency.py`), so they are left out
#: of both sides of the comparison.
_ERROR_KINDS = ("substitution", "omission")


@dataclass
class CaseResult:
    name: str
    words: int
    true_errors: set[int]
    flagged: set[int]
    suppressed: int
    wcpm: int | None
    transcript: str

    @property
    def caught(self) -> int:
        return len(self.true_errors & self.flagged)

    @property
    def missed(self) -> int:
        return len(self.true_errors - self.flagged)

    @property
    def false_accusations(self) -> int:
        return len(self.flagged - self.true_errors)


@dataclass
class EvalSummary:
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def correct_words(self) -> int:
        return sum(c.words - len(c.true_errors) for c in self.cases)

    @property
    def true_errors(self) -> int:
        return sum(len(c.true_errors) for c in self.cases)

    @property
    def false_accusation_rate(self) -> float | None:
        correct = self.correct_words
        if not correct:
            return None
        return sum(c.false_accusations for c in self.cases) / correct

    @property
    def catch_rate(self) -> float | None:
        errors = self.true_errors
        if not errors:
            return None
        return sum(c.caught for c in self.cases) / errors


def _error_positions(miscues) -> set[int]:
    return {m.position for m in miscues if m.kind in _ERROR_KINDS}


def load_case(label_path: Path) -> tuple[str, str, Path]:
    """Return (passage, said, audio path) for one labelled recording."""
    label = json.loads(label_path.read_text())
    if "passage" in label:
        passage = label["passage"]
    else:
        passage = (label_path.parent / label["passage_file"]).read_text()
    audio = label_path.parent / label.get("audio", label_path.with_suffix(".wav").name)
    return passage.strip(), label["said"], audio


def evaluate_case(
    name: str,
    passage: str,
    said: str,
    audio,
    asr: ASRAdapter,
    confidence_threshold: float | None = None,
) -> CaseResult:
    expected = normalize_words(passage)
    true_errors = _error_positions(align(expected, normalize_words(said)))

    utterance = asr.transcribe(audio)
    result = ReadingAgent().assess(passage, utterance, confidence_threshold)

    return CaseResult(
        name=name,
        words=len(expected),
        true_errors=true_errors,
        flagged=_error_positions(result.miscues),
        suppressed=result.suppressed_miscues,
        wcpm=result.wcpm,
        transcript=utterance.text,
    )


def evaluate_folder(
    folder: str | Path,
    asr_for_passage,
    confidence_threshold: float | None = None,
) -> EvalSummary:
    """Run every labelled recording in `folder`.

    `asr_for_passage` is called with each passage and returns the adapter to
    use, because passage-constrained recognisers are built per passage.
    """
    summary = EvalSummary()
    for label_path in sorted(Path(folder).glob("*.json")):
        passage, said, audio = load_case(label_path)
        summary.cases.append(
            evaluate_case(
                label_path.stem,
                passage,
                said,
                str(audio),
                asr_for_passage(passage),
                confidence_threshold,
            )
        )
    return summary


def format_summary(summary: EvalSummary) -> str:
    def pct(value: float | None) -> str:
        return "-" if value is None else f"{value:.0%}"

    lines = [
        f"{'recording':<24}{'words':>6}{'errors':>8}{'caught':>8}{'missed':>8}"
        f"{'false':>7}{'quiet':>7}{'wcpm':>6}",
    ]
    for c in summary.cases:
        lines.append(
            f"{c.name:<24}{c.words:>6}{len(c.true_errors):>8}{c.caught:>8}{c.missed:>8}"
            f"{c.false_accusations:>7}{c.suppressed:>7}{(c.wcpm if c.wcpm is not None else '-'):>6}"
        )
    lines += [
        "",
        f"Recordings:            {len(summary.cases)}",
        f"False-accusation rate: {pct(summary.false_accusation_rate)}"
        f"  (correct words learnling called wrong, of {summary.correct_words})",
        f"Catch rate:            {pct(summary.catch_rate)}"
        f"  (real errors learnling flagged, of {summary.true_errors})",
        "",
        "false = flagged a word the reader got right. quiet = possible errors held back"
        " because the recogniser was unsure.",
    ]
    return "\n".join(lines)
