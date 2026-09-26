# Data protection impact assessment (draft)

GDPR Art. 35(3)(b) requires one before "processing on a large scale of special
categories of data", which includes health data said in medical board meetings.
This draft covers the four elements Art. 35(7) asks for. The hospital's data
protection officer completes and signs it before deployment.

## 1. What is processed, and why

Meeting audio is transcribed and diarized on the hospital's own server. The
transcript is turned into minutes by a local language model and emailed to the
meeting's distribution list through the hospital's own mail server. Purpose: an
accurate record of decisions and actions, with owners and deadlines. See
`data-inventory.md`.

## 2. Necessity and proportionality

- Minutes are a normal governance duty; automating them does not widen what is
  recorded.
- Only what minutes need is kept: patients as initials, no audio in the minutes
  step, no quotes in the emailed document, deletion after the retention period.
- Nothing leaves the hospital: no cloud services, no internet at any point.

## 3. Risks to the people concerned

| Risk | Likelihood before measures | Impact |
|---|---|---|
| A wrong fact in the minutes (for example, the wrong owner of a task) | medium: language models can invent | medium: a wrong record |
| A patient identified from the minutes | low | high |
| Minutes sent to the wrong people | low | high |
| Unauthorised access to transcripts on the server | low | high |
| Staff judged by talk time or task counts | low | medium |

## 4. Measures

- Every fact is checked by code against the transcript lines; unconfirmed facts
  go to a person under *Needs confirmation*.
- Patient names are replaced by initials before the text reaches the writing step.
- Distribution lists are fixed per meeting type; the minutes wait 60 seconds
  before sending, and anyone can stop them.
- Owner-only files, no network, and a language model reachable only on the
  machine itself (tested).
- The intended purpose forbids using the output to evaluate staff.

Status: draft by the development team, 26 September 2026. To be reviewed by the
data protection officer.
