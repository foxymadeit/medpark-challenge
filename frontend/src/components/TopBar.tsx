import { useEffect, useRef, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { FiShield as ShieldCheck, FiLogOut as SignOut } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/useAuth";
import LanguageSwitcher from "./LanguageSwitcher";
import Button from "./Button";
import LiminalLogo from "./LiminalLogo";
import { usePresence } from "../hooks/usePresence";
export default function TopBar({
  publicOnly = false,
}: {
  publicOnly?: boolean;
}) {
  const { t } = useTranslation();
  const { user, logout, error } = useAuth();
  const [open, setOpen] = useState(false);
  const menu = usePresence(open, 120);
  const wrap = useRef<HTMLDivElement>(null);
  // Esc or a click elsewhere closes the menu, and Esc returns focus to the
  // button that opened it.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      wrap.current?.querySelector<HTMLButtonElement>(".account")?.focus();
    };
    const onPointer = (event: PointerEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);
  return (
    <header className="top-bar">
      <LiminalLogo publicOnly={publicOnly} />
      {!publicOnly && (
        <nav className="desktop-nav">
          {[
            ["meetings", "/meetings"],
            ["actions", "/action-items"],
            ["people", "/people"],
          ].map(([label, path]) => (
            <NavLink key={path} to={path}>
              {t(label)}
            </NavLink>
          ))}
        </nav>
      )}
      <div className="top-right">
        <span className="network">
          <ShieldCheck size={18} strokeWidth={2.5} />
          {t("network")}
        </span>
        <LanguageSwitcher />
        {!publicOnly && (
          <div className="account-wrap" ref={wrap}>
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
            {menu.present && (
              <div
                className="account-menu"
                data-closing={menu.closing || undefined}
              >
                <p>{user?.name}</p>
                <small>{user?.email}</small>
                {error && (
                  <p className="error" role="alert">
                    {t(error)}
                  </p>
                )}
                {user?.role === "admin" && (
                  <>
                    <Link to="/admin" onClick={() => setOpen(false)}>
                      {t("administration")}
                    </Link>
                    <Link to="/system" onClick={() => setOpen(false)}>
                      {t("system")}
                    </Link>
                  </>
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
