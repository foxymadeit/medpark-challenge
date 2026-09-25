import { Warning, WifiSlash } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Button from "./Button";
export default function StatePanel({
  error,
  empty,
  retry,
}: {
  error?: string;
  empty?: string;
  retry?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <section className="panel state-panel" role={error ? "alert" : "status"}>
      {error &&
        (error === "offline" ? <WifiSlash size={32} /> : <Warning size={32} />)}
      <h2>{t(error ? "errorTitle" : (empty ?? "loading"))}</h2>
      {error && (
        <p>
          {t(error === "storage" ? "storageError" : error, {
            defaultValue: t("requestFailed"),
          })}
        </p>
      )}
      {error && (
        <div className="button-row">
          {retry && <Button onClick={retry}>{t("retry")}</Button>}
          <Link
            className="button secondary"
            to={error === "unauthorized" ? "/login" : "/meetings"}
          >
            {t(error === "unauthorized" ? "signIn" : "backMeetings")}
          </Link>
        </div>
      )}
    </section>
  );
}
