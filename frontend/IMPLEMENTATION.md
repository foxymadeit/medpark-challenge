# Liminal implementation and validation

## Result

The existing frontend was continued in place on `frontend-secure-mom`. The final state pass adds a real 404, a 30-minute inactivity sign-out, FLAC and canonical upload errors, queued/failed processing, failed delivery, stopped sending, offline recording feedback and the first-day dashboard. No backend teammate files were changed.

The demo account is Administrator / AD. It is distinct from participants, including Elena Ciobanu. Versioned sessions discard legacy identities, and System requires the admin role. Credentials are environment-only; `.env.local` is ignored. The actual local password is absent from source files eligible for commit and from the production bundle. Production builds disable demo authentication.

Automatic delivery is the default whenever the server reports `autoModeAvailable: true`, which the Liminal backend does: processing ends in a 60-second send window that anyone can stop, and Stop moves the meeting into Manual review. Items the minutes checks could not confirm always wait for a person first (Needs confirmation), and continuing sends the minutes in automatic mode. Manual mode stays one checkbox away on the new-meeting screen: review, corrections stored as honest feedback, participants confirmed, explicit Send. The demo store (`VITE_DEMO_MODE=true`) still keeps Manual mode only. Content editing is locked during delivery. The intermediate send phase lasts 800 ms in the prototype.

## Verification

- `npm run build`: passed.
- `npm test`: see the current final validation report; the suite covers six test files.
- `npm run lint`: passed.
- `git diff --check`: passed.
- Auth: normalized login, rejection, logout, stale-session handling, Administrator identity, account/participant separation and non-admin System guard.
- EN/RO/RU: complete dictionary parity, major-route render checks, language persistence and unchanged original transcript content.
- Recorder: mocked MediaRecorder lifecycle, pause/resume/stop, Strict Mode, track cleanup, unsupported and denied states. Real hardware microphone capture was not reverified in this continuation.
- Upload: drag/drop, remove/replace, filename/metadata, extension/MIME, nonzero size, maximum size and 3-hour limit.
- Processing: timestamp persistence through reload and off-page reconciliation.
- Delivery: automatic by default against the Liminal backend (60-second window, Stop into review, Needs confirmation before sending), Manual review in the demo store, participant validation, explicit send, distinct failed state, intermediate sending state, idempotency and persistence. Playwright covers the real backend end to end (`npm run e2e`, see README).
- Final Figma states: X02 processing failed, X03 delivery failed, X04 upload problems, X05 service unavailable banner, X06 page not found, X07 signed out, X08 first day, X09 queued and X10 sending stopped.

## Visual verification

Desktop screenshots confirmed Meetings, History, People, System, New Meeting (Medical), Recording, Minutes and Transcript in this continuation; Action Items had already been visually checked in the preceding work. The account menu was inspected and showed Administrator, admin@medpark.local, System and Log out; AD was visible in the top bar. The mixed-language transcript remained unchanged.

The initial retry failed because Vite was no longer listening on port 5173. Brave retained the previous rendered page in memory, so its URL changed while the content stayed stale. Restarting Vite outside the sandbox restored normal navigation. A separate Chrome attempt had also failed with ScreenCaptureKit error -3811 (audio/video capture failure), but Brave now captures correctly.

The current product wordmark is Liminal. The implementation uses the official local SVG asset and a reusable `LiminalLogo`. Responsive behavior is covered by component tests and CSS review. Real microphone capture still requires hardware permission and must be verified on the deployment machine.

## Prototype and backend boundary

Processing/transcripts/minutes generation, speaker activity, enrollment recognition, system availability and mail delivery remain local simulations. Real audio capture/storage is implemented, but the prototype does not perform speech recognition or send email.

Backend work: authenticated account sessions and authorization, participant directory, authenticated audio storage/streaming, local ASR and speaker processing, structured minutes generation, durable processing jobs, server-owned send scheduling and idempotent local SMTP delivery. See [API_CONTRACT.md](API_CONTRACT.md) for endpoints and the explicit `/auth/me` account versus `/people` participant boundary.

## Changed files

Paths below are relative to `frontend/`; they include earlier uncommitted v2 work plus this continuation. Deleted obsolete files remain in the inventory.

- `.env.example`
- `.gitignore`
- `API_CONTRACT.md`
- `IMPLEMENTATION.md`
- `README.md`
- `index.html`
- `package-lock.json`
- `package.json`
- `public/assets/departments/administrative-L.svg`
- `public/assets/departments/administrative-M.svg`
- `public/assets/departments/executive-L.svg`
- `public/assets/departments/executive-M.svg`
- `public/assets/departments/medical-L.svg`
- `public/assets/departments/medical-M.svg`
- `public/icons.svg`
- `src/App.tsx`
- `src/api/audio.ts`
- `src/api/client.ts`
- `src/api/config.ts`
- `src/api/meetings.ts`
- `src/api/validation.ts`
- `src/assets/hero.png`
- `src/assets/react.svg`
- `src/assets/vite.svg`
- `src/auth/AdminRoute.tsx`
- `src/auth/AuthContext.tsx`
- `src/auth/ProtectedRoute.tsx`
- `src/auth/demoSession.ts`
- `src/auth/useAuth.ts`
- `src/components/ActionItem.tsx`
- `src/components/ActionItemRow.tsx`
- `src/components/Button.tsx`
- `src/components/DepartmentDoor.tsx`
- `src/components/DepartmentTile.tsx`
- `src/components/EditableMinutes.tsx`
- `src/components/ErrorBoundary.tsx`
- `src/components/InputField.tsx`
- `src/components/LanguageSwitcher.tsx`
- `src/components/Layout.tsx`
- `src/components/MeetingHeader.tsx`
- `src/components/MeetingList.tsx`
- `src/components/MeetingTable.tsx`
- `src/components/MobileTabBar.tsx`
- `src/components/Modal.tsx`
- `src/components/RouteProgress.tsx`
- `src/components/SendCountdown.tsx`
- `src/components/Sidebar.tsx`
- `src/components/SpeakerLabel.tsx`
- `src/components/StatePanel.tsx`
- `src/components/StatusTag.tsx`
- `src/components/TopBar.tsx`
- `src/components/Waveform.tsx`
- `src/hooks/useData.ts`
- `src/hooks/useMeeting.ts`
- `src/hooks/useRecorder.ts`
- `src/i18n/i18n.ts`
- `src/main.tsx`
- `src/mock/meetings.ts`
- `src/mock/seed.ts`
- `src/mock/store.ts`
- `src/pages/ActionItemsPage.tsx`
- `src/pages/EnrollVoicePage.tsx`
- `src/pages/HistoryPage.tsx`
- `src/pages/LoginPage.tsx`
- `src/pages/MeetingsPage.tsx`
- `src/pages/MomPage.tsx`
- `src/pages/NewMeetingPage.tsx`
- `src/pages/PeoplePage.tsx`
- `src/pages/ProcessingPage.tsx`
- `src/pages/RecordingPage.tsx`
- `src/pages/SentPage.tsx`
- `src/pages/SystemPage.tsx`
- `src/pages/TranscriptPage.tsx`
- `src/pages/UploadPage.tsx`
- `src/styles/global.css`
- `src/styles/tokens.css`
- `src/types/meeting.ts`
- `src/utils.ts`
- `tests/auth.test.tsx`
- `tests/recorder.test.tsx`
- `tests/setup.ts`
- `tests/ui.test.tsx`
- `tests/workflow.test.ts`
- `vite.config.ts`
- `vitest.config.ts`
