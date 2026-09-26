import { useMemo, useState } from "react";
import { FiDownload, FiMail } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  createMinutesDocx,
  downloadMinutesDocx,
  minutesDocxFilename,
} from "../api/docx";
import { sendNow, updateMeeting } from "../api/meetings";
import Button from "../components/Button";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import { useMeeting } from "../hooks/useMeeting";

const validEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

export default function EmailPreviewPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { data: meeting, error, refresh } = useMeeting();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const recipients = useMemo(
    () =>
      meeting?.participantSnapshots?.map((person) => person.emailAtMeeting) ??
      [],
    [meeting],
  );
  const invalidRecipients = recipients.filter((email) => !validEmail(email));
  const [bodyOverride, setBodyOverride] = useState<string | null>(null);

  if (!meeting) return <StatePanel error={error} retry={refresh} />;
  if (meeting.reviewState !== "reviewed")
    return <Navigate to={`/meetings/${meeting.id}/minutes`} replace />;

  const date = new Date(meeting.createdAt).toLocaleDateString(i18n.language);
  const subject = `${t("minutes")} — ${meeting.title} — ${date}`;
  const participantNames = meeting.participantSnapshots
    ?.map((person) => person.nameAtMeeting)
    .join(", ");
  const decisions = meeting.decisions
    ?.map((decision, index) => `${index + 1}. ${decision.text}`)
    .join("\n");
  const actions = meeting.actionItems
    ?.map((item) => {
      const owner =
        meeting.participantSnapshots?.find(
          (person) => person.staffId === item.ownerStaffId,
        )?.nameAtMeeting ?? t("unassigned");
      return `• ${item.task} — ${owner} — ${item.deadline ?? t("noDeadline")}`;
    })
    .join("\n");
  const generatedBody = t("emailPreviewBody", {
    title: meeting.title,
    date,
    participants: participantNames || "—",
    summary: meeting.summary || "—",
    decisions: decisions || "—",
    actions: actions || "—",
  });
  const body = bodyOverride ?? generatedBody;

  async function handleSend() {
    if (busy || invalidRecipients.length || !recipients.length) return;
    setBusy(true);
    setActionError("");
    try {
      await createMinutesDocx(meeting!);
      const attachmentFilename = minutesDocxFilename(meeting!);
      await updateMeeting(meeting!.id, {
        delivery: {
          id: meeting!.delivery?.id ?? crypto.randomUUID(),
          meetingId: meeting!.id,
          subject,
          body,
          recipients: meeting!.participantSnapshots!.map(
            ({ staffId, nameAtMeeting, emailAtMeeting }) => ({
              staffId,
              nameAtMeeting,
              emailAtMeeting,
            }),
          ),
          attachmentFilename,
          status: "sending",
        },
        artifacts: [
          ...(meeting!.artifacts ?? []).filter(
            (artifact) => artifact.type !== "minutes_docx",
          ),
          {
            id: crypto.randomUUID(),
            meetingId: meeting!.id,
            type: "minutes_docx",
            filename: attachmentFilename,
            createdAt: new Date().toISOString(),
          },
        ],
      });
      await sendNow(meeting!.id);
      navigate(`/meetings/${meeting!.id}/minutes`);
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "requestFailed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <MeetingHeader meeting={meeting} stage="minutes" />
      <section className="panel email-preview-card">
        <div className="email-preview-heading">
          <div>
            <p className="eyebrow">{t("emailPreview")}</p>
            <h2>{subject}</h2>
          </div>
          <span className="email-preview-icon">
            <FiMail />
          </span>
        </div>
        <dl className="email-preview-meta">
          <div>
            <dt>{t("to")}</dt>
            <dd>
              {meeting.participantSnapshots?.length
                ? meeting.participantSnapshots.map((person) => (
                    <span className="recipient-line" key={person.staffId}>
                      {person.nameAtMeeting} &lt;
                      {person.emailAtMeeting || t("emailUnavailable")}&gt;
                    </span>
                  ))
                : t("emailUnavailable")}
            </dd>
          </div>
          <div>
            <dt>{t("subject")}</dt>
            <dd>{subject}</dd>
          </div>
          <div>
            <dt>{t("attachment")}</dt>
            <dd>{minutesDocxFilename(meeting)}</dd>
          </div>
        </dl>
        {(!recipients.length || invalidRecipients.length > 0) && (
          <p className="error" role="alert">
            {t("invalidRecipient")}
          </p>
        )}
        <label className="form-field email-body-field">
          <span>{t("emailBody")}</span>
          <textarea
            value={body}
            onChange={(event) => setBodyOverride(event.target.value)}
            rows={8}
          />
        </label>
        <div className="button-row email-preview-actions">
          <Link className="button quiet" to={`/meetings/${meeting.id}/minutes`}>
            {t("backMinutes")}
          </Link>
          <Button
            onClick={() =>
              void downloadMinutesDocx(meeting).catch(() =>
                setActionError("documentGenerationFailed"),
              )
            }
          >
            <FiDownload /> {t("downloadWord")}
          </Button>
          <Button
            variant="primary"
            disabled={
              busy || !recipients.length || invalidRecipients.length > 0
            }
            onClick={() => void handleSend()}
          >
            <FiMail /> {t(busy ? "sending" : "send")}
          </Button>
        </div>
        {actionError && (
          <p className="error" role="alert">
            {t(actionError, { defaultValue: t("requestFailed") })}
          </p>
        )}
      </section>
    </>
  );
}
