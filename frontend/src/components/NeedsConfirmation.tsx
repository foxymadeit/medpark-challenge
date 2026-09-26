import { useState } from "react";
import { useTranslation } from "react-i18next";
import { decideConfirmation, markReviewed } from "../api/meetings";
import { openSendWindow } from "../api/sendWindow";
import { notifyUpdate } from "../hooks/useData";
import type { ConfirmItem, Meeting } from "../types/meeting";
import Button from "./Button";
import { explainProblems } from "../api/reasons";
import { listName } from "../api/routing";

type Choice = "keep" | "remove";

/** Figma M03: items the checks could not confirm wait for a person; sending
 * resumes only when each one is kept or taken out. */
export default function NeedsConfirmation({
  meeting,
  onDone,
}: {
  meeting: Meeting;
  onDone?: () => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  // Switching the type changes meeting.type; the question keeps naming the
  // board the meeting started with.
  const [startType] = useState(meeting.type);
  // The server drops an item from its list once it is settled, so keep the
  // list this person started with; their choices stay on screen.
  const [seen, setSeen] = useState<ConfirmItem[]>(meeting.confirmItems ?? []);
  const server = new Map((meeting.confirmItems ?? []).map((i) => [i.id, i]));
  const fresh = [...server.values()].filter(
    (i) => !seen.some((s) => s.id === i.id),
  );
  if (fresh.length) setSeen([...seen, ...fresh]);
  // Optimistic: a choice shows at once and rolls back if the server refuses.
  const [chosen, setChosen] = useState<Record<string, Choice>>({});
  const items = seen.map((item) => {
    const current = server.get(item.id);
    return {
      ...(current ?? item),
      decision: chosen[item.id] ?? current?.decision,
      settledElsewhere: !current && !chosen[item.id],
    };
  });
  const open = items.filter((i) => !i.decision && !i.settledElsewhere).length;
  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setError("");
    try {
      await action();
      notifyUpdate();
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "requestFailed");
      return false;
    } finally {
      setBusy("");
    }
  }
  async function decide(itemId: string, keep: boolean) {
    const before = chosen[itemId];
    setChosen((c) => ({ ...c, [itemId]: keep ? "keep" : "remove" }));
    const ok = await run(itemId, () =>
      decideConfirmation(meeting.id, itemId, keep),
    );
    if (!ok)
      setChosen((c) => {
        const next = { ...c };
        if (before) next[itemId] = before;
        else delete next[itemId];
        return next;
      });
  }
  async function finish() {
    const ok = await run("continue", () => markReviewed(meeting.id));
    // Automatic sending promised a window in which anyone can stop it; the
    // settled minutes get that window rather than going at once.
    if (ok && meeting.sendMode === "auto")
      openSendWindow(meeting.id, meeting.sendWindowSeconds ?? 60);
    if (ok) onDone?.();
  }
  const typeItem = items.find((i) => i.detectedType);
  const others = items.filter((i) => !i.detectedType);
  function actions(item: (typeof items)[number], wide = false) {
    const chosen = typeItem?.chosenType ?? startType;
    const labels = item.detectedType
      ? {
          keep: t("keepType", { list: listName(chosen, t) }),
          takeOut: t("switchType", { list: listName(item.detectedType, t) }),
          kept: t("typeKept", { list: listName(chosen, t) }),
          takenOut: t("typeSwitched", {
            list: listName(item.detectedType, t),
          }),
        }
      : {
          keep: t("keep"),
          takeOut: t("takeOut"),
          kept: t("kept"),
          takenOut: t("takenOut"),
        };
    // one key per state, so the new state fades in rather than snapping
    if (item.settledElsewhere)
      return (
        <span key="settled" className="confirm-state expand-in">
          {t("settled")}
        </span>
      );
    if (item.decision)
      return (
        <div key="decided" className="button-row expand-in">
          <span className="confirm-state">
            {item.decision === "keep" ? labels.kept : labels.takenOut}
          </span>
          <Button
            variant="quiet"
            disabled={!!busy}
            onClick={() => void decide(item.id, item.decision !== "keep")}
          >
            {t("change")}
          </Button>
        </div>
      );
    return (
      <div
        key="open"
        className={`button-row expand-in ${wide ? "confirm-choice" : ""}`}
      >
        <Button
          disabled={!!busy}
          aria-label={
            item.detectedType ? undefined : `${labels.takeOut}: ${item.text}`
          }
          onClick={() => void decide(item.id, false)}
        >
          {labels.takeOut}
        </Button>
        <Button
          disabled={!!busy}
          aria-label={
            item.detectedType ? undefined : `${labels.keep}: ${item.text}`
          }
          onClick={() => void decide(item.id, true)}
        >
          {labels.keep}
        </Button>
      </div>
    );
  }
  // The type check reads as where the minutes go, now and after a choice.
  function typeQuestion(item: ConfirmItem & { decision?: Choice }) {
    const chosen = listName(item.chosenType ?? startType, t);
    const detected = listName(item.detectedType!, t);
    if (item.decision === "remove")
      return t("typeCheckSwitched", { list: detected });
    if (item.decision === "keep") return t("typeCheckKept", { list: chosen });
    return t("typeCheck", { chosen, detected });
  }
  return (
    <section className="panel needs-confirmation" aria-labelledby="nc-title">
      <h2 id="nc-title" key={open ? "open" : "settled"} className="expand-in">
        {open ? t("needsPerson", { count: open }) : t("allSettled")}
      </h2>
      {typeItem && (
        <div
          className="confirm-type"
          role="group"
          aria-labelledby="nc-type-title"
        >
          <h3 id="nc-type-title">{t("typeSection")}</h3>
          <div className="confirm-row">
            <div>
              <strong key={typeItem.decision ?? "open"} className="expand-in">
                {typeQuestion(typeItem)}
              </strong>
              <p>{t("typeCheckWhy")}</p>
            </div>
            {actions(typeItem, true)}
          </div>
        </div>
      )}
      {others.length > 0 && (
        <>
          <p className="muted">{t("needsPersonDetail")}</p>
          <ul className="confirm-list">
            {others.map((item) => (
              <li key={item.id} className="confirm-row">
                <div>
                  <strong>{item.text}</strong>
                  <p>
                    {item.problems?.length
                      ? explainProblems(item.problems, t)
                      : item.reason}
                  </p>
                </div>
                {actions(item)}
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="confirm-footer">
        <p className="muted">
          {t("sendingWaits", { list: listName(meeting.type, t) })}
        </p>
        <Button
          variant="primary"
          disabled={open > 0 || !!busy}
          onClick={() => void finish()}
        >
          {t("continueToSending")}
        </Button>
      </div>
      {error && (
        <p className="error" role="alert">
          {t(error, { defaultValue: t("requestFailed") })}
        </p>
      )}
    </section>
  );
}
