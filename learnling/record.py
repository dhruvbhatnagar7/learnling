"""Record a reading from the microphone, score it, and optionally keep it for evaluation.

    python -m learnling record --passage passages/sample_level1.txt --asr vosk --vosk-model PATH

The adult presses Enter to start and Enter again to stop. The recording is
scored on this computer and the result is shown to the adult.

By default the audio is held in a temporary file only for as long as scoring
takes, then deleted. Passing `--save-to FOLDER` keeps the WAV and writes a
label file next to it with an empty `said` field, ready for an adult to type
what was actually read, so `learnling eval FOLDER` can score it later. That
is the one place this package writes audio to disk, and only when asked.
See SAFETY.md.

Needs the `mic` extra: `pip install learnling[mic]`.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import wave
from datetime import datetime
from pathlib import Path

SAMPLE_RATE = 16000


def record_until_enter(prompt=input) -> bytes:
    """Record 16 kHz mono 16-bit audio from the default microphone until Enter."""
    try:
        import sounddevice as sd
    except (ImportError, OSError) as exc:  # pragma: no cover - needs real hardware
        raise ImportError(
            "Recording needs the 'mic' extra: pip install learnling[mic]"
        ) from exc

    chunks: list[bytes] = []

    def callback(indata, frames, time, status):  # pragma: no cover - needs real hardware
        chunks.append(bytes(indata))

    stream = sd.RawInputStream(  # pragma: no cover - needs real hardware
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback
    )
    stream.start()  # pragma: no cover - needs real hardware
    try:  # pragma: no cover - needs real hardware
        prompt("Listening. Press Enter when the reading is finished. ")
    finally:
        _close_quietly(stream)
    return b"".join(chunks)


def _close_quietly(stream, timeout: float = 2.0) -> None:
    """Stop the microphone without letting a stuck audio driver hang the program.

    Stopping a stream waits for the driver, and on some Macs that wait never
    ends. Abort instead of stop, do it on a background thread, and move on
    after `timeout` seconds either way; the audio is already captured.
    """

    def close():
        stream.abort(ignore_errors=True)
        stream.close(ignore_errors=True)

    worker = threading.Thread(target=close, daemon=True)
    worker.start()
    worker.join(timeout)


def write_wav(path: str | Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)


def save_for_evaluation(folder: str | Path, passage_text: str, pcm: bytes) -> Path:
    """Keep a recording and a label stub in `folder`; return the label path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("reading-%Y%m%d-%H%M%S")
    write_wav(folder / f"{stem}.wav", pcm)
    label = folder / f"{stem}.json"
    label.write_text(json.dumps({"passage": passage_text, "said": ""}, indent=1) + "\n")
    return label


def transcribe_pcm(asr, pcm: bytes):
    """Score raw audio through an adapter that expects a file path.

    The temporary file is removed as soon as the adapter has read it.
    """
    handle, path = tempfile.mkstemp(suffix=".wav")
    os.close(handle)
    try:
        write_wav(path, pcm)
        return asr.transcribe(path)
    finally:
        os.remove(path)
