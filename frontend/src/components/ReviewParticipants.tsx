import { useState } from "react";
import { useTranslation } from "react-i18next";
import { getPeople, updateParticipants } from "../api/meetings";
import { useData, notifyUpdate } from "../hooks/useData";
import type { Meeting } from "../types/meeting";
import Button from "./Button";
import StatePanel from "./StatePanel";
import { listName } from "../api/routing";

export default function ReviewParticipants({ meeting }: { meeting: Meeting }) {
  const { t } = useTranslation();
  const { data, error, refresh } = useData(getPeople, 0);
  const [selected, setSelected] = useState(() =>
    meeting.participants.map((participant) => participant.id),
  );
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!data) return <StatePanel error={error} retry={refresh} />;
  return (
    <section className="panel review-participants">
      <div className="section-heading spread">
        <div>
          <h2>{t("participantsRecipients")}</h2>
          <small>
            {t("routingToCount", {
              list: listName(meeting.type, t),
              count: meeting.distributionList.length,
            })}
          </small>
        </div>
        <Button variant="quiet" onClick={() => setEditing(!editing)}>
          {t(editing ? "cancel" : "reviewParticipants")}
        </Button>
      </div>
      {editing ? (
        <>
          <div className="participant-checklist">
            {data.map((person) => (
              <label key={person.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(person.id)}
                  onChange={() =>
                    setSelected((current) =>
                      current.includes(person.id)
                        ? current.filter((id) => id !== person.id)
                        : [...current, person.id],
                    )
                  }
                />
                <span>
                  <strong>{person.name}</strong>
                  <small>{person.email ?? t("emailUnavailable")}</small>
                </span>
              </label>
            ))}
          </div>
          <Button
            variant="primary"
            disabled={busy || !selected.length}
            onClick={async () => {
              setBusy(true);
              try {
                await updateParticipants(
                  meeting.id,
                  data.filter((person) => selected.includes(person.id)),
                );
                setEditing(false);
                notifyUpdate();
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("saveParticipants")}
          </Button>
        </>
      ) : (
        <div className="participant-summary">
          {meeting.participants.length ? (
            meeting.participants.map((person) => (
              <span key={person.id}>{person.name}</span>
            ))
          ) : (
            <span className="error">{t("noParticipants")}</span>
          )}
        </div>
      )}
    </section>
  );
}
