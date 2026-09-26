import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./useAuth";
export default function AdminRoute() {
  const { user } = useAuth();
  return user?.role === "admin" ? (
    <Outlet />
  ) : (
    <Navigate to="/meetings" replace />
  );
}
