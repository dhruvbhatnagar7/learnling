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
        [(0.5, "the big"), (6.0, "the big dog ran to the park")],  # stuck on "dog"
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
    assert "Hints given for: dog." in report
    assert "it ran to the park" not in report
    assert "Talked about 1 story question(s)." in report
    # The live recogniser only times hints, so the quick report judges no words.
    assert "didn't match" not in report and "%" not in report
    assert "by email" not in report
    assert "by email" in report_text(session, full_report_coming=True)


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


def test_cloud_voice_sends_only_the_line_to_say():
    from learnling.live_io import CloudVoice

    voice = CloudVoice("coral", api_key="test")
    body = voice.request_body("Take your time.")
    assert body["input"] == "Take your time."
    assert body["voice"] == "coral" and body["response_format"] == "pcm"


def test_cloud_model_is_chosen_by_name():
    from learnling.buddy import OllamaChat, OpenAIChat, make_chat

    assert isinstance(make_chat("gemma3:1b"), OllamaChat)
    assert isinstance(OpenAIChat(api_key="test"), OpenAIChat)


def test_stopping_partway_is_scored_on_the_part_read():
    long_passage = PASSAGE + " and then the dog sat down under a big green tree by the gate"
    rec = PhaseRecognizer([
        [(1.0, "im ready to read")],
        [(0.5, "the big dog ran"), (1.0, "the big dog ran done")],
        [(0.5, "the big dog ran to"), (1.0, "the big dog ran to stop")],
    ])
    buddy = ReadingBuddy(long_passage, 8, chat=FakeChat("Nice!"))
    session = run_stand(long_passage, rec, open_mic, lambda text: None, buddy, [], on_status=lambda text: None)
    first, second = [e["report_notes"]["reading_result"] for e in session.orchestrator.session.events]
    assert first.accuracy == 1.0 and second.accuracy == 1.0
    assert "skipped" not in report_text(session)


def test_the_pilot_keeps_both_reads_and_nothing_else(tmp_path):
    import json

    from learnling.pilot import stand_recorder

    rec = PhaseRecognizer([
        [(1.0, "im ready to read")],
        [(0.5, PASSAGE)],
        [(0.5, PASSAGE)],
        [(1.0, "it ran to the park")],
    ])
    buddy = ReadingBuddy(PASSAGE, 7, chat=FakeChat())
    saved = []
    on_read = stand_recorder("child99", 7, PASSAGE, root=tmp_path, on_status=saved.append)
    run_stand(PASSAGE, rec, open_mic, lambda text: None, buddy, ["Where did the dog go?"],
              on_status=lambda text: None, on_read=on_read)

    labels = sorted((tmp_path / "child99").glob("*.json"))
    notes = sorted(json.loads(p.read_text())["read"] for p in labels)
    assert notes == ["read 1, with hints", "read 2, no hints"]
    assert len(list((tmp_path / "child99").glob("*.wav"))) == 2  # the answer is not one of them
    assert all(json.loads(p.read_text())["said"] == "" for p in labels)
    assert len(saved) == 2


def test_the_pilot_needs_a_child_code(capsys):
    import pytest

    from learnling.cli import main

    with pytest.raises(SystemExit):
        main(["stand", "--passage", "passages/sample_level1.txt", "--model", "x", "--pilot", "Sam"])
    assert "never a name" in capsys.readouterr().err


def test_the_full_report_rescores_both_reads_and_keeps_no_audio(tmp_path):
    from learnling.asr.base import utterance_from_words
    from learnling.fullreport import ReadKeeper, full_report_text, score_reads

    rec = PhaseRecognizer([
        [(1.0, "im ready to read")],
        [(0.5, PASSAGE)],
        [(0.5, PASSAGE)],
    ])
    buddy = ReadingBuddy(PASSAGE, 7, chat=FakeChat())
    keeper = ReadKeeper()
    session = run_stand(PASSAGE, rec, open_mic, lambda text: None, buddy, [],
                        on_status=lambda text: None, on_read=keeper)
    assert [(n, h) for n, h, _, _ in keeper.reads] == [(1, True), (2, False)]

    class CarefulASR:
        """The slower model hears the dropped ending the live one missed."""
        def __init__(self):
            self.paths = []

        def transcribe(self, path):
            self.paths.append(path)
            said = "the big dog run to the park" if len(self.paths) == 1 else PASSAGE
            return utterance_from_words([(w, i * 0.5, i * 0.5 + 0.4, 0.95) for i, w in enumerate(said.split())])

    import os

    asr = CarefulASR()
    scored = score_reads(keeper.reads, asr)
    assert not any(os.path.exists(p) for p in asr.paths)  # temporary audio is deleted
    text = full_report_text(scored, session.words_helped)
    assert '"ran", read as "run"' in text
    assert "No words stood out." in text  # the clean second read
    assert "can get words wrong" in text


def test_the_full_report_leaves_out_added_words_and_abbreviations():
    from learnling.asr.base import utterance_from_words
    from learnling.fullreport import full_report_text, hard_page_words, score_reads

    page = "Teachers use DIBELS and IEPs with 11 children who jumped"
    said = "a teachers use debels and i with one children uh who jump"

    class FakeASR:
        def transcribe(self, path):
            return utterance_from_words([(w, i * 0.5, i * 0.5 + 0.4, 0.95) for i, w in enumerate(said.split())])

    assert hard_page_words(page) == {"dibels", "ieps", "eleven"}
    text = full_report_text(score_reads([(1, True, b"\1\0" * 1600, page)], FakeASR()), [])
    assert '"jumped", read as "jump" (dropped the -ed ending)' in text
    assert "added" not in text
    assert "dibels" not in text and "ieps" not in text and "eleven" not in text


def test_the_full_report_tells_the_scorer_each_page():
    from learnling.asr.base import utterance_from_words
    from learnling.fullreport import score_reads

    class PromptableASR:
        def __init__(self, prompt=None, seen=None):
            self.prompt, self.seen = prompt, seen if seen is not None else []

        def with_prompt(self, passage):
            return PromptableASR(passage, self.seen)

        def transcribe(self, path):
            self.seen.append(self.prompt)
            return utterance_from_words([("the", 0.0, 0.4, 0.95)])

    asr = PromptableASR()
    reads = [(1, True, b"\1\0" * 1600, "page one"), (2, False, b"\1\0" * 1600, "page two")]
    score_reads(reads, asr, story_prompt=True)
    score_reads(reads, asr)
    assert asr.seen == ["page one", "page two", None, None]
