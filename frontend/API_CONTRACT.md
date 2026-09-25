# Secure MOM v2 — local API contract

The existing React + TypeScript + Vite client uses `src/api/meetings.ts` for all meeting, participant, audio, and delivery operations. Pages do not access browser storage. `src/api/client.ts` provides relative `/api` requests with `credentials: include`, generic errors and a 20-second timeout. Real authentication uses `/api/auth/login`, `/api/auth/me`, and `/api/auth/logout`.

## Run and demo mode

```sh
cd frontend
npm install
npm run dev
```

Local, git-ignored `.env.local`:

```ini
VITE_DEMO_MODE=true
VITE_DEMO_EMAIL=admin@medpark.local
VITE_DEMO_PASSWORD=CHANGE_ME
# Optional: use 15 for a short hackathon demonstration; default is 300.
VITE_DEMO_SEND_COUNTDOWN_SECONDS=300
```

Restart Vite after changing the environment. Demo login is `admin@medpark.local` / `<VITE_DEMO_PASSWORD from .env.local>`. Replace CHANGE_ME locally; quote passwords containing #. These browser-visible variables are development configuration, never production authentication. Demo authentication is additionally gated on `import.meta.env.DEV`; production builds never accept these credentials. Passwords and authentication tokens are not stored in localStorage. The versioned `secure-mom-demo-auth-v3` session marker contains version, account ID and email only. Stale sessions are discarded; account name/role are never restored from participant data.

Demo metadata is stored under `secure-mom-v2` in localStorage. Audio blobs and prototype voice samples are stored in the `secure-mom-audio` IndexedDB database. No external services are required: fonts, icons and department SVGs are served locally. Processing lasts 12 seconds in demo mode and returns clearly labeled sample content, not speech recognition of the uploaded recording. Speaker activity is explicitly simulated. Enrollment does not perform biometric recognition. Delivery changes the local status to `sent`; no real email is sent.

Timestamp-based processing and delivery reconcile while the app is open and on the next read after reopening. No browser app can run a timer while the browser is closed. The backend must own scheduling in real mode.

## Connect the local backend

Set `VITE_DEMO_MODE=false` and configure the optional Vite development proxy:

```ini
API_PROXY_TARGET=http://127.0.0.1:8000
```

Restart Vite. In production, serve the frontend and `/api` under the same hospital origin (reverse proxy). The proxy target is server-only configuration, not a `VITE_` browser value. Do not use an external cloud endpoint.

All IDs are strings. Timestamps are ISO 8601 with an explicit offset or `Z`; task deadlines are `YYYY-MM-DD`. Status and department values are stable lowercase values, never translated. UI language does not change recorded titles, transcript segments or minutes content.

Types are defined in `src/types/meeting.ts`:

- Department: `medical | executive | administrative`.
- Status: `draft | recording | uploaded | processing | sending_soon | ready | sending | sent | stopped | failed`.
- Meeting includes title, timestamps, input mode, participants, distribution list, audio metadata, decisions, summary, action items, raw transcript, speaker timeline, progress, and scheduled/sent timestamps.
- Participant includes an immutable ID, display name, optional staff email/role/department, speaker ID/slot, enrollment state and measured speaking seconds.
- Action item includes immutable ID, task, nullable participant owner, nullable deadline, completion flag and optional source timestamp. Unresolved fields stay null.
- Transcript segments include original spoken text, speaker ID or null, start/end seconds and optional language. Preserve code-switching and the original speech; normalize terminology only in structured minutes.

## Endpoints

| Method / path                                 | Input                                              | Response                                                                               |
| --------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------- |
| POST `/api/auth/login`                        | `{email,password}`                                 | AuthUser `{id,email,name,role,initials?}` and HttpOnly session cookie                  |
| GET `/api/auth/me`                            | —                                                  | AuthUser or 401                                                                        |
| POST `/api/auth/logout`                       | —                                                  | 204; invalidate server session                                                         |
| GET `/api/meetings`                           | —                                                  | `Meeting[]` including current states; newest first                                     |
| POST `/api/meetings`                          | `{title,type,inputMode,participants}`              | Created `Meeting` with server distribution routing                                     |
| GET `/api/meetings/{id}`                      | —                                                  | Complete `Meeting`, including current processing/minutes state                         |
| PATCH `/api/meetings/{id}`                    | Allowed changed fields                             | Updated `Meeting`                                                                      |
| POST `/api/meetings/{id}/recording`           | Multipart `audio` blob                             | 204 or persisted metadata                                                              |
| GET `/api/meetings/{id}/recording`            | —                                                  | Audio binary; authenticated streaming/range support recommended                        |
| POST `/api/meetings/{id}/upload`              | Multipart `audio` file                             | 204 or persisted metadata                                                              |
| POST `/api/meetings/{id}/process`             | —                                                  | Updated `Meeting`; enqueue local processing                                            |
| GET `/api/meetings/{id}/processing`           | —                                                  | `Meeting` with progress, estimated finish, speaker events and status                   |
| GET `/api/meetings/{id}/minutes`              | —                                                  | `Meeting` with generated minutes                                                       |
| PATCH `/api/meetings/{id}/minutes`            | `{summary?,decisions?}`                            | Updated `Meeting`; reset active review window                                          |
| PATCH `/api/meetings/{id}/actions/{actionId}` | `{task?,ownerParticipantId?,deadline?,completed?}` | Updated `Meeting`                                                                      |
| GET `/api/meetings/{id}/transcript`           | —                                                  | `TranscriptSegment[]`, original text only                                              |
| POST `/api/meetings/{id}/send`                | `Idempotency-Key: minutes-{id}`                    | Updated `Meeting`; once-only local delivery                                            |
| POST `/api/meetings/{id}/stop-send`           | —                                                  | Updated `Meeting`; atomically cancel unsent job                                        |
| GET `/api/action-items`                       | Optional future filters                            | `{meetingId,actionItem}[]`; current UI derives these from meetings                     |
| GET `/api/people`                             | —                                                  | Staff `Participant[]`                                                                  |
| POST `/api/people`                            | `{name,email?}`                                    | Created staff participant                                                              |
| POST `/api/people/{id}/voice-enrollment`      | Multipart `audio`                                  | 204; store local enrollment metadata                                                   |
| GET `/api/system`                             | —                                                  | `{local:boolean,services:[{id,available}]}` for `asr,speakers,automation,mail,storage` |

