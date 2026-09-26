import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, DownloadSimple, Warning } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { getRecording, startProcessing } from "../api/meetings";
import Button from "../components/Button";
import { DEMO_MODE } from "../api/config";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import { formatTime } from "../utils";
export default function ProcessingPage() {
  const { t, i18n } = useTranslation();
  const { data: m, error, refresh } = useMeeting();
  const navigate = useNavigate();
  useEffect(() => {
    if (m && ["sending_soon", "ready", "sending", "sent"].includes(m.status))
      navigate(
        `/meetings/${m.id}/${m.status === "sent" ? "sent" : "minutes"}`,
        { replace: true },
      );
  }, [m, navigate]);
  if (!m) return <StatePanel error={error} retry={refresh} />;
  if (m.processingState === "queued")
    return (
      <>
        <MeetingHeader meeting={m} stage="transcribe" />
        <section className="state-page panel">
          <span className="state-badge">{t("queued")}</span>
          <h1>{t("waitingInLine")}</h1>
          <p>{t("queueDetail")}</p>
          <Link className="button secondary" to="/meetings">
            {t("backMeetings")}
          </Link>
        </section>
      </>
    );
  if (m.status === "failed" || m.processingState === "failed")
    return (
      <>
        <MeetingHeader meeting={m} stage="transcribe" />
        <section className="state-page panel processing-failed-card">
          <span className="processing-failed-badge">
            <Warning size={22} />
          </span>
          <h2>{t("transcriptionStopped")}</h2>
          <p>{t("recordingSafe")}</p>
          <p className="mono">
            {t("reference")}:{" "}
            {m.failureReference ?? `PROC-${m.id.slice(-8).toUpperCase()}`}
          </p>
          <div className="button-row">
            <Button
              variant="primary"
              onClick={() =>
                void startProcessing(m.id).then(refresh).catch(refresh)
              }
            >
              {t("retry")}
            </Button>
            <Button
              onClick={async () => {
                const blob = await getRecording(m.id);
                if (!blob) return;
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = m.audioFilename ?? `${m.id}.webm`;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              <DownloadSimple size={20} />
              {t("downloadAudio")}
            </Button>
          </div>
        </section>
      </>
    );
  const at = Math.min(4, Math.floor((m.progress ?? 0) / 22));
  const steps = [
    "audioPrepared",
    "transcribed",
    "findingSpeakers",
    "writingMinutes",
    "preparingDelivery",
  ];
  return (
    <>
      <MeetingHeader
        meeting={m}
        stage={at < 2 ? "transcribe" : at === 2 ? "speakers" : "minutes"}
      />
      <div className="processing-grid">
        <section className="panel process-timeline">
          {steps.map((s, i) => (
            <div
              key={s}
              className={`process-step ${i < at ? "complete" : i === at ? "current" : ""}`}
            >
              <span className="process-marker">
                {i < at && <Check size={14} />}
              </span>
              <div>
                <strong>{t(s)}</strong>
                <p>
                  {i === 0
                    ? formatTime(m.durationSeconds ?? 0)
                    : i === 1 && DEMO_MODE
                      ? t("languagesDemo")
                      : i === 2
                        ? t("voices", { count: m.participants.length })
                        : i === 3
                          ? t("decisionsOwners")
                          : i === 4
                            ? m.distributionList.join(", ")
                            : ""}
                </p>
              </div>
            </div>
          ))}
        </section>
        <aside className="panel estimate">
          <p>{t("minutesAbout")}</p>
          <div className="mono">
            {new Date(
              m.processingEndsAt ?? new Date().getTime() + 60000,
            ).toLocaleTimeString(i18n.language, {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
          <Link to="/meetings" className="button secondary">
            {t("backMeetings")}
          </Link>
        </aside>
      </div>
      {error && <p className="error">{t(error)}</p>}
    </>
  );
}
