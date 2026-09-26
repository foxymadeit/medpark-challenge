import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./useAuth";

export const INACTIVITY_MS = 30 * 60 * 1000;

export default function InactivityGuard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    if (!user) return;
    let timer: ReturnType<typeof setTimeout>;
    const expire = () => {
      sessionStorage.setItem("secure-mom-timeout", "1");
      void logout().finally(() =>
        navigate("/login?reason=timeout", { replace: true }),
      );
    };
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(expire, INACTIVITY_MS);
    };
    const events = ["pointerdown", "keydown", "touchstart"] as const;
    events.forEach((event) =>
      window.addEventListener(event, reset, { passive: true }),
    );
    reset();
    return () => {
      clearTimeout(timer);
      events.forEach((event) => window.removeEventListener(event, reset));
    };
  }, [user, logout, navigate]);
  return null;
}
