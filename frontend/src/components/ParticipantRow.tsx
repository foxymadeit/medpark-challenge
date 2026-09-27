import { useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Meeting, Participant } from "../types/meeting";
import {
  MAX_NAME,
  mergeParticipant,
  nameProblem,
  renameParticipant,
} from "../api/meetings";
import { notifyUpdate } from "../hooks/useData";
import { personName } from "../utils";
import Button from "./Button";
import SpeakerLabel from "./SpeakerLabel";

/** One person in the minutes' People list. Until the minutes are sent the
 * moderator can give them a real name or merge them into someone else, so
 * the email and the documents never say "Participant 3". */
export default function ParticipantRow({
  meeting,
  person,
  slot,
  share,
}: {
  meeting: Meeting;
  person: Participant;
  slot: number;
  share: string;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [mode, setMode] = useState<"" | "name" | "merge">("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const shown = personName(person, t);
  const others = meeting.participants.filter((p) => p.id !== person.id);
  const editable = !["sent", "sending"].includes(meeting.status);
  function open(next: "name" | "merge") {
    setMode(next);
    setError("");
    setValue(
      next === "name"
        ? shown === person.name
          ? person.name
          : ""
        : (others[0]?.id ?? ""),
    );
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    const problem =
      mode === "name" ? nameProblem(meeting, person.id, value) : "";
    if (problem) return setError(problem);
    setBusy(true);
    setError("");
    try {
      if (mode === "name")
        await renameParticipant(meeting.id, person.id, value.trim());
      else await mergeParticipant(meeting.id, person.id, value);
      setMode("");
      notifyUpdate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "requestFailed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="participant-row">
      <div className="speaker-row">
        <SpeakerLabel person={person} slot={slot} />
        <span className="mono">{share}</span>
      </div>
      {editable && !mode && (
        <div className="participant-tools">
          <Button
            variant="quiet"
            aria-label={t("nameParticipantFor", { name: shown })}
            onClick={() => open("name")}
          >
            {t("nameParticipant")}
          </Button>
          {others.length > 0 && (
            <Button
              variant="quiet"
              aria-label={t("mergeIntoFor", { name: shown })}
              onClick={() => open("merge")}
            >
              {t("mergeInto")}
            </Button>
          )}
        </div>
      )}
      {mode && (
        <form
          className="participant-edit expand-in"
          onSubmit={(e) => void save(e)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setMode("");
          }}
        >
          <label htmlFor={id}>
            {t(mode === "name" ? "nameParticipantFor" : "mergeIntoFor", {
              name: shown,
            })}
          </label>
          {mode === "name" ? (
            <input
              id={id}
              value={value}
              maxLength={MAX_NAME}
              autoFocus
              autoComplete="off"
              aria-invalid={!!error}
              onChange={(e) => setValue(e.target.value)}
            />
          ) : (
            <select
              id={id}
              value={value}
              autoFocus
              onChange={(e) => setValue(e.target.value)}
            >
              {others.map((p) => (
                <option key={p.id} value={p.id}>
                  {personName(p, t)}
                </option>
              ))}
            </select>
          )}
          <div className="button-row">
            <Button
              type="submit"
              variant="primary"
              disabled={busy || !value.trim()}
            >
              {t(mode === "name" ? "save" : "merge")}
            </Button>
            <Button variant="quiet" onClick={() => setMode("")}>
              {t("cancel")}
            </Button>
          </div>
          {error && (
            <p className="error" role="alert">
              {t(error, { defaultValue: t("requestFailed") })}
            </p>
          )}
        </form>
      )}
    </div>
  );
}
