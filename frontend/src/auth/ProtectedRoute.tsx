import { Navigate, Outlet } from "react-router-dom";
import StatePanel from "../components/StatePanel";
import { useAuth } from "./useAuth";

function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) return <StatePanel />;

  if (!user) {
    const timeout = sessionStorage.getItem("secure-mom-timeout") === "1";
    return (
      <Navigate to={timeout ? "/login?reason=timeout" : "/login"} replace />
    );
  }

  return <Outlet />;
}

export default ProtectedRoute;
