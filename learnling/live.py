"""Live reading: listen while someone reads, help when they get stuck, stay quiet otherwise.

    python -m learnling live --passage passages/sample_level1.txt --model PATH --voice PATH

The flow follows the product design:

1. **First read, coached.** learnling follows along word by word. If the
   reader stalls on a word, it gives a hint first (how the word starts, never
   the word). If they are still stuck, it says the word and lets them carry on.
   Misreadings and self-corrections get no interruption: a reader who fixes
   their own mistake should not hear about it.
2. **Second read, quiet.** The same passage again with no help, which gives a
   fair words-correct-per-minute number.
3. **Feedback.** One short coaching line after the first read, and a report
   for the adult at the end.

Everything here is driven by how much audio has been heard, not by the wall
clock, so the same recording always produces the same hints. That is what
makes it testable, and it means time spent while learnling itself is talking
does not count as the reader being stuck.

The listening loop needs no LLM and no internet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from learnling.adaptation import shape
from learnling.agents.reading import normalize_words
from learnling.models import LearnerProfile
from learnling.orchestrator import Orchestrator
from learnling.safety import check_output

SAMPLE_RATE = 16000

#: How far ahead of the current word a match may start and still count as
#: the reader moving on. Large enough for skipping a word or two, small enough
#: that a common word ("the") heard much later in the passage can't drag the
#: position forward.
_MAX_SKIP = 3


def stuck_seconds_for(age_years: int) -> float:
    """Silence on one word before a hint.

    About three seconds is the hesitation that fluency scoring counts as an
    error (see `fluency.py`); younger readers get longer.
    """
    return 5.0 if age_years <= 6 else 3.0


class PositionTracker:
    """Where in the passage the reader is, from the recogniser's running guess.

    The position only moves forward. It is the number of passage words the
    reader is past: either heard (in order, allowing small skips) or supplied
    by learnling.
    """

    def __init__(self, passage_text: str):
        self.expected = normalize_words(passage_text)
        self.position = 0

    @property
    def finished(self) -> bool:
        return self.position >= len(self.expected)

    @property
    def current_word(self) -> str | None:
        return None if self.finished else self.expected[self.position]

    def update(self, heard_words: list[str]) -> int:
        matcher = SequenceMatcher(None, self.expected, heard_words, autojunk=False)
        for block in matcher.get_matching_blocks():
            if block.size == 0:
                continue
            end = block.a + block.size
            if end > self.position and block.a <= self.position + _MAX_SKIP:
                self.position = end
        return self.position

    def supply_current_word(self) -> None:
        """learnling said the word for the reader; move past it."""
        if not self.finished:
            self.position += 1


@dataclass
class CoachEvent:
    """Something learnling says, and when (seconds of reading audio heard)."""

    at_seconds: float
    kind: str  # "hint" or "supply"
    word: str
    position: int
    spoken: str


def hint_for(word: str) -> str:
    """Coach toward the word without saying it."""
    if len(word) <= 2:
        return "Take your time. Look at the next word and sound it out."
    return f"Take your time. That word starts with '{word[:2]}'."


def supply_for(word: str) -> str:
    return f"That word is '{word}'. Keep going."


@dataclass
class ReadingCoach:
    """Follows one reading and decides when to help.

    `recognizer` needs `reset()`, `accept(pcm)`, `partial_words()` and
    `finish()`, as `asr.sherpa.SherpaStreamingASR` provides.
    """

    passage_text: str
    recognizer: object
    age_years: int = 8
    hints: bool = True
    stuck_seconds: float | None = None
    events: list[CoachEvent] = field(default_factory=list)

    def __post_init__(self):
        self.tracker = PositionTracker(self.passage_text)
        if self.stuck_seconds is None:
            self.stuck_seconds = stuck_seconds_for(self.age_years)
        self.heard_seconds = 0.0
        self._last_move = 0.0
        self._hinted_at: int | None = None
        self._started = False
        self.recognizer.reset()

    def _speakable(self, text: str) -> str:
        return shape(check_output(text), LearnerProfile(age_years=self.age_years).age_band)

    def feed(self, pcm: bytes) -> CoachEvent | None:
        """Hear the next stretch of audio; return what to say, if anything."""
        self.heard_seconds += len(pcm) / 2 / SAMPLE_RATE
        self.recognizer.accept(pcm)
        heard = self.recognizer.partial_words()
        if heard:
            self._started = True

        before = self.tracker.position
        if self.tracker.update(heard) > before:
            self._last_move = self.heard_seconds
            return None

        # A reader who has said nothing at all may be stuck on the first word;
        # give them twice as long before treating it that way.
        started = self._started or self.heard_seconds >= 2 * self.stuck_seconds
        if not (self.hints and started) or self.tracker.finished:
            return None
        if self.heard_seconds - self._last_move < self.stuck_seconds:
            return None

        position = self.tracker.position
        word = self.tracker.current_word
        if self._hinted_at != position:
            self._hinted_at = position
            event = CoachEvent(self.heard_seconds, "hint", word, position, self._speakable(hint_for(word)))
        else:
            self.tracker.supply_current_word()
            event = CoachEvent(self.heard_seconds, "supply", word, position, self._speakable(supply_for(word)))
        self._last_move = self.heard_seconds
        self.events.append(event)
        return event

    @property
    def finished(self) -> bool:
        return self.tracker.finished

    def finish(self):
        """Close the reading; returns the recogniser's final Utterance."""
        return self.recognizer.finish()


