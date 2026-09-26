# Liminal demo video: script

About 100 seconds, 1920×1080. Narration: Kokoro-82M, voice `bm_lewis`, British
English, generated offline. Screen: the real web app on the real backend,
replaying what the real pipeline produced from our recorded mock board (the
processing wait is cut, and the video says so on screen).

| # | Screen | Narration |
|---|---|---|
| 1 | Title card: "Liminal" | In 2023, a medical transcription company lost the records of nearly nine million patients. The hospitals never lost a laptop. They had sent their audio to someone else. |
| 2 | Title card: the three languages in one sentence | Medpark's boards speak Romanian, switch to Russian mid-sentence, and borrow English terms. Cloud note-takers can't follow that, and a hospital can't let them try. |
| 3 | Terminal: `offline_check.sh` passes, cable icon | This is Liminal. Everything you are about to see runs on one hospital server, with the network cable pulled out. |
| 4 | Meetings list, pick Medical, upload the recording | Someone picks the meeting type, uploads the recording, and presses Write the minutes. Nobody has to touch anything after that. |
| 5 | Processing screen (wait cut, labelled) | Each phrase is transcribed twice, as Romanian and as Russian, and the better reading wins. At the same time, Liminal works out who spoke when, on the processor alone. |
| 6 | Minutes page: decisions, actions, owners, dates | A local model drafts the minutes, then code checks every fact against the recording. A proposal nobody accepted stays a proposal. A deadline said as "by Friday" becomes Friday, the second of October. Patients appear only as initials. |
| 7 | Needs-confirmation card | Anything the checks cannot prove waits for a person before a single email goes out. |
| 8 | Countdown, then n8n canvas, then the inbox with three PDFs | After a sixty-second window that anyone can stop, n8n routes the minutes to the right board, in Romanian, Russian and English. |
| 9 | Numbers card | Ninety-three percent speaker accuracy on mixed-language meetings. Every decision in our test meetings found, and none invented. Zero calls outside the building. |
| 10 | End card | Liminal. Minutes you can send, from meetings that never leave the hospital. |

Checked with the humanizer and voice rules: no em dashes, no filler
intensifiers, figures stated as measured (see the README for the data behind
each one).
