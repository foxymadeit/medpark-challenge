import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AccessLayout, AppLayout, OnboardingLayout, RequireAuth } from './components/Layouts';
import { LogIn, SignUp, Welcome } from './screens/Access';
import { History, HistoryRecord } from './screens/History';
import { NewMeeting } from './screens/NewMeeting';
import { Onboarding } from './screens/Onboarding';
import { Participants } from './screens/Participants';
import { Processing } from './screens/Processing';
import { Recording } from './screens/Recording';
import { Review } from './screens/Review';
import { Sent } from './screens/Sent';
import { Settings } from './screens/Settings';
import { Templates } from './screens/Templates';
import { Upload } from './screens/Upload';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AccessLayout />}>
          <Route path="/" element={<Welcome />} />
          <Route path="/signup" element={<SignUp />} />
          <Route path="/login" element={<LogIn />} />
        </Route>
        <Route
          element={
            <RequireAuth onboarding>
              <OnboardingLayout />
            </RequireAuth>
          }
        >
          <Route path="/onboarding/:step" element={<Onboarding />} />
        </Route>
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/participants" element={<Participants />} />
          <Route path="/new" element={<NewMeeting />} />
          <Route path="/recording" element={<Recording />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/processing/:id" element={<Processing />} />
          <Route path="/review/:id" element={<Review />} />
          <Route path="/sent/:id" element={<Sent />} />
          <Route path="/history" element={<History />} />
          <Route path="/history/:id" element={<HistoryRecord />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
