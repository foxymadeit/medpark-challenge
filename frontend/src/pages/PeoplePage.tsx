import { Link } from "react-router-dom";
import { UserPlus } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { getPeople } from "../api/meetings";
import { useData } from "../hooks/useData";
import StatePanel from "../components/StatePanel";
export default function PeoplePage() {
  const { t } = useTranslation();
  const { data, error, refresh } = useData(getPeople);
  if (!data) return <StatePanel error={error} retry={refresh} />;
  return (
    <>
      <div className="section-heading spread">
        <h1>{t("people")}</h1>
        <Link className="button primary" to="/people/enroll">
          <UserPlus size={20} />
          {t("enroll")}
        </Link>
      </div>
      <div className="panel people-table">
        <div className="person-row table-heading">
          <span>{t("name")}</span>
          <span>{t("role")}</span>
          <span>{t("voice")}</span>
          <span>{t("lists")}</span>
        </div>
        {data.map((p) => (
          <Link className="person-row" key={p.id} to={`/people/${p.id}/enroll`}>
            <strong>
              <span className="avatar">
                {p.name
                  .replace("Dr. ", "")
                  .split(" ")
                  .map((s) => s[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              {p.name}
            </strong>
            <span>{p.role ? t(p.role, { defaultValue: p.role }) : "—"}</span>
            <span className={p.enrolled ? "success" : ""}>
              {t(
                p.enrollmentKind === "prototype"
                  ? "prototypeEnrollment"
                  : p.enrolled
                    ? "enrolled"
                    : "notEnrolled",
              )}
            </span>
            <span>{p.department ? t(p.department) : "—"}</span>
          </Link>
        ))}
      </div>
    </>
  );
}
