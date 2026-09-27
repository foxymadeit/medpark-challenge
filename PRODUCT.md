# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People in Medpark International Hospital meetings: executive and administrative leadership, medical boards, and interdisciplinary hospital teams (doctors, medical professionals, managers). Anyone attending a meeting may be the one who runs Secure MOM for it: starting a recording or uploading one, choosing the meeting type, and checking the minutes. There is no dedicated operator and no training, so every step has to explain itself. Most attendees mostly read the finished minutes and their own action items.

## Product Purpose

Secure MOM turns a meeting recording, or a live meeting, into Minutes of Meeting: a summary, the decisions taken, and the action items with their owners and deadlines. The minutes go by email to the meeting type's distribution list. Success is minutes that people can use without editing, delivered within minutes of the meeting ending. The target is under 15 minutes for a 60-minute recording on the reference hardware.

## Positioning

Everything runs inside the hospital. There are no cloud calls at any point, and audio and transcripts never leave the internal network. It is built for the way Moldovan hospital meetings actually sound: Romanian sentence structure, Russian switches mid-sentence, English business terms and medical vocabulary. Speaker attribution means each action item is tied to the person who took it.

## Operating Context

- Meeting types: Medical, Executive, Administrative. Each routes to its own predefined distribution list.
- Input is either an uploaded recording (WAV, MP3, M4A) or a live recording from the room's laptop microphone.
- Pipeline: local ASR (Whisper-class), speaker diarization, local LLM extraction, then n8n routing to a local mail server.
- After generation, minutes are sent automatically, with an undo window in which the person running the meeting can review, correct an owner or deadline, or stop the send.
- Transcripts keep the original mixed language; the interface language is separate from the meeting language.

## Capabilities and Constraints

- Hard constraint: zero external network calls at runtime. The demo may be run with the network physically off.
- Reference deployment: one on-prem server with a single 16 GB GPU, or CPU-only with 32 GB RAM. Also runs on team laptops.
- Speaker labels: unknown number of speakers (1 to many). Voices can be enrolled so minutes show names instead of "Speaker N".
- Interface language: English, with a RO/RU switch.
- Devices: desktop, tablet and phone.
- Open decision: authentication method (current screens show username and password on a local account).

## Brand Commitments

Product name: Secure MOM. Client: Medpark International Hospital. The user asked for a new visual identity for the alternative designs, so no existing palette or typography is binding.

## Evidence on Hand

- Real sample meeting: `data/Medpark_audio.m4a` (11 min 43 s, multilingual).
- Diarization on it: 4 speakers, 227 turns (`diarization/`, file mode).
- Measured diarization quality: AMI far-field benchmarks in `diarization/README.md`.
- No real hospital minutes, names, patients or email lists exist in this repo. Any shown in designs must be clearly synthetic and must not invent real staff.

## Product Principles

1. The meeting is the unit. Everything starts from one meeting and ends in its minutes.
2. Self-explaining over configurable. Anyone in the room can run it without help.
3. Decisions and owners first. The transcript is evidence, not the product.
4. Visibly local. It is always clear that nothing left the building.
5. Mistakes stay cheap. Any automatic step can be reviewed and undone in time.

## Accessibility & Inclusion

Used by clinicians and managers of all ages, often under time pressure, sometimes on tablets or phones between duties. It needs WCAG 2.2 AA contrast, large touch targets and keyboard operation, plus a UI in English, Romanian and Russian.
