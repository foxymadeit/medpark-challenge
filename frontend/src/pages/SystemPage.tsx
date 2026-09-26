import { FiShield as ShieldCheck } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import {
  auditAction,
  getAudit,
  getCapabilities,
  getSystem,
} from "../api/meetings";
import { DEMO_MODE, departments } from "../api/config";
import { listName, routingLine } from "../api/routing";
import { useRouting } from "../hooks/useRouting";
import { useData } from "../hooks/useData";
import StatePanel from "../components/StatePanel";
import CorrectedWords from "../components/CorrectedWords";
import { formatClock } from "../utils";
export default function SystemPage() {
  const { t, i18n } = useTranslation();
  const { data, error, refresh } = useData(getSystem, 10000);
  const routing = useRouting();
  // the same answer the new-meeting page uses to offer automatic sending
  const { data: capabilities } = useData(getCapabilities, 0);
  const { data: audit } = useData(getAudit, 10000);
  if (!data) return <StatePanel error={error} retry={refresh} />;
  return (
    <>
      <h1>{t("system")}</h1>
      <section className="panel delivery-banner">
        <ShieldCheck size={40} strokeWidth={2.5} className="success" />
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
                ? formatClock(data.lastCheckedAt, i18n.language)
                : t("notGiven"),
              host: data.host ?? t("notGiven"),
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
              <small>
                {t(`serviceDesc_${s.id}`, {
                  defaultValue: s.description ?? t("descriptionUnavailable"),
                })}
              </small>
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
      <section className="panel auto-mode-card">
        <div>
          <h2>{t("autoMode")}</h2>
          <p>{t("autoModeDescription")}</p>
        </div>
        <span className="state-badge">
          {t(capabilities?.autoModeAvailable ? "available" : "unavailable")}
        </span>
      </section>
      <section className="panel minutes-card audit-trail">
        <h2>{t("auditTrail")}</h2>
        <p className="muted">{t("auditIntro")}</p>
        {audit?.length ? (
          <table>
            <thead>
              <tr>
                <th>{t("auditWhen")}</th>
                <th>{t("auditWho")}</th>
                <th>{t("auditWhat")}</th>
                <th>{t("auditResult")}</th>
              </tr>
            </thead>
            <tbody>
              {audit.slice(0, 12).map((row, i) => (
                <tr key={`${row.at}-${i}`}>
                  <td>{formatClock(row.at, i18n.language)}</td>
                  <td>{row.user ?? t("auditNobody")}</td>
                  <td>{t(auditAction(row))}</td>
                  <td>{t(row.status < 400 ? "auditDone" : "auditRefused")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>{t("auditEmpty")}</p>
        )}
      </section>
      <CorrectedWords />
      <section className="panel minutes-card">
        <h2>{t("distribution")}</h2>
        <div className="distribution-grid">
          {departments.map((d) => (
            <div key={d}>
              <strong>{listName(d, t)}</strong>
              <p>{routingLine(d, routing, t)}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
