# Children's speech models, 15 October 2026

Two open recognisers trained on children's speech, run through the same `learnling eval` test as
[`../2026-10-13/`](../2026-10-13/): the same 600 speechocean762 cases (300 clips, 42 children aged 6 to 10,
seed 7, 2842 correctly read words, 300 errors). Rebuild the cases with [`eval/`](../../eval/).

| | Kid-Whisper | pasketti-phonetic |
|---|---|---|
| Correct words wrongly flagged | 11.8% (335) | 7.5% (214) |
| Mistakes caught | 63.0% (189) | 75.0% (225) |

- **Kid-Whisper** (`aadel4/kid-whisper-small-myst`, Apache 2.0): whisper-small fine-tuned on American
  children's speech (MyST), converted for faster-whisper and run with `--asr whisper --whisper-model <folder>`.
- **pasketti-phonetic** (`drivendata/pasketti-phonetic`, bigcode-openrail-m): a WavLM model fine-tuned on
  children's speech that writes sounds, not words. Run with `--asr pasketti --max-word-error 0.5`.

Files: `child-kidwhisper.txt` and `child-pasketti.txt` are the raw output of `learnling eval`. Results by age
group are in [`../age-groups.md`](../age-groups.md).

Neither is good enough yet: the pipeline works, but it is not yet accurate on children's voices. These
children are native Mandarin speakers reading English sentences, so accent is part of what is measured.
