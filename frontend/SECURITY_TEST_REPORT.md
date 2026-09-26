# Secure MOM frontend security test

Date: 2026-09-26. Scope: the local `frontend/` application and its demo data. No external host, production service, real account, or real patient recording was tested.

## Result

No committed credential, DOM injection sink, external runtime request, or dependency vulnerability was found. React escapes rendered meeting and participant text. Login failures use one generic response and the password field is cleared after a failed attempt. The production build does not contain the local demo password. Unknown URLs, protected routes, stale sessions, inactivity expiry and the admin-only System route have automated coverage.

One security bug was fixed: local sign-out previously depended on a successful backend logout response. The client now clears its local authenticated state in `finally`, so an unavailable backend cannot leave an expired session visible in the interface.

Browser policy files now provide CSP, clickjacking, MIME-sniffing, referrer and unnecessary-device restrictions. The production web server must emit `public/_headers`; the file itself only configures hosts that support this convention.

## Checks performed

- Searched tracked frontend code for credentials, tokens, logging, `dangerouslySetInnerHTML`, dynamic code execution, external URLs and unsafe window messaging.
- Confirmed `.env.local`, build output, audio formats and test artifacts are ignored.
- Scanned the production bundle for the configured local password.
- Ran the package audit from the installed lockfile: zero known production dependency vulnerabilities.
- Exercised login rejection/success/logout, stale session rejection, inactivity reset/expiry, route guards, role guard, 404, language changes, upload validation, recorder lifecycle and the meeting delivery states.
- Checked keyboard submission of login and keyboard access to primary navigation in automated DOM tests.

## Security boundary

Demo mode is intentionally a development prototype. Its password is a browser-visible Vite value and its session marker can be modified by anyone with local browser developer access. Demo metadata, transcripts and participant details persist in localStorage; audio persists in IndexedDB. These mechanisms are not suitable for real personal or medical information.

Production must disable demo mode and keep personal data on the hospital backend. The server must enforce authorization on every record, idle and absolute session expiry, CSRF protection, login throttling, secure HttpOnly/SameSite cookies, upload content inspection, audit logging without transcript/audio content, and the response headers listed above. Frontend controls do not replace those protections.
