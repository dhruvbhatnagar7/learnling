# Streaming recogniser, adults, 14 October 2026

Same 21 adult cases as [`../2026-10-13/`](../2026-10-13/) (6 LibriSpeech clips, errors made by editing the
passage), now through the streaming recogniser used for live reading (`learnling/asr/sherpa.py`). Rebuild
the cases with [`eval/`](../../eval/); the models are on the sherpa-onnx releases page.

| Model | Threshold | False accusations | Catch rate |
|---|---|---|---|
| `sherpa-onnx-streaming-zipformer-en-2023-06-26` | 0.75 (default) | 0% | 53% |
| `sherpa-onnx-streaming-zipformer-en-2023-06-26` | 0.5 | 0% | 100% |
| `sherpa-onnx-streaming-zipformer-en-20M-2023-02-17` | 0.75 (default) | 0% | 18% |
| `sherpa-onnx-streaming-zipformer-en-20M-2023-02-17` | 0.5 | 8% | 94% |

What it means:

- The larger streaming model heard every word of these clear adult recordings correctly. At the default
  threshold it still held back about half the real errors as unsure. Its confidence scores run lower than
  Whisper's, so the default threshold, which was set with no real data, is too cautious for it.
- At 0.5 the larger model caught every error with no false accusations here. That is 17 errors on clean
  audiobook speech, far too few to choose a threshold from, and nothing on children. The default stays at
  0.75 until there is better data.
- The smaller model, the one sized for a Raspberry Pi, mishears more ("brothels" as "broffels") and tends
  to drop the first words of a clip.
- Speed on 2 CPU threads of a cloud Xeon: 35.5 seconds of audio in 3.0 seconds (larger model) and 1.3
  seconds (smaller). Not yet measured on a Raspberry Pi.

Files: `adult-sherpa-*.txt` are the raw output of `learnling eval`.

Children's speech was not run on this model yet: the children's dataset could not be downloaded from the
test machine on this date.
