"""Audio in and out for live reading: microphone, recordings, offline voice, listening light.

Kept apart from `live.py` so the reading logic can be tested without any
audio hardware. Nothing here sends audio anywhere: the microphone feeds the
recogniser in memory, and the voice is synthesised on this machine.
"""

from __future__ import annotations

import queue
import sys
import threading
import wave
from pathlib import Path

SAMPLE_RATE = 16000
CHUNK_SECONDS = 0.1
_CHUNK_BYTES = int(SAMPLE_RATE * CHUNK_SECONDS) * 2


def file_chunks(path: str | Path):
    """A 16 kHz mono 16-bit WAV, a tenth of a second at a time."""
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != SAMPLE_RATE:
            raise ValueError(
                "expected 16 kHz 16-bit mono WAV; convert with: "
                "ffmpeg -i in.m4a -ac 1 -ar 16000 -sample_fmt s16 out.wav"
            )
        while True:
            pcm = wav.readframes(_CHUNK_BYTES // 2)
            if not pcm:
                return
            yield pcm


def silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(SAMPLE_RATE * seconds)


class OfflineVoice:
    """Text to speech on this machine, with a sherpa-onnx VITS (Piper) voice.

    Voices are on https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models,
    for example `vits-piper-en_US-amy-low`.
    """

    def __init__(self, voice_dir: str | Path, speed: float = 0.9):
        import sherpa_onnx

        folder = Path(voice_dir)
        model = next(folder.glob("*.onnx"))
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(model),
                    tokens=str(folder / "tokens.txt"),
                    data_dir=str(folder / "espeak-ng-data"),
                ),
                num_threads=2,
            ),
        )
        self._tts = sherpa_onnx.OfflineTts(config)
        self._speed = speed

    def synthesize(self, text: str) -> tuple[list[float], int]:
        audio = self._tts.generate(text, sid=0, speed=self._speed)
        return list(audio.samples), audio.sample_rate


def to_pcm16(samples, rate: int) -> bytes:
    """Float samples at `rate` to 16 kHz 16-bit PCM (simple resampling, fine for speech)."""
    import numpy as np

    x = np.asarray(samples, dtype=np.float32)
    if rate != SAMPLE_RATE:
        n = int(len(x) * SAMPLE_RATE / rate)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()


class ListeningLight:
    """The light on the stand: on while listening, off while learnling talks.

    On a Raspberry Pi, pass the GPIO pin an LED is wired to. Anywhere else it
    prints the state, which is enough to see it working.
    """

    def __init__(self, gpio_pin: int | None = None):
        self._led = None
        if gpio_pin is not None:
            from gpiozero import LED

            self._led = LED(gpio_pin)

    def on(self) -> None:
        if self._led:
            self._led.on()
        else:
            print("  [light on: listening]")

    def off(self) -> None:
        if self._led:
            self._led.off()
        else:
            print("  [light off]")


class Speaker:
    """Says things out loud (or just prints them), pausing the microphone while it talks."""

    def __init__(
        self,
        voice: OfflineVoice | None = None,
        play: bool = True,
        light: ListeningLight | None = None,
        timeline: list[bytes] | None = None,
    ):
        self.voice = voice
        self.play = play
        self.light = light
        self.muted = threading.Event()
        #: When given, spoken audio is appended here, for writing a demo recording.
        self.timeline = timeline

    def __call__(self, text: str) -> None:
        print(f"learnling: {text}")
        if self.voice is None:
            return
        samples, rate = self.voice.synthesize(text)
        if self.timeline is not None:
            self.timeline += [silence(0.3), to_pcm16(samples, rate), silence(0.3)]
        if not self.play:
            return
        import sounddevice as sd

        self.muted.set()
        if self.light:
            self.light.off()
        try:
            sd.play(samples, rate)
            sd.wait()
        finally:
            if self.light:
                self.light.on()
            self.muted.clear()


def mic_chunks(speaker: Speaker, max_seconds: float):
    """The microphone, a tenth of a second at a time, until Enter or `max_seconds`.

    Audio that arrives while learnling is speaking is dropped, so it never hears
    (or waits on) itself.
    """
    try:
        import sounddevice as sd
    except (ImportError, OSError) as exc:  # pragma: no cover - needs real hardware
        raise ImportError("Live listening needs the 'mic' extra: pip install learnling[mic]") from exc

    chunks: queue.Queue[bytes] = queue.Queue()
    stop = threading.Event()

    def callback(indata, frames, time, status):  # pragma: no cover - needs real hardware
        if not speaker.muted.is_set():
            chunks.put(bytes(indata))

    def wait_for_enter():  # pragma: no cover - needs a terminal
        sys.stdin.readline()
        stop.set()

    threading.Thread(target=wait_for_enter, daemon=True).start()
    heard = 0.0
    with sd.RawInputStream(  # pragma: no cover - needs real hardware
        samplerate=SAMPLE_RATE, channels=1, dtype="int16",
        blocksize=int(SAMPLE_RATE * CHUNK_SECONDS), callback=callback,
    ):
        while not stop.is_set() and heard < max_seconds:
            try:
                pcm = chunks.get(timeout=0.5)
            except queue.Empty:
                continue
            heard += len(pcm) / 2 / SAMPLE_RATE
            yield pcm


def recorded(chunks, timeline: list[bytes]):
    """Pass chunks through, keeping a copy on `timeline` for a demo recording."""
    for pcm in chunks:
        timeline.append(pcm)
        yield pcm


def write_demo(path: str | Path, pieces: list[bytes]) -> None:
    """Write reading audio and learnling's voice, in order, as one WAV."""
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for pcm in pieces:
            wav.writeframes(pcm)
