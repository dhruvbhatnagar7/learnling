"""Generic Whisper ASR adapter (optional extra: `pip install learnling[asr]`).

This adapter is a stopgap, not the destination. Generic Whisper models are
trained overwhelmingly on adult speech, and child ASR error rates on them
run several times higher than on adults — the exact gap learnling exists to
route around at the agent layer. The roadmap (see README, M2/M3) is to
replace or complement this with adapters for open child-speech models,
including word- and phoneme-level output, as they publish open weights.
`ASRAdapter` is the seam where those adapters plug in without touching
anything above the ASR layer.

Two settings here matter more than they look:

- The passage is never given to Whisper as a prompt. Whisper is built to
  produce fluent, plausible text, and with the expected words in its prompt
  it will quietly turn "stem" back into "steam". That hides exactly the
  mistakes a reading tutor exists to catch.
- Voice activity filtering is on, because Whisper tends to invent words
  over silence, and a child pausing on a hard word is silence.
"""

from __future__ import annotations

from learnling.asr.base import utterance_from_words
from learnling.models import Utterance


class WhisperASR:
    """Adapts faster-whisper to the learnling ASRAdapter protocol.

    `model` lets a caller (or a test) pass an already-loaded model; otherwise
    one is loaded by size.
    """

    def __init__(self, model_size: str = "base.en", model=None, **model_kwargs):
        if model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise ImportError(
                    "WhisperASR requires the 'asr' extra. Install with: pip install learnling[asr]"
                ) from exc
            model = WhisperModel(model_size, **model_kwargs)
        self._model = model

    def transcribe(self, audio: str | bytes) -> Utterance:
        if isinstance(audio, bytes):
            raise TypeError("WhisperASR.transcribe expects an audio file path")

        segments, _info = self._model.transcribe(
            audio,
            # Multilingual models (such as children's fine-tunes of whisper-small)
            # otherwise guess the language, and an accent can tip the guess.
            language="en",
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        words = [word for segment in segments for word in (segment.words or [])]
        return utterance_from_words(
            [(w.word, w.start, w.end, w.probability) for w in words]
        )

