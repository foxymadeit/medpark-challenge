import { useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { ShieldCheck, SignOut } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/useAuth";
import LanguageSwitcher from "./LanguageSwitcher";
import Button from "./Button";
export default function TopBar({
  publicOnly = false,
}: {
  publicOnly?: boolean;
}) {
  const { t } = useTranslation();
  const { user, logout, error } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <header className="top-bar">
      <Link className="wordmark" to={publicOnly ? "/login" : "/meetings"}>
        Secure MOM
      </Link>
      {!publicOnly && (
        <nav className="desktop-nav">
          {[
            ["meetings", "/meetings"],
            ["actions", "/action-items"],
            ["history", "/history"],
            ["people", "/people"],
            ["system", "/system"],
          ]
            .filter(([label]) => label !== "system" || user?.role === "admin")
            .map(([label, path]) => (
              <NavLink key={path} to={path}>
                {t(label)}
              </NavLink>
            ))}
        </nav>
      )}
      <div className="top-right">
        <span className="network">
          <ShieldCheck size={18} weight="bold" />
          {t("network")}
        </span>
        <LanguageSwitcher />
        {!publicOnly && (
          <div className="account-wrap">
            <button
              className="account"
              aria-label={t("account")}
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              {user?.initials ??
                user?.name
                  .split(" ")
                  .map((x) => x[0])
                  .slice(0, 2)
                  .join("")}
            </button>
            {open && (
              <div className="account-menu">
                <p>{user?.name}</p>
                <small>{user?.email}</small>
                {error && (
                  <p className="error" role="alert">
                    {t(error)}
                  </p>
                )}
                {user?.role === "admin" && (
                  <Link to="/system" onClick={() => setOpen(false)}>
                    {t("system")}
                  </Link>
                )}
                <Button
                  onClick={() => {
                    void logout();
                  }}
                >
                  <SignOut size={20} />
                  {t("logout")}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