@dataclass
class LiveSessionResult:
    first_read_events: list[CoachEvent]
    first_feedback: str
    second_wcpm: int | None
    second_accuracy: float
    orchestrator: Orchestrator


def run_reading(coach: ReadingCoach, chunks, speak, done_after_seconds: float = 1.5):
    """Feed audio chunks to `coach` until the passage is read or audio runs out.

    `speak(text)` is called for every hint. Once the last word is reached the
    reading ends after `done_after_seconds` more audio, so a trailing word is
    not cut off.
    """
    finished_at = None
    for pcm in chunks:
        event = coach.feed(pcm)
        if event is not None:
            speak(event.spoken)
        if coach.finished and finished_at is None:
            finished_at = coach.heard_seconds
        if finished_at is not None and coach.heard_seconds - finished_at >= done_after_seconds:
            break
    return coach.finish()


def run_session(
    passage_text: str,
    recognizer,
    first_read_chunks,
    second_read_chunks,
    speak,
    age_years: int = 8,
) -> LiveSessionResult:
    """Coached first read, quiet second read, then feedback."""
    orchestrator = Orchestrator(LearnerProfile(age_years=age_years))
    orchestrator.load_passage(passage_text)

    coach = ReadingCoach(passage_text, recognizer, age_years=age_years, hints=True)
    first = run_reading(coach, first_read_chunks, speak)
    first_feedback = orchestrator.handle_utterance(first)
    speak(first_feedback)

    speak(orchestrator_say(orchestrator, "Now read it one more time, all by yourself."))
    quiet = ReadingCoach(passage_text, recognizer, age_years=age_years, hints=False)
    second = run_reading(quiet, second_read_chunks, speak)
    orchestrator.handle_utterance(second)
    second_result = orchestrator.session.events[-1]["report_notes"]["reading_result"]
    speak(orchestrator_say(orchestrator, "Well done. That's the end of this reading."))

    return LiveSessionResult(
        first_read_events=coach.events,
        first_feedback=first_feedback,
        second_wcpm=second_result.wcpm,
        second_accuracy=second_result.accuracy,
        orchestrator=orchestrator,
    )


def orchestrator_say(orchestrator: Orchestrator, text: str) -> str:
    """A fixed line, passed through the same safety and age shaping as everything else."""
    return shape(check_output(text), orchestrator.session.profile.age_band)
