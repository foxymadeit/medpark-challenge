import { meetingUrl } from "../utils";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Meeting } from "../types/meeting";
import DepartmentTile from "./DepartmentTile";
import StatusTag from "./StatusTag";
export default function MeetingList({ meetings }: { meetings: Meeting[] }) {
  const { t, i18n } = useTranslation();
  return (
    <div className="panel meeting-list">
      {meetings.length === 0 ? (
        <p className="empty-inline">{t("emptyMeetings")}</p>
      ) : (
        meetings.map((m) => (
          <Link key={m.id} className="meeting-list-row" to={meetingUrl(m)}>
            <DepartmentTile type={m.type} />
            <span
              className={`mobile-department-dot ${m.type}`}
              aria-hidden="true"
            />
            <div>
              <strong>{m.title}</strong>
              <small>
                {new Date(m.createdAt).toLocaleString(i18n.language, {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </small>
            </div>
            <StatusTag status={m.status} />
          </Link>
        ))
      )}
    </div>
  );
}
