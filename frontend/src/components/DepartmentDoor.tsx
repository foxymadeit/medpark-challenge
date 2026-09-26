import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { MeetingType } from "../types/meeting";
import { routingLine, type Routing } from "../api/routing";
export default function DepartmentDoor({
  type,
  mode,
  routing,
}: {
  type: MeetingType;
  mode?: string;
  routing?: Routing;
}) {
  const { t } = useTranslation();
  return (
    <Link
      className="department-door panel"
      to={`/meetings/new?type=${type}${mode === "upload" ? "&mode=upload" : ""}`}
    >
      <h2>{t(type)}</h2>
      <p>{routingLine(type, routing, t)}</p>
    </Link>
  );
}
