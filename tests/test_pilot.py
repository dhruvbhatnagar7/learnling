import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from learnling import pilot
from learnling.cli import build_parser

PASSAGE = "The cat sat on the mat."


def test_only_child_codes_are_accepted():
    assert pilot.check_child_code("Child03") == "child03"
    for bad in ["maya", "child3", "child03 smith", ""]:
        with pytest.raises(ValueError):
            pilot.check_child_code(bad)


def test_a_session_saves_each_kept_read_and_stays_silent(tmp_path, capsys):
    answers = iter(["", "", "", "", "d", "q"])  # ready, keep, another; ready, discard, finish
    saved = pilot.run_start(
        "child03", PASSAGE, age=6, root=tmp_path,
        record=lambda prompt: b"\0\0" * 16000, prompt=lambda _q="": next(answers),
    )
    assert len(saved) == 1
    label = json.loads(saved[0].read_text())
    assert label == {"passage": PASSAGE, "said": "", "child": "child03", "age": 6}
    assert saved[0].with_suffix(".wav").exists()
    assert saved[0].parent == tmp_path / "child03"
    out = capsys.readouterr().out
    # Nothing that would be a hint or a score.
    assert "starts with" not in out and "%" not in out


class FakeStand:
    """Stands in for ssh and tar against a folder playing the Pi's home."""

    def __init__(self, home: Path):
        self.folder = home / pilot.PILOT_FOLDER
        self.corrupt: set[str] = set()

    def __call__(self, cmd, input=None, capture_output=False, text=False):
        if cmd[0] == "ssh" and "sha256sum" in cmd[2]:
            lines = [
                f"{hashlib.sha256(p.read_bytes()).hexdigest()}  ./{p.relative_to(self.folder)}"
                for p in sorted(self.folder.rglob("*")) if p.is_file()
            ]
            return subprocess.CompletedProcess(cmd, 0, stdout="\n".join(lines) + "\n")
        if cmd[0] == "ssh" and cmd[2].startswith("tar"):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as tar:
                for p in sorted(self.folder.rglob("*")):
                    if p.is_file():
                        data = p.read_bytes()
                        name = str(p.relative_to(self.folder))
                        if name in self.corrupt:
                            data = data[:-1] + b"x"
                        info = tarfile.TarInfo(f"./{name}")
                        info.size = len(data)
                        tar.addfile(info, io.BytesIO(data))
            return subprocess.CompletedProcess(cmd, 0, stdout=buffer.getvalue())
        if cmd[0] == "tar":
            with tarfile.open(fileobj=io.BytesIO(input)) as tar:
                tar.extractall(cmd[3], filter="data")
            return subprocess.CompletedProcess(cmd, 0)
        if cmd[0] == "ssh" and "rm" in cmd[2]:
            for name in input.decode().split("\0"):
                (self.folder / name).unlink()
            for d in sorted(self.folder.rglob("*"), reverse=True):
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError(f"unexpected command {cmd}")


def _stand_with_readings(tmp_path):
    stand = FakeStand(tmp_path / "pi")
    for child in ("child01", "child02"):
        pilot.save_reading(stand.folder / child, child, 7, PASSAGE, b"\1\0" * 800)
    return stand


def test_copy_moves_checked_files_and_clears_the_stand(tmp_path):
    stand = _stand_with_readings(tmp_path)
    dest = tmp_path / "mac"
    moved = pilot.run_copy("pi@stand", dest=dest, run=stand)
    assert len(moved) == 4
    assert sorted(p.name for p in dest.rglob("*.wav")) == sorted(
        p for p in (m.split("/")[-1] for m in moved) if p.endswith(".wav")
    )
    assert not any(stand.folder.rglob("*"))


def test_a_file_that_arrives_damaged_stays_on_the_stand(tmp_path):
    stand = _stand_with_readings(tmp_path)
    damaged = next(str(p.relative_to(stand.folder)) for p in stand.folder.rglob("*.wav"))
    stand.corrupt.add(damaged)
    moved = pilot.run_copy("pi@stand", dest=tmp_path / "mac", run=stand)
    assert damaged not in moved and len(moved) == 3
    assert (stand.folder / damaged).exists()
    assert not (tmp_path / "mac" / damaged).exists()


def test_labelling_saves_what_was_said(tmp_path):
    first = pilot.save_reading(tmp_path, "child01", 7, PASSAGE, b"\0\0")
    answers = iter(["r", "The cat sat on the hat."])
    assert pilot.run_label(tmp_path, play=lambda wav: None, ask=lambda q, prefill: next(answers)) == 1
    assert json.loads(first.read_text())["said"] == "The cat sat on the hat."
    # Labelled readings are not asked about again.
    assert pilot.run_label(tmp_path, play=lambda wav: None, ask=lambda q, prefill: "") == 0


def test_an_unchanged_answer_means_read_exactly(tmp_path):
    label = pilot.save_reading(tmp_path, "child01", 7, PASSAGE, b"\0\0")
    pilot.run_label(tmp_path, play=lambda wav: None, ask=lambda q, prefill: prefill)
    assert json.loads(label.read_text())["said"] == PASSAGE


def test_the_pilot_commands_parse():
    args = build_parser().parse_args(["pilot", "start", "child03", "--passage", "p.txt", "--age", "6"])
    assert (args.pilot_command, args.child, args.age) == ("start", "child03", 6)
    assert build_parser().parse_args(["pilot", "copy", "pi@learnling.local"]).host == "pi@learnling.local"


def test_an_unreachable_stand_is_an_error_not_an_empty_copy(tmp_path):
    def offline(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 255, stdout="", stderr="no route to host")

    with pytest.raises(ValueError, match="Could not reach"):
        pilot.run_copy("pi@stand", dest=tmp_path, run=offline)
