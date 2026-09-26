# Liminal — local API contract

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
- Meeting includes `sendMode: manual | auto`, `reviewState: not_ready | needs_review | reviewed`, title, timestamps, input mode, participants, distribution list, audio metadata, decisions, summary, action items, raw transcript, speaker timeline, progress, and scheduled/sent timestamps.
- `UserAccount`, `StaffProfile`, temporal `StaffRoleAssignment`, and immutable `MeetingParticipantSnapshot` are separate concepts. Historical meetings and exports render snapshots.
- `VoiceProfile` and `DetectedSpeakerCluster` are separate from staff identity. An unidentified cluster is never inferred from a staff member without enrollment.
- `MeetingTemplate` stores staff IDs and reusable setup data; each created meeting snapshots its setup and participants.
- Action item includes immutable ID, task, nullable participant owner, nullable deadline, completion flag and optional source timestamp. Unresolved fields stay null.
- Transcript segments include original spoken text, speaker ID or null, start/end seconds and optional language. Preserve code-switching and the original speech; normalize terminology only in structured minutes.

## Endpoints

| Method / path                                 | Input                                                       | Response                                                                               |
| --------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| POST `/api/auth/login`                        | `{email,password}`                                          | AuthUser `{id,email,name,role,initials?}` and HttpOnly session cookie                  |
| GET `/api/auth/me`                            | —                                                           | AuthUser or 401                                                                        |
| POST `/api/auth/logout`                       | —                                                           | 204; invalidate server session                                                         |
| GET `/api/meetings`                           | —                                                           | `Meeting[]` including current states; newest first                                     |
| POST `/api/meetings`                          | `{title,type,inputMode,participants}`                       | Created `Meeting` with server distribution routing                                     |
| GET `/api/meetings/{id}`                      | —                                                           | Complete `Meeting`, including current processing/minutes state                         |
| PATCH `/api/meetings/{id}`                    | Allowed changed fields                                      | Updated `Meeting`                                                                      |
| POST `/api/meetings/{id}/recording`           | Multipart `audio` blob                                      | 204 or persisted metadata                                                              |
| GET `/api/meetings/{id}/recording`            | —                                                           | Audio binary; authenticated streaming/range support recommended                        |
| POST `/api/meetings/{id}/upload`              | Multipart `audio` file                                      | 204 or persisted metadata                                                              |
| POST `/api/meetings/{id}/process`             | —                                                           | Updated `Meeting`; enqueue local processing                                            |
| GET `/api/meetings/{id}/processing`           | —                                                           | `Meeting` with progress, estimated finish, speaker events and status                   |
| GET `/api/meetings/{id}/minutes`              | —                                                           | `Meeting` with generated minutes                                                       |
| PATCH `/api/meetings/{id}/minutes`            | `{summary?,decisions?}`                                     | Updated `Meeting`; reset active review window                                          |
| PATCH `/api/meetings/{id}/actions/{actionId}` | `{task?,ownerParticipantId?,deadline?,completed?}`          | Updated `Meeting`                                                                      |
| PATCH `/api/meetings/{id}/participants`       | `{participants}`                                            | Updated `Meeting`; participant identities remain separate from AuthUser                |
| POST `/api/meetings/{id}/feedback`            | `{meetingId,field,before,after,sourceTimestamp?,createdAt}` | Persisted correction feedback; does not claim model training                           |
| POST `/api/meetings/{id}/review`              | —                                                           | Updated `Meeting` with `reviewState: reviewed` after validation                        |
| GET `/api/meetings/{id}/transcript`           | —                                                           | `TranscriptSegment[]`, original text only                                              |
| POST `/api/meetings/{id}/send`                | `Idempotency-Key: minutes-{id}`                             | Updated `Meeting`; once-only local delivery                                            |
| POST `/api/meetings/{id}/stop-send`           | —                                                           | Updated `Meeting`; atomically cancel unsent job                                        |
| GET `/api/action-items`                       | Optional future filters                                     | `{meetingId,actionItem}[]`; current UI derives these from meetings                     |
| GET `/api/people`                             | —                                                           | Staff `Participant[]`                                                                  |
| GET `/api/voice-profiles`                     | —                                                           | Enrolled `VoiceProfile[]`                                                              |
| GET `/api/speaker-clusters`                   | —                                                           | Detected speaker clusters                                                              |
| GET `/api/speaker-clusters/{id}/sample`       | —                                                           | Audio snippet or 404; UI never fabricates playback                                     |
| POST `/api/speaker-clusters/{id}/identify`    | `{staffId}`                                                 | Human-confirmed cluster identity                                                       |
| POST `/api/people/{id}/voice-enrollment`      | Multipart `audio`                                           | 204; store local enrollment metadata                                                   |
| GET `/api/templates`                          | —                                                           | Active templates                                                                       |
| GET `/api/templates/{id}`                     | —                                                           | Template                                                                               |
| POST/PATCH `/api/templates[/{id}]`            | Template setup metadata                                     | ADMIN-only create/update                                                               |
| POST `/api/templates/{id}/deactivate`         | —                                                           | ADMIN-only deactivation                                                                |
| GET `/api/admin`                              | —                                                           | ADMIN-only users, staff, roles and distribution lists                                  |
| POST `/api/admin/users`                       | Account fields                                              | ADMIN-only account creation                                                            |
| PATCH `/api/admin/users/{id}`                 | `{active}`                                                  | ADMIN-only account activation                                                          |
| POST/PATCH `/api/admin/people[/{id}]`         | Official staff fields                                       | ADMIN-only staff creation/update/deactivation                                          |
| POST `/api/admin/people/{id}/roles`           | `{title,department,validFrom}`                              | ADMIN-only temporal role assignment; closes current role                               |
| PATCH `/api/admin/lists/{id}`                 | Distribution-list fields                                    | ADMIN-only list management                                                             |
| GET `/api/system`                             | —                                                           | `{local:boolean,services:[{id,available}]}` for `asr,speakers,automation,mail,storage` |
| GET `/api/capabilities`                       | —                                                           | `{autoModeAvailable}`; the Liminal backend reports `true`                              |
| GET `/api/routing`                            | —                                                           | `{medical, executive, administrative}`: recipient addresses (or a count) per type. Optional: without it the app reads `/api/admin` for administrators, else shows no count |
| POST `/api/meetings/{id}/confirmations/{factId}` | `{action: "keep" \| "remove"}`                           | Updated `Meeting`; settles one item the checks could not confirm                       |
| GET `/api/meetings/{id}/documents/{lang}.{ext}` | `lang` ro/ru/en, `ext` pdf/docx                            | The Medpark-template minutes file for that language                                    |

