import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPeople, getTemplate, saveTemplate } from "../api/meetings";
import { useData } from "../hooks/useData";
import { useAuth } from "../auth/useAuth";
import { departments } from "../api/config";
import type { MeetingType } from "../types/meeting";
import StatePanel from "../components/StatePanel";
import Button from "../components/Button";
import InputField from "../components/InputField";

export default function TemplateEditorPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const people = useData(getPeople);
  const loadTemplate = useCallback(
    () => (id ? getTemplate(id) : Promise.resolve(undefined)),
    [id],
  );
  const template = useData(loadTemplate, 0);
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [type, setType] = useState<MeetingType>("medical");
  const [participants, setParticipants] = useState<string[]>([]);
  const [topics, setTopics] = useState("");
  const [recurrence, setRecurrence] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (template.data) {
      // Populate the editable draft when the persisted template arrives.
      // oxlint-disable-next-line react/set-state-in-effect
      setName(template.data.name);
      setTitle(template.data.defaultTitle ?? "");
      setType(template.data.meetingType);
      setParticipants(template.data.participantStaffIds);
      setTopics(
        template.data.agendaTopics
          .sort((a, b) => a.order - b.order)
          .map((topic) => topic.text)
          .join("\n"),
      );
      setRecurrence(template.data.recurrence?.label ?? "");
    }
  }, [template.data]);
  if (user?.role !== "admin") return <Navigate to="/templates" replace />;
  if (!people.data || (id && !template.data))
    return (
      <StatePanel
        error={people.error || template.error}
        retry={() => {
          people.refresh();
          template.refresh();
        }}
      />
    );
  return (
    <>
      <h1>{t(id ? "editTemplate" : "newTemplate")}</h1>
      <section className="panel template-editor">
        <InputField
          label={t("templateName")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <label className="form-field">
          {t("meetingType")}
          <select
            value={type}
            onChange={(e) => setType(e.target.value as MeetingType)}
          >
            {departments.map((department) => (
              <option key={department} value={department}>
                {t(department)}
              </option>
            ))}
          </select>
        </label>
        <InputField
          label={t("defaultMeetingTitle")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <fieldset>
          <legend>{t("participants")}</legend>
          {people.data
            .filter((person) => person.active !== false)
            .map((person) => (
              <label key={person.id} className="check-row">
                <input
                  type="checkbox"
                  checked={participants.includes(person.id)}
                  onChange={() =>
                    setParticipants((current) =>
                      current.includes(person.id)
                        ? current.filter((item) => item !== person.id)
                        : [...current, person.id],
                    )
                  }
                />
                {person.name}
              </label>
            ))}
        </fieldset>
        <label className="form-field">
          {t("agendaTopics")}
          <textarea
            rows={6}
            value={topics}
            onChange={(e) => setTopics(e.target.value)}
          />
        </label>
        <InputField
          label={t("recurrence")}
          value={recurrence}
          onChange={(e) => setRecurrence(e.target.value)}
        />
        <div className="button-row">
          <Button
            variant="primary"
            disabled={busy || !name.trim()}
            onClick={async () => {
              setBusy(true);
              const saved = await saveTemplate(
                {
                  id,
                  name,
                  meetingType: type,
                  defaultTitle: title,
                  participantStaffIds: participants,
                  agendaTopics: topics
                    .split("\n")
                    .filter(Boolean)
                    .map((text, order) => ({
                      id: crypto.randomUUID(),
                      text: text.trim(),
                      order,
                    })),
                  recurrence: recurrence
                    ? { type: "custom", label: recurrence }
                    : undefined,
                  active: true,
                },
                user.role,
              );
              setBusy(false);
              navigate(`/templates/${saved.id}/edit`);
            }}
          >
            {t("save")}
          </Button>
          <Link className="button secondary" to="/templates">
            {t("cancel")}
          </Link>
        </div>
      </section>
    </>
  );
}
