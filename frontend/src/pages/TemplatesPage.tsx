import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPeople, getTemplates } from "../api/meetings";
import { useData } from "../hooks/useData";
import { useAuth } from "../auth/useAuth";
import StatePanel from "../components/StatePanel";

export default function TemplatesPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const templates = useData(getTemplates);
  const people = useData(getPeople);
  if (!templates.data || !people.data)
    return (
      <StatePanel
        error={templates.error || people.error}
        retry={() => {
          templates.refresh();
          people.refresh();
        }}
      />
    );
  const staff = people.data;
  return (
    <>
      <div className="section-heading spread">
        <h1>{t("templates")}</h1>
        {user?.role === "admin" && (
          <Link className="button primary" to="/templates/new">
            {t("newTemplate")}
          </Link>
        )}
      </div>
      <div className="template-grid">
        {templates.data.map((template) => {
          const participants = template.participantStaffIds
            .map((id) => staff.find((person) => person.id === id))
            .filter((person) => person !== undefined);
          const unavailable = participants.filter(
            (person) => person.active === false,
          );
          return (
            <article className="panel template-card" key={template.id}>
              <div className="section-heading spread">
                <h2>{template.name}</h2>
                <span className="state-badge">{t(template.meetingType)}</span>
              </div>
              <p>{template.recurrence?.label ?? t("notGiven")}</p>
              <strong>
                {t("participantCount", { count: participants.length })}
              </strong>
              <div className="template-avatars">
                {participants.slice(0, 3).map((person) => (
                  <span className="avatar" key={person.id}>
                    {person.name
                      .replace("Dr. ", "")
                      .split(" ")
                      .map((part) => part[0])
                      .slice(0, 2)
                      .join("")}
                  </span>
                ))}
                {participants.length > 3 && (
                  <span className="avatar">+{participants.length - 3}</span>
                )}
              </div>
              {unavailable.length > 0 && (
                <p className="error">
                  {t("participantUnavailable", { count: unavailable.length })}
                </p>
              )}
              <div className="template-topics">
                <strong>
                  {t("recurringTopics", {
                    count: template.agendaTopics.length,
                  })}
                </strong>
                {template.agendaTopics.slice(0, 3).map((topic) => (
                  <span key={topic.id}>{topic.text}</span>
                ))}
              </div>
              <div className="button-row">
                {user?.role === "admin" && (
                  <Link
                    className="button secondary"
                    to={`/templates/${template.id}/edit`}
                  >
                    {t("edit")}
                  </Link>
                )}
                <Link
                  className={`button primary ${unavailable.length ? "disabled" : ""}`}
                  aria-disabled={Boolean(unavailable.length)}
                  to={
                    unavailable.length
                      ? "/templates"
                      : `/meetings/new?template=${template.id}`
                  }
                >
                  {t("start")}
                </Link>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}
