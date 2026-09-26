import { useState } from "react";
import { Link } from "react-router-dom";
import { FiEdit2 as PencilSimple } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import type { ActionItem, Meeting } from "../types/meeting";
import {
  saveCorrectionFeedback,
  toggleActionItem,
  updateActionItem,
} from "../api/meetings";
import { notifyUpdate } from "../hooks/useData";
import SpeakerLabel from "./SpeakerLabel";
import Button from "./Button";
import Modal from "./Modal";
import InputField from "./InputField";
import { formatTime } from "../utils";
export default function ActionItemRow({
  meeting,
  item,
  compact = false,
  displayTask,
}: {
  meeting: Meeting;
  item: ActionItem;
  compact?: boolean;
  /** The task in the minutes language the reader chose. */
  displayTask?: string;
}) {
  const { t, i18n } = useTranslation();
  const [edit, setEdit] = useState(false);
  const [task, setTask] = useState(item.task);
  const [owner, setOwner] = useState(item.ownerParticipantId ?? "");
  const [deadline, setDeadline] = useState(item.deadline ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const person = meeting.participants.find(
    (p) => p.id === item.ownerParticipantId,
  );
  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      notifyUpdate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "requestFailed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div
        className={`action-row ${compact ? "compact" : ""} ${item.completed ? "completed" : ""}`}
      >
        <input
          type="checkbox"
          aria-label={item.task}
          checked={item.completed}
          disabled={busy}
          onChange={() => void run(() => toggleActionItem(meeting.id, item.id))}
        />
        <div className="action-task">
          <span>{displayTask ?? item.task}</span>
          <small>
            {compact ? (
              <Link to={`/meetings/${meeting.id}/minutes`}>
                {meeting.title}
              </Link>
            ) : item.sourceTimestampSeconds !== undefined ? (
              <Link
                className="mono"
                to={`/meetings/${meeting.id}/transcript?at=${item.sourceTimestampSeconds}`}
              >
                {t("saidAt", { time: formatTime(item.sourceTimestampSeconds) })}
              </Link>
            ) : null}
          </small>
        </div>
        {!compact && (
          <>
            {person ? (
              <SpeakerLabel person={person} />
            ) : (
              <span className="muted">{t("unassigned")}</span>
            )}
          </>
        )}
        <span
          className={`deadline mono ${!item.completed && item.deadline && item.deadline <= new Date().toLocaleDateString("sv-SE") ? "overdue" : ""}`}
        >
          {item.completed
            ? t("done")
            : item.deadline
              ? new Date(item.deadline + "T12:00:00").toLocaleDateString(
                  i18n.language,
                  { day: "numeric", month: "short" },
                )
              : t("noDeadline")}
        </span>
        {!compact && !["sent", "sending"].includes(meeting.status) && (
          <Button
            variant="quiet"
            aria-label={t("edit")}
            onClick={() => {
              setTask(item.task);
              setOwner(item.ownerParticipantId ?? "");
              setDeadline(item.deadline ?? "");
              setEdit(true);
            }}
          >
            <PencilSimple size={20} />
          </Button>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {t(error, { defaultValue: t("requestFailed") })}
        </p>
      )}
      {edit && (
        <Modal title={t("editAction")} onClose={() => setEdit(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                await updateActionItem(meeting.id, item.id, {
                  task: task.trim(),
                  ownerParticipantId: owner || null,
                  deadline: deadline || null,
                });
                const before = JSON.stringify({
                  task: item.task,
                  ownerParticipantId: item.ownerParticipantId,
                  deadline: item.deadline,
                });
                const after = JSON.stringify({
                  task: task.trim(),
                  ownerParticipantId: owner || null,
                  deadline: deadline || null,
                });
                if (before !== after)
                  await saveCorrectionFeedback({
                    meetingId: meeting.id,
                    field: `actionItems.${item.id}`,
                    before,
                    after,
                    sourceTimestamp: item.sourceTimestampSeconds,
                  });
                setEdit(false);
              });
            }}
          >
            <InputField
              label={t("task")}
              value={task}
              required
              maxLength={500}
              onChange={(e) => setTask(e.target.value)}
            />
            <label className="form-field">
              {t("owner")}
              <select value={owner} onChange={(e) => setOwner(e.target.value)}>
                <option value="">{t("unassigned")}</option>
                {meeting.participants.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <InputField
              label={t("deadline")}
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
            {item.sourceTimestampSeconds !== undefined && (
              <p className="mono">
                {t("saidAt", { time: formatTime(item.sourceTimestampSeconds) })}
              </p>
            )}
            <p className="muted">{t("correctionFeedbackNotice")}</p>
            <div className="button-row">
              <Button
                type="submit"
                variant="primary"
                disabled={busy || !task.trim()}
              >
                {t("save")}
              </Button>
              <Button onClick={() => setEdit(false)}>{t("cancel")}</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
