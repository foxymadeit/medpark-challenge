import { useState } from "react";
import { Link } from "react-router-dom";
import {
  FiCalendar as CalendarBlank,
  FiMic as Microphone,
  FiUpload as UploadSimple,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { getMeetings } from "../api/meetings";
import { departments } from "../api/config";
import { useData } from "../hooks/useData";
import { useAuth } from "../auth/useAuth";
import DepartmentDoor from "../components/DepartmentDoor";
import { useRouting } from "../hooks/useRouting";
import MeetingList from "../components/MeetingList";
import ActionItemRow from "../components/ActionItemRow";
import StatePanel from "../components/StatePanel";
import Modal from "../components/Modal";
import Button from "../components/Button";
export default function MeetingsPage() {
  const { t } = useTranslation();
  const routing = useRouting();
  const { user } = useAuth();
  const { data, error, refresh } = useData(getMeetings);
  const [choose, setChoose] = useState<false | "record" | "upload">(false);
  if (!data) return <StatePanel error={error} retry={refresh} />;
  const actions = data.flatMap((m) =>
    (m.actionItems ?? [])
      .filter((a) => !a.completed && a.ownerStaffId === user?.staffProfileId)
      .map((item) => ({ meeting: m, item })),
  );
  return (
    <>
      <div className="desktop-dashboard">
        <div className="section-heading spread">
          <h1>{data.length ? t("startMeeting") : t("meetings")}</h1>
          <Link className="button secondary" to="/templates">
            {t("templates")}
          </Link>
        </div>
        <p className="dashboard-helper">{t("meetingStartHint")}</p>
        {data.length === 0 && (
          <p className="first-day-kicker">{t("startMeeting")}</p>
        )}
        <div className="department-doors">
          {departments.map((type) => (
            <DepartmentDoor key={type} type={type} routing={routing} />
          ))}
        </div>
        {data.length === 0 ? (
          <section className="first-day panel">
            <CalendarBlank size={28} />
            <h2>{t("emptyMeetings")}</h2>
            <p>{t("firstDayDescription")}</p>
            <Button onClick={() => setChoose("upload")}>
              <UploadSimple size={20} />
              {t("uploadRecording")}
            </Button>
          </section>
        ) : (
          <div className="dashboard-columns">
            <section>
              <div className="section-heading">
                <h2>{t("myActions")}</h2>
                <small>{t("openCount", { count: actions.length })}</small>
              </div>
              <div className="panel">
                {actions.length ? (
                  actions.map(({ meeting, item }) => (
                    <ActionItemRow
                      key={meeting.id + item.id}
                      meeting={meeting}
                      item={item}
                      compact
                    />
                  ))
                ) : (
                  <p className="empty-inline">{t("noActions")}</p>
                )}
              </div>
            </section>
            <section>
              <div className="section-heading spread">
                <h2>{t("recent")}</h2>
                <Link className="text-link" to="/history">
                  {t("allMeetings")}
                </Link>
              </div>
              <MeetingList meetings={data.slice(0, 4)} />
            </section>
          </div>
        )}
      </div>
      <div className="mobile-dashboard">
        <h1>{t("meetings")}</h1>
        <Button variant="primary" onClick={() => setChoose("record")}>
          <Microphone size={20} />
          {t("startMeeting")}
        </Button>
        {data.length > 0 && (
          <>
            <h2>{t("recent")}</h2>
            <MeetingList meetings={data.slice(0, 4)} />
          </>
        )}
        {data.length === 0 && (
          <div className="first-day">
            <h2>{t("emptyMeetings")}</h2>
            <p>{t("firstDayDescription")}</p>
          </div>
        )}
        <Button onClick={() => setChoose("upload")}>
          <UploadSimple size={20} />
          {t("uploadRecording")}
        </Button>
      </div>
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      {
        <Modal
          open={Boolean(choose)}
          title={t("selectDepartment")}
          onClose={() => setChoose(false)}
        >
          <div className="door-stack">
            {departments.map((type) => (
              <DepartmentDoor
                key={type}
                type={type}
                mode={choose || undefined}
                routing={routing}
              />
            ))}
          </div>
        </Modal>
      }
    </>
  );
}
