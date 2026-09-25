import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
export default function MobileTabBar() {
  const { t } = useTranslation();
  return (
    <nav className="mobile-tabs">
      {[
        ["meetings", "/meetings"],
        ["actions", "/action-items"],
        ["history", "/history"],
        ["people", "/people"],
      ].map(([label, to]) => (
        <NavLink key={to} to={to}>
          {t(label)}
        </NavLink>
      ))}
    </nav>
  );
}
