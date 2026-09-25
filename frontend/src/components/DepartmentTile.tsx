import type { MeetingType } from "../types/meeting";
export default function DepartmentTile({
  type,
  size = "M",
}: {
  type: MeetingType;
  size?: "M" | "L";
}) {
  return (
    <img
      className="department-tile"
      src={`/assets/departments/${type}-${size}.svg`}
      width={size === "M" ? 40 : 56}
      height={size === "M" ? 40 : 56}
      alt=""
    />
  );
}
