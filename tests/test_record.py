"""`learnling record`, with the microphone and recogniser replaced by stand-ins."""

import json
import os
import wave

from learnling import cli, record
from learnling.evaluate import evaluate_folder
from learnling.models import Utterance

PASSAGE = "the cat sat on the mat"
ONE_SECOND = b"\x00\x00" * record.SAMPLE_RATE


class FileCheckingASR:
    """Checks it was handed a real WAV, and remembers the path."""

    def __init__(self, text):
        self.text = text
        self.paths = []

    def transcribe(self, audio):
        with wave.open(audio) as wav:
            assert wav.getframerate() == record.SAMPLE_RATE
        self.paths.append(audio)
        return Utterance(text=self.text, duration_seconds=3.0)


def test_scoring_leaves_no_audio_behind():
    asr = FileCheckingASR(PASSAGE)
    record.transcribe_pcm(asr, ONE_SECOND)
    assert not os.path.exists(asr.paths[0])


def test_saved_recording_waits_for_a_label(tmp_path):
    label = record.save_for_evaluation(tmp_path, PASSAGE, ONE_SECOND)
    assert label.with_suffix(".wav").exists()
    assert json.loads(label.read_text()) == {"passage": PASSAGE, "said": ""}

    summary = evaluate_folder(tmp_path, lambda passage: FileCheckingASR(PASSAGE))
    assert summary.cases == []
    assert summary.unlabelled == [label.name]


def _run_record(tmp_path, monkeypatch, *extra):
    passage = tmp_path / "story.txt"
    passage.write_text(PASSAGE)
    asr = FileCheckingASR("the cat sat on the hat")
    monkeypatch.setattr(record, "record_until_enter", lambda: ONE_SECOND)
    monkeypatch.setattr(cli, "_build_asr", lambda args, text: asr)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    cli.main(["record", "--passage", str(passage), *extra])
    return asr


def test_record_scores_the_reading(tmp_path, monkeypatch, capsys):
    _run_record(tmp_path, monkeypatch)
    out = capsys.readouterr().out
    assert "substitution" in out and "mat" in out
    assert "WCPM" in out


def test_record_keeps_audio_only_when_asked(tmp_path, monkeypatch):
    _run_record(tmp_path, monkeypatch)
    assert list(tmp_path.glob("*.wav")) == []

    saved = tmp_path / "readings"
    _run_record(tmp_path, monkeypatch, "--save-to", str(saved))
    assert len(list(saved.glob("*.wav"))) == 1
    assert len(list(saved.glob("*.json"))) == 1


def test_close_quietly_does_not_wait_for_a_stuck_driver():
    import threading
    import time

    release = threading.Event()

    class StuckStream:
        def abort(self, ignore_errors=True):
            release.wait()

        def close(self, ignore_errors=True):
            pass

    start = time.monotonic()
    record._close_quietly(StuckStream(), timeout=0.2)
    assert time.monotonic() - start < 1.0
    release.set()
