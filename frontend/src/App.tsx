import { Outlet } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import InactivityGuard from "./auth/InactivityGuard";
import ErrorBoundary from "./components/ErrorBoundary";
export default function App() {
  return (
    <AuthProvider>
      <InactivityGuard />
      <ErrorBoundary>
        <Outlet />
      </ErrorBoundary>
    </AuthProvider>
  );
}
