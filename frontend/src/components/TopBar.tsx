import { useEffect, useRef, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import {
  FiShield as ShieldCheck,
  FiSettings as Settings,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import LanguageSwitcher from "./LanguageSwitcher";
import LiminalLogo from "./LiminalLogo";
import { usePresence } from "../hooks/usePresence";
export default function TopBar() {
  const { t } = useTranslation();
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
      wrap.current
        ?.querySelector<HTMLButtonElement>(".admin-menu-button")
        ?.focus();
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
      <LiminalLogo />
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
      <div className="top-right">
        <span className="network">
          <ShieldCheck size={18} strokeWidth={2.5} />
          {t("network")}
        </span>
        <LanguageSwitcher />
        <div className="admin-menu-wrap" ref={wrap}>
          <button
            className="admin-menu-button"
            aria-label={t("administration")}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            <Settings size={18} />
          </button>
          {menu.present && (
            <div
              className="admin-menu"
              data-closing={menu.closing || undefined}
            >
              <Link to="/admin" onClick={() => setOpen(false)}>
                {t("administration")}
              </Link>
              <Link to="/system" onClick={() => setOpen(false)}>
                {t("system")}
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