The full meeting endpoint supports the current polling UI. Backend teams can implement focused processing/minutes endpoints without changing page data models. No model/runtime names need to appear in the user-facing payload.

## Delivery and state ownership

Processing completion in Manual mode creates minutes, sets `ready` plus `reviewState: needs_review`, and does not schedule delivery. The user reviews content and participants, marks review complete, then explicitly sends. Sending validates the latest stored minutes, participants and recipients in the same transaction as the status transition.

Auto mode is the default for new meetings whenever `/api/capabilities` reports it available (the Liminal backend does). When processing ends with nothing to confirm, the server holds the meeting as `sending_soon` for `sendWindowSeconds` (60 s) and sends at expiry; the frontend shows the countdown with Stop sending and Send now. Stop converts the meeting to Manual review and cancels the deadline atomically. When items need confirmation (`needsConfirmation`), the meeting waits as `ready`/`needs_review`; the person keeps or takes out each item, then Continue to sending marks the review and, in auto mode, sends.

Fields the Liminal backend adds to `Meeting`, mapped in `src/api/meetings.ts` (`fromServer`):

- `processingStages`: `{asr|diarize|minutes: {state: running|done|failed, startedAt, endedAt}}`, shown as the stage list on the Processing screen.
- `needsConfirmation`: `[{id, kind, text, problems[]}]`; an item disappears once settled.
- `documents`: `{ro|ru|en: {pdf, docx}}`, the languages offered in the Documents card.
- `sendWindowSeconds`: the length of the send countdown.

