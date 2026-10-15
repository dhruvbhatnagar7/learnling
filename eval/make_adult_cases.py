"""Build labelled eval cases from real LibriSpeech read speech.

    python eval/make_adult_cases.py CLIPS_DIR CASES_DIR   (CLIPS_DIR from fetch_adult_clips.sh)

The audio is never edited. Errors are made by changing the *passage* the
reader is checked against, so from learnling's point of view the reader
misread, skipped or added a word. `said` is always the true transcript.
"""
import json, sys, shutil
from pathlib import Path

clips = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
T = {
 "ls-0": "after early nightfall the yellow lamps would light up here and there the squalid quarter of the brothels",
 "ls-1": "god as a direct consequence of the sin which man thus punished had given her a lovely child whose place was on that same dishonoured bosom to connect her parent for ever with the race and descent of mortals and to be finally a blessed soul in heaven",
 "ls-8k": "yet these thoughts affected hester prynne less with hope than apprehension",
 "ls-2830-3980-0043": "experience proves this",
 "ls-4507-16021-0012": "why should one halt on the way",
 "ls-8455-210777-0068": "your power is sufficient i said",
}
# (case suffix, passage the reader is checked against). said = T[clip].
E = {
 "ls-0": [
  ("clean", None),
  ("sub-close", "after early nightfall the yellow lumps would light up here and there the squalid quarter of the brothels"),   # read lumps as lamps
  ("sub-far", "after early nightfall the yellow lamps would shine up here and there the squalid quarter of the brothels"),     # read shine as light
  ("sub-inpassage", "after early nightfall a yellow lamps would light up here and there the squalid quarter of the brothels"),  # read a as the (the is in passage)
  ("skip", "after early nightfall the bright yellow lamps would light up here and there the squalid quarter of the brothels"),  # skipped bright
  ("two-errors", "after early nightfall the yellow lamps could light up here and over there the squalid quarter of the brothels"), # could->would, skipped over
 ],
 "ls-1": [
  ("clean", None),
  ("sub-close", "god as a direct consequence of the sin which men thus punished had given her a lovely child whose place was on that same dishonoured bosom to connect her parent for ever with the race and descent of mortals and to be finally a blessed soul in heaven"),
  ("sub-far", "god as a direct consequence of the sin which man thus punished had given her a lovely baby whose place was on that same dishonoured bosom to connect her parent for ever with the race and descent of mortals and to be finally a blessed soul in heaven"),
  ("skip", "god as a direct consequence of the sin which man thus punished had given her a lovely little child whose place was on that same dishonoured bosom to connect her parent for ever with the race and descent of mortals and to be finally a blessed soul in heaven"),
  ("two-errors", "god as a direct consequence of the sin which man thus punished had given him a lovely child whose place was on that same dishonoured bosom to connect her parent for ever with the race and descent of mortals and to be finally a blessed spirit in heaven"),
 ],
 "ls-8k": [
  ("clean", None),
  ("sub-close", "yet these thoughts affected hester prynne less with hop than apprehension"),
  ("sub-far", "yet those thoughts affected hester prynne less with hope than apprehension"),
  ("skip", "yet these sad thoughts affected hester prynne less with hope than apprehension"),
 ],
 "ls-2830-3980-0043": [("clean", None), ("sub-close", "experience proves that")],
 "ls-4507-16021-0012": [("clean", None), ("sub-far", "why should one stop on the way")],
 "ls-8455-210777-0068": [("clean", None), ("skip", "your power is quite sufficient i said")],
}
n = 0
for clip, edits in E.items():
    for name, passage in edits:
        stem = f"{clip}-{name}"
        shutil.copy(clips / f"{clip}.wav", out / f"{stem}.wav")
        (out / f"{stem}.json").write_text(json.dumps({"passage": passage or T[clip], "said": T[clip]}, indent=1))
        n += 1
print(n, "cases in", out)
