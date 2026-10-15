# Trying learnling with real audio

This is the README's M2 milestone: a recorded reading goes in, and the same report the
simulated demo produces comes out. Nothing here is live yet, and none of it has been tested with
children.

## Two recognisers

| | Whisper (`--asr whisper`) | Vosk (`--asr vosk`) |
|---|---|---|
| What it listens for | Any English words | Only the words on the page, plus "something else" |
| Good at | Telling you what a misreading was | Not turning a misreading back into the right word |
| Weak at | Pulled toward fluent, correct-sounding text | Can only say a word was wrong, not what was said |
| Size | `base.en` is about 150 MB | Small English model is about 40 MB, fits a Raspberry Pi |
| Install | `pip install learnling[asr]` | `pip install learnling[vosk]` and a small model from https://alphacephei.com/vosk/models |

Both run offline once the model is downloaded. Audio is read from the file and never copied or
uploaded.

```
python -m learnling read --passage passages/sample_level1.txt --age 6 --audio reading.wav
python -m learnling read --passage passages/sample_level1.txt --age 6 --audio reading.wav \
    --asr vosk --vosk-model ~/models/vosk-model-small-en-us-0.15
```

Vosk wants 16-bit mono WAV. To convert a phone recording:
`ffmpeg -i reading.m4a -ac 1 -ar 16000 -sample_fmt s16 reading.wav`

## Recording yourself

```
pip install "learnling[vosk,mic]"
python -m learnling record --passage passages/sample_level1.txt --asr vosk \
    --vosk-model ~/models/vosk-model-small-en-us-0.15 --save-to my-test-set
```

Press Enter, read the passage aloud, press Enter again. You see the score straight away. With `--save-to`,
the recording and a label file are kept in that folder; open the label and type what you actually said
into `said`. Without `--save-to`, nothing is kept.

## Measuring it

A test set is a folder of recordings, each with a label file of the same name:

```
my-test-set/
  r01.wav
  r01.json    {"passage_file": "../passages/sample_level1.txt", "said": "the cat sat on the hat"}
  r02.wav
  r02.json    {"passage": "The dog ran to the park.", "said": "the dog ran to park"}
```

`said` is what the reader actually said, typed by someone who listened: misread words as they sounded,
skipped words left out, a self-correction written as both attempts ("hat mat").

```
python -m learnling eval my-test-set --asr vosk --vosk-model ~/models/vosk-model-small-en-us-0.15
```

It prints, per recording and overall:

- **False-accusation rate**: of the words read correctly, how many learnling said were wrong. This is
  the number to keep lowest; see `MISCUE_CONFIDENCE_THRESHOLD` in `learnling/agents/reading.py`.
- **Catch rate**: of the real errors, how many learnling flagged.
- **Quiet**: possible errors held back because the recogniser was unsure.
- **WCPM**: words correct per minute for each reading.

`--confidence 0.6` tries a different threshold, so the trade-off between the two rates can be seen
on the same recordings.

## Recordings and consent

- Start with adults reading the sample passages, making deliberate mistakes: skips, swapped words,
  sounding out, self-corrections. It tests the pipeline without involving any child.
- Record a child only with a parent's written consent, keep the files on that computer, and never
  commit them. `*.wav` is in `.gitignore` for this reason.
- Public research collections of children reading aloud (for example the CMU Kids corpus) have their
  own licences; check them before use.

## What is not built yet

Live listening from a microphone, the hint when a child is stuck, staying quiet on self-corrections in
real time, and spoken feedback. Those are the next step. Sound-level (phoneme) scoring is M3.
