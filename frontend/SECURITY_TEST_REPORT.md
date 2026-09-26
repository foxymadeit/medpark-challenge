# Liminal frontend security test

Date: 2026-09-26. Scope: the local `frontend/` application and its demo data. No external host, production service or real patient recording was tested.

## Result

No committed credential, DOM injection sink, external runtime request, or dependency vulnerability was found. React escapes rendered meeting and participant text. Unknown URLs have automated coverage.

Liminal has no sign-in, by product decision: no accounts, passwords, sessions, cookies or roles. Opening the app goes straight to the Meetings page, `/` and `/login` both lead there, and every page, including Administration and System, is open to anyone who can reach the server. Automated tests check that the app opens with no sign-in and makes no network request in demo mode, and that the backend answers no route with 401 or 403 for a request from its own origin.

Browser policy files now provide CSP, clickjacking, MIME-sniffing, referrer and unnecessary-device restrictions. The production web server must emit `public/_headers`; the file itself only configures hosts that support this convention.

## Checks performed

- Searched tracked frontend code for credentials, tokens, logging, `dangerouslySetInnerHTML`, dynamic code execution, external URLs and unsafe window messaging.
- Confirmed `.env.local`, build output, audio formats and test artifacts are ignored.
- Ran the package audit from the installed lockfile: zero known production dependency vulnerabilities.
- Exercised opening without sign-in, the Administration and System menu, 404, language changes, upload validation, recorder lifecycle and the meeting delivery states.
- Checked keyboard access to primary navigation and the Administration menu (Esc closes it and returns focus) in automated tests.

## Security boundary

Demo mode is intentionally a development prototype. Demo metadata, transcripts and participant details persist in localStorage; audio persists in IndexedDB. These mechanisms are not suitable for real personal or medical information.

Production must disable demo mode and keep personal data on the hospital backend. With no sign-in, access is limited by where the server runs: every port bound to 127.0.0.1 on the server or to the hospital network only, and the services on an internal Docker network with no route out. Anyone who can reach that address can read and change every meeting, so the network boundary is the access control. The server must keep the Origin check on state-changing requests, upload content inspection, an append-only audit trail that records every change and every read of a recording, transcript or document with the time and network address (never transcript or audio content), and the response headers listed above.
