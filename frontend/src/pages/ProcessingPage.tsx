import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { startProcessing } from "../api/meetings";
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
  if (["failed", "stopped"].includes(m.status))
    return (
      <StatePanel
        error="requestFailed"
        retry={() => {
          void startProcessing(m.id).then(refresh).catch(refresh);
        }}
      />
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
