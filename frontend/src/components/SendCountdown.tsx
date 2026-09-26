import { useEffect, useRef, useState } from "react";
import { FiMail as EnvelopeSimple, FiPause as Pause } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { markReviewed, sendNow, stopScheduledSend } from "../api/meetings";
import { invalidMinutes } from "../api/validation";
import { listName } from "../api/routing";
import type { Meeting } from "../types/meeting";
import { notifyUpdate } from "../hooks/useData";
import Button from "./Button";
import { formatTime } from "../utils";
/** Empties linearly over the real send window. The timing is fixed once per
 * window (keyed by deadline) so re-renders never make the bar jump. */
function CountdownBar({
  deadline,
  windowSeconds,
  label,
  seconds,
}: {
  deadline: string;
  windowSeconds: number;
  label: string;
  seconds: number;
}) {
  const [elapsed] = useState(() =>
    Math.min(
      windowSeconds,
      Math.max(0, windowSeconds - (Date.parse(deadline) - Date.now()) / 1000),
    ),
  );
  return (
    <div
      className="countdown-bar"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={windowSeconds}
      aria-valuenow={seconds}
    >
      <span
        style={{
          animationDuration: `${windowSeconds}s`,
          animationDelay: `-${elapsed}s`,
        }}
      />
    </div>
  );
}
/** The send window (Figma X09) and, in the same place once stopped, the one
 * button that sends (X10). `onStop` replaces the server call for a window
 * this tab keeps (api/sendWindow.ts). */
export default function SendCountdown({
  meeting,
  onStop,
}: {
  meeting: Meeting;
  onStop?: () => void;
}) {
  const { t } = useTranslation();
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);
  const seconds = meeting.sendScheduledAt
    ? Math.max(0, Math.ceil((Date.parse(meeting.sendScheduledAt) - now) / 1000))
    : 0;
  const invalid = invalidMinutes(meeting);
  // A missing owner already shows as an error; a missing deadline only asks.
  const lacking =
    !invalid &&
    meeting.actionItems?.some((a) => !a.ownerParticipantId || !a.deadline);
  const sentWindow = useRef<string | undefined>(undefined);
  const stopped = meeting.deliveryState === "stopped";
  useEffect(() => {
    const window = meeting.sendScheduledAt;
    if (
      meeting.status !== "sending_soon" ||
      !window ||
      invalid ||
      seconds > 0 ||
      sentWindow.current === window
    )
      return;
    sentWindow.current = window;
    void sendNow(meeting.id)
      .then(notifyUpdate)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "requestFailed");
      });
  }, [meeting.id, meeting.status, meeting.sendScheduledAt, invalid, seconds]);
  async function act(stop: boolean) {
    setBusy(true);
    try {
      if (stop && onStop) onStop();
      else if (stop) await stopScheduledSend(meeting.id);
      else {
        // After a stop the server wants a review before a manual send; the
        // person pressing Send now after stopping has just done that.
        if (meeting.status === "ready" && meeting.reviewState !== "reviewed")
          await markReviewed(meeting.id);
        await sendNow(meeting.id);
      }
      notifyUpdate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "requestFailed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel send-countdown">
      <div className="send-line">
        {stopped ? <Pause size={24} /> : <EnvelopeSimple size={24} />}
        {/* announced once when it stops; the timer is read only on request */}
        <div role={stopped ? "status" : undefined}>
          <strong>
            {stopped
              ? t("sendingStopped")
              : t("sendingIn", {
                  list: listName(meeting.type, t),
                  time: formatTime(seconds),
                })}
          </strong>
          {stopped ? (
            <p>{t("sendingStoppedDetail")}</p>
          ) : (
            lacking && <p>{t("fixBeforeSending")}</p>
          )}
        </div>
        <div className="button-row">
          {!stopped && meeting.status === "sending_soon" && (
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => void act(true)}
            >
              {t("stopSending")}
            </Button>
          )}
          <Button
            variant="primary"
            disabled={
              busy ||
              invalid ||
              !["ready", "sending_soon"].includes(meeting.status)
            }
            onClick={() => void act(false)}
          >
            {t("sendNow")}
          </Button>
        </div>
      </div>
      {invalid && <p className="error">{t("unresolved")}</p>}
      {error && (
        <p role="alert" className="error">
          {t(error, { defaultValue: t("requestFailed") })}
        </p>
      )}
      {!stopped &&
        meeting.status === "sending_soon" &&
        meeting.sendScheduledAt && (
          <CountdownBar
            key={meeting.sendScheduledAt}
            deadline={meeting.sendScheduledAt}
            windowSeconds={meeting.sendWindowSeconds ?? 60}
            label={t("sendingStatus")}
            seconds={seconds}
          />
        )}
    </section>
  );
}
