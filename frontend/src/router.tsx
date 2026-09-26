import {
  createBrowserRouter,
  Navigate,
  type RouteObject,
} from "react-router-dom";
import App from "./App";
import Layout from "./components/Layout";
import LegacyRoute from "./components/routing/LegacyRoute";
import ActionItemsPage from "./pages/ActionItemsPage";
import EnrollVoicePage from "./pages/EnrollVoicePage";
import HistoryPage from "./pages/HistoryPage";
import MeetingsPage from "./pages/MeetingsPage";
import MomPage from "./pages/MomPage";
import NewMeetingPage from "./pages/NewMeetingPage";
import NotFoundPage from "./pages/NotFoundPage";
import PeoplePage from "./pages/PeoplePage";
import ProcessingPage from "./pages/ProcessingPage";
import RecordingPage from "./pages/RecordingPage";
import SentPage from "./pages/SentPage";
import SystemPage from "./pages/SystemPage";
import TranscriptPage from "./pages/TranscriptPage";
import UploadPage from "./pages/UploadPage";
import TemplatesPage from "./pages/TemplatesPage";
import TemplateEditorPage from "./pages/TemplateEditorPage";
import EmailPreviewPage from "./pages/EmailPreviewPage";
import AdminPage from "./pages/AdminPage";

export const routes: RouteObject[] = [
  {
    path: "/",
    Component: App,
    children: [
      // There is nothing to sign in to; an old bookmark lands on the meetings.
      { path: "login", element: <Navigate to="/meetings" replace /> },
      {
        Component: Layout,
        children: [
          { index: true, element: <Navigate to="/meetings" replace /> },
          { path: "meetings", Component: MeetingsPage },
          { path: "meetings/new", Component: NewMeetingPage },
          { path: "meetings/new/:department", Component: NewMeetingPage },
          { path: "meetings/:id/record", Component: RecordingPage },
          { path: "meetings/:id/upload", Component: UploadPage },
          { path: "meetings/:id/processing", Component: ProcessingPage },
          { path: "meetings/:id/minutes", Component: MomPage },
          { path: "meetings/:id/email", Component: EmailPreviewPage },
          { path: "meetings/:id/transcript", Component: TranscriptPage },
          { path: "meetings/:id/sent", Component: SentPage },
          { path: "action-items", Component: ActionItemsPage },
          { path: "history", Component: HistoryPage },
          { path: "people", Component: PeoplePage },
          { path: "people/enroll", Component: EnrollVoicePage },
          { path: "people/:id/enroll", Component: EnrollVoicePage },
          { path: "templates", Component: TemplatesPage },
          { path: "templates/new", Component: TemplateEditorPage },
          { path: "templates/:id/edit", Component: TemplateEditorPage },
          { path: "system", Component: SystemPage },
          { path: "admin", element: <AdminPage /> },
          {
            path: "admin/people",
            element: <AdminPage section="people" />,
          },
          {
            path: "admin/roles",
            element: <AdminPage section="roles" />,
          },
          {
            path: "admin/lists",
            element: <AdminPage section="lists" />,
          },
          {
            path: "new-meeting",
            element: <Navigate to="/meetings/new" replace />,
          },
          {
            path: "mom/:meetingId",
            element: <LegacyRoute page="minutes" />,
          },
          {
            path: "processing/:meetingId",
            element: <LegacyRoute page="processing" />,
          },
          {
            path: "transcript/:meetingId",
            element: <LegacyRoute page="transcript" />,
          },
          { path: "*", Component: NotFoundPage },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
