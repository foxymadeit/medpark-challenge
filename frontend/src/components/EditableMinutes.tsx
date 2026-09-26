import { useState } from "react";
import { FiEdit2 as PencilSimple } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import type { LocalizedMinutes, Meeting } from "../types/meeting";
import { saveCorrectionFeedback, updateMinutes } from "../api/meetings";
import { notifyUpdate } from "../hooks/useData";
import Button from "./Button";
export default function EditableMinutes({
  meeting,
  field,
  localized,
}: {
  meeting: Meeting;
  field: "summary" | "decisions";
  /** Read-only view in the chosen minutes language; edits apply to the base. */
  localized?: LocalizedMinutes;
}) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function begin() {
    setValue(
      field === "summary"
        ? (meeting.summary ?? "")
        : (meeting.decisions ?? []).map((d) => d.text).join("\n"),
    );
    setEditing(true);
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      const before =
        field === "summary"
          ? (meeting.summary ?? "")
          : (meeting.decisions ?? [])
              .map((decision) => decision.text)
              .join("\n");
      await updateMinutes(
        meeting.id,
        field === "summary"
          ? { summary: value.trim() }
          : {
              decisions: value
                .split("\n")
                .filter((s) => s.trim())
                .map((text, i) => ({
                  id: meeting.decisions?.[i]?.id ?? crypto.randomUUID(),
                  text: text.trim(),
                })),
            },
      );
      if (before !== value.trim())
        await saveCorrectionFeedback({
          meetingId: meeting.id,
          field,
          before,
          after: value.trim(),
        });
      setEditing(false);
      notifyUpdate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "requestFailed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel minutes-card">
      <div className="section-heading spread">
        <h2>{t(field)}</h2>
        {!["sent", "sending"].includes(meeting.status) && !editing && (
          <Button
            variant="quiet"
            aria-label={`${t("edit")} ${t(field)}`}
            onClick={begin}
          >
            <PencilSimple size={20} />
          </Button>
        )}
      </div>
      {editing ? (
        <>
          <textarea
            aria-label={t(field)}
            rows={5}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              // Esc cancels, like the action dialog does
              if (e.key === "Escape") setEditing(false);
            }}
            autoFocus
            maxLength={10000}
          />
          <div className="button-row">
            <Button
              onClick={() => void save()}
              disabled={busy || !value.trim()}
            >
              {t("save")}
            </Button>
            <Button variant="quiet" onClick={() => setEditing(false)}>
              {t("cancel")}
            </Button>
          </div>
        </>
      ) : field === "summary" ? (
        <p>{localized?.summary || meeting.summary || t("notGiven")}</p>
      ) : (
        <ul className="decisions">
          {(localized?.decisions ?? meeting.decisions)?.map((d) => (
            <li key={d.id}>{d.text}</li>
          ))}
        </ul>
      )}
      {error && (
        <p className="error" role="alert">
          {t(error, { defaultValue: t("requestFailed") })}
        </p>
      )}
      {editing && <p className="muted">{t("correctionFeedbackNotice")}</p>}
    </section>
  );
}
