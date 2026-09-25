import { Navigate, Outlet } from "react-router-dom";
import StatePanel from "../components/StatePanel";
import { useAuth } from "./useAuth";

function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) return <StatePanel />;

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
