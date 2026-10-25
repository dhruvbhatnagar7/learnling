"""A hands-free reading session on the book stand, started and moved along by voice.

    python -m learnling stand --passage passages/sample_level1.txt --model PATH --voice PATH

1. The stand waits, listening, until the reader says "I'm ready to read".
2. The reading buddy (a language model, see `buddy.py`) greets them. The
   stand says "Ready? Go!" and they read the story, with hints if they get
   stuck. The read ends at the last word, or when they say "done" or "stop".
3. The buddy says something about the read, and on the next "Go!" they read
   it once more with no hints.
4. The buddy asks the questions the adult approved before the session, and
   answers what the reader says.
5. The buddy says goodbye, and the adult gets the report (see `emailer.py`).

The reader's voice is only ever heard by the speech recogniser on the stand.
What they answer is turned into words for the buddy and then forgotten: it is
not kept in the report or anywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass

from learnling.agents.reading import normalize_words
from learnling.buddy import ReadingBuddy
from learnling.live import ReadingCoach, run_reading, said_stop_word
from learnling.models import LearnerProfile
from learnling.orchestrator import Orchestrator

WAKE_WORDS = ("ready",)
#: What the stand says to start each read. The reader starts straight after
#: it; there is no word for them to say first, since a single short word like
#: "read" is easily missed.
GO_LINE = "When I say go, start reading. Ready? Go!"

#: How long one listening window lasts while waiting for a word; the
#: recogniser starts fresh each window so a long wait doesn't pile up.
_WINDOW_SECONDS = 10.0


def heard_any(words: list[str], wanted) -> bool:
    return any(w in wanted for w in words)


def listen(recognizer, chunks, until=None, quiet_after: float = 1.5, max_seconds: float = _WINDOW_SECONDS):
    """Words heard from `chunks`.

    Stops as soon as `until(words)` is true, or, without `until`, once the
    speaker has said something and then gone quiet for `quiet_after` seconds.
    """
    recognizer.reset()
    words: list[str] = []
    heard = last_change = 0.0
    chunks = iter(chunks)
    try:
        for pcm in chunks:
            heard += len(pcm) / 2 / 16000
            recognizer.accept(pcm)
            now = recognizer.partial_words()
            if now != words:
                words, last_change = now, heard
            if until is not None and until(words):
                break
            if until is None and words and heard - last_change >= quiet_after:
                break
            if heard >= max_seconds:
                break
    finally:
        close = getattr(chunks, "close", None)
        if close is not None:
            close()
    return words


def wait_for(recognizer, open_mic, wanted, light=None, tries: int | None = None, on_status=None) -> bool:
    """Listen in short windows until one of `wanted` is heard; False if `tries` run out.

    `on_status` is shown what was heard, so the adult can see why it is still waiting.
    """
    attempt = 0
    while tries is None or attempt < tries:
        attempt += 1
        if light:
            light.on()
        words = listen(recognizer, open_mic(_WINDOW_SECONDS), until=lambda w: heard_any(w, wanted))
        if words and on_status:
            on_status(f"  (heard: {' '.join(words)})")
        if heard_any(words, wanted):
            return True
    return False


@dataclass
class StandSession:
    orchestrator: Orchestrator
    words_helped: list[str]
    reading_seconds: float
    questions_asked: int

    @property
    def minutes(self) -> float:
        return self.reading_seconds / 60.0


def run_stand(
    passage_text: str,
    recognizer,
    open_mic,
    speak,
    buddy: ReadingBuddy,
    questions: list[str],
    age_years: int = 8,
    light=None,
    wake: bool = True,
    on_status=print,
) -> StandSession:
    """One hands-free session. `open_mic(max_seconds)` gives a fresh stream of microphone chunks."""
    orchestrator = Orchestrator(LearnerProfile(age_years=age_years))
    orchestrator.load_passage(passage_text)
    max_read = max(30.0, len(normalize_words(passage_text)) * 3.0)

    if wake:
        on_status('Waiting for "I\'m ready to read"...')
        wait_for(recognizer, open_mic, WAKE_WORDS, light, on_status=on_status)
    speak(buddy.greet())

    def reading(hints: bool):
        speak(_line(orchestrator, GO_LINE))
        if light:
            light.on()
        coach = ReadingCoach(passage_text, recognizer, age_years=age_years, hints=hints)
        utterance = run_reading(coach, open_mic(max_read), speak, stop_when=said_stop_word)
        if light:
            light.off()
        on_status(f"  (read heard as: {utterance.text})")
        # A reader who stops partway is scored on the part they read, not
        # marked as skipping the rest of the page.
        if not coach.finished and coach.tracker.position > 0:
            orchestrator.load_passage(" ".join(coach.tracker.expected[:coach.tracker.position]))
        orchestrator.handle_utterance(_without_stop_word(utterance))
        orchestrator.load_passage(passage_text)
        result = orchestrator.session.events[-1]["report_notes"]["reading_result"]
        return coach, result

    first_coach, first = reading(hints=True)
    helped = list(dict.fromkeys(e.word for e in first_coach.events))
    speak(buddy.after_first_read(helped, first.accuracy))
    second_coach, _ = reading(hints=False)

    for question in questions:
        speak(buddy.ask(question))
        if light:
            light.on()
        answer = listen(recognizer, open_mic(15.0), quiet_after=2.0, max_seconds=15.0)
        if light:
            light.off()
        speak(buddy.answer(" ".join(answer)))

    seconds = first_coach.heard_seconds + second_coach.heard_seconds
    speak(buddy.goodbye(seconds / 60.0))
    return StandSession(orchestrator, helped, seconds, len(questions))


def _line(orchestrator: Orchestrator, text: str) -> str:
    from learnling.live import orchestrator_say

    return orchestrator_say(orchestrator, text)


def _without_stop_word(utterance):
    """Drop a trailing "done" so it isn't scored as an extra word."""
    from learnling.live import STOP_WORDS

    words = normalize_words(utterance.text)
    if not words or words[-1] not in STOP_WORDS:
        return utterance
    utterance.text = " ".join(words[:-1])
    if utterance.word_confidences is not None:
        utterance.word_confidences = utterance.word_confidences[:-1]
    if utterance.word_timestamps:
        utterance.word_timestamps = utterance.word_timestamps[:-1]
        if utterance.word_timestamps:
            first, last = utterance.word_timestamps[0], utterance.word_timestamps[-1]
            utterance.duration_seconds = max(last["end"] - first["start"], 0.0) or None
    return utterance
