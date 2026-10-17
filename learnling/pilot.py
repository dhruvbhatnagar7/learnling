"""Record-only reading sessions for the family pilot, and getting the recordings off the stand.

On the book stand (over SSH from the adult's laptop):

    learnling pilot start child03 --passage passages/sample_level1.txt --age 6 --led-pin 17

On the adult's laptop afterwards:

    learnling pilot copy pi@learnling.local         # copy every recording, check it, then delete it from the Pi
    learnling pilot label ~/learnling-pilot/child03  # listen to each one and type what was read
    learnling eval ~/learnling-pilot/child03 --asr whisper --whisper-model PATH

Record-only means the child hears nothing from learnling: no hints, no
corrections and no score. The light shows when it is listening. Scoring
happens later, on the laptop, once an adult has typed what was actually read,
so the pilot measures the recogniser on children before any child is ever
told they got a word wrong by it.

Children are known only by a code such as `child03`, never a name. The
recordings stay on the stand's SD card until `pilot copy` moves them, and the
copy is checked file by file before anything is deleted from the stand.
Only for children whose parent has signed the consent form.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from learnling.record import record_until_enter, write_wav

#: Where recordings go, on the stand and on the laptop.
PILOT_FOLDER = "learnling-pilot"

_CHILD_CODE = re.compile(r"^child\d{2,3}$")


def pilot_root() -> Path:
    return Path.home() / PILOT_FOLDER


def check_child_code(code: str) -> str:
    """Codes only: `child03`, never a name."""
    code = code.strip().lower()
    if not _CHILD_CODE.match(code):
        raise ValueError(
            f"'{code}' is not a child code. Use child01, child02 and so on, never a name."
        )
    return code


def save_reading(
    folder: Path, child: str, age: int, passage_text: str, pcm: bytes, now: datetime | None = None
) -> Path:
    """Write one reading and its label stub; return the label path."""
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{child}-{(now or datetime.now()).strftime('%Y%m%d-%H%M%S')}"
    write_wav(folder / f"{stem}.wav", pcm)
    label = folder / f"{stem}.json"
    record = {"passage": passage_text, "said": "", "child": child, "age": age}
    label.write_text(json.dumps(record, indent=1) + "\n")
    return label


def run_start(child: str, passage_text: str, age: int, led_pin: int | None = None,
              root: Path | None = None, record=record_until_enter, prompt=input) -> list[Path]:
    """One child's record-only session: as many reads of the passage as the adult wants."""
    from learnling.live_io import ListeningLight

    child = check_child_code(child)
    folder = (root or pilot_root()) / child
    light = ListeningLight(led_pin)
    saved: list[Path] = []
    print(f"\nRecording {child} (record only: learnling stays silent).")
    print(f"Passage:\n\n  {passage_text}\n")
    while True:
        prompt("Press Enter when the child is ready to start reading. ")
        light.on()
        try:
            pcm = record(prompt=prompt)
        finally:
            light.off()
        seconds = len(pcm) / 2 / 16000
        if prompt(f"Got {seconds:.0f} seconds. Enter to keep it, d to discard: ").strip().lower() == "d":
            print("Discarded.\n")
        else:
            saved.append(save_reading(folder, child, age, passage_text, pcm))
            print(f"Saved to {folder}.\n")
        if prompt("Another read? Enter for yes, q to finish: ").strip().lower() == "q":
            break
    print(f"Done. {len(saved)} reading(s) for {child} are on this stand until you run 'learnling pilot copy'.")
    return saved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def run_copy(host: str, dest: Path | None = None, run=subprocess.run) -> list[str]:
    """Move every recording from the stand at `host` to this computer.

    Copies with tar over SSH, checks each file's checksum against the stand's,
    and only then deletes from the stand the files that arrived intact. A
    file that already exists here with different contents is left on the
    stand. Returns the paths copied, relative to the pilot folder.
    """
    dest = dest or pilot_root()
    listing = run(
        ["ssh", host, f"cd {PILOT_FOLDER} 2>/dev/null && find . -type f -exec sha256sum {{}} +"],
        capture_output=True, text=True,
    )
    if listing.returncode == 255:
        # ssh's own exit code for "could not connect".
        raise ValueError(f"Could not reach {host} over SSH: {listing.stderr.strip()}")
    remote: dict[str, str] = {}
    for line in listing.stdout.splitlines():
        digest, _, name = line.partition("  ")
        if digest and name:
            remote[name.removeprefix("./")] = digest
    if not remote:
        print(f"No recordings on {host}.")
        return []

    moved: list[str] = []
    kept: list[str] = []
    with tempfile.TemporaryDirectory() as staging:
        tar_out = run(["ssh", host, f"tar -C {PILOT_FOLDER} -cf - ."], capture_output=True)
        run(["tar", "-x", "-C", staging], input=tar_out.stdout, capture_output=True)
        for name, digest in sorted(remote.items()):
            arrived = Path(staging) / name
            if not arrived.exists() or _sha256(arrived) != digest:
                kept.append(name)
                continue
            target = dest / name
            if target.exists() and _sha256(target) != digest:
                kept.append(name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(arrived), target)
            moved.append(name)

    if moved:
        run(
            ["ssh", host, f"cd {PILOT_FOLDER} && xargs -0 rm -f -- && find . -mindepth 1 -type d -empty -delete"],
            input="\0".join(moved).encode(), capture_output=True,
        )
    print(f"Copied {len(moved)} file(s) to {dest} and removed them from {host}.")
    if kept:
        print(f"Left {len(kept)} file(s) on {host} because the copy did not match: " + ", ".join(kept))
    return moved


def _play(wav: Path) -> None:  # pragma: no cover - needs a speaker
    if shutil.which("afplay"):
        subprocess.run(["afplay", str(wav)], check=False)
    elif shutil.which("aplay"):
        subprocess.run(["aplay", "-q", str(wav)], check=False)
    else:
        print("  (no audio player found; open the file to listen)")


def _ask_prefilled(question: str, prefill: str, prompt=input) -> str:
    """Ask with `prefill` already typed, so the adult only edits the misread words."""
    try:
        import readline
    except ImportError:  # pragma: no cover - Windows
        return prompt(question) or prefill
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return prompt(question)
    finally:
        readline.set_startup_hook()


def run_label(folder: Path, play=_play, ask=_ask_prefilled) -> int:
    """Listen to each unlabelled reading and type what the child actually said."""
    labels = sorted(p for p in Path(folder).glob("*.json") if not json.loads(p.read_text())["said"].strip())
    if not labels:
        print("Nothing left to label here.")
        return 0
    print(
        "For each reading: listen, then edit the passage text to match what the child said.\n"
        "Change misread words to what was said, delete skipped words, leave self-corrections as the\n"
        "final word. Press Enter with the text unchanged if it was read exactly. Type r to replay,\n"
        "s to skip for now.\n"
    )
    done = 0
    for label_path in labels:
        record = json.loads(label_path.read_text())
        wav = label_path.with_suffix(".wav")
        while True:
            print(f"-- {label_path.stem}")
            play(wav)
            said = ask("Said: ", record["passage"]).strip()
            if said.lower() == "r":
                continue
            break
        if said.lower() == "s":
            continue
        record["said"] = said or record["passage"]
        label_path.write_text(json.dumps(record, indent=1) + "\n")
        done += 1
    print(f"Labelled {done} reading(s). Score them with: learnling eval {folder}")
    return done
