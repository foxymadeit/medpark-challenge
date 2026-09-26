import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useData } from "../hooks/useData";
import { getMeetings } from "../api/meetings";
import { departments } from "../api/config";
import { meetingUrl } from "../utils";
import StatePanel from "../components/StatePanel";
import StatusTag from "../components/StatusTag";
import InputField from "../components/InputField";
import { formatTime } from "../utils";
export default function HistoryPage() {
  const { t, i18n } = useTranslation();
  const { data, error, refresh } = useData(getMeetings);
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  if (!data) return <StatePanel error={error} retry={refresh} />;
  const rows = data.filter(
    (m) =>
      (!type || m.type === type) &&
      (!status || m.status === status) &&
      [
        m.title,
        ...m.participants.map((p) => p.name),
        ...(m.transcript ?? []).map((s) => s.text),
      ]
        .join(" ")
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
  );
  return (
    <>
      <h1>{t("history")}</h1>
      <div className="history-filters">
        <InputField
          label={t("searchMeetings")}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="filter-chips">
          <button
            className={`chip ${!type ? "active" : ""}`}
            onClick={() => setType("")}
          >
            {t("allTypes")}
          </button>
          {departments.map((d) => (
            <button
              key={d}
              className={`chip ${type === d ? "active" : ""}`}
              onClick={() => setType(d)}
            >
              {t(d)}
            </button>
          ))}
        </div>
        <select
          aria-label={t("status")}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">{t("allStatuses")}</option>
          {Array.from(new Set(data.map((m) => m.status))).map((s) => (
            <option key={s} value={s}>
              {t(s)}
            </option>
          ))}
        </select>
      </div>
      <div className="panel history-table">
        <div className="history-row table-heading">
          <span>{t("meetings")}</span>
          <span>{t("date")}</span>
          <span>{t("length")}</span>
          <span>{t("status")}</span>
        </div>
        {rows.length ? (
          rows.map((m) => (
            <Link className="history-row" key={m.id} to={meetingUrl(m)}>
              <div className="history-title">
                <strong>{m.title}</strong>
              </div>
              <span className="mono">
                {new Date(m.createdAt).toLocaleString(i18n.language, {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span className="mono">
                {m.durationSeconds ? formatTime(m.durationSeconds) : "—"}
              </span>
              <StatusTag status={m.status} />
            </Link>
          ))
        ) : (
          <p className="empty-inline">{t("noResults")}</p>
        )}
      </div>
    </>
  );
}
