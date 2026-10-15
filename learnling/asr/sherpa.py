"""Streaming speech recognition with sherpa-onnx (optional extra: `pip install learnling[live]`).

This is the recogniser for live reading. It hears audio a tenth of a second at
a time and keeps an up-to-date guess of the words so far, which is what lets
learnling notice a reader stalling on a word while they are still reading.
It runs fully offline and is small enough for a Raspberry Pi.

It works with sherpa-onnx's streaming Zipformer transducer models, for example
`sherpa-onnx-streaming-zipformer-en-2023-06-26` (more accurate) or
`sherpa-onnx-streaming-zipformer-en-20M-2023-02-17` (smaller, for a Pi). They
are on the sherpa-onnx releases page:
https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models

Like the Whisper adapter, it is open vocabulary and never told the passage, so
it reports what it heard rather than what it expected.

Per-word confidence comes from the model's own token probabilities: the
average log probability of a word's pieces, turned back into a probability.
It is a rough score and has not been calibrated against the miscue threshold.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

from learnling.agents.reading import normalize_words
from learnling.asr.base import utterance_from_words
from learnling.models import Utterance

SAMPLE_RATE = 16000

#: Silence fed before the first audio and after the last. Without the lead-in
#: the model tends to drop the first word or two; the tail lets it finish the
#: last word.
_LEAD_IN_SECONDS = 0.5
_TAIL_SECONDS = 1.0


def _pick(folder: Path, part: str) -> str:
    """The model file for `part`, preferring the int8 version where present."""
    candidates = sorted(folder.glob(f"{part}*.onnx"))
    if not candidates:
        raise FileNotFoundError(f"no {part}*.onnx in {folder}")
    int8 = [c for c in candidates if ".int8." in c.name]
    # The int8 decoder is known to cost accuracy on some models; keep it full size.
    if part != "decoder" and int8:
        return str(int8[0])
    full = [c for c in candidates if ".int8." not in c.name]
    return str((full or candidates)[0])


def load_recognizer(model_dir: str | Path, num_threads: int = 2):
    """Load a sherpa-onnx streaming transducer from a model folder."""
    try:
        import sherpa_onnx
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "Live listening needs the 'live' extra: pip install learnling[live]"
        ) from exc
    folder = Path(model_dir)
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(folder / "tokens.txt"),
        encoder=_pick(folder, "encoder"),
        decoder=_pick(folder, "decoder"),
        joiner=_pick(folder, "joiner"),
        num_threads=num_threads,
        sample_rate=SAMPLE_RATE,
        feature_dim=80,
        decoding_method="greedy_search",
        enable_endpoint_detection=False,
    )


def words_from_tokens(
    tokens: list[str], timestamps: list[float], log_probs: list[float] | None
) -> list[tuple[str, float, float, float | None]]:
    """Join BPE pieces into (word, start, end, probability) tuples.

    A piece starting with a space (or the sentencepiece marker) begins a new
    word. A word ends where the next one starts, or a quarter second after its
    last piece.
    """
    words: list[list] = []
    for i, token in enumerate(tokens):
        starts_word = token.startswith((" ", "▁")) or not words
        piece = token.lstrip(" ▁")
        if starts_word:
            words.append([piece, timestamps[i], [] if log_probs is not None else None])
        else:
            words[-1][0] += piece
        if log_probs is not None:
            words[-1][2].append(log_probs[i])

    out = []
    for i, (text, start, logs) in enumerate(words):
        end = words[i + 1][1] if i + 1 < len(words) else start + 0.25
        prob = math.exp(sum(logs) / len(logs)) if logs else None
        out.append((text, start, end, prob))
    return out


class SherpaStreamingASR:
    """One reading at a time: feed audio as it arrives, read the words so far.

    Also satisfies the batch `ASRAdapter` contract through `transcribe`, so the
    same model can be scored with `learnling eval`.
    """

    def __init__(self, model_dir: str | Path | None = None, recognizer=None):
        self._recognizer = recognizer if recognizer is not None else load_recognizer(model_dir)
        self._stream = None
        self.reset()

    def reset(self) -> None:
        """Start listening to a new reading."""
        self._stream = self._recognizer.create_stream()
        self._feed_silence(_LEAD_IN_SECONDS)

    def _feed_silence(self, seconds: float) -> None:
        import numpy as np

        self._stream.accept_waveform(SAMPLE_RATE, np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32))

    def accept(self, pcm: bytes) -> None:
        """Feed 16 kHz mono 16-bit audio."""
        import numpy as np

        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        self._stream.accept_waveform(SAMPLE_RATE, samples)
        while self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)

    def partial_words(self) -> list[str]:
        """The recogniser's current best guess at the words read so far."""
        return normalize_words(self._recognizer.get_result(self._stream))

    def finish(self) -> Utterance:
        """Close the reading and return it with word timings and confidences."""
        self._feed_silence(_TAIL_SECONDS)
        self._stream.input_finished()
        while self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)
        result = self._recognizer.get_result_all(self._stream)
        log_probs = list(result.ys_probs) if len(result.ys_probs) == len(result.tokens) else None
        words = words_from_tokens(list(result.tokens), list(result.timestamps), log_probs)
        # Timestamps include the lead-in silence; take it back out.
        return utterance_from_words(
            [(w, s - _LEAD_IN_SECONDS, e - _LEAD_IN_SECONDS, p) for w, s, e, p in words]
        )

    def transcribe(self, audio: str | bytes) -> Utterance:
        if isinstance(audio, bytes):
            raise TypeError("SherpaStreamingASR.transcribe expects a WAV file path")
        with wave.open(audio, "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != SAMPLE_RATE:
                raise ValueError(
                    "expected 16 kHz 16-bit mono WAV; convert with: "
                    "ffmpeg -i in.m4a -ac 1 -ar 16000 -sample_fmt s16 out.wav"
                )
            pcm = wav.readframes(wav.getnframes())
        self.reset()
        self.accept(pcm)
        return self.finish()
