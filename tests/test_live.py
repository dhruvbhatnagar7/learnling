"""The live reading coach, driven by a scripted recogniser instead of audio."""

from learnling.asr.sherpa import words_from_tokens
from learnling.live import PositionTracker, ReadingCoach, hint_for, run_reading, run_session
from learnling.models import Utterance

PASSAGE = "the big dog ran to the park"
TENTH = b"\x00\x00" * 1600  # 0.1 s of audio


class ScriptedRecognizer:
    """Reveals words on a schedule: [(seconds, "words heard so far"), ...]."""

    def __init__(self, script):
        self.script = script

    def reset(self):
        self.heard = 0.0

    def accept(self, pcm):
        self.heard += len(pcm) / 2 / 16000

    def partial_words(self):
        words = ""
        for at, text in self.script:
            if self.heard + 1e-9 >= at:
                words = text
        return words.split()

    def finish(self):
        return Utterance(text=" ".join(self.partial_words()), duration_seconds=self.heard)


def _coach(script, **kwargs):
    return ReadingCoach(PASSAGE, ScriptedRecognizer(script), **kwargs)


def _run(coach, seconds):
    said = []
    for _ in range(int(seconds * 10)):
        event = coach.feed(TENTH)
        if event:
            said.append((round(event.at_seconds), event.kind, event.word))
    return said


def test_tracker_follows_the_reader_and_allows_a_skip():
    tracker = PositionTracker(PASSAGE)
    assert tracker.update("the big".split()) == 2
    assert tracker.update("the big ran".split()) == 4  # skipped "dog"


def test_tracker_ignores_a_common_word_far_ahead():
    tracker = PositionTracker("the cat sat on a mat by a big tree near the house")
    tracker.update("the cat".split())
    assert tracker.update("the cat um the".split()) == 2


def test_a_steady_reader_gets_no_help():
    script = [(0.5, "the"), (1.0, "the big"), (1.5, "the big dog"), (2.0, "the big dog ran"),
              (2.5, "the big dog ran to"), (3.0, "the big dog ran to the"), (3.5, "the big dog ran to the park")]
    coach = _coach(script)
    assert _run(coach, 5) == []
    assert coach.finished


def test_a_stall_gets_a_hint_then_the_word():
    coach = _coach([(0.5, "the"), (1.0, "the big")], age_years=8)
    said = _run(coach, 8)
    assert said == [(4, "hint", "dog"), (7, "supply", "dog")]
    assert coach.tracker.position == 3


def test_younger_readers_get_longer_before_a_hint():
    coach = _coach([(0.5, "the"), (1.0, "the big")], age_years=5)
    assert _run(coach, 8) == [(6, "hint", "dog")]


def test_sounding_out_without_progress_still_counts_as_stuck():
    coach = _coach([(0.5, "the"), (1.0, "the big"), (2.0, "the big d"), (3.0, "the big d do")])
    assert _run(coach, 5)[0] == (4, "hint", "dog")


def test_a_misreading_the_reader_moves_past_is_left_alone():
    script = [(0.5, "the big"), (1.0, "the big dug"), (1.5, "the big dug ran"), (2.0, "the big dug ran to the park")]
    coach = _coach(script)
    assert _run(coach, 4) == []


def test_a_self_correction_is_left_alone():
    script = [(0.5, "the big"), (1.0, "the big dug"), (1.5, "the big dug dog"), (2.0, "the big dug dog ran to the park")]
    coach = _coach(script)
    assert _run(coach, 4) == []


def test_hints_never_say_the_word():
    for word in ("dog", "steam", "apprehension"):
        assert word not in hint_for(word).lower().replace(f"'{word[:2]}'", "")


def test_quiet_read_never_speaks():
    coach = _coach([(0.5, "the")], hints=False)
    assert _run(coach, 10) == []


def test_saying_nothing_at_all_is_stuck_on_the_first_word():
    coach = _coach([])
    assert _run(coach, 7)[0] == (6, "hint", "the")


def test_reading_ends_soon_after_the_last_word():
    script = [(0.5, PASSAGE)]
    coach = _coach(script)
    run_reading(coach, (TENTH for _ in range(100)), lambda text: None)
    assert coach.heard_seconds < 3


def test_session_reads_twice_and_reports_fluency():
    spoken = []
    script = [(1.0, PASSAGE)]
    result = run_session(
        PASSAGE,
        ScriptedRecognizer(script),
        (TENTH for _ in range(40)),
        (TENTH for _ in range(40)),
        spoken.append,
    )
    assert result.first_read_events == []
    assert result.second_accuracy == 1.0
    assert result.second_wcpm is not None
    assert any("one more time" in line for line in spoken)


def test_bpe_pieces_join_into_words_with_confidence():
    words = words_from_tokens([" THE", " YE", "LL", "OW", " LA", "MP"], [0.1, 0.4, 0.5, 0.6, 0.9, 1.0],
                              [-0.1, -0.2, -0.2, -0.2, -0.5, -0.5])
    assert [w[0] for w in words] == ["THE", "YELLOW", "LAMP"]
    assert words[1][1] == 0.4 and words[1][2] == 0.9
    assert 0.6 < words[2][3] < 0.61


def test_the_stuck_clock_starts_when_the_reader_does():
    # Quiet while the reader settles, a false start, then a steady read: no hint.
    script = [(2.5, "um"), (3.2, "um the"), (3.6, "um the big"), (4.0, "um the big dog"),
              (4.5, "um the big dog ran"), (5.0, "um the big dog ran to the park")]
    assert _run(_coach(script), 6) == []


def test_misheard_words_that_keep_coming_are_not_stuck():
    # The recogniser mishears the opening, but words keep arriving: no hint.
    script = [(0.5, "a"), (1.0, "a guard"), (1.5, "a guard sat"), (2.0, "a guard sat on"),
              (2.5, "a guard sat on mud"), (3.0, "a guard sat on mud and"),
              (3.5, "a guard sat on mud and ran to"), (4.0, "a guard sat on mud and ran to the park")]
    assert _run(_coach(script), 5) == []
