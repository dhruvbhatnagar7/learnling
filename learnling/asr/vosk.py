"""Passage-constrained ASR with Vosk (optional extra: `pip install learnling[vosk]`).

Whisper answers "what did this person say?" and can pick from any word in
English. For a child reading a known page that is the wrong question, and a
dangerous one: open recognition is pulled toward fluent text and toward the
words it expected to hear.

This adapter asks a narrower one: "which of the words on this page did the
child say, in what order, and how sure are we?" The recogniser is given a
grammar made of the passage's own words plus Vosk's `[unk]` token, which
absorbs anything that is not one of them. So a misreading of "steam" comes
back as `unk` in that position, a skipped word comes back as a gap, and the
reading agent's alignment does the rest.

It runs fully offline. Grammars need one of Vosk's small models (for example
`vosk-model-small-en-us-0.15`), which are also the ones that fit on a
Raspberry Pi. Download one from https://alphacephei.com/vosk/models and pass
its folder as `model_path`.

What this does not do yet: it cannot say *what* a misreading was, only that
it was not the expected word. Real-word neighbours ("stem", "steal") could be
added to the grammar later, and the phoneme track (README M3) is where
sound-level detail is meant to come from.
"""

from __future__ import annotations

import json
import wave

from learnling.agents.reading import normalize_words
from learnling.asr.base import utterance_from_words
from learnling.models import Utterance

#: What an out-of-grammar stretch of speech is reported as. Plain letters, so
#: it survives `normalize_words` and lands in the alignment as one heard word.
UNKNOWN_WORD = "unk"


def passage_grammar(passage_text: str) -> list[str]:
    """The Vosk grammar for a passage: its distinct words, then `[unk]`."""
    words = list(dict.fromkeys(normalize_words(passage_text)))
    return words + ["[unk]"]


class VoskPassageASR:
    """Recognises speech against one passage's vocabulary.

    `model` lets a caller (or a test) pass an already-loaded `vosk.Model`;
    otherwise one is loaded from `model_path`. `recognizer_factory` exists for
    the same reason and defaults to `vosk.KaldiRecognizer`.
    """

    def __init__(
        self,
        passage_text: str,
        model_path: str | None = None,
        model=None,
        recognizer_factory=None,
    ):
        if model is None or recognizer_factory is None:
            try:
                import vosk
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise ImportError(
                    "VoskPassageASR requires the 'vosk' extra. Install with: pip install learnling[vosk]"
                ) from exc
            vosk.SetLogLevel(-1)
            if model is None:
                if model_path is None:
                    raise ValueError("pass model_path, the folder of a Vosk small model")
                model = vosk.Model(model_path)
            recognizer_factory = recognizer_factory or vosk.KaldiRecognizer
        self._model = model
        self._factory = recognizer_factory
        self._grammar = json.dumps(passage_grammar(passage_text))

    def transcribe(self, audio: str | bytes) -> Utterance:
        if isinstance(audio, bytes):
            raise TypeError("VoskPassageASR.transcribe expects a WAV file path")

        with wave.open(audio, "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise ValueError(
                    "expected 16-bit mono WAV; convert with: "
                    "ffmpeg -i in.m4a -ac 1 -ar 16000 -sample_fmt s16 out.wav"
                )
            recognizer = self._factory(self._model, wav.getframerate(), self._grammar)
            recognizer.SetWords(True)
            results = []
            while True:
                chunk = wav.readframes(4000)
                if not chunk:
                    break
                if recognizer.AcceptWaveform(chunk):
                    results.append(json.loads(recognizer.Result()))
            results.append(json.loads(recognizer.FinalResult()))

        return utterance_from_words(
            [
                (
                    UNKNOWN_WORD if word["word"] == "[unk]" else word["word"],
                    word["start"],
                    word["end"],
                    word.get("conf"),
                )
                for result in results
                for word in result.get("result", [])
            ]
        )

