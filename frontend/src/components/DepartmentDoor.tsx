import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { MeetingType } from "../types/meeting";
import { distribution } from "../api/config";
export default function DepartmentDoor({
  type,
  mode,
}: {
  type: MeetingType;
  mode?: string;
}) {
  const { t } = useTranslation();
  return (
    <Link
      className="department-door panel"
      to={`/meetings/new?type=${type}${mode === "upload" ? "&mode=upload" : ""}`}
    >
      <h2>{t(type)}</h2>
      <p>{t("routing", distribution[type])}</p>
    </Link>
  );
}
