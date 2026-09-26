import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { FiCheck as Check } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { DEMO_MODE } from "../api/config";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import StatusTag from "../components/StatusTag";
import Button from "../components/Button";
import { downloadMinutesPdf } from "../api/pdf";
import {
  createRttm,
  createTranscriptText,
  downloadBlob,
  downloadText,
  safeName,
} from "../api/exports";
import { getRecording } from "../api/meetings";
import { listName } from "../api/routing";
export default function SentPage() {
  const { t, i18n } = useTranslation();
  const { data: m, error, refresh } = useMeeting();
  const [recording, setRecording] = useState<Blob>();
  useEffect(() => {
    if (m?.id)
      void getRecording(m.id)
        .then(setRecording)
        .catch(() => setRecording(undefined));
  }, [m?.id]);
  if (!m) return <StatePanel error={error} retry={refresh} />;
  if (m.status !== "sent")
    return <Navigate to={`/meetings/${m.id}/minutes`} replace />;
  return (
    <>
      <MeetingHeader meeting={m} stage="sent" />
      <section className="panel delivery-banner">
        <Check size={28} className="success success-check" />
        <div>
          <h2>{t("deliveryConfirmed")}</h2>
          <p>
            {listName(m.type, t)} ·{" "}
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
        <section className="panel minutes-card downloads-card">
          <h2>{t("downloads")}</h2>
          <Button onClick={() => downloadMinutesPdf(m)}>
            {t("minutesPdf")}
          </Button>
          <Button
            disabled={!m.transcript?.length}
            onClick={() =>
              downloadText(
                createTranscriptText(m),
                `${safeName(m.title)}-transcript.txt`,
              )
            }
          >
            {t("transcriptTxt")}
          </Button>
          <Button
            disabled={!recording}
            onClick={() =>
              recording &&
              downloadBlob(
                recording,
                `${safeName(m.title)}-recording.${recording.type.includes("mp4") ? "m4a" : "webm"}`,
              )
            }
          >
            {t("recordingDownload")}
          </Button>
          <Button
            disabled={!m.speakerTimeline?.length}
            onClick={() =>
              downloadText(
                createRttm(m),
                `${safeName(m.title)}-speakers.rttm`,
                "text/plain;charset=utf-8",
              )
            }
          >
            {t("speakersRttm")}
          </Button>
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
