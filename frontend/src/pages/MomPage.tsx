import { Link, Navigate } from "react-router-dom";
import {
  FiDownload as DownloadSimple,
  FiMail as EnvelopeSimple,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import SendCountdown from "../components/SendCountdown";
import ManualReviewBar from "../components/ManualReviewBar";
import ReviewParticipants from "../components/ReviewParticipants";
import EditableMinutes from "../components/EditableMinutes";
import ActionItemRow from "../components/ActionItemRow";
import SpeakerLabel from "../components/SpeakerLabel";
import { formatTime } from "../utils";
import { sendNow } from "../api/meetings";
import { downloadMinutesPdf } from "../api/pdf";
export default function MomPage() {
  const { t } = useTranslation();
  const { data: m, error, refresh } = useMeeting();
  if (!m) return <StatePanel error={error} retry={refresh} />;
  if (m.status === "processing")
    return <Navigate to={`/meetings/${m.id}/processing`} replace />;
  const total = m.participants.reduce(
    (sum, p) => sum + (p.speakingSeconds ?? 0),
    0,
  );
  return (
    <>
      <MeetingHeader
        meeting={m}
        stage={m.status === "sent" ? "sent" : "minutes"}
      />
      {m.demoGenerated && <p className="sample-note">{t("sampleContent")}</p>}
      <div className="minutes-grid">
        <div className="minutes-main">
          {m.deliveryState === "failed" ? (
            <section className="panel delivery-failed">
              <span className="delivery-failed-badge">
                <EnvelopeSimple size={22} />
              </span>
              <div>
                <h2>{t("deliveryFailed")}</h2>
                <p>
                  {t("deliveryFailedDetail", {
                    list: m.distributionList.join(", "),
                  })}
                </p>
                <p>{t("deliveryRetryThirty")}</p>
              </div>
              <button
                className="button primary"
                type="button"
                onClick={() => void sendNow(m.id).then(refresh)}
              >
                {t("sendNow")}
              </button>
              <button
                className="button secondary"
                type="button"
                onClick={() => downloadMinutesPdf(m)}
              >
                <DownloadSimple size={20} />
                {t("downloadPdf")}
              </button>
            </section>
          ) : m.status === "sent" ? (
            <Link
              className="panel delivery-banner"
              to={`/meetings/${m.id}/sent`}
            >
              {t("deliveryConfirmed")}
            </Link>
          ) : m.sendMode === "auto" && m.status === "sending_soon" ? (
            <SendCountdown meeting={m} />
          ) : (
            <ManualReviewBar meeting={m} />
          )}
          <ReviewParticipants meeting={m} />
          <EditableMinutes meeting={m} field="summary" />
          <EditableMinutes meeting={m} field="decisions" />
          <section className="panel action-card">
            <h2>{t("actions")}</h2>
            {m.actionItems?.length ? (
              m.actionItems.map((item) => (
                <ActionItemRow key={item.id} meeting={m} item={item} />
              ))
            ) : (
              <p className="empty-inline">{t("noActions")}</p>
            )}
          </section>
        </div>
        <aside className="panel minutes-people">
          <h2>{t("people")}</h2>
          {m.participants.map((p, i) => (
            <div key={p.id} className="speaker-row">
              <SpeakerLabel person={p} slot={i} />
              <span className="mono">
                {total > 0 && p.speakingSeconds !== undefined
                  ? `${Math.round((p.speakingSeconds / total) * 100)}%`
                  : "—"}
              </span>
            </div>
          ))}
          <hr />
          <p className="muted">{t("recording")}</p>
          <p className="mono">{formatTime(m.durationSeconds ?? 0)}</p>
          <Link
            className="button secondary"
            to={`/meetings/${m.id}/transcript`}
          >
            {t("transcript")}
          </Link>
        </aside>
      </div>
      {error && <p className="error">{t(error)}</p>}
    </>
  );
}
