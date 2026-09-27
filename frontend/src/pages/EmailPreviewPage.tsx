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
import { LANGUAGE_NAMES, personName } from "../utils";
import type { Meeting } from "../types/meeting";
import { listName } from "../api/routing";
import { useRouting } from "../hooks/useRouting";

const validEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

// The email the server sends (backend/services/EmailService.py compose_email):
// official Romanian whatever the interface language; keep the two in step.
const BOARD_RO = {
  medical: "Consiliului Medical",
  executive: "Comitetului Executiv",
  administrative: "Consiliului Administrativ",
} as const;
const MONTHS_RO =
  "ianuarie februarie martie aprilie mai iunie iulie august septembrie octombrie noiembrie decembrie".split(
    " ",
  );
const LANGUAGE_RO = { ro: "română", ru: "rusă", en: "engleză" } as const;
const AI_NOTICE_RO =
  "Notă: procesul-verbal a fost întocmit automat de un sistem de inteligență artificială care funcționează " +
  "local, pe serverul instituției, iar fiecare punct a fost verificat în raport cu înregistrarea ședinței " +
  "(mențiune de transparență conform art. 50 din Regulamentul (UE) 2024/1689 privind inteligența artificială).";

type EmailMeeting = Pick<
  Meeting,
  "type" | "startedAt" | "createdAt" | "documents"
>;

function meetingRo(meeting: EmailMeeting) {
  const day = /^(\d{4})-(\d{2})-(\d{2})/.exec(
    meeting.startedAt || meeting.createdAt || "",
  );
  const date = day
    ? ` din ${Number(day[3])} ${MONTHS_RO[Number(day[2]) - 1]} ${day[1]}`
    : "";
  return `ședinței ${BOARD_RO[meeting.type]}${date}`;
}

function emailSubject(meeting: EmailMeeting) {
  return `Proces-verbal al ${meetingRo(meeting)}`;
}

function emailBody(meeting: EmailMeeting) {
  const board = BOARD_RO[meeting.type];
  const listed = (["ro", "ru", "en"] as const)
    .filter((lang) => meeting.documents?.includes(lang))
    .map(
      (lang, i) =>
        `${i + 1}. Procesul-verbal în limba ${LANGUAGE_RO[lang]} (format PDF)`,
    );
  return [
    `Stimați membri ai ${board},`,
    listed.length
      ? `Vă transmitem, în anexă, procesul-verbal al ${meetingRo(meeting)}. Vă rugăm să luați cunoștință de conținutul acestuia.`
      : `Procesul-verbal al ${meetingRo(meeting)} a fost întocmit.`,
    ...(listed.length ? [`Anexe:\n${listed.join("\n")}`] : []),
    AI_NOTICE_RO,
    `Cu stimă,\nSecretariatul ${board}`,
  ].join("\n\n");
}

export default function EmailPreviewPage() {
  const { t } = useTranslation();
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
  const body = emailBody(meeting);

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
        <section className="email-body" lang="ro" aria-label={t("emailBody")}>
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
