import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <section className="state-page not-found-page">
      <div className="broken-route" aria-hidden="true">
        <i />
        <span />
        <i />
        <span />
        <i />
        <span className="route-gap" />
        <i />
        <span />
        <i />
      </div>
      <p className="mono state-code">404</p>
      <h1>{t("pageNotHere")}</h1>
      <p>{t("pageNotHereDetail")}</p>
      <Link className="button primary" to="/meetings">
        {t("backMeetings")}
      </Link>
    </section>
  );
}