The full meeting endpoint supports the current polling UI. Backend teams can implement focused processing/minutes endpoints without changing page data models. No model/runtime names need to appear in the user-facing payload.

## Delivery and state ownership

Processing completion creates minutes, sets `sending_soon` and an absolute `sendScheduledAt`. The default review window is 300 seconds. The frontend displays the server deadline, can stop it or send immediately, and requests an idempotent send at expiry when the minutes page is open. The server scheduler must also trigger delivery if the frontend is closed. Sending must validate the latest stored minutes in the same transaction as the status transition.

Missing task text, unknown/missing owners, missing required deadlines or unresolved `reviewFlags` pause automatic sending. Stop sets `ready` and clears the deadline. Edits reset an active countdown; editing a stopped window does not silently restart sending. `sent` is terminal for delivery; completion checkboxes may still update, but sent content is not silently changed or resent. Duplicate send requests return the existing result.

Frontend recordings use the browser-supported MediaRecorder MIME (`audio/webm;codecs=opus`, WebM or MP4). Uploaded files support WAV, MP3, M4A, at most 3 hours and 500 MB. The frontend checks extension, MIME, nonzero size and decodable duration. The backend must inspect actual content, decode it and enforce the limits independently. Periodic local recording checkpoints improve refresh recovery; a page close may still lose the last few seconds. Real-mode chunk upload/append semantics should be defined before deploying long-recording recovery.

## Backend security and processing requirements

- Parameterized SQL or ORM; Argon2id/bcrypt password hashing, generic login failures and login rate limiting.
- Session cookie `HttpOnly`, `Secure` in deployment, `SameSite=Strict`; enforce authentication and authorization on every endpoint. Apply CSRF protections for state-changing requests.
- Generate server-side random audio filenames; validate MIME/content, size and duration. Never trust client filenames, IDs, recipient lists or frontend route protection.
- Never return passwords, store frontend JWTs, execute uploaded data, or log audio/transcripts.
- Keep raw multilingual ASR separate from normalized structured minutes. Preserve overlap, acronyms, regional speech, unfinished statements and speaker uncertainty.
- Use measured diarization durations for percentages; deterministic unique speaker slots within each meeting. The frontend must not fabricate real-mode speaker identities or measurements.
- Local processing only: FastAPI → local pipeline → local n8n → department routing → local Mailpit/MailHog/SMTP. No Gmail, Outlook, SendGrid, external SMTP or external AI APIs during the demo.
- Recognize prototype enrollment separately from verified voice identity. Participants are staff, not patients.

## Verification

```sh
npm test
npm run lint
npm run build
```

Tests cover authenticated routing, demo credentials, language persistence, original transcript preservation, department setup, data editing/completion, metadata/audio persistence, processing across navigation, configured countdown, stop/send/idempotency, unresolved-data blocking, file constraints and the mocked MediaRecorder lifecycle. A physical microphone and actual local mail/backend delivery still need integration testing on the deployment machine.

## Account and participant boundary

`GET /api/auth/me` returns the authenticated **account** (`AuthUser`), including `role: "admin" | "user"`. `GET /api/people` returns **staff/participants** (`Participant[]`). These are distinct models and must never share a current-user variable. The demo admin is Administrator / AD; Elena Ciobanu is only a participant. Adding or enrolling a participant cannot change the authenticated account. The frontend hides and guards System for non-admins; the server must also authorize its endpoint.

Demo delivery transitions `ready/sending_soon → sending → sent`, with a persisted 800 ms simulated delivery phase. Reopening reconciles elapsed timestamps; this does not send email. Backend scheduling, retries, delivery receipts and idempotency belong to the local server.
