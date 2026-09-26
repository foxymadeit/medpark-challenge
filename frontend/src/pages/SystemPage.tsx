import { ShieldCheck } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { getSystem } from "../api/meetings";
import { DEMO_MODE, departments, distribution } from "../api/config";
import { useData } from "../hooks/useData";
import StatePanel from "../components/StatePanel";
export default function SystemPage() {
  const { t, i18n } = useTranslation();
  const { data, error, refresh } = useData(getSystem, 10000);
  if (!data) return <StatePanel error={error} retry={refresh} />;
  return (
    <>
      <h1>{t("system")}</h1>
      <section className="panel delivery-banner">
        <ShieldCheck size={40} weight="bold" className="success" />
        <div>
          <h2>
            {t(
              DEMO_MODE
                ? "demoSystemStatus"
                : data.local
                  ? "noOutside"
                  : "network",
            )}
          </h2>
          <p>
            {t("lastChecked", {
              time: data.lastCheckedAt
                ? new Date(data.lastCheckedAt).toLocaleTimeString(
                    i18n.language,
                    { hour: "2-digit", minute: "2-digit" },
                  )
                : "—",
              host: data.host ?? "—",
            })}
            {DEMO_MODE ? ` · ${t("demoStatusNotice")}` : ""}
          </p>
        </div>
      </section>
      <div className="panel system-services">
        {data.services.map((s) => (
          <div key={s.id} className="service-row">
            <div>
              <strong>{t(s.id)}</strong>
              <small>{s.description ?? t("descriptionUnavailable")}</small>
            </div>
            <span className={s.available ? "success" : "error"}>
              {t(
                DEMO_MODE
                  ? s.available
                    ? "simulatedRunning"
                    : "simulatedUnavailable"
                  : s.available
                    ? "available"
                    : "unavailable",
              )}
            </span>
          </div>
        ))}
      </div>
      <section className="panel minutes-card">
        <h2>{t("distribution")}</h2>
        <div className="distribution-grid">
          {departments.map((d) => (
            <div key={d}>
              <strong>{distribution[d].list}</strong>
              <p>{t("routing", distribution[d])}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
