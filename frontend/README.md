# Secure MOM v2

Local-first hospital meeting prototype built with React, TypeScript and Vite. The Figma v2 interface includes desktop top navigation, mobile tabs, department selection, recording/upload, processing, editable minutes, transcript, action items, history, staff enrollment and system status.

```sh
npm install
cp .env.example .env.local

# Set VITE_DEMO_PASSWORD in .env.local before starting.
npm run dev
```

Replace `CHANGE_ME` with your local demo password; quote values containing `#`. Never commit `.env.local`. Vite environment values are visible to the browser and are for development only.

The demo account is **Administrator / AD**, separate from staff participants. System is admin-only.

Open the local URL printed by Vite. Demo credentials: `admin@medpark.local` / `<VITE_DEMO_PASSWORD from .env.local>`. Set `VITE_DEMO_SEND_COUNTDOWN_SECONDS=15` for a shorter demo and restart Vite. The default is five minutes.

Demo mode uses localStorage for metadata and IndexedDB for audio. Processing, speaker activity and email delivery are simulated; sample transcripts are explicitly labeled. Interface language supports EN/RO/RU without translating spoken content. All runtime assets are served locally.

Run `npm test`, `npm run lint`, and `npm run build`. Production builds disable demo authentication. Real backend integration, endpoint payloads, security and local delivery behavior are documented in [API_CONTRACT.md](API_CONTRACT.md). The implementation inventory and verification notes are in [IMPLEMENTATION.md](IMPLEMENTATION.md).
