"""Guided recording session for adult test readers.

    python eval/record_takes.py

Shows ten short reads one at a time, some clean and some with planned
mistakes, records each from the microphone, and writes the label file
automatically, so nobody has to type what was said. Each reader gets their
own folder, and everything is zipped onto the Desktop at the end.

Only for adult volunteers reading the script below. Needs the `mic` extra:
pip install -e ".[mic]"
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learnling.record import record_until_enter, write_wav  # noqa: E402

CAT = "The cat sat on the mat. The cat had a hat. The cat ran to the mat and sat."
DUCK = (
    "The little duck swam in the pond. She saw a frog sitting on a log. "
    "The duck and the frog became good friends and played there every day."
)
KITE = (
    "Sam has a red kite. He runs up the hill with his dad. "
    "The wind lifts the kite high in the sky. Sam laughs and holds the string tight."
)
SHELL = (
    "Mia found a shell on the beach. It was pink and white and smooth. "
    "She held it to her ear and heard the sea. Then she put it in her bag to show her mom."
)

# What to read aloud. [word] is a planned mistake: say the word in brackets.
# (pause) means stop for about three seconds before the next word.
# (skip) marks where a word of the passage is left out; say nothing there.
TAKES = [
    ("cat-clean", CAT, CAT),
    ("duck-clean", DUCK, DUCK),
    ("kite-clean", KITE, KITE),
    ("shell-clean", SHELL, SHELL),
    (
        "cat-mistakes",
        CAT,
        "The cat sat on the [hat]. The cat had a hat. The cat ran (skip) the mat and sat.",
    ),
    (
        "duck-mistakes",
        DUCK,
        "The little duck swam in the [pound]. She saw a [fog] sitting on a log. "
        "The duck and the frog became (skip) friends and played there every day.",
    ),
    (
        "kite-mistakes",
        KITE,
        "Sam has a red kite. He runs up the hill with his dad. "
        "The wind (pause) lifts the kite [hig] high in the sky. Sam [laws] and holds the string tight.",
    ),
    (
        "shell-mistakes",
        SHELL,
        "Mia [fond] a [sell] shell on the beach. It was pink (skip) (skip) and smooth. "
        "She held it to her ear and heard the sea. Then she put it in her bag to show her mom.",
    ),
    (
        "duck-close-misreads",
        DUCK,
        "The little duck [swim] in the pond. She saw a frog [sit] on a log. "
        "The duck and the frog (pause) became good friends and played there every day.",
    ),
    (
        "shell-close-misreads",
        SHELL,
        "Mia found a shell on the [bench]. It was pink and white and smooth. "
        "She held it to her ear and [hard] the sea. (skip) She put it in her bag to show her mom.",
    ),
]


def said_text(script: str) -> str:
    """What the reader actually says, for the label file."""
    text = script.replace("(pause)", " ").replace("(skip)", " ")
    text = re.sub(r"\[([^\]]+)\]", r"\1", text)
    return " ".join(text.split())


def display_text(script: str) -> str:
    """The script as shown on screen, with mistakes in capitals."""
    text = re.sub(r"\[([^\]]+)\]", lambda m: m.group(1).upper(), script)
    text = text.replace("(pause)", "... (wait 3 seconds) ...")
    text = re.sub(r"(\s*\(skip\))+", "", text)
    return " ".join(text.split())


def changes(script: str) -> list[str]:
    notes = []
    for word in re.findall(r"\[([^\]]+)\]", script):
        notes.append(f'say "{word}"')
    skips = script.count("(skip)")
    if skips:
        notes.append(f"leave out {skips} word{'s' if skips > 1 else ''} (already removed above)")
    if "(pause)" in script:
        notes.append("stop for about 3 seconds where shown")
    return notes


def run() -> None:
    print("\nlearnling guided recording\n")
    reader = input("Reader's first name or initials: ").strip() or "reader"
    reader = re.sub(r"[^A-Za-z0-9_-]", "", reader) or "reader"
    root = Path.home() / "learnling-recordings"
    folder = root / reader
    folder.mkdir(parents=True, exist_ok=True)
    print(f"\nRecordings go to {folder}")
    print("Read each one in a normal voice. Words in CAPITALS are the planned mistakes.\n")

    for number, (name, passage, script) in enumerate(TAKES, start=1):
        stem = f"take-{number:02d}-{name}"
        if (folder / f"{stem}.json").exists():
            print(f"[{number}/{len(TAKES)}] already recorded, skipping.")
            continue
        while True:
            print("-" * 70)
            print(f"[{number}/{len(TAKES)}] Read exactly this:\n")
            print("   " + display_text(script) + "\n")
            notes = changes(script)
            if notes:
                print("   Mistakes in this one: " + "; ".join(notes) + "\n")
            input("Press Enter, then start reading. ")
            pcm = record_until_enter()
            seconds = len(pcm) / 2 / 16000
            answer = input(
                f"Got {seconds:.0f} seconds. Enter to keep it, r to redo: "
            ).strip().lower()
            if answer != "r":
                break
        write_wav(folder / f"{stem}.wav", pcm)
        label = {"passage": passage, "said": said_text(script), "reader": reader, "take": name}
        (folder / f"{stem}.json").write_text(json.dumps(label, indent=1) + "\n")
        print("Saved.\n")

    zip_base = Path.home() / "Desktop" / "learnling-recordings"
    if not zip_base.parent.exists():
        zip_base = Path.home() / "learnling-recordings-zip"
    archive = shutil.make_archive(str(zip_base), "zip", root)
    print("-" * 70)
    print(f"Done. All readers so far are zipped here:\n   {archive}")
    print("To add another reader, run this again and type their name.")


if __name__ == "__main__":
    run()
