import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  FiCheck as Check,
  FiDownload as DownloadSimple,
  FiAlertTriangle as Warning,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { getRecording, startProcessing } from "../api/meetings";
import Button from "../components/Button";
import { DEMO_MODE } from "../api/config";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import ProcessingStages from "../components/ProcessingStages";
import { displayStages, expectedFinish } from "../api/stages";
import { formatClock } from "../utils";
import { listName } from "../api/routing";
import { useNow } from "../hooks/useNow";
import { formatTime } from "../utils";
export default function ProcessingPage() {
  const { t, i18n } = useTranslation();
  const { data: m, error, refresh } = useMeeting();
  const now = useNow();
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
  const stages = displayStages(m, now);
  const finish = expectedFinish(m, now);
  const running = stages.find((s) => s.state === "running")?.id;
  // The bar follows the server's progress, and between its updates the
  // time spent against the expected finish, so it never stands still.
  const started = m.processingStartedAt
    ? Date.parse(m.processingStartedAt)
    : now;
  const byTime =
    finish > started ? (95 * (now - started)) / (finish - started) : 0;
  // Server progress when given; otherwise finished stages, counting a running
  // stage's own done/total so the bar keeps moving inside long steps.
  const overall = Math.min(
    100,
    Math.max(
      byTime,
      m.progress ??
        (stages.length
          ? (100 *
              stages.reduce(
                (sum, s) =>
                  sum +
                  (s.state === "done"
                    ? 1
                    : s.state === "running" && s.total
                      ? (s.done ?? 0) / s.total
                      : 0),
                0,
              )) /
            stages.length
          : 0),
    ),
  );
  const headerStage = stages.length
    ? running === "transcribe" || running === "speakers"
      ? running
      : "minutes"
    : at < 2
      ? "transcribe"
      : at === 2
        ? "speakers"
        : "minutes";
  return (
    <>
      <MeetingHeader meeting={m} stage={headerStage} />
      <div className="processing-grid">
        {stages.length ? (
          <ProcessingStages stages={stages} now={now} />
        ) : (
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
                              ? listName(m.type, t)
                              : ""}
                  </p>
                </div>
              </div>
            ))}
          </section>
        )}
        <aside className="panel estimate">
          <div
            className="processing-bar"
            role="progressbar"
            aria-label={t("processing")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(overall)}
          >
            <span style={{ transform: `scaleX(${overall / 100})` }} />
          </div>
          {/* a clock time only when it is at least a minute away */}
          {finish - now >= 60_000 ? (
            <>
              <p>{t("minutesAbout")}</p>
              <div className="mono">
                {formatClock(new Date(finish), i18n.language)}
              </div>
            </>
          ) : (
            <>
              <p>{t("minutesSoon")}</p>
              <div className="mono estimate-soon">{t("almostReady")}</div>
            </>
          )}
          <Link to="/meetings" className="button secondary">
            {t("backMeetings")}
          </Link>
        </aside>
      </div>
      {error && <p className="error">{t(error)}</p>}
    </>
  );
}
