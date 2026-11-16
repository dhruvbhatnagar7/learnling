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

- The passage can be given to Whisper as a prompt (`prompt=`, or
  `with_prompt(passage)`), and learnling does so by default. It is a trade-off:
  with the expected words in front of it, Whisper hears unclear children's
  words better, but it will sometimes write the page word ("steam") when the
  reader said something else ("stem"). On the 600 children's test cases it
  halved correct words called wrong for Kid-Whisper (11.8% to 5.6%) and
  caught fewer real errors (61% to 52%). `--no-story-prompt` turns it off.
- Voice activity filtering is on, because Whisper tends to invent words
  over silence, and a child pausing on a hard word is silence.
- Each stretch of speech the voice detector finds is decoded on its own.
  faster-whisper's own `vad_filter` glues the stretches back together into
  one window, and after a long pause (a reader stuck on a word) Whisper
  can stop writing partway through that window, so the rest of the read
  looks skipped.
"""

from __future__ import annotations

from learnling.asr.base import utterance_from_words
from learnling.models import Utterance


def _speech_clips(path: str) -> list[float]:
    """Start and end, in seconds, of each stretch of speech in the file."""
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    rate = 16000
    stamps = get_speech_timestamps(decode_audio(path, sampling_rate=rate), VadOptions())
    return [t for s in stamps for t in (s["start"] / rate, s["end"] / rate)]


class WhisperASR:
    """Adapts faster-whisper to the learnling ASRAdapter protocol.

    `model` lets a caller (or a test) pass an already-loaded model; otherwise
    one is loaded by size. `find_speech` returns the speech stretches to
    decode, as flat [start, end, start, end, ...] seconds.
    """

    def __init__(
        self, model_size: str = "base.en", model=None, find_speech=None, prompt: str | None = None, **model_kwargs
    ):
        self._find_speech = find_speech or _speech_clips
        self.prompt = prompt.strip() if prompt and prompt.strip() else None
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

        clips = self._find_speech(audio)
        if not clips:
            return utterance_from_words([])
        options = dict(
            # Multilingual models (such as children's fine-tunes of whisper-small)
            # otherwise guess the language, and an accent can tip the guess.
            language="en",
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        if self.prompt is None:
            runs = [{"clip_timestamps": clips}]
        else:
            # faster-whisper only uses the prompt for the first window when
            # condition_on_previous_text is off, so each stretch gets its own call.
            runs = [
                {"clip_timestamps": clips[i:i + 2], "initial_prompt": self.prompt}
                for i in range(0, len(clips), 2)
            ]
        words = []
        for run in runs:
            segments, _info = self._model.transcribe(audio, **options, **run)
            words += [word for segment in segments for word in (segment.words or [])]
        return utterance_from_words(
            [(w.word, w.start, w.end, w.probability) for w in words]
        )

    def with_prompt(self, passage: str | None) -> "WhisperASR":
        """The same loaded model, prompted with `passage` (None for no prompt)."""
        copy = WhisperASR(model=self._model, find_speech=self._find_speech, prompt=passage)
        return copy
