# AI Act assessment

Regulation (EU) 2024/1689. Moldova is not bound by it, but Medpark wants EU
alignment and the GigaHack scorecard asks for it (criterion B2).

## Where the AI is

1. A local language model reads the transcript and proposes facts: agenda items,
   decisions, actions, owners, deadlines, each with the transcript lines it rests on.
2. The same model writes the minutes' text from the facts that passed the checks.

Code, not the model, checks every fact against the transcript before anything
is written (`mom/verify.py`). The model cannot add a fact the checks did not pass.

## Risk class: limited risk, not high risk

- **Not prohibited (Art. 5).** No manipulation, no social scoring, no emotion
  recognition at work, no biometric categorisation.
- **Not high risk under Art. 6(1).** It is not a safety component of a regulated
  product and not a medical device (see `intended-purpose.md`).
- **Not high risk under Art. 6(2) and Annex III.** Of the eight areas, the closest
  is employment (Annex III, point 4(b)): allocating tasks based on behaviour or
  traits, or monitoring and evaluating staff. The system does neither: it records
  tasks that people assigned in the meeting. The intended purpose forbids using it
  to evaluate staff.
- **Voice enrollment is handled separately.** Naming people from their voice is
  biometric identification. It is off by default (people are "Speaker 1, 2"),
  opt-in, recorded with consent, local, and deletable (`diarizer voices forget`).
  If the hospital enables it widely, it should reassess whether Annex III, point 1
  applies.

## What we must do: transparency (Art. 50)

Art. 50(2), in force since 2 August 2026: "Providers of AI systems … generating
synthetic … text content, shall ensure that the outputs of the AI system are
marked in a machine-readable format and detectable as artificially generated or
manipulated." The exception for "an assistive function for standard editing" does
not apply, because turning a meeting into minutes substantially alters the input.

How we meet it:

- **Machine-readable:** the PDF's XMP metadata and the DOCX's core properties
  state that the text is AI-generated in the Author, Subject and Keywords fields,
  together with the generator (Secure MOM), the model and the date. Each
  `report.json` also records the digest of the model file.
- **Human-readable:** every page footer says the minutes were generated locally by
  AI and reviewed by the chair before sending.

## Human oversight (good practice, and ALTAI)

- Every fact the checks could not confirm is shown to a person under
  *Needs confirmation* before sending.
- In the product flow (Figma S07 and M03), the minutes send only after a 60-second window in which anyone can stop them. The email step belongs to the product shell; this package writes the documents and does not send anything.
- Every decision and action in `facts.json` links to the transcript lines it came
  from, so a reader can verify any line of the minutes.