Writes carry `X-Requested-With: Liminal`; the server also checks Origin/Referer.

Missing task text, unknown/missing owners, missing required deadlines, missing participants or incomplete review block Manual sending. In the future Auto path, the same validation cancels automatic delivery into review. `sent` is terminal for delivery; completion checkboxes may still update, but sent content is not silently changed or resent. Duplicate send requests return the existing result.

Frontend recordings use the browser-supported MediaRecorder MIME (`audio/webm;codecs=opus`, WebM or MP4). Uploaded files support WAV, MP3, M4A and FLAC, at most 3 hours and 500 MB. The frontend distinguishes unsupported type, empty, oversized, too long and unreadable files. The backend must inspect actual content, decode it and enforce the limits independently. Periodic local recording checkpoints improve refresh recovery; a page close may still lose the last few seconds. Active recording continues if the local backend is temporarily unavailable; queued checkpoints retry only after connectivity returns. Real-mode chunk upload/append semantics should be defined before deploying long-recording recovery.

Processing may return `processingState: queued | running | failed | complete` and an optional opaque `failureReference`. Delivery may return `deliveryState: scheduled | stopped | sending | sent | failed` and an optional failure reference. A failed delivery leaves minutes available and must never report the meeting as sent. The backend owns queue order, retries, idempotency and failure references.

Authenticated sessions expire after 30 minutes without pointer, keyboard or touch activity in the frontend prototype. The backend must enforce its own idle and absolute session limits; frontend timers are only a usability layer.

## Backend security and processing requirements

- Parameterized SQL or ORM; Argon2id/bcrypt password hashing, generic login failures and login rate limiting.
- Session cookie `HttpOnly`, `Secure` in deployment, `SameSite=Strict`; enforce authentication and authorization on every endpoint. Apply CSRF protections for state-changing requests.
- Generate server-side random audio filenames; validate MIME/content, size and duration. Never trust client filenames, IDs, recipient lists or frontend route protection.
- Never return passwords, store frontend JWTs, execute uploaded data, or log audio/transcripts.
- Keep raw multilingual ASR separate from normalized structured minutes. Preserve overlap, acronyms, regional speech, unfinished statements and speaker uncertainty.
- Use measured diarization durations for percentages; deterministic unique speaker slots within each meeting. The frontend must not fabricate real-mode speaker identities or measurements.
- Local processing only: FastAPI → local pipeline → department routing by meeting type → local Mailpit/MailHog/SMTP. No Gmail, Outlook, SendGrid, external SMTP or external AI APIs during the demo.
- Recognize prototype enrollment separately from verified voice identity. Participants are staff, not patients.

## Verification

```sh
npm test
npm run lint
npm run build
```

Tests cover authenticated routing, demo credentials, language persistence, original transcript preservation, department setup, manual review, data editing/completion, metadata/audio persistence, processing across navigation, the demo store's 30-second Auto logic, explicit send/idempotency, unresolved-data blocking, file constraints and the mocked MediaRecorder lifecycle. A physical microphone and actual local mail/backend delivery still need integration testing on the deployment machine.

## Account and participant boundary

`GET /api/auth/me` returns the authenticated **account** (`AuthUser`), including `role: "admin" | "staff"`. `GET /api/people` returns active official staff available for selection. These models must never share a current-user variable. The demo admin is Administrator / AD; Elena Ciobanu is only a participant. The server must enforce every Admin and template write permission; hidden frontend controls are not authorization.

Demo delivery transitions `ready/sending_soon → sending → sent`, with a persisted 800 ms simulated delivery phase. Reopening reconciles elapsed timestamps; this does not send email. Backend scheduling, retries, delivery receipts and idempotency belong to the local server.
