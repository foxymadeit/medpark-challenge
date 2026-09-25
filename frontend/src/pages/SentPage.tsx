import { Link, Navigate } from "react-router-dom";
import { Check } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { DEMO_MODE } from "../api/config";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import StatusTag from "../components/StatusTag";
export default function SentPage() {
  const { t, i18n } = useTranslation();
  const { data: m, error, refresh } = useMeeting();
  if (!m) return <StatePanel error={error} retry={refresh} />;
  if (m.status !== "sent")
    return <Navigate to={`/meetings/${m.id}/minutes`} replace />;
  return (
    <>
      <MeetingHeader meeting={m} stage="sent" />
      <section className="panel delivery-banner">
        <Check size={28} className="success" />
        <div>
          <h2>{t("deliveryConfirmed")}</h2>
          <p>
            {m.distributionList.join(", ")} ·{" "}
            {m.sentAt && new Date(m.sentAt).toLocaleString(i18n.language)}
          </p>
          {DEMO_MODE && <p>{t("demoDelivery")}</p>}
        </div>
      </section>
      <div className="sent-grid">
        <section className="panel minutes-card">
          <h2>{t("deliveredTo")}</h2>
          {m.distributionList.map((list) => (
            <div key={list} className="delivery-row">
              <strong>{list}</strong>
              <StatusTag status="sent" />
            </div>
          ))}
        </section>
        <aside className="panel minutes-card button-stack">
          <Link className="button secondary" to={`/meetings/${m.id}/minutes`}>
            {t("viewMinutes")}
          </Link>
          <Link
            className="button secondary"
            to={`/meetings/${m.id}/transcript`}
          >
            {t("transcript")}
          </Link>
          <Link className="button quiet" to="/meetings">
            {t("backMeetings")}
          </Link>
        </aside>
      </div>
    </>
  );
}
