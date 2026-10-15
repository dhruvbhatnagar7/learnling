"""The Reading Agent: oral reading practice with scaffolded feedback.

A child reads a known passage aloud; the ASR layer produces a transcript;
this agent aligns transcript against expected text, classifies the reading
into a miscue-driven assessment, and returns feedback that coaches toward
the answer without ever giving it away.
"""

from __future__ import annotations

import os
import re
import string
from difflib import SequenceMatcher

from learnling.fluency import compute_wcpm
from learnling.models import AgentResponse, Assessment, Miscue, ReadingResult, Utterance

_WHITESPACE = re.compile(r"\s+")

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def _number_words(token: str) -> list[str]:
    """Spell out 0-99, since recognisers often write "nine" as "9"."""
    if not token.isdigit() or len(token) > 2:
        return [token]
    n = int(token)
    if n < 20:
        return [_ONES[n]]
    tens, ones = divmod(n, 10)
    return [_TENS[tens - 2]] + ([_ONES[ones]] if ones else [])

#: Confidence a candidate miscue must reach before the child hears about it.
#:
#: Miscue detection here is deliberately biased toward *not* flagging: high
#: precision over high recall. Child ASR still misrecognises correct
#: productions, and the two failure modes are not symmetric. A missed error
#: costs one coaching opportunity out of many, and the next read will surface
#: it again. A false accusation costs a child's confidence in their own
#: reading and their trust in the tool, and no later correction takes that
#: back — a child told they got a word wrong when they did not learns that
#: the machine is unfair, or worse, that they are worse at reading than they
#: thought.
#:
#: Set `LEARNLING_MISCUE_CONFIDENCE` to override. Raising it makes the agent
#: quieter and more trustworthy; lowering it catches more real miscues at the
#: cost of occasionally correcting a child who was right.
MISCUE_CONFIDENCE_THRESHOLD = 0.75


def configured_confidence_threshold() -> float:
    """The active threshold, from the environment or the default above."""
    raw = os.environ.get("LEARNLING_MISCUE_CONFIDENCE")
    if raw is None:
        return MISCUE_CONFIDENCE_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return MISCUE_CONFIDENCE_THRESHOLD


