import type { AuthUser } from "./useAuth";
export const DEMO_SESSION_KEY = "secure-mom-demo-auth-v3";
export const DEMO_EMAIL = (import.meta.env.VITE_DEMO_EMAIL ?? "")
  .trim()
  .toLowerCase();
export const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? "";
export function demoAccount(): AuthUser {
  return {
    id: "demo-admin",
    email: DEMO_EMAIL,
    name: "Administrator",
    initials: "AD",
    role: "admin",
  };
}
export function restoreDemoAccount(): AuthUser | null {
  sessionStorage.removeItem("secure-mom-demo-auth");
  const raw = sessionStorage.getItem(DEMO_SESSION_KEY);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw);
    if (
      session.version === 3 &&
      session.accountId === "demo-admin" &&
      session.email === DEMO_EMAIL &&
      DEMO_EMAIL &&
      DEMO_PASSWORD &&
      DEMO_PASSWORD !== "CHANGE_ME"
    )
      return demoAccount();
  } catch {
    /* Invalid/old sessions never supply account identity. */
  }
  sessionStorage.removeItem(DEMO_SESSION_KEY);
  return null;
}
export function saveDemoSession() {
  sessionStorage.setItem(
    DEMO_SESSION_KEY,
    JSON.stringify({ version: 3, accountId: "demo-admin", email: DEMO_EMAIL }),
  );
}
