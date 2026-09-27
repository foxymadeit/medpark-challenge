import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  FiArrowLeft as ArrowLeft,
  FiEdit2 as PencilSimple,
} from "react-icons/fi";
import type { Meeting } from "../types/meeting";
import { renameMeeting } from "../api/meetings";
import { notifyUpdate } from "../hooks/useData";
import RouteProgress, { type Stage } from "./RouteProgress";
import Button from "./Button";
import { formatDayTime } from "../utils";
export default function MeetingHeader({
  meeting,
  stage,
}: {
  meeting: Meeting;
  stage: Stage;
}) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // the moderator may retitle finished minutes until they are sent
  const editable =
    stage === "minutes" && !["sent", "sending"].includes(meeting.status);
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await renameMeeting(meeting.id, value.trim());
      setEditing(false);
      notifyUpdate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "requestFailed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link to="/meetings" className="back-link">
        <ArrowLeft size={16} />
        {t("meetings")}
      </Link>
      <div className="meeting-heading">
        <div className="meeting-heading-title">
          {editing ? (
            <form
              className="title-edit expand-in"
              onSubmit={(e) => void save(e)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setEditing(false);
              }}
            >
              <label htmlFor={id}>{t("meetingTitleLabel")}</label>
              <input
                id={id}
                value={value}
                maxLength={120}
                autoFocus
                autoComplete="off"
                onChange={(e) => setValue(e.target.value)}
              />
              <div className="button-row">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={busy || !value.trim()}
                >
                  {t("save")}
                </Button>
                <Button variant="quiet" onClick={() => setEditing(false)}>
                  {t("cancel")}
                </Button>
              </div>
              {error && (
                <p className="error" role="alert">
                  {t(error, { defaultValue: t("requestFailed") })}
                </p>
              )}
            </form>
          ) : (
            <div>
              <h1>{meeting.title}</h1>
              <p>
                {t(meeting.type)} ·{" "}
                {formatDayTime(meeting.createdAt, i18n.language)}
              </p>
            </div>
          )}
          {editable && !editing && (
            <Button
              variant="quiet"
              aria-label={t("editTitle")}
              onClick={() => {
                setValue(meeting.title);
                setError("");
                setEditing(true);
              }}
            >
              <PencilSimple size={18} />
            </Button>
          )}
        </div>
        <RouteProgress stage={stage} upload={meeting.inputMode === "upload"} />
      </div>
    </>
  );
}