def normalize_words(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    stripped = text.translate(str.maketrans("", "", string.punctuation))
    return [
        word
        for token in _WHITESPACE.split(stripped.lower().strip())
        if token
        for word in _number_words(token)
    ]


def edit_distance(a: str, b: str) -> int:
    """Plain Levenshtein distance (stdlib only, no rapidfuzz/etc.)."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def is_near_miss(expected: str | None, heard: str | None) -> bool:
    """A substitution that looks like a decoding slip rather than a random swap."""
    if not expected or not heard:
        return False
    if edit_distance(expected, heard) <= 2:
        return True
    return expected[0] == heard[0]


def match_word_joins(
    expected_words: list[str],
    transcript_words: list[str],
    word_confidences: list[float] | None = None,
) -> tuple[list[str], list[float] | None]:
    """Write heard words the way the page splits them.

    "for ever" and "forever", or "in to" and "into", sound the same; the
    recogniser picks one spelling and the page may use the other. Left alone,
    that counts as a misreading the child never made. A heard word that is two
    adjacent page words joined is split, and two heard words that join into a
    page word are merged (keeping the lower confidence).
    """
    page = set(expected_words)
    joined_pairs = {
        a + b: (a, b) for a, b in zip(expected_words, expected_words[1:])
    }
    adjacent = set(zip(expected_words, expected_words[1:]))

    def conf(index: int) -> float | None:
        if word_confidences is None or not 0 <= index < len(word_confidences):
            return None
        return word_confidences[index]

    words: list[str] = []
    confidences: list[float | None] = []
    i = 0
    while i < len(transcript_words):
        word = transcript_words[i]
        nxt = transcript_words[i + 1] if i + 1 < len(transcript_words) else None
        if word not in page and word in joined_pairs:
            words += joined_pairs[word]
            confidences += [conf(i), conf(i)]
            i += 1
        elif nxt is not None and word + nxt in page and (word, nxt) not in adjacent:
            words.append(word + nxt)
            pair = [c for c in (conf(i), conf(i + 1)) if c is not None]
            confidences.append(min(pair) if pair else None)
            i += 2
        else:
            words.append(word)
            confidences.append(conf(i))
            i += 1

    if word_confidences is None:
        return words, None
    return words, confidences


def align(
    expected_words: list[str],
    transcript_words: list[str],
    word_confidences: list[float] | None = None,
    default_confidence: float | None = None,
) -> list[Miscue]:
    """Diff expected vs. heard words into a list of ordered Miscues.

    Each miscue carries the ASR confidence it was judged at, so a caller can
    decline to surface the ones the recogniser was unsure about.
    """
    transcript_words, word_confidences = match_word_joins(
        expected_words, transcript_words, word_confidences
    )

    def heard_confidence(index: int) -> float | None:
        if word_confidences is not None and 0 <= index < len(word_confidences):
            return word_confidences[index]
        return default_confidence

    matcher = SequenceMatcher(None, expected_words, transcript_words)
    miscues: list[Miscue] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            span = max(i2 - i1, j2 - j1)
            for k in range(span):
                expected = expected_words[i1 + k] if i1 + k < i2 else None
                heard = transcript_words[j1 + k] if j1 + k < j2 else None
                if expected is not None and heard is not None:
                    miscues.append(
                        Miscue(
                            "substitution", expected, heard, i1 + k,
                            heard_confidence(j1 + k),
                        )
                    )
                elif expected is not None:
                    # Nothing was heard, so there is no word-level score to
                    # consult; fall back to how sure the recogniser was overall.
                    miscues.append(
                        Miscue("omission", expected, None, i1 + k, default_confidence)
                    )
                else:
                    miscues.append(
                        Miscue("insertion", None, heard, i1, heard_confidence(j1 + k))
                    )
        elif tag == "delete":
            for k in range(i1, i2):
                miscues.append(
                    Miscue("omission", expected_words[k], None, k, default_confidence)
                )
        elif tag == "insert":
            for k in range(j1, j2):
                miscues.append(
                    Miscue(
                        "insertion", None, transcript_words[k], i1, heard_confidence(k)
                    )
                )
    return miscues


def surfaceable(miscues: list[Miscue], threshold: float) -> list[Miscue]:
    """Drop miscues the recogniser was not confident enough about.

    See `MISCUE_CONFIDENCE_THRESHOLD` for why this errs toward silence. A
    miscue with no confidence information at all is kept: unknown is not the
    same as low, and a typed or simulated transcript is exact by construction.
    """
    return [m for m in miscues if m.confidence is None or m.confidence >= threshold]


_FLUENCY_WPM_FLOOR = 40.0


def classify(
    expected_words: list[str], miscues: list[Miscue], accuracy: float, wpm: float | None
) -> Assessment:
    if accuracy >= 0.95:
        return "clean"

    substitutions = [m for m in miscues if m.kind == "substitution"]
    flow_miscues = [m for m in miscues if m.kind in ("omission", "insertion")]
    near_misses = [m for m in substitutions if is_near_miss(m.expected, m.heard)]

    decoding_signal = bool(substitutions) and len(near_misses) / len(substitutions) >= 0.5
    fluency_signal = len(flow_miscues) > len(substitutions) or (
        wpm is not None and wpm < _FLUENCY_WPM_FLOOR
    )

    if decoding_signal and not fluency_signal:
        return "decoding"
    if fluency_signal:
        return "fluency"
    if decoding_signal:
        return "decoding"
    return "comprehension"


def _feedback_for(miscues: list[Miscue]) -> str:
    """Scaffold, don't solve: coach the FIRST miscue only, never the answer."""
    if not miscues:
        return "Beautiful! Every word matched. Want to try a trickier one?"

    first = miscues[0]
    if first.kind == "substitution":
        hint = (first.expected or "")[:2]
        return (
            f"Nice reading! Let's look at one word again — it starts with '{hint}'. "
            "Try that word one more time."
        )
    if first.kind == "omission":
        # Deliberately not "you're moving fast" — praising pace teaches a
        # child that reading is a race, and that the moment it stops being
        # fast they are failing at it. The skip is named without the compliment.
        return "Nearly all of it! One little word got skipped — try that line again and see if you can catch it."
    return "Great try! Let's read that part again, nice and slow, so every word matches the page."


class ReadingAgent:
    name = "reading"

    def can_handle(self, utterance: Utterance, context: dict) -> bool:
        return bool(context.get("passage_text"))

    def assess(
        self,
        passage_text: str,
        utterance: Utterance,
        confidence_threshold: float | None = None,
    ) -> ReadingResult:
        expected_words = normalize_words(passage_text)
        transcript_words = normalize_words(utterance.text)

        threshold = (
            configured_confidence_threshold()
            if confidence_threshold is None
            else confidence_threshold
        )
        candidates = align(
            expected_words,
            transcript_words,
            word_confidences=utterance.word_confidences,
            default_confidence=utterance.confidence,
        )
        miscues = surfaceable(candidates, threshold)
        suppressed = len(candidates) - len(miscues)

        # Accuracy is computed from what survives the confidence gate: a
        # miscue we were not willing to raise with the child must not quietly
        # count against them in the number either.
        matched = len(expected_words) - sum(
            1 for m in miscues if m.kind in ("substitution", "omission")
        )
        accuracy = matched / len(expected_words) if expected_words else 0.0

        wpm = None
        wcpm = None
        if utterance.duration_seconds:
            wpm = len(transcript_words) / (utterance.duration_seconds / 60.0)
            # Same counting rule as accuracy: only errors we were willing to
            # raise count against the reader.
            wcpm = compute_wcpm(
                len(expected_words), len(expected_words) - matched, utterance.duration_seconds
            )

        assessment = classify(expected_words, miscues, accuracy, wpm)

        return ReadingResult(
            passage=passage_text,
            transcript=utterance.text,
            miscues=miscues,
            accuracy=accuracy,
            wpm=wpm,
            assessment=assessment,
            suppressed_miscues=suppressed,
            wcpm=wcpm,
        )

    def handle(self, utterance: Utterance, context: dict) -> AgentResponse:
        result = self.assess(context["passage_text"], utterance)
        feedback = _feedback_for(result.miscues)

        miscue_counts: dict[str, int] = {}
        for m in result.miscues:
            miscue_counts[m.kind] = miscue_counts.get(m.kind, 0) + 1

        return AgentResponse(
            agent_name=self.name,
            spoken_text=feedback,
            report_notes={
                "reading_result": result,
                "miscue_counts": miscue_counts,
                "accuracy": result.accuracy,
                "wpm": result.wpm,
                "wcpm": result.wcpm,
                "assessment": result.assessment,
                "suppressed_miscues": result.suppressed_miscues,
            },
        )
