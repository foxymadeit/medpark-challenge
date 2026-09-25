import { useTranslation } from "react-i18next";
export type Stage = "record" | "transcribe" | "speakers" | "minutes" | "sent";
const stages: Stage[] = ["record", "transcribe", "speakers", "minutes", "sent"];
export default function RouteProgress({
  stage,
  upload = false,
}: {
  stage: Stage;
  upload?: boolean;
}) {
  const { t } = useTranslation();
  const at = stages.indexOf(stage);
  return (
    <ol className="route-progress">
      {stages.map((s, i) => (
        <li
          key={s}
          className={i < at ? "complete" : i === at ? "current" : ""}
          aria-current={i === at ? "step" : undefined}
        >
          <span className="route-dot" />
          <span>{t(s === "record" && upload ? "upload" : s)}</span>
        </li>
      ))}
    </ol>
  );
}
