# Safety & privacy

learnling is built for children from age 4 up, including older students
reading below grade level. Safety and privacy are
architectural constraints, not features bolted on afterward — every layer
in the pipeline is designed with them in mind.

## Data handling

- **No audio retention.** Audio is not kept by this package. ASR adapters
  receive audio (a path or bytes you provide) and return a transcript.
  `learnling record` holds the microphone recording in a temporary file only
  while it is scored, then deletes it. The one exception is
  `learnling record --save-to FOLDER`, which an adult passes on purpose to
  keep a recording for testing accuracy; see `docs/audio-evaluation.md`. The
  other is `learnling pilot start`, which records for the consented family
  pilot under a child code, never a name, until `learnling pilot copy` moves
  the recordings to the adult's computer; see `docs/raspberry-pi.md`.
- **Session-only memory.** Transcripts and utterance text live only in the
  in-memory `Session` object for the lifetime of the process. Nothing is
  written to disk unless you explicitly ask for it.
- **Reports over transcripts.** The `--save-report` CLI flag writes a
  session summary (accuracy, words-per-minute, miscue counts, assessment
  categories) — not raw transcripts — so an adult can review progress
  without a recording of what the child said. It lists the passage words
  that were missed, and for a misread word the single word heard in its
  place, so the adult knows what to practise.
- **No PII collection.** learnling does not ask for or store a child's
  name, address, school, or any other personal identifier. Attempts to
  solicit that information from the agent (e.g. "what's your address?")
  are caught by the content guardrail and redirected.

## Content guardrails

Every response — whether from a rule-based template or an optional LLM
call — passes through `learnling/safety.py`'s `check_output` before it
reaches the child. Responses that trip a guardrail (violence, adult
content, personal-data solicitation, drugs/alcohol) are replaced with a
safe redirect line.

## Adult-in-the-loop

learnling is designed to sit alongside an adult, not replace one. Session
reports are meant for a teacher or parent to review; the Learning/Q&A
agent's offline behavior explicitly encourages the child to bring
questions to a grown-up as well as thinking them through together.

## COPPA-informed design

The data-minimization choices above (no audio retention, session-only
transcripts, no PII collection, stats-based reporting) are made with COPPA
(Children's Online Privacy Protection Act) constraints in mind. This is a
design posture for an open-source project, not a compliance certification
for any particular deployment — anyone deploying learnling in a product
context is responsible for their own legal review.
