# Liminal

Hackathon prototype for Medpark hospital: record or upload a meeting → AI writes the minutes (MoM) → the organizer reviews → the MoM is emailed to participants.

Frontend only — **everything is mocked** (auth, speech-to-text, diarization, email). Built from the Figma file `bnCzuQd39C1F9AkGe7lwo7`, page "Liminal — minimal v3" (desktop 1440×800, responsive down to phone).

**Live demo:** https://liminal-delta-five.vercel.app — on Log in, pick a demo account (any password).

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
- No tests or linter yet — see the code-debt list in the project notes.
