import { createContext, useContext } from "react";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  role: "admin" | "staff";
  staffProfileId?: string;
  initials?: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  error: string;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

export function useAuth() {
  const value = useContext(AuthContext);

  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return value;
}
