# How learnling's speech recognition was evaluated

First run: 13 October 2026. Results: [`results/2026-10-13/`](../results/2026-10-13/). Scripts to rebuild every
case: [`eval/`](../eval/).

## The question

When someone reads a known passage aloud, how often does learnling get the judgement of each word right?
Two numbers answer it:

- **False-accusation rate.** Of the words the reader read correctly, the share learnling marked as wrong.
  This is the number that matters most. Telling a child they misread a word they read correctly damages
  their confidence and their trust in the tool, so learnling is built to stay quiet when unsure (see
  `MISCUE_CONFIDENCE_THRESHOLD` in `learnling/agents/reading.py`).
- **Catch rate.** Of the words the reader really got wrong, the share learnling flagged.

A word counts as wrong if it was misread or skipped. Added words and self-corrections are not errors,
following the oral reading fluency counting rules in `learnling/fluency.py`.

## How a test case works

Each case is a recording, the passage the reader is checked against, and `said`: what the reader actually
said, typed by a person. learnling's own alignment turns `passage` and `said` into the answer key (which
words were really wrong). Then the recording goes through a speech recogniser and learnling's reading
agent, and the words it flags are compared with the key. The harness is `learnling/evaluate.py`, run as
`python -m learnling eval FOLDER`.

## Where the errors come from

Public recordings of people reading are almost all read correctly. To get reading errors without editing
any audio, the passage was changed instead of the recording. If the reader said "the yellow lamps" and the
passage is changed to "the yellow lumps", then from learnling's point of view the reader misread "lumps"
as "lamps". The same trick makes skipped words (a word added to the passage that the reader never says) and
clearly different words ("shine" in the passage, "light" in the recording). The true transcript is known in
every case, so the answer key is exact.

This has a real limitation: these are tidy errors made by fluent readers. Children learning to read also
sound words out, stop part way through a word, and restart lines. None of that is in this test.

## Recordings used

| Set | Source | Speakers | Cases |
|---|---|---|---|
| Adults | 6 LibriSpeech clips (audiobooks, CC BY 4.0) shipped as samples with Mozilla DeepSpeech and sherpa-onnx | Adult native English speakers | 21 (412 correct words, 17 errors) |
| Children | speechocean762 test split, only clips its experts scored as complete | 42 children aged 6 to 10, native Mandarin speakers reading English sentences | 600 (2842 correct words, 300 errors) |

Each child clip gives two cases: the clean reading, and one error (a close misreading, a different word, or
a skip, in turn). Clips and edits are chosen with a fixed random seed.

## Recognisers tested

- **Vosk**, small English model `vosk-model-small-en-us-0.15`, limited to the words on the page plus an
  "unknown" token (`learnling/asr/vosk.py`).
- **Whisper**, `base.en` through faster-whisper, open vocabulary, never given the passage as a prompt
  (`learnling/asr/whisper.py`).

Both ran on a CPU in a cloud container with learnling's default confidence threshold (0.75).

## Results

| | Adults, Vosk | Adults, Whisper | Children, Vosk | Children, Whisper |
|---|---|---|---|---|
| False-accusation rate | 2% | 0% | 16% | 7% |
| Catch rate | 65% | 94% | 83% | 51% |

Details, per-case tables and a breakdown by error type and age are in
[`results/2026-10-13/`](../results/2026-10-13/).

## What the results do and do not show

- The pipeline works end to end on real recorded speech: audio in, a per-word judgement and a fluency
  number out.
- On clear adult speech both recognisers are usable, and Whisper is close to the goal (no false
  accusations, almost every error caught).
- On these children's voices neither is good enough yet. A 7 to 16% false-accusation rate means a child
  would regularly be told a correct word was wrong. learnling should not be used with children on the
  strength of these numbers.
- The children in this set are reading a second language, so accent is part of what was measured. Native
  English-speaking children reading a real passage at home have not been tested.
- Younger children fared worse with both recognisers.
- Nothing here was tested with live listening, on a Raspberry Pi, or with real reading errors by children.

## Next

Recordings of the intended use: people reading the sample passages aloud with `learnling record`, labelled
by hand, starting with adults and then, with written parent consent, children at home. Results will be
added here as new dated folders, and earlier results will stay as they are.
