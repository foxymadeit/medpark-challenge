import { useState } from "react";
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
import { LANGUAGE_NAMES, formatDay, personName } from "../utils";
import type { Meeting } from "../types/meeting";
import { listName } from "../api/routing";
import { useRouting } from "../hooks/useRouting";

const validEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

/** The subject the server's EmailService writes: "MoM | Medical | <title>". */
function emailSubject(meeting: Pick<Meeting, "type" | "title">) {
  const type = meeting.type[0].toUpperCase() + meeting.type.slice(1);
  return `MoM | ${type} | ${meeting.title.split(/\r?\n/).join(" ").trim()}`;
}

export default function EmailPreviewPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { data: meeting, error, refresh } = useMeeting();
  const [busy, setBusy] = useState(false);
  const routing = useRouting();
  const [actionError, setActionError] = useState("");

  if (!meeting) return <StatePanel error={error} retry={refresh} />;
  if (meeting.reviewState !== "reviewed")
    return <Navigate to={`/meetings/${meeting.id}/minutes`} replace />;

  // The minutes go to the board's list; a participant with an address also
  // gets a copy, one without simply gets none. Only a malformed address stops
  // the send, because the mail server would refuse it.
  const people = meeting.participants;
  const invalid = people.some((p) => p.email && !validEmail(p.email));
  const subject = emailSubject(meeting);
  const ownerName = (id?: string | null) => {
    const owner = people.find((p) => p.id === id);
    return owner ? personName(owner, t) : t("unassigned");
  };
  const body = [
    meeting.title,
    `${t("summary")}\n${meeting.summary || t("notGiven")}`,
    people.length &&
      `${t("participants")}\n${people.map((p) => `- ${personName(p, t)}`).join("\n")}`,
    meeting.decisions?.length &&
      `${t("decisions")}\n${meeting.decisions.map((d) => `- ${d.text}`).join("\n")}`,
    meeting.actionItems?.length &&
      `${t("actions")}\n${meeting.actionItems
        .map(
          (a) =>
            `- ${a.task} | ${t("owner")}: ${ownerName(a.ownerParticipantId)} | ${t("deadline")}: ${a.deadline ? formatDay(a.deadline, i18n.language) : t("noDeadline")}`,
        )
        .join("\n")}`,
  ]
    .filter(Boolean)
    .join("\n\n");

  async function handleSend() {
    if (busy || invalid) return;
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
          recipients: people
            .filter((p) => p.email)
            .map((p) => ({
              staffId: p.staffId ?? p.id,
              nameAtMeeting: p.name,
              emailAtMeeting: p.email!,
            })),
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
      navigate(`/meetings/${meeting!.id}/sent`);
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
          <h2>{t("emailPreview")}</h2>
        </div>
        <dl className="email-preview-meta">
          <div>
            <dt>{t("to")}</dt>
            <dd>
              <span className="recipient-line">
                {routing?.[meeting.type]
                  ? t("listRecipients", {
                      list: listName(meeting.type, t),
                      count: routing[meeting.type],
                    })
                  : listName(meeting.type, t)}
              </span>
              {people.map((person) => (
                <span className="recipient-line" key={person.id}>
                  {person.email
                    ? `${personName(person, t)} <${person.email}>`
                    : `${personName(person, t)}: ${t("noCopyNoEmail")}`}
                </span>
              ))}
            </dd>
          </div>
          <div>
            <dt>{t("subject")}</dt>
            <dd>{subject}</dd>
          </div>
          <div>
            <dt>{t("attachment")}</dt>
            <dd>
              {meeting.documents?.length
                ? meeting.documents
                    .map((lang) => `${LANGUAGE_NAMES[lang]} (PDF)`)
                    .join(", ")
                : minutesDocxFilename(meeting)}
            </dd>
          </div>
        </dl>
        {invalid && (
          <p className="error" role="alert">
            {t("invalidRecipient")}
          </p>
        )}
        <section className="email-body" aria-label={t("emailBody")}>
          {body}
        </section>
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
            disabled={busy || invalid}
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
