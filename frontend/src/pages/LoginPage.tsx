import { useState } from "react";
import { Navigate, useLocation, useSearchParams } from "react-router-dom";
import { FiClock as Clock } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/useAuth";
import TopBar from "../components/TopBar";
import Button from "../components/Button";
import InputField from "../components/InputField";
export default function LoginPage() {
  const { t } = useTranslation();
  const { user, login } = useAuth();
  const [params] = useSearchParams();
  // back to the page that asked for a sign-in; only paths inside this app
  const asked = (useLocation().state as { from?: string } | null)?.from;
  const back =
    asked?.startsWith("/") &&
    !asked.startsWith("//") &&
    !asked.startsWith("/login")
      ? asked
      : "/meetings";
  const timedOut =
    params.get("reason") === "timeout" ||
    sessionStorage.getItem("secure-mom-timeout") === "1";
  const [email, setEmail] = useState(import.meta.env.VITE_DEMO_EMAIL ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  if (user) return <Navigate to={back} replace />;
  const form = (
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
          setPassword("");
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2>{t("signIn")}</h2>
      {timedOut && (
        <div className="login-timeout" role="status">
          <Clock size={18} />
          {t("sessionTimedOut")}
        </div>
      )}
      <InputField
        label={t("signInEmail")}
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
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
    </form>
  );
  if (timedOut)
    return (
      <main className="timeout-login">
        <strong className="timeout-brand">Liminal</strong>
        {form}
      </main>
    );
  return (
    <>
      <TopBar publicOnly />
      <main className="login-layout">
        <h1>{t("loginMessage")}</h1>
        {form}
      </main>
    </>
  );
}
