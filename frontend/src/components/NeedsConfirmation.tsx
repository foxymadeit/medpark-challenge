import { useState } from "react";
import { useTranslation } from "react-i18next";
import { decideConfirmation, markReviewed, sendNow } from "../api/meetings";
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
    const ok = await run("continue", async () => {
      await markReviewed(meeting.id);
      // The person has settled every flagged item and asked to send: in
      // automatic mode that is the go-ahead, with no second click.
      if (meeting.sendMode === "auto") await sendNow(meeting.id);
    });
    if (ok) onDone?.();
  }
  // The meeting-type check reads as a choice between two lists, not keep or take out.
  const startedAs = (item: ConfirmItem) => item.chosenType ?? meeting.type;
  function title(item: ConfirmItem) {
    return item.detectedType
      ? t("typeCheck", {
          chosen: listName(startedAs(item), t),
          detected: listName(item.detectedType, t),
        })
      : item.text;
  }
  function labels(item: ConfirmItem) {
    if (!item.detectedType) {
      return {
        takeOut: `${t("takeOut")}: ${item.text}`,
        takeOutText: t("takeOut"),
        keep: `${t("keep")}: ${item.text}`,
        keepText: t("keep"),
      };
    }
    const keepText = t("keepType", { list: listName(startedAs(item), t) });
    const takeOutText = t("switchType", {
      list: listName(item.detectedType, t),
    });
    return { takeOut: takeOutText, takeOutText, keep: keepText, keepText };
  }
  return (
    <section className="panel needs-confirmation" aria-labelledby="nc-title">
      <h2 id="nc-title">{t("needsPerson", { count: items.length })}</h2>
      <p className="muted">{t("needsPersonDetail")}</p>
      <ul className="confirm-list">
        {items.map((item) => (
          <li key={item.id} className="confirm-row">
            <div>
              <strong>{title(item)}</strong>
              <p>
                {item.detectedType
                  ? t("typeCheckWhy")
                  : item.problems?.length
                    ? explainProblems(item.problems, t)
                    : item.reason}
              </p>
            </div>
            {item.settledElsewhere ? (
              <span className="confirm-state">{t("settled")}</span>
            ) : item.decision ? (
              <div className="button-row">
                <span className="confirm-state">
                  {t(item.decision === "keep" ? "kept" : "takenOut")}
                </span>
                <Button
                  variant="quiet"
                  disabled={!!busy}
                  onClick={() => void decide(item.id, item.decision !== "keep")}
                >
                  {t("change")}
                </Button>
              </div>
            ) : (
              <div className="button-row">
                <Button
                  disabled={!!busy}
                  aria-label={labels(item).takeOut}
                  onClick={() => void decide(item.id, false)}
                >
                  {labels(item).takeOutText}
                </Button>
                <Button
                  disabled={!!busy}
                  aria-label={labels(item).keep}
                  onClick={() => void decide(item.id, true)}
                >
                  {labels(item).keepText}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
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
