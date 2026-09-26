import { useTranslation } from "react-i18next";
export type Stage = "record" | "transcribe" | "speakers" | "minutes" | "sent";
// DESIGN.md: the route has three stops. Transcribing and finding speakers
// happen inside Minutes; nobody has to learn those words to follow along.
const stops = ["record", "minutes", "sent"] as const;
const stopOf = (stage: Stage) =>
  stage === "transcribe" || stage === "speakers" ? "minutes" : stage;
export default function RouteProgress({
  stage,
  upload = false,
}: {
  stage: Stage;
  upload?: boolean;
}) {
  const { t } = useTranslation();
  const at = stops.indexOf(stopOf(stage));
  return (
    <ol className="route-progress">
      {stops.map((s, i) => (
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
