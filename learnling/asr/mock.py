"""A zero-dependency ASR stand-in: text in, transcript out.

This is what powers `--simulate` on the CLI, the `demo` command, and the
test suite. It lets every layer above ASR (orchestrator, agents, adaptation,
safety) be built and exercised before any real audio pipeline exists.
"""

from __future__ import annotations

from learnling.models import Utterance


class SimulatedASR:
    """Treats an already-typed string as if it were the ASR transcript."""

    def transcribe(self, audio: str | bytes) -> Utterance:
        text = audio.decode("utf-8") if isinstance(audio, bytes) else audio
        return Utterance(text=text, confidence=1.0, duration_seconds=None, word_timestamps=None)
