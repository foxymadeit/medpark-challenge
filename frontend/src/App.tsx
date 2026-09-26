import AdminRoute from "./auth/AdminRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import MeetingsPage from "./pages/MeetingsPage";
import NewMeetingPage from "./pages/NewMeetingPage";
import RecordingPage from "./pages/RecordingPage";
import UploadPage from "./pages/UploadPage";
import ProcessingPage from "./pages/ProcessingPage";
import MomPage from "./pages/MomPage";
import TranscriptPage from "./pages/TranscriptPage";
import SentPage from "./pages/SentPage";
import ActionItemsPage from "./pages/ActionItemsPage";
import HistoryPage from "./pages/HistoryPage";
import PeoplePage from "./pages/PeoplePage";
import EnrollVoicePage from "./pages/EnrollVoicePage";
import SystemPage from "./pages/SystemPage";
import NotFoundPage from "./pages/NotFoundPage";
import InactivityGuard from "./auth/InactivityGuard";
import LegacyRoute from "./components/routing/LegacyRoute";
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <InactivityGuard />
        <ErrorBoundary>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route index element={<Navigate to="/meetings" replace />} />
                <Route path="meetings" element={<MeetingsPage />} />
                <Route path="meetings/new" element={<NewMeetingPage />} />
                <Route
                  path="meetings/new/:department"
                  element={<NewMeetingPage />}
                />
                <Route path="meetings/:id/record" element={<RecordingPage />} />
                <Route path="meetings/:id/upload" element={<UploadPage />} />
                <Route
                  path="meetings/:id/processing"
                  element={<ProcessingPage />}
                />
                <Route path="meetings/:id/minutes" element={<MomPage />} />
                <Route
                  path="meetings/:id/transcript"
                  element={<TranscriptPage />}
                />
                <Route path="meetings/:id/sent" element={<SentPage />} />
                <Route path="action-items" element={<ActionItemsPage />} />
                <Route path="history" element={<HistoryPage />} />
                <Route path="people" element={<PeoplePage />} />
                <Route path="people/enroll" element={<EnrollVoicePage />} />
                <Route path="people/:id/enroll" element={<EnrollVoicePage />} />
                <Route element={<AdminRoute />}>
                  <Route path="system" element={<SystemPage />} />
                </Route>
                <Route
                  path="new-meeting"
                  element={<Navigate to="/meetings/new" replace />}
                />
                <Route
                  path="mom/:meetingId"
                  element={<LegacyRoute page="minutes" />}
                />
                <Route
                  path="processing/:meetingId"
                  element={<LegacyRoute page="processing" />}
                />
                <Route
                  path="transcript/:meetingId"
                  element={<LegacyRoute page="transcript" />}
                />
              </Route>
            </Route>
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Route>
          </Routes>
        </ErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  );
}
