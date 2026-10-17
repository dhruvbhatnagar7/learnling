"""Real-audio adapters, exercised with stand-in models so no download is needed."""

import json
import wave
from types import SimpleNamespace

import pytest

from learnling.agents.reading import ReadingAgent, normalize_words
from learnling.asr.base import utterance_from_words
from learnling.asr.vosk import UNKNOWN_WORD, VoskPassageASR, passage_grammar
from learnling.asr.whisper import WhisperASR
from learnling.models import Utterance

PASSAGE = "The cat sat on the mat."


def test_word_confidences_line_up_with_normalized_words():
    utterance = utterance_from_words(
        [(" The", 0.5, 0.7, 0.9), (" cat,", 0.7, 1.0, 0.4), (" -", 1.0, 1.1, 0.2), (" sat.", 1.1, 1.5, 0.8)]
    )
    assert normalize_words(utterance.text) == ["the", "cat", "sat"]
    assert utterance.word_confidences == [0.9, 0.4, 0.8]


def test_duration_is_reading_time_not_file_length():
    utterance = utterance_from_words([("the", 3.0, 3.2, 0.9), ("cat", 3.4, 4.0, 0.9)])
    assert utterance.duration_seconds == pytest.approx(1.0)


def test_no_words_gives_an_empty_utterance():
    assert utterance_from_words([]).text == ""


def _fake_whisper(words):
    segment = SimpleNamespace(
        words=[SimpleNamespace(word=w, start=s, end=e, probability=p) for w, s, e, p in words]
    )

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            self.kwargs = kwargs
            return iter([segment]), SimpleNamespace(language_probability=0.99)

    return FakeModel()


def test_whisper_is_never_prompted_with_the_passage():
    model = _fake_whisper([(" The", 0.0, 0.2, 0.9)])
    WhisperASR(model=model, find_speech=lambda path: [0.5, 3.0, 6.0, 9.0]).transcribe("reading.wav")
    assert "initial_prompt" not in model.kwargs
    # Speech stretches are decoded one by one, never glued into one window.
    assert model.kwargs["vad_filter"] is False
    assert model.kwargs["clip_timestamps"] == [0.5, 3.0, 6.0, 9.0]
    assert model.kwargs["condition_on_previous_text"] is False


def test_a_shaky_whisper_word_is_held_back_from_the_child():
    model = _fake_whisper(
        [(" the", 0.0, 0.2, 0.95), (" cat", 0.2, 0.5, 0.95), (" sat", 0.5, 0.8, 0.95),
         (" on", 0.8, 0.9, 0.95), (" the", 0.9, 1.0, 0.95), (" hat", 1.0, 1.3, 0.30)]
    )
    utterance = WhisperASR(model=model, find_speech=lambda path: [0.0, 2.0]).transcribe("reading.wav")
    result = ReadingAgent().assess(PASSAGE, utterance)
    assert result.miscues == []
    assert result.suppressed_miscues == 1


def test_wcpm_counts_only_raised_errors():
    utterance = Utterance(
        text="the cat sat on the hat", duration_seconds=6.0, word_confidences=[0.9] * 6
    )
    result = ReadingAgent().assess(PASSAGE, utterance)
    # 6 words, 1 error, 6 seconds -> 5 correct words in a tenth of a minute
    assert result.wcpm == 50


def test_grammar_is_the_passage_words_plus_unknown():
    assert passage_grammar(PASSAGE) == ["the", "cat", "sat", "on", "mat", "[unk]"]


def _write_silence(path, rate=16000):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * rate)


class FakeRecognizer:
    """Stands in for vosk.KaldiRecognizer, returning a fixed final result."""

    words = []

    def __init__(self, model, rate, grammar):
        FakeRecognizer.seen_grammar = json.loads(grammar)

    def SetWords(self, on):
        pass

    def AcceptWaveform(self, chunk):
        return False

    def Result(self):
        return "{}"

    def FinalResult(self):
        return json.dumps({"result": FakeRecognizer.words})


def test_vosk_reports_an_out_of_passage_word_as_unknown(tmp_path):
    audio = tmp_path / "reading.wav"
    _write_silence(audio)
    FakeRecognizer.words = [
        {"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25, "conf": 1.0}
        for i, w in enumerate(["the", "cat", "sat", "on", "the", "[unk]"])
    ]
    asr = VoskPassageASR(PASSAGE, model=object(), recognizer_factory=FakeRecognizer)
    utterance = asr.transcribe(str(audio))

    assert FakeRecognizer.seen_grammar[-1] == "[unk]"
    assert utterance.text.split()[-1] == UNKNOWN_WORD
    result = ReadingAgent().assess(PASSAGE, utterance)
    assert [(m.kind, m.expected) for m in result.miscues] == [("substitution", "mat")]


def test_vosk_rejects_stereo_audio(tmp_path):
    audio = tmp_path / "stereo.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00\x00\x00" * 100)
    asr = VoskPassageASR(PASSAGE, model=object(), recognizer_factory=FakeRecognizer)
    with pytest.raises(ValueError, match="mono"):
        asr.transcribe(str(audio))
