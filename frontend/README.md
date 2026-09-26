# Liminal

Local-first hospital meeting prototype built with React, TypeScript and Vite. The Figma v2 interface includes desktop top navigation, mobile tabs, department selection, recording/upload, processing, editable minutes, transcript, action items, history, staff enrollment and system status.

```sh
npm install
cp .env.example .env.local

# Set VITE_DEMO_PASSWORD in .env.local before starting.
npm run dev
```

Replace `CHANGE_ME` with your local demo password; quote values containing `#`. Never commit `.env.local`. Vite environment values are visible to the browser and are for development only.

The demo account is **Administrator / AD**, separate from staff participants. Administration and System are admin-only. Admin owns official accounts, staff profiles, temporal role history and distribution lists.

Open the local URL printed by Vite. Demo credentials: `admin@medpark.local` / `<VITE_DEMO_PASSWORD from .env.local>`.

Automatic delivery is the default when the server offers it (the Liminal backend does): upload or record, pick the meeting type, and the minutes go out after a 60-second window that anyone can stop. Items the checks could not confirm always wait for a person first. Manual mode stays one checkbox away: process → review the transcript, minutes and tasks → correct content → confirm participants → mark the review complete → preview the generated email → Send. The demo store (`VITE_DEMO_MODE=true`) keeps Manual mode only.

End-to-end: `npm run build && npm run e2e` runs Playwright against a mock of the contract; with `E2E_BACKEND=<backend folder> E2E_PYTHON=<its venv python>` it runs against the real backend with its fake pipeline stages and a local SMTP catcher.

Demo mode uses localStorage for metadata and IndexedDB for audio. WAV, MP3, M4A and FLAC uploads are validated in the browser, while a real backend must validate decoded content again. Processing, queue/failure states, speaker activity and email delivery are simulated deterministically; sample transcripts are explicitly labeled. Interface language supports EN/RO/RU without translating spoken content. Sessions sign out after 30 minutes without pointer, keyboard or touch activity while preserving meeting data. All runtime assets are served locally.

Run `npm test`, `npm run lint`, and `npm run build`. Production builds disable demo authentication. Real backend integration, endpoint payloads, security and local delivery behavior are documented in [API_CONTRACT.md](API_CONTRACT.md). The implementation inventory and verification notes are in [IMPLEMENTATION.md](IMPLEMENTATION.md). The latest frontend security review, its scope and production requirements are in [SECURITY_TEST_REPORT.md](SECURITY_TEST_REPORT.md).
