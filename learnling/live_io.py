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
    """Text to speech on this machine, with a sherpa-onnx voice.

    Voices are on https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models.
    Three kinds work, told apart by the folder: a VITS (Piper) voice such as
    `vits-piper-en_US-amy-low`, a Kokoro voice such as `kokoro-int8-en-v0_19`,
    or a Kitten voice such as `kitten-nano-en-v0_2-fp16`. Kokoro and Kitten
    folders hold several speakers; `speaker` picks one (4 is Sky in Kokoro v0.19).
    """

    def __init__(self, voice_dir: str | Path, speed: float = 0.9, speaker: int = 0, num_threads: int = 2):
        import sherpa_onnx

        folder = Path(voice_dir)
        model = str(next(folder.glob("*.onnx")))
        files = dict(tokens=str(folder / "tokens.txt"), data_dir=str(folder / "espeak-ng-data"))
        if (folder / "voices.bin").exists():
            files["voices"] = str(folder / "voices.bin")
            if "kitten" in folder.name.lower():
                kind = dict(kitten=sherpa_onnx.OfflineTtsKittenModelConfig(model=model, **files))
            else:
                kind = dict(kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(model=model, **files))
        else:
            kind = dict(vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=model, **files))
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(**kind, num_threads=num_threads),
        )
        self._tts = sherpa_onnx.OfflineTts(config)
        self._speed = speed
        self._speaker = speaker

    def synthesize(self, text: str) -> tuple[list[float], int]:
        audio = self._tts.generate(text, sid=self._speaker, speed=self._speed)
        if not audio.sample_rate:
            raise RuntimeError(
                "the voice made no sound; sherpa-onnx 2.0 breaks these voices, "
                'install 1.13.8 with: pip install "sherpa-onnx==1.13.8"'
            )
        return list(audio.samples), audio.sample_rate


class PreparedVoice:
    """A voice that makes known lines ahead of time, in the background.

    `prepare(lines)` starts making them while the session does other things
    (waiting for the reader, greeting them). A line that is ready plays at
    once; one that isn't is made on the spot, as before. Nothing is written
    to disk.
    """

    def __init__(self, voice):
        self.voice = voice
        self._ready: dict[str, tuple[list[float], int]] = {}
        self._lock = threading.Lock()

    def prepare(self, lines) -> threading.Thread:
        def work():
            for line in lines:
                if line not in self._ready:
                    made = self._synthesize_locked(line)
                    self._ready[line] = made

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        return worker

    def _synthesize_locked(self, text: str):
        # The voice model is not safe to run from two threads at once.
        with self._lock:
            return self.voice.synthesize(text)

    def synthesize(self, text: str) -> tuple[list[float], int]:
        ready = self._ready.get(text)
        return ready if ready is not None else self._synthesize_locked(text)


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
        self._lit = False
        if gpio_pin is not None:
            from gpiozero import LED

            self._led = LED(gpio_pin)

    def on(self) -> None:
        if self._led:
            self._led.on()
        elif not self._lit:
            print("  [light on: listening]")
        self._lit = True

    def off(self) -> None:
        if self._led:
            self._led.off()
        elif self._lit:
            print("  [light off]")
        self._lit = False


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


def mic_chunks(speaker: Speaker, max_seconds: float, enter_stops: bool = True):
    """The microphone, a tenth of a second at a time, until Enter or `max_seconds`.

    Audio that arrives while learnling is speaking is dropped, so it never hears
    (or waits on) itself. With `enter_stops=False` only `max_seconds` (or the
    caller letting go) ends it, for hands-free sessions.
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

    if enter_stops:
        threading.Thread(target=wait_for_enter, daemon=True).start()
    heard = 0.0
    stream, rate = _open_input(sd, callback)  # pragma: no cover - needs real hardware
    with stream:  # pragma: no cover - needs real hardware
        while not stop.is_set() and heard < max_seconds:
            try:
                pcm = chunks.get(timeout=0.5)
            except queue.Empty:
                continue
            if rate != SAMPLE_RATE:
                pcm = resample_pcm16(pcm, rate)
            heard += len(pcm) / 2 / SAMPLE_RATE
            yield pcm


def _open_input(sd, callback):  # pragma: no cover - needs real hardware
    """A 16 kHz input stream, or the device's own rate if it refuses 16 kHz.

    Some USB speakerphones only record at 44.1 or 48 kHz; the audio is then
    converted to 16 kHz as it arrives.
    """
    try:
        rate = SAMPLE_RATE
        stream = sd.RawInputStream(samplerate=rate, channels=1, dtype="int16",
                                   blocksize=int(rate * CHUNK_SECONDS), callback=callback)
    except sd.PortAudioError:
        rate = int(sd.query_devices(kind="input")["default_samplerate"])
        stream = sd.RawInputStream(samplerate=rate, channels=1, dtype="int16",
                                   blocksize=int(rate * CHUNK_SECONDS), callback=callback)
    return stream, rate


def resample_pcm16(pcm: bytes, rate: int) -> bytes:
    """16-bit mono audio at `rate` to 16 kHz."""
    import numpy as np

    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    return to_pcm16(x, rate)


def recorded(chunks, timeline: list[bytes]):
    """Pass chunks through, keeping a copy on `timeline` for a demo recording."""
    chunks = iter(chunks)
    try:
        for pcm in chunks:
            timeline.append(pcm)
            yield pcm
    finally:
        close = getattr(chunks, "close", None)
        if close is not None:
            close()


def write_demo(path: str | Path, pieces: list[bytes]) -> None:
    """Write reading audio and learnling's voice, in order, as one WAV."""
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        for pcm in pieces:
            wav.writeframes(pcm)
