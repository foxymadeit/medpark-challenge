# Liminal

Hackathon prototype for Medpark hospital: record or upload a meeting → AI writes the minutes (MoM) → the organizer reviews → the MoM is emailed to participants.

Frontend only — **everything is mocked** (auth, speech-to-text, diarization, email). Built from the Figma file `bnCzuQd39C1F9AkGe7lwo7`, page "Liminal — minimal v3" (desktop 1440×800, responsive down to phone).

**Live demo:** https://liminal-delta-five.vercel.app

> In the team repo (`foxymadeit/medpark-challenge`, branch `Cristina-Iftodi`) this app lives in the `liminal/` folder and is independent of the Python pipeline next to it — it does not call it yet.

## Demo accounts

On **Log in**, click one of the demo accounts under the form (any password works):

| Account | Role |
|---|---|
| Dr. Ana Popescu · `ana.popescu@medpark.md` | Admin (manages participants and access) |
| Dr. Igor Rusu · `igor.rusu@medpark.md` | Organizer |

## 3-minute demo script

1. **Welcome → Log in** as Dr. Ana Popescu.
2. **New meeting:** rename the meeting (pen next to the title), pick a date, type *Medical*, add participants (type a name, pick from the list). On the red card, show **Test microphone** and the mic picker.
3. **Record:** click the red card → 3‥2‥1 countdown → live waveform coloured by speaker, voices and languages detected on the right → **Stop and write minutes**.
   *Or* **Upload:** click the blue card, pick any audio file → upload bar → **Write minutes**.
4. **Processing:** steps and live transcript fill in. It takes ~1 min — click **Skip to the minutes (demo)** to jump ahead.
5. **Review:** click a highlighted word to pick the right reading, fix it, flag its language (RO/RU/EN) or remove it; select a sentence to listen/edit/remove; name unknown voices ("Who is this?"); edit the Task · Owner · Deadline table.
6. **Send MoM** → sending bar → sent. **Go to History** → open the record → **Download PDF** / **Save as template**.
7. Switch **EN / RO / RU** in the top bar at any point.

Tips: start from **Templates** (e.g. *Tumor board*) to get a meeting with its participants pre-filled. Settings → *Default review mode: Auto* sends the minutes without the review step.

## Run locally

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build
```

Add `?reset` to any URL to wipe the demo data (it lives in the browser's localStorage).

## Stack

Vite + React + TypeScript, React Router, plain CSS with design tokens (`src/styles/tokens.css`, names mirror the Figma variables), Phosphor icons, pdfmake (lazy-loaded) for the PDF export. No UI kit.

## Where things live

| Path | What |
|---|---|
| `src/screens/` | One file per Figma section (Access, Onboarding, Participants, NewMeeting, Recording, Upload, Processing, Review, Sent, History, Templates, Settings) |
| `src/components/` | Shell (`Layouts.tsx`), Button, TextField, Dropdown, Segmented, Dialog, transcript (`Minutes.tsx`) |
| `src/store/AppStore.tsx` | Mock state + actions, persisted to localStorage |
| `src/mocks/` | **All example data** — people, meetings, transcript, word alternatives, diarization timeline, demo accounts |
| `src/i18n/` | `en.ts` (source, copy from Figma), `ro.json` / `ru.json` (**draft translations — need native review**) |
| `src/lib/` | Formatting, recorder (MediaRecorder + AnalyserNode), transcript tokens, PDF builder |

## Translations

Add English strings to `src/i18n/en.ts`, then run `python3 scripts/sync-i18n.py` — it adds the new keys to RO/RU as `"TODO"` (shown in English until translated). Plurals: add `_one` / `_few` / `_many` variants next to a key that uses `{count}`.

## Deploy

```bash
npx vercel deploy --prod
```

## Known limits (prototype)

- Mocked login; patient data sits unencrypted in localStorage — **never use real patient data**.
- Every processed meeting gets the example Cardiology board transcript and tasks.
- Mocked upload (the bar just fills) and mocked sending (no email leaves the browser).
- No tests or linter yet.
