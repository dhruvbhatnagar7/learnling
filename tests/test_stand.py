"""The hands-free stand session, driven by a scripted recogniser and a pretend language model."""

from learnling.buddy import FALLBACK_QUESTIONS, ReadingBuddy, clean_for_speech, parse_questions
from learnling.emailer import report_text
from learnling.live import ReadingCoach, lines_for_passage, run_reading, said_stop_word
from learnling.stand import listen, run_stand
from tests.test_live import TENTH, ScriptedRecognizer

PASSAGE = "the big dog ran to the park"


class PhaseRecognizer(ScriptedRecognizer):
    """A new script each time listening starts again, like a child taking turns."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.script = []

    def reset(self):
        super().reset()
        self.script = self.scripts.pop(0) if self.scripts else []


def open_mic(seconds):
    return (TENTH for _ in range(int(seconds * 10)))


class FakeChat:
    def __init__(self, reply="Great reading!"):
        self.reply = reply
        self.seen = []

    def __call__(self, messages, max_words=40):
        self.seen.append(messages)
        return self.reply


def test_listen_stops_once_the_word_is_heard():
    rec = PhaseRecognizer([[(0.5, "um"), (1.0, "um ready")]])
    assert listen(rec, open_mic(10), until=lambda w: "ready" in w) == ["um", "ready"]
    assert rec.heard < 1.2


def test_listen_for_an_answer_waits_for_a_pause():
    rec = PhaseRecognizer([[(0.5, "the"), (1.0, "the dog")]])
    assert listen(rec, open_mic(15), quiet_after=2.0) == ["the", "dog"]
    assert 2.9 < rec.heard < 3.2


def test_saying_done_ends_the_reading():
    rec = ScriptedRecognizer([(0.5, "the big"), (1.0, "the big done")])
    coach = ReadingCoach(PASSAGE, rec)
    run_reading(coach, open_mic(20), lambda text: None, stop_when=said_stop_word)
    assert coach.heard_seconds < 1.2


def test_done_on_the_page_is_read_not_obeyed():
    rec = ScriptedRecognizer([(0.5, "we are done")])
    coach = ReadingCoach("we are done with the cake", rec)
    run_reading(coach, open_mic(3), lambda text: None, stop_when=said_stop_word)
    assert coach.heard_seconds > 2.9


def test_a_whole_session_by_voice():
    rec = PhaseRecognizer([
        [(1.0, "im ready to read")],          # wake
        [(1.0, "read")],                      # start the first read
        [(0.5, "the big"), (6.0, "the big dog ran to the park")],  # stuck on "dog"
        [(1.0, "read")],                      # start the second read
        [(0.5, PASSAGE), (1.0, PASSAGE + " done")],
        [(1.0, "it ran to the park")],        # answer to the question
    ])
    spoken = []
    chat = FakeChat("You did it!")
    buddy = ReadingBuddy(PASSAGE, 8, chat=chat)
    session = run_stand(PASSAGE, rec, open_mic, spoken.append, buddy, ["Where did the dog go?"],
                        on_status=lambda text: None)

    assert session.words_helped == ["dog"]
    assert any("starts with 'do'" in line for line in spoken)
    assert "Where did the dog go?" in spoken
    assert spoken[-1] == "You did it!"
    # The model was told what the child answered, and nothing else from them was kept.
    assert "it ran to the park" in chat.seen[-2][-1]["content"]
    second = session.orchestrator.session.events[-1]["report_notes"]["reading_result"]
    assert second.accuracy == 1.0
    assert "done" not in second.transcript

    report = report_text(session)
    assert "Words it gave a hint for on the first read: dog." in report
    assert "it ran to the park" not in report
    assert "not yet accurate on children's voices" in report


def test_buddy_falls_back_when_the_model_fails():
    def broken(messages, max_words=40):
        raise OSError("no model")

    buddy = ReadingBuddy(PASSAGE, 6, chat=broken)
    assert buddy.greet()
    assert buddy.questions() == FALLBACK_QUESTIONS


def test_buddy_lines_pass_the_safety_gate():
    buddy = ReadingBuddy(PASSAGE, 8, chat=FakeChat("What's your home address?"))
    assert "address" not in buddy.greet()


def test_model_text_is_cleaned_for_speaking():
    assert clean_for_speech("**Wow!** 🎉 (smiles) You read it all. Let's go again. One more. And more.") == \
        "Wow! You read it all. Let's go again."


def test_questions_are_read_from_a_numbered_list():
    text = "Sure! Here are some:\n1. Where did the dog run?\n2) Was the dog big or small?\n"
    assert parse_questions(text) == ["Where did the dog run?", "Was the dog big or small?"]


def test_every_hint_line_for_a_passage_is_known_ahead():
    lines = lines_for_passage(PASSAGE, 8)
    assert "Take your time. That word starts with 'do'." in lines
    assert "That word is 'park'. Keep going." in lines
