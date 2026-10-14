# Real speech test, 13 October 2026

Code tested: this repository as of the commit "Count digits as the number words they stand for", with 153 tests passing. Method: [`docs/evaluation-method.md`](../../docs/evaluation-method.md). To rebuild the cases: [`eval/`](../../eval/).

Files here: `adult-vosk.txt`, `adult-whisper.txt`, `child-vosk.txt` and `child-whisper.txt` are the raw output of `learnling eval`; the `-breakdown.txt` files split the child results by error type and age.

## Audio used

6 real recordings of adults reading audiobooks aloud (LibriSpeech, CC BY 4.0, from the Mozilla DeepSpeech and sherpa-onnx sample releases on GitHub). 3 to 48 words each. This is adult speech, not children's. Only these 6 clips could be downloaded from the test machine, which could not reach the main LibriSpeech site.

Errors were made without editing audio: the passage the reader is checked against was changed, so to learnling the reader skipped a word, misread one, or read it right. `said` is always the real transcript. 21 cases, 412 correctly read words, 17 errors. See `eval/make_adult_cases.py`.

## Vosk (passage words only), small English model

- False-accusation rate: 2% (10 of 412 correct words flagged). All 10 are the same two spots in one long clip, which appears in 5 cases: "as a" heard as "as", and "in heaven" heard as "and heaven".
- Catch rate: 65% (11 of 17).
- Skipped words: 5 of 5 caught. Clearly different word ("shine" for "light", "stop" for "halt"): 6 of 6 caught.
- Close misreadings were all missed (0 of 6): "lamps" read for "lumps", "hope" for "hop", "man" for "men", "these" for "those", "this" for "that", "would" for "could". Because Vosk may only pick words on the page, a near miss is snapped to the page word, with confidence 1.0. So the confidence threshold cannot catch it.
- About 0.5 seconds per recording on a laptop-class CPU.

## Experiment, not in the code

Adding real words one letter away from each passage word to Vosk's list (`eval/neighbour_experiment.py`): catch rate 71%, false accusations 1%. It catches "hop" and "those", but homophones like "witch" for "which" start showing up and are held back as unsure. Worth a proper look in stage 3, with a homophone filter.

## Whisper base.en

- False-accusation rate: 0% (0 of 412). Before the fix below it was 1%: Whisper wrote "forever" where the page said "for ever".
- Catch rate: 94% (16 of 17). It caught all the close misreadings Vosk missed. The one miss ("the" read for "a") was heard correctly but held back as unsure.
- About 1.5 seconds per recording on CPU, versus 0.5 for Vosk.
- Caveat: this is clear adult audiobook speech, where Whisper is strongest. Its known weakness is children's speech and its pull toward fluent text, which these clips cannot show.

## Fixed during testing

- Joined or split words ("forever" / "for ever", "into" / "in to") no longer count as misreadings.
- `pip install learnling[asr]` installed PyAV 19, which the latest faster-whisper cannot open audio with. The asr extra now caps PyAV below 19.

## Not fixed

- British vs American spelling ("dishonoured" / "dishonored") still counts as a mismatch. Here it was held back as unsure, but it could surface.

## Children's speech (speechocean762)

Data: speechocean762, free for commercial and non-commercial use, from Hugging Face. 300 clips from 42 children aged 6 to 10, test split, only clips its experts scored as complete (every word read). Short sentences, 2 to 9 words. Caveat: these children are native Mandarin speakers reading English, so accent is part of what is measured, and the sentences are not a reading passage. Errors made the same way as above, one per clip (100 close misreadings, 100 different words, 100 skips), plus each clip read clean. 600 cases, 2842 correctly read words. Scripts: `eval/make_child_cases.py`, `eval/breakdown.py`.

| | Whisper base.en | Vosk small |
|---|---|---|
| False accusations | 7% | 16% |
| Catch rate | 51% | 83% |
| Close misreadings caught | 58% | 58% |
| Different word caught | 46% | 94% |
| Skips caught | 48% | 98% |
| Held back as unsure | 858 | 74 |
| False accusations, age 6 / 7 / 8 / 9 / 10 | 8 / 10 / 4 / 6 / 4% | 17 / 24 / 15 / 14 / 6% |

What it means:
- Both are far worse on children than on adults (0 to 2% false accusations there). For a product that must not tell a child they were wrong when they were right, neither is good enough yet.
- Whisper mishears accented child speech a lot ("mary got on the train" heard as "my real god on the tree"). Its low confidence then holds most of those back, which keeps false accusations lower but also hides real errors.
- Vosk catches more because it only has to choose among page words, but it also forces wrong page words onto correct readings. Missing vocabulary is not the cause (checked).
- Younger children fare worse with both, as expected.
- Fixed during this run: Whisper writes "nine" as "9", which counted as a misreading (it made Whisper look like 9% false accusations instead of 7%).

Other child datasets, not used: CMU Kids (children reading aloud, real miscues, closest match to learnling) and CSLU Kids are licensed through LDC; MyST is conversational, research licence. None are free to use.
