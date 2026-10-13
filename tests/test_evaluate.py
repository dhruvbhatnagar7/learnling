"""The evaluation harness, run with a scripted recogniser instead of audio."""

import json

from learnling.evaluate import evaluate_folder, format_summary
from learnling.models import Utterance

PASSAGE = "the cat sat on the mat"


class ScriptedASR:
    """Returns a fixed transcript per audio file, as if it had heard it."""

    def __init__(self, transcripts, confidence=None):
        self.transcripts = transcripts
        self.confidence = confidence

    def transcribe(self, audio):
        name = audio.rsplit("/", 1)[-1]
        return Utterance(text=self.transcripts[name], confidence=self.confidence)


def _label(folder, name, said):
    (folder / f"{name}.json").write_text(json.dumps({"passage": PASSAGE, "said": said}))


def test_perfect_recogniser_catches_everything_and_accuses_no_one(tmp_path):
    _label(tmp_path, "clean", PASSAGE)
    _label(tmp_path, "one-slip", "the cat sat on the hat")
    asr = ScriptedASR({"clean.wav": PASSAGE, "one-slip.wav": "the cat sat on the hat"})

    summary = evaluate_folder(tmp_path, lambda passage: asr)

    assert summary.false_accusation_rate == 0
    assert summary.catch_rate == 1


def test_a_misheard_correct_word_is_a_false_accusation(tmp_path):
    _label(tmp_path, "clean", PASSAGE)
    asr = ScriptedASR({"clean.wav": "the cat sat on the map"})

    summary = evaluate_folder(tmp_path, lambda passage: asr)

    assert summary.cases[0].false_accusations == 1
    assert summary.false_accusation_rate == 1 / 6
    assert summary.catch_rate is None  # no real errors to catch


def test_self_correction_is_not_an_error(tmp_path):
    _label(tmp_path, "fixed-it", "the cat sat on the hat mat")
    asr = ScriptedASR({"fixed-it.wav": "the cat sat on the hat mat"})

    summary = evaluate_folder(tmp_path, lambda passage: asr)

    assert summary.cases[0].true_errors == set()
    assert summary.cases[0].false_accusations == 0


def test_unsure_recogniser_stays_quiet_and_misses(tmp_path):
    _label(tmp_path, "slip", "the cat sat on the hat")
    asr = ScriptedASR({"slip.wav": "the cat sat on the hat"}, confidence=0.5)

    summary = evaluate_folder(tmp_path, lambda passage: asr)

    assert summary.cases[0].missed == 1
    assert summary.cases[0].suppressed == 1
    assert "False-accusation rate: 0%" in format_summary(summary)


def test_passage_can_come_from_a_file(tmp_path):
    (tmp_path / "story.txt").write_text(PASSAGE)
    (tmp_path / "r1.json").write_text(json.dumps({"passage_file": "story.txt", "said": PASSAGE}))
    asr = ScriptedASR({"r1.wav": PASSAGE})

    summary = evaluate_folder(tmp_path, lambda passage: asr)

    assert summary.cases[0].words == 6
