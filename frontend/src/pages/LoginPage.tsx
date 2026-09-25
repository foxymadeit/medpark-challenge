import { useState } from "react";
import { Navigate } from "react-router-dom";
import { ShieldCheck } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/useAuth";
import TopBar from "../components/TopBar";
import Button from "../components/Button";
import InputField from "../components/InputField";
export default function LoginPage() {
  const { t } = useTranslation();
  const { user, login } = useAuth();
  const [email, setEmail] = useState(import.meta.env.VITE_DEMO_EMAIL ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  if (user) return <Navigate to="/meetings" replace />;
  return (
    <>
      <TopBar publicOnly />
      <main className="login-layout">
        <h1>{t("loginMessage")}</h1>
        <form
          className="panel login-panel"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(false);
            try {
              await login(email.trim(), password);
            } catch {
              setError(true);
            } finally {
              setBusy(false);
            }
          }}
        >
          <h2>{t("signIn")}</h2>
          <InputField
            label={t("username")}
            autoComplete="username"
            value={email}
            maxLength={254}
            required
            onChange={(e) => setEmail(e.target.value)}
          />
          <InputField
            label={t("password")}
            type="password"
            autoComplete="current-password"
            value={password}
            maxLength={128}
            required
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && (
            <p className="error" role="alert">
              {t("invalidCredentials")}
            </p>
          )}
          <Button type="submit" variant="primary" disabled={busy}>
            {t(busy ? "signingIn" : "signIn")}
          </Button>
          <p className="login-note">
            <ShieldCheck size={18} weight="bold" />
            {t("network")}
          </p>
        </form>
      </main>
    </>
  );
}
