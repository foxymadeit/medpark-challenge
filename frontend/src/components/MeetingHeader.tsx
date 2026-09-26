import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FiArrowLeft as ArrowLeft } from "react-icons/fi";
import type { Meeting } from "../types/meeting";
import DepartmentTile from "./DepartmentTile";
import RouteProgress, { type Stage } from "./RouteProgress";
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
          <DepartmentTile type={meeting.type} />
          <div>
            <h1>{meeting.title}</h1>
            <p>
              {t(meeting.type)} ·{" "}
              {new Date(meeting.createdAt).toLocaleString(i18n.language, {
                day: "numeric",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
        </div>
        <RouteProgress stage={stage} upload={meeting.inputMode === "upload"} />
      </div>
    </>
  );
}
