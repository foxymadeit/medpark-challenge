import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FiArrowLeft as ArrowLeft } from "react-icons/fi";
import type { Meeting } from "../types/meeting";
import RouteProgress, { type Stage } from "./RouteProgress";
import { formatDayTime } from "../utils";
export default function MeetingHeader({
  meeting,
  stage,
}: {
  meeting: Meeting;
  stage: Stage;
}) {
  const { t, i18n } = useTranslation();
  return (
    <>
      <Link to="/meetings" className="back-link">
        <ArrowLeft size={16} />
        {t("meetings")}
      </Link>
      <div className="meeting-heading">
        <div className="meeting-heading-title">
          <div>
            <h1>{meeting.title}</h1>
            <p>
              {t(meeting.type)} ·{" "}
              {formatDayTime(meeting.createdAt, i18n.language)}
            </p>
          </div>
        </div>
        <RouteProgress stage={stage} upload={meeting.inputMode === "upload"} />
      </div>
    </>
  );
}
