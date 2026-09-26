import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AuthContext, type AuthUser } from "./useAuth";
import { DEMO_MODE } from "../api/config";
import { request } from "../api/client";
import {
  DEMO_EMAIL,
  DEMO_PASSWORD,
  DEMO_SESSION_KEY,
  demoAccount,
  restoreDemoAccount,
  saveDemoSession,
} from "./demoSession";
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() =>
    DEMO_MODE ? restoreDemoAccount() : null,
  );
  const [loading, setLoading] = useState(!DEMO_MODE);
  const [error, setError] = useState("");
  useEffect(() => {
    if (DEMO_MODE) return;
    let active = true;
    void request<AuthUser>("/auth/me")
      .then((u) => {
        if (active) setUser(u);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const login = useCallback(async (email: string, password: string) => {
    if (DEMO_MODE) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      if (
        !DEMO_EMAIL ||
        !DEMO_PASSWORD ||
        DEMO_PASSWORD === "CHANGE_ME" ||
        email.trim().toLowerCase() !== DEMO_EMAIL ||
        password !== DEMO_PASSWORD
      )
        throw new Error("invalidCredentials");
      saveDemoSession();
      sessionStorage.removeItem("secure-mom-timeout");
      setUser(demoAccount());
      return;
    }
    setUser(
      await request<AuthUser>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      }),
    );
    sessionStorage.removeItem("secure-mom-timeout");
  }, []);
  const logout = useCallback(async () => {
    setError("");
    try {
      if (!DEMO_MODE) await request("/auth/logout", { method: "POST" });
    } catch {
      setError("requestFailed");
    } finally {
      sessionStorage.removeItem(DEMO_SESSION_KEY);
      sessionStorage.removeItem("secure-mom-demo-auth");
      setUser(null);
    }
  }, []);
  const value = useMemo(
    () => ({ user, loading, error, login, logout }),
    [user, loading, error, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
