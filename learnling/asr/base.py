"""The ASR adapter contract.

Every speech-recognition backend — simulated, generic Whisper, or a future
open child-speech model — implements this single method and returns an
`Utterance`. Nothing downstream (orchestrator, agents) needs to know which
backend produced the transcript.
"""

from __future__ import annotations

from typing import Protocol

from learnling.models import Utterance


class ASRAdapter(Protocol):
    def transcribe(self, audio: str | bytes) -> Utterance:
        """Transcribe an audio file path or raw bytes into an Utterance."""
        ...
