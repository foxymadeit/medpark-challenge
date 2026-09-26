import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/useAuth";
import { useData } from "../hooks/useData";
import { getMeetings } from "../api/meetings";
import ActionItemRow from "../components/ActionItemRow";
import StatePanel from "../components/StatePanel";
export default function ActionItemsPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { data, error, refresh } = useData(getMeetings);
  const [filter, setFilter] = useState("mine");
  if (!data) return <StatePanel error={error} retry={refresh} />;
  const today = new Date().toLocaleDateString("sv-SE");
  const soon = new Date(new Date().getTime() + 7 * 86400000).toLocaleDateString(
    "sv-SE",
  );
  const actions = data
    .flatMap((meeting) =>
      (meeting.actionItems ?? []).map((item) => ({ meeting, item })),
    )
    .filter(({ item }) =>
      filter === "mine"
        ? item.ownerStaffId === user?.staffProfileId
        : filter === "overdue"
          ? Boolean(!item.completed && item.deadline && item.deadline < today)
          : true,
    );
  const groups = ["today", "thisWeek", "later", "done"];
  return (
    <>
      <h1>{t("actions")}</h1>
      <div className="filter-chips">
        {["mine", "everyone", "overdue"].map((f) => (
          <button
            key={f}
            className={`chip ${filter === f ? "active" : ""}`}
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
          >
            {t(f)}
          </button>
        ))}
      </div>
      {actions.length === 0 && <StatePanel empty="noActions" />}
      {groups.map((group) => {
        const rows = actions.filter(
          ({ item }) =>
            (item.completed
              ? "done"
              : item.deadline && item.deadline <= today
                ? "today"
                : item.deadline && item.deadline <= soon
                  ? "thisWeek"
                  : "later") === group,
        );
        return rows.length ? (
          <section className="action-group" key={group}>
            <h2>
              {t(group)} <small>{rows.length}</small>
            </h2>
            <div className="panel">
              {rows.map(({ meeting, item }) => (
                <ActionItemRow
                  key={meeting.id + item.id}
                  meeting={meeting}
                  item={item}
                />
              ))}
            </div>
          </section>
        ) : null;
      })}
    </>
  );
}
