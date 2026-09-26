# Figma map: Liminal design v2

File: [Liminal design v2](https://www.figma.com/design/5gmJObntS61v2ehrmh01j9), key `5gmJObntS61v2ehrmh01j9`.
This is the parity checklist between the Figma screens and the frontend on
`frontend-secure-mom` (`frontend/src/router.tsx`). Every frame named here
should have a matching page or state in the app, and every route should have
a frame.

## Pages

| Order | Page | ID | What is on it |
|---|---|---|---|
| 1 | Cover | `131:2054` | File cover (frame `131:2055`) |
| 2 | Style guide | `1:50` | SG/01 to SG/10: colour, type, space, components, motion, accessibility, words, handoff, states |
| 3 | Components | `1:51` | Five category frames: Icons, Atoms, Wayfinding, Feedback, Minutes |
| 4 | Screens | `0:1` | Eight sections, one per flow (below) |
| 5 | README | `136:2` | README hero (`136:3`) and headline numbers (`136:64`), exported to `docs/readme/` at 2x |

Colour variables live in the collection **Liminal v2** (`VariableCollectionId:1:2`).
Text styles: `v2/sign/{display,h1,h2,h3,plate}`, `v2/body/{lg,md,sm}`,
`v2/ui/{button,strong}`, `v2/data/{md,sm}`.

## Screens, by section

Frame codes: S = main screens, M = minutes stage, E = voice enrollment,
X = states and errors, T = tablet, P = phone. There is no S14 (the code was
retired); S15 and S16 keep their codes so older notes stay valid.

### 1 · Start and record (`131:2040`)

| Frame | ID | Route | Page component |
|---|---|---|---|
| S01 Sign in | `6:2` | `/login` | `LoginPage` |
| S02 Meetings | `6:57` | `/meetings` | `MeetingsPage` |
| S03 Start a Medical meeting | `6:189` | `/meetings/new/:department` | `NewMeetingPage` |
| S04 Recording | `8:164` | `/meetings/:id/record` | `RecordingPage` |
| S05 Upload | `8:359` | `/meetings/:id/upload` | `UploadPage` |

### 2 · Processing (`131:2041`)

| Frame | ID | Route | Page component |
|---|---|---|---|
| S06 Processing | `8:426` | `/meetings/:id/processing` | `ProcessingPage` |

### 3 · Minutes (M01 to M03): writing, confirming, ready (`131:2042`)

| Frame | ID | Route | Page component |
|---|---|---|---|
| M01 Writing the minutes | `116:1592` | `/meetings/:id/processing` (minutes stage opened up) | `ProcessingPage` |
| M03 Needs confirmation | `116:1701` | `/meetings/:id/minutes` when the review has flagged items | `MomPage` |
| M02 Minutes ready | `116:1665` | `/meetings/:id/minutes`, with the Documents card | `MomPage` |

### 4 · Minutes and sending (`131:2043`)

| Frame | ID | Route | Page component |
|---|---|---|---|
| S07 Minutes | `12:284` | `/meetings/:id/minutes` | `MomPage` |
| S07 Minutes (RO) | `15:898` | same, interface in Romanian | `MomPage` |
| S08 Edit action item | `12:433` | `/meetings/:id/minutes` (edit dialog) | `MomPage`, `ActionItemRow` |
| S09 Transcript | `12:509` | `/meetings/:id/transcript` | `TranscriptPage` |
| S10 Sent | `13:573` | `/meetings/:id/sent` | `SentPage` |

### 5 · Workspace (`131:2044`)

| Frame | ID | Route | Page component |
|---|---|---|---|
| S11 Action items | `13:682` | `/action-items` | `ActionItemsPage` |
| S12 History | `13:806` | `/history` | `HistoryPage` |
| S13 People | `14:770` | `/people` | `PeoplePage` |
| S15 System | `14:965` | `/system` (admin only) | `SystemPage` |

### 6 · Voice enrollment, optional (`131:2045`)

| Frame | ID | Route | Page component |
|---|---|---|---|
| E01 Enroll: pick a person | `48:1076` | `/people/enroll` | `EnrollVoicePage` |
| E02 Enroll: ready to record | `48:1163` | `/people/:id/enroll` | `EnrollVoicePage` |
| E03 Enroll: reading | `48:1222` | `/people/:id/enroll` | `EnrollVoicePage` |
| E04 Enroll: checking | `48:1274` | `/people/:id/enroll` | `EnrollVoicePage` |
| E05 Enroll: saved | `48:1317` | `/people/:id/enroll` | `EnrollVoicePage` |
| E06 Enroll: microphone blocked | `49:1222` | `/people/:id/enroll` (error) | `EnrollVoicePage` |
| E07 Enroll: not enough speech | `49:1273` | `/people/:id/enroll` (error) | `EnrollVoicePage` |
| E08 Enroll: sounds like someone else | `49:1319` | `/people/:id/enroll` (error) | `EnrollVoicePage` |
| E09 Enroll: reading (phone) | `49:1369` | `/people/:id/enroll`, phone width | `EnrollVoicePage` |

### 7 · States and errors (`131:2046`)

| Frame | ID | Where it appears |
|---|---|---|
| S16 States | `14:1038` | Reference sheet of component states, not a route |
| X01 Loading | `51:1309` | Any list while data loads (skeleton) |
| X02 Processing failed | `51:1377` | `/meetings/:id/processing` |
| X03 Delivery failed | `51:1436` | `/meetings/:id/minutes` after a failed send |
| X04 Upload problems | `51:1484` | `/meetings/:id/upload` |
| X05 Service not answering | `51:1550` | Banner on any page (`/api/system` reports a service down) |
| X06 Page not found | `52:1481` | `*` (`NotFoundPage`) |
| X07 Signed out | `52:1515` | `/login` after the 30-minute inactivity sign-out |
| X08 Meetings, first day | `52:1535` | `/meetings` with no meetings yet |
| X09 Waiting in line | `52:1588` | `/meetings/:id/processing` while queued |
| X10 Sending stopped | `52:1639` | `/meetings/:id/minutes` after Stop sending |

### 8 · Tablet and phone (`131:2047`)

| Frame | ID | Route |
|---|---|---|
| T01 Recording (tablet) | `15:1044` | `/meetings/:id/record` |
| T02 Minutes (tablet) | `15:1175` | `/meetings/:id/minutes` |
| P01 Meetings (phone) | `16:1034` | `/meetings` |
| P02 Recording (phone) | `16:1081` | `/meetings/:id/record` |
| P03 Minutes (phone) | `16:1170` | `/meetings/:id/minutes` |
| P04 Action items (phone) | `16:1215` | `/action-items` |

### Prototype flows (Screens page)

| Flow | Starts at |
|---|---|
| 1 Main: record to sent minutes | S01 `6:2` |
| 2 First day: upload a recording | X08 `52:1535` |
| 3 Optional: enroll a voice | E01 `48:1076` |
| 4 Recovery: processing failed | X02 `51:1377` |
| 5 Loading into meetings | X01 `51:1309` |
| 6 Phone | P01 `16:1034` |
| 7 Tablet | T01 `15:1044` |
| 8 Minutes: writing, confirming, ready | M01 `116:1592` |

## Routes with no Figma frame yet

These exist in `router.tsx` but have no screen in the file. The frontend
builds them from the same components and tokens:

- `/meetings/:id/email` (`EmailPreviewPage`)
- `/templates`, `/templates/new`, `/templates/:id/edit` (`TemplatesPage`, `TemplateEditorPage`)
- `/admin`, `/admin/users`, `/admin/people`, `/admin/roles`, `/admin/lists` (`AdminPage`)
- Legacy redirects: `/new-meeting`, `/mom/:meetingId`, `/processing/:meetingId`, `/transcript/:meetingId`

## Components (page `1:51`)

Names follow `Category/Name`, so the assets panel groups them in folders.

| Component | ID | Type |
|---|---|---|
| Atoms/Button | `2:204` | set |
| Atoms/Department door | `2:300` | set |
| Atoms/Speaker label | `2:327` | set |
| Atoms/Status tag | `2:358` | set |
| Atoms/Language switch | `2:382` | set |
| Wayfinding/Route | `4:110` | set |
| Wayfinding/Input field | `4:129` | set |
| Wayfinding/Top bar | `4:256` | set (wordmark "Liminal") |
| Wayfinding/Send countdown | `4:298` | set |
| Wayfinding/Action item | `4:301` | component |
| Feedback/Loader | `46:1102` | set |
| Feedback/Skeleton | `46:1111` | set |
| Feedback/Check | `46:1123` | set |
| Feedback/Recording pulse | `46:1132` | set |
| Feedback/Toast | `46:1158` | set |
| Minutes/Needs confirmation | `126:1871` | component |
| Minutes/Documents | `126:1889` | component |
| Icons/* (33 Phosphor Bold icons) | `2:7` to `2:135` | components |
