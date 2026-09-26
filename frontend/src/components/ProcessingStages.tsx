import { FiCheck as Check, FiAlertTriangle as Warning } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import type { ProcessingStage } from "../types/meeting";

/** The server's real pipeline stages (Figma M01): what is done, what runs
 * now with its live count, and when the rest should finish. */
export default function ProcessingStages({
  stages,
}: {
  stages: ProcessingStage[];
}) {
  const { t, i18n } = useTranslation();
  const clock = (iso?: string) =>
    iso
      ? new Date(iso).toLocaleTimeString(i18n.language, {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";
  const current = stages.find((s) => s.state === "running");
  return (
    <section className="panel process-timeline">
      <p className="visually-hidden" aria-live="polite">
        {current ? t(`stage_${current.id}`) : ""}
      </p>
      <ol className="process-list">
        {stages.map((s) => (
          <li
            key={s.id}
            className={`process-step ${s.state === "done" ? "complete" : s.state === "running" ? "current" : s.state === "failed" ? "failed" : ""}`}
            aria-current={s.state === "running" ? "step" : undefined}
          >
            <span className="process-marker">
              {s.state === "done" && <Check size={14} />}
              {s.state === "failed" && <Warning size={14} />}
            </span>
            <div className="process-text">
              <strong>{t(`stage_${s.id}`)}</strong>
              {s.total !== undefined && s.total > 0 && (
                <p>{t("stageCount", { done: s.done ?? 0, total: s.total })}</p>
              )}
            </div>
            <span className="process-time mono">
              {s.state === "done"
                ? clock(s.finishedAt)
                : s.state === "running"
                  ? t("stageNow")
                  : s.etaAt
                    ? t("stageAbout", { time: clock(s.etaAt) })
                    : ""}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
