# Component holders

Components are grouped by the part of the interface that owns them:

- **Application shell:** `Layout`, `TopBar`, `MobileTabBar`, `RouteProgress`
- **Shared controls and feedback:** `Button`, `InputField`, `Modal`, `StatePanel`, `StatusTag`, `Waveform`, `LanguageSwitcher`, `ErrorBoundary`
- **Meeting workflow:** `DepartmentDoor`, `DepartmentTile`, `MeetingHeader`, `MeetingList`, `SendCountdown`, `EditableMinutes`
- **People and speakers:** `SpeakerLabel`
- **Action items:** `ActionItemRow`
- **Voice enrollment:** `enrollment/EnrollmentParts` (`LanguageChoice`, `PersonCard`, `PersonHeader`, `SpeechProgress`, `EnrollmentMessage`)
- **Routing adapters:** `routing/LegacyRoute`

Route-level state containers remain in `src/pages`; authentication boundaries remain in `src/auth`. Icons come from `react-icons/fi`.
