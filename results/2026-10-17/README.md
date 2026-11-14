# Streaming Nemotron, children, 17 October 2026

The streaming recogniser used for live reading on the book stand, on the same 600 speechocean762 cases as
[`../2026-10-13/`](../2026-10-13/) (300 clips, 42 children aged 6 to 10, seed 7, 2842 correctly read words,
300 errors). Rebuild the cases with [`eval/`](../../eval/).

Model: nemotron-speech-streaming-en-0.6b, 560 ms chunks, int8, through sherpa-onnx (`--asr sherpa`),
confidence 0.75.

| | Nemotron streaming |
|---|---|
| Correct words wrongly flagged | 7.0% (200) |
| Mistakes caught | 46.0% (138) |

`child-nemotron.txt` is the raw output of `learnling eval`, rerun on 1 November 2026 with identical totals.
Results by age group are in [`../age-groups.md`](../age-groups.md).
