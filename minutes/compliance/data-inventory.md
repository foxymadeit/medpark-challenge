# Personal data the minutes pipeline touches

GDPR Art. 5 and 25 and, for Medpark, Moldova's Law No. 195/2024 on personal data
protection, which follows the GDPR and has applied since 23 August 2026.

| Data | Whose | Where it comes from | Kept where, for how long | Special category |
|---|---|---|---|---|
| Transcript text | attendees, anyone mentioned | the transcription step | `sessions/`, owner-only files; deleted after the retention period (default 30 days, set by the hospital) | may contain health data |
| Speaker labels and names | attendees | the diarizer; names typed by the chair or enrolled with consent | inside the session files | no (names); voiceprints stay in the diarizer, never in the minutes |
| Facts with evidence lines (`facts.json`) | attendees, patients mentioned | the model, checked by code | next to the minutes; same retention | may contain health data |
| The minutes (PDF, DOCX) | attendees, patients mentioned | rendered from the facts | emailed to the distribution list; archived as the hospital's record | patients as initials, age and bed only |

## Minimisation decisions

- Patients appear as initials, age and bed (for example "A.P., 54 ani, salonul 12"),
  never by name. Real minutes in our corpus do the same (`research/corpus.md`).
- The emailed minutes contain no verbatim quotes; quotes stay in the local
  `facts.json` for checking.
- No audio is kept by the minutes step.
- Intermediate files are deleted after the retention period.

## Lawful basis

- **Recording the meeting in minutes:** the hospital's legitimate interest and its
  governance duties in running its services (Art. 6(1)(f), or 6(1)(c) where a law
  requires minutes).
- **Health details said in the meeting:** Art. 9(2)(h), the management of health
  care services, with 9(3): processed by or under the responsibility of staff bound
  by professional secrecy.
- **Voiceprints (optional):** explicit consent, Art. 9(2)(a), recorded at enrollment.
