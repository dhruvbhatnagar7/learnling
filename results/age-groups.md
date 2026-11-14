# Children's results by age group

The same 600 speechocean762 cases as the combined results (300 clips, 42 children, seed 7), with the same
models and settings, split by the child's age. The combined numbers are unchanged; the "all" row for each
model is the combined result. Each child's age is the one speechocean762 records for that speaker, carried
in the case name. Rebuild with `python eval/by_age_group.py` on the raw outputs in each results folder.

Models: Whisper base.en and Vosk small ([`2026-10-13/`](2026-10-13/)), Kid-Whisper and pasketti-phonetic
([`2026-10-15/`](2026-10-15/)), Nemotron streaming 0.6b, 560 ms, int8, through sherpa-onnx, confidence 0.75
([`2026-10-17/`](2026-10-17/)).

| Model | Age group | Children | Correct words | Real mistakes | Correct words wrongly flagged | Mistakes caught |
|---|---|---|---|---|---|---|
| Whisper base.en | 1-3 | 0 | no data | no data | no data | no data |
| Whisper base.en | 3-5 | 0 | no data | no data | no data | no data |
| Whisper base.en | 5-8 | 24 | 1347 | 159 | 9.1% | 40.3% |
| Whisper base.en | 8-12 | 18 | 1495 | 141 | 4.8% | 62.4% |
| Whisper base.en | all | 42 | 2842 | 300 | 6.8% | 50.7% |
| Vosk small | 1-3 | 0 | no data | no data | no data | no data |
| Vosk small | 3-5 | 0 | no data | no data | no data | no data |
| Vosk small | 5-8 | 24 | 1347 | 159 | 20.4% | 84.9% |
| Vosk small | 8-12 | 18 | 1495 | 141 | 11.8% | 81.6% |
| Vosk small | all | 42 | 2842 | 300 | 15.9% | 83.3% |
| Kid-Whisper | 1-3 | 0 | no data | no data | no data | no data |
| Kid-Whisper | 3-5 | 0 | no data | no data | no data | no data |
| Kid-Whisper | 5-8 | 24 | 1347 | 159 | 14.3% | 51.6% |
| Kid-Whisper | 8-12 | 18 | 1495 | 141 | 9.6% | 75.9% |
| Kid-Whisper | all | 42 | 2842 | 300 | 11.8% | 63.0% |
| pasketti-phonetic | 1-3 | 0 | no data | no data | no data | no data |
| pasketti-phonetic | 3-5 | 0 | no data | no data | no data | no data |
| pasketti-phonetic | 5-8 | 24 | 1347 | 159 | 9.0% | 77.4% |
| pasketti-phonetic | 8-12 | 18 | 1495 | 141 | 6.2% | 72.3% |
| pasketti-phonetic | all | 42 | 2842 | 300 | 7.5% | 75.0% |
| Nemotron streaming | 1-3 | 0 | no data | no data | no data | no data |
| Nemotron streaming | 3-5 | 0 | no data | no data | no data | no data |
| Nemotron streaming | 5-8 | 24 | 1347 | 159 | 7.5% | 40.3% |
| Nemotron streaming | 8-12 | 18 | 1495 | 141 | 6.6% | 52.5% |
| Nemotron streaming | all | 42 | 2842 | 300 | 7.0% | 46.0% |

Age groups do not overlap: "1-3" is under 3, "3-5" is 3 and 4, "5-8" is 5 to 7, and "8-12" is 8 to 12. A
catch rate is marked "too few mistakes" when its group has fewer than 30 real mistakes.

The speakers are Mandarin-speaking children learning English, reading single sentences. There is no open
data in this set for children under 5, which is part of learnling's target age (4 and up).
