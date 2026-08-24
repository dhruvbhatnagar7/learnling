# Corpus review: foundational 1c–3 at content_tier `upper`

**Status: drafts awaiting review. Not signed off.**

These three passages are the cell no existing tool serves — early decodable
patterns written for a reader of twelve or older. Two things about them are
editorial judgments rather than mechanical ones, so they are flagged here
rather than treated as finished:

1. **Pattern coverage has to be exact.** A decodable passage that quietly
   leans on patterns the learner has not been taught is not decodable; it
   just looks like it.
2. **The tone must not read as juvenile.** This is the entire reason the cell
   exists. If the prose condescends, the passage fails even with perfect
   pattern coverage.

Below is what each draft actually contains, and every compromise made.

---

## `last_bus_01` — foundational 1c, upper

> The last bus left at six. Rick ran up the ramp and felt his bag slip. The
> strap had snapped. His kit went into the mud — his lamp, his drill, and a
> stack of prints for the job.
>
> The bus did not stop. Rick felt the cost of it sink in. He had to text Ben
> and ask for a lift.

**Target patterns (new at 1c):** `ck`, `ng`, `nk`, three-letter blends, CVCC/CCVC.

| Pattern | Words |
|---|---|
| `ck` | Rick, stack |
| `nk` | sink |
| three-letter blend | strap |
| final blends | last, left, felt ×2, went, lamp, ramp, cost, lift, ask, text |
| initial blends | slip, snapped, drill, prints, stop, stack |

**Compromises to check:**
- **`ng` is not represented.** No natural `-ng` word fit the scene. Either accept
  that the sibling passages carry it, or a line can be added.
- **`for`** appears twice and is r-controlled (a stage-4 pattern). It is a top-50
  sight word, so this is the usual decodable-text allowance — but it is an
  allowance.
- **`into`** is two syllables; standard sight word, flagging for completeness.
- **`snapped`, `prints`, `prints`** use inflections (`-ed`, `-s`). Conventionally
  fine at this stage; confirm it matches the progression you want.

**Tone:** missing the last bus, dropped tools, texting someone for a lift. No
animals, no whimsy, real consequence. The em-dash list is the one stylistic
flourish — cut it if the pacing should be flatter.

---

## `the_shift_01` — foundational 2, upper

> Josh was on shift at the shop. The last van had left at ten. He had to check
> the batch, match it to the list, then lock up.
>
> Then — a crash. Josh went stiff. His chest felt thick with it.
>
> He went up the path to the back. A shelf had split and the stock had shot off
> it. Chips of glass sat in the dust.
>
> Just a shelf. Not a theft. Josh let his breath go and got the brush.

**Target patterns (new at 2):** `sh`, `ch`, `th`, `tch`, `wh`.

| Pattern | Count | Words |
|---|---|---|
| `sh` | 7 | Josh ×3, shift, shop, shelf ×2, shot, brush |
| `ch` | 3 | check, chest, chips |
| `th` | 5 | then ×2, thick, path, theft, breath |
| `tch` | 2 | batch, match |
| `wh` | 0 | — |

**Compromises to check:**
- **`wh` is absent.** No `wh-` word fit without forcing a question into the prose.
  Deliberate; say if you want it in.
- `tch` gets two instances, both in one sentence (`check the batch, match it`).
  That line is doing a lot of pattern work at once — check it doesn't read as
  drill rather than story.

**Tone:** a late shift, a noise, a moment of fear, an anticlimax. The intended
beat is the relief of "just a shelf, not a theft" — an adult worry, not a
child's. This is the draft I am least sure of: the four short paragraphs make
it feel slightly like a reading exercise shaped as suspense.

---

## `coast_road_01` — foundational 3, upper

> Jake rose at five to make the nine train. The rain had not let up all week,
> and the coast road was long.
>
> He drove east. The sea was pale and the road was bleak. He kept his speed and
> made up time.
>
> A late train would mean he lost the deal. He had made that plain to no one but
> himself.
>
> He reached the gate at three. The train was still at the rail.

**Target patterns (new at 3):** silent-e and vowel teams.

| Pattern | Words |
|---|---|
| `a_e` | make, made ×2, late, pale, gate |
| `i_e` | five, nine, time |
| `o_e` | rose, drove |
| `ai` | train ×3, rain, plain, rail |
| `ee` | week, speed, three |
| `ea` | east, sea, bleak, mean, deal, reached |
| `oa` | coast, road ×2 |

**Compromises to check:**
- **`u_e`, `ay` are absent** from the stage-3 pattern set. Add a passage or extend
  this one if the stage needs full coverage before a learner is assessed on it.
- **`ea` as short /e/ was deliberately excluded.** Earlier drafts used *steady* and
  *ahead*; both were cut, because a learner meeting `ea` for the first time
  should not simultaneously meet its irregular mapping. Worth confirming you
  agree — it cost some natural phrasing.
- **`would`, `all`, `one`** are irregular sight words.
- **`reached`** carries a stage-2 `ch`; cumulative progression makes this correct,
  but noting it since it is the only cross-stage borrow doing semantic work.

**Tone:** the strongest of the three. A missed train costing a deal is
recognisably adult stakes, and *"He had made that plain to no one but himself"*
carries real interiority while staying inside the pattern set.

---

## Cross-cutting questions for you

1. **Names.** Rick, Josh, Ben, Jake — all short, monosyllabic, decodable, and
   all male. Deliberate on decodability, accidental on gender. Worth fixing;
   decodable feminine names exist (Kim, Meg, Jan, Fran, Steph, Jade).
2. **Length.** 55–75 words each. Long enough for a WCPM sample, short enough not
   to exhaust a struggling reader. Confirm that is the range you want, since the
   fluency norms assume a one-minute sample.
3. **British vs American spelling.** `practise` is used as a verb in
   `progression.py`; the passages avoid the question entirely. Pick one for the
   project.
4. **One passage per cell is thin.** A learner who re-reads the same text is no
   longer doing an unpracticed reading, which the fluency measure depends on.
   Three or four per cell is the real target.
