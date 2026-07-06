"""Generic Whisper ASR adapter (optional extra: `pip install learnling[asr]`).

This adapter is a stopgap, not the destination. Generic Whisper models are
trained overwhelmingly on adult speech, and child ASR error rates on them
run several times higher than on adults — the exact gap learnling exists to
route around at the agent layer. The roadmap (see README, M2/M3) is to
replace or complement this with adapters for open child-speech models,
including word- and phoneme-level output, as they publish open weights.
`ASRAdapter` is the seam where those adapters plug in without touching
anything above the ASR layer.
"""

from __future__ import annotations

from learnling.models import Utterance

try:
    from faster_whisper import WhisperModel
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "WhisperASR requires the 'asr' extra. Install with: pip install learnling[asr]"
    ) from exc


class WhisperASR:
    """Adapts faster-whisper to the learnling ASRAdapter protocol."""

    def __init__(self, model_size: str = "base", **model_kwargs):
        self._model = WhisperModel(model_size, **model_kwargs)

    def transcribe(self, audio: str | bytes) -> Utterance:
        if isinstance(audio, bytes):
            raise TypeError("WhisperASR.transcribe expects an audio file path")

        segments, info = self._model.transcribe(audio, word_timestamps=True)
        segments = list(segments)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        word_timestamps = [
            {"word": word.word, "start": word.start, "end": word.end}
            for segment in segments
            for word in (segment.words or [])
        ]
        duration = segments[-1].end if segments else None
        return Utterance(
            text=text,
            confidence=getattr(info, "language_probability", None),
            duration_seconds=duration,
            word_timestamps=word_timestamps or None,
        )
