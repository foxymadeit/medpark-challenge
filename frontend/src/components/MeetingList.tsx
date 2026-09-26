import { formatDayTime, meetingUrl } from "../utils";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Meeting } from "../types/meeting";
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
            <div>
              <strong>{m.title}</strong>
              <small>{formatDayTime(m.createdAt, i18n.language)}</small>
            </div>
            <StatusTag status={m.status} />
          </Link>
        ))
      )}
    </div>
  );
}
