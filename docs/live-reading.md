# Live reading

`learnling live` listens while someone reads a passage aloud and helps only when they get stuck. It is
the README's two-pass read, working end to end on a laptop. It has been tried on recordings, not yet with a
child or on a Raspberry Pi.

## What happens

1. **First read, coached.** learnling follows along word by word. If the reader stalls on a word for about
   three seconds (five for ages 6 and under), it gives a hint: "Take your time. That word starts with
   'pr'." If they are still stuck after the same time again, it says the word and they carry on.
   Misreadings and self-corrections are not interrupted.
2. **Feedback.** One short coaching line about the first read.
3. **Second read, quiet.** The same passage again with no help. This one gives the words-correct-per-minute
   number.
4. **For the adult.** When and where help was given, accuracy and words correct per minute on the second
   read, and the words to practise.

The microphone is paused while learnling speaks, so it never hears itself. The listening light is on while
it listens and off while it talks. Nothing is recorded or sent anywhere, and no LLM is involved.

## Running it

```
pip install "learnling[live]"
```

Download a streaming recognition model and a voice from the sherpa-onnx releases
(https://github.com/k2-fsa/sherpa-onnx/releases):

- recognition: `sherpa-onnx-streaming-zipformer-en-2023-06-26` (about 320 MB, more accurate) or
  `sherpa-onnx-streaming-zipformer-en-20M-2023-02-17` (about 130 MB, for small devices)
- voice: `vits-piper-en_US-amy-low` (about 80 MB)

```
python -m learnling live --passage passages/sample_level1.txt \
    --model ~/models/sherpa-onnx-streaming-zipformer-en-2023-06-26 \
    --voice ~/models/vits-piper-en_US-amy-low
```

Press Enter, read, and it ends on its own after the last word (or press Enter to stop). Then the same again
for the second read. Without `--voice`, learnling prints what it would say instead of speaking.

To try it on recordings instead of the microphone, pass `--audio first.wav --audio second.wav`, and add
`--save-demo demo.wav` to get one file with the reading and learnling's voice in order.

## How it decides someone is stuck

The recogniser keeps a running guess of the words heard so far. learnling lines that guess up with the
passage and keeps track of how far the reader has got, allowing them to skip a word or two. If that
position has not moved for the stuck time, the reader is stuck on the next word, whether they are silent
or sounding it out. Time is counted in audio heard, not on the clock, so the same recording always gets
the same hints. The logic is in `learnling/live.py` and tested in `tests/test_live.py`.

## Known limits

- The streaming recogniser's confidence scores are not calibrated yet (see `results/2026-10-14/`), so the
  end-of-read judgements are more cautious than they need to be.
- The hint is always "starts with" the first two letters. It does not yet use the phonics pattern of the
  word.
- Children's speech has not been tested with this recogniser.
