import { useEffect, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  FiCheck as Check,
  FiMic as Microphone,
  FiUpload as UploadSimple,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { createMeeting, getPeople, getTemplate } from "../api/meetings";
import { departments, distribution } from "../api/config";
import type { AgendaTopic, MeetingType, Participant } from "../types/meeting";
import DepartmentDoor from "../components/DepartmentDoor";
import RouteProgress from "../components/RouteProgress";
import InputField from "../components/InputField";
import Button from "../components/Button";
export default function NewMeetingPage() {
  const { t, i18n } = useTranslation();
  const [search] = useSearchParams();
  const { department } = useParams();
  const templateId = search.get("template") ?? undefined;
  const [templateType, setTemplateType] = useState<MeetingType>();
  const chosen = department ?? search.get("type") ?? templateType;
  const type = departments.includes(chosen as MeetingType)
    ? (chosen as MeetingType)
    : null;
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState<"record" | "upload">(
    search.get("mode") === "upload" ? "upload" : "record",
  );
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [agendaTopics, setAgendaTopics] = useState<AgendaTopic[]>([]);
  const [templateLoading, setTemplateLoading] = useState(Boolean(templateId));
  useEffect(() => {
    if (!templateId) return;
    let active = true;
    void Promise.all([getTemplate(templateId), getPeople()])
      .then(([template, people]) => {
        if (!active) return;
        setTemplateType(template.meetingType);
        setTitle(template.defaultTitle ?? template.name);
        setAgendaTopics(structuredClone(template.agendaTopics));
        setParticipants(
          template.participantStaffIds
            .map((id) => people.find((person) => person.id === id))
            .filter((person) => person !== undefined),
        );
        setTemplateLoading(false);
      })
      .catch(() => {
        if (active) {
          setFailure("requestFailed");
          setTemplateLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [templateId]);
  if (templateLoading) return <p>{t("loading")}</p>;
  if (!type)
    return (
      <>
        <h1>{t("selectDepartment")}</h1>
        <div className="department-doors">
          {departments.map((d) => (
            <DepartmentDoor
              key={d}
              type={d}
              mode={search.get("mode") ?? undefined}
            />
          ))}
        </div>
      </>
    );
  return (
    <>
      <Link className="back-link" to="/meetings">
        {t("meetings")}
      </Link>
      <div className="meeting-heading">
        <div className="meeting-heading-title">
          <div>
            <h1>{t("meetingFor", { department: t(type) })}</h1>
            <p>{t("routing", distribution[type])}</p>
          </div>
        </div>
        <RouteProgress stage="record" upload={mode === "upload"} />
      </div>
      <div className="input-choices">
        {(["record", "upload"] as const).map((m) => (
          <button
            type="button"
            key={m}
            className={`panel input-choice ${mode === m ? "selected" : ""}`}
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
          >
            {m === "record" ? (
              <Microphone size={32} strokeWidth={2.5} />
            ) : (
              <UploadSimple size={32} strokeWidth={2.5} />
            )}
            {mode === m && (
              <span className="selection-check">
                <Check size={18} />
              </span>
            )}
            <h2>{t(m === "record" ? "recordRoom" : "uploadRecording")}</h2>
            <p>{t(m === "record" ? "micDescription" : "audioFormats")}</p>
          </button>
        ))}
      </div>
      <div className="setup-fields setup-fields-simple">
        <InputField
          label={t("optionalTitle")}
          maxLength={120}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t("titlePlaceholder")}
        />
        {templateId && (
          <section className="template-prefill">
            <strong>
              {t("participants")}:{" "}
              {participants.map((person) => person.name).join(", ") || "—"}
            </strong>
            <span>
              {t("agendaTopics")}:{" "}
              {agendaTopics.map((topic) => topic.text).join(" · ") || "—"}
            </span>
          </section>
        )}
      </div>
      <div className="page-footer">
        {failure && (
          <p className="error" role="alert">
            {t(failure, { defaultValue: t("requestFailed") })}
          </p>
        )}
        <Button
          variant="primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const m = await createMeeting({
                title:
                  title.trim() ||
                  `${t("meetingFor", { department: t(type) })} — ${new Date().toLocaleDateString(i18n.language, { day: "numeric", month: "short", year: "numeric" })}`,
                type,
                inputMode: mode,
                participants,
                templateId,
                agendaTopics,
              });
              navigate(
                `/meetings/${m.id}/${mode === "record" ? "record" : "upload"}`,
              );
            } catch (e) {
              setFailure(e instanceof Error ? e.message : "requestFailed");
            } finally {
              setBusy(false);
            }
          }}
        >
          {mode === "record" ? (
            <Microphone size={20} />
          ) : (
            <UploadSimple size={20} />
          )}{" "}
          {t(mode === "record" ? "startRecording" : "continue")}
        </Button>
      </div>
    </>
  );
}
