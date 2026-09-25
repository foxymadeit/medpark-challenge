import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Layout from "./components/Layout";
import MeetingsPage from "./pages/MeetingsPage";
import NewMeetingPage from "./pages/NewMeetingPage";
import ProcessingPage from "./pages/ProcessingPage";
import MomPage from "./pages/MomPage";
import TranscriptPage from "./pages/TranscriptPage";
import HistoryPage from "./pages/HistoryPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/meetings" replace />} />

          <Route path="/meetings" element={<MeetingsPage />} />
          <Route path="/new-meeting" element={<NewMeetingPage />} />

          <Route
            path="/processing/:meetingId"
            element={<ProcessingPage />}
          />

          <Route
            path="/mom/:meetingId"
            element={<MomPage />}
          />

          <Route
            path="/transcript/:meetingId"
            element={<TranscriptPage />}
          />

          <Route path="/history" element={<HistoryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
