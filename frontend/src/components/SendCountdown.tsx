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
export default function SendCountdown({ meeting }: { meeting: Meeting }) {
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
      if (stop) await stopScheduledSend(meeting.id);
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
        <div>
          <strong>
            {stopped
              ? t("sendingStopped")
              : meeting.status === "sending_soon"
                ? t("sendingIn", {
                    list: listName(meeting.type, t),
                    time: formatTime(seconds),
                  })
                : meeting.status === "sending"
                  ? t("sending")
                  : t("sendPaused")}
          </strong>
          <p>
            {stopped
              ? t("sendingStoppedDetail")
              : t("reviewWindow", { count: meeting.distributionList.length })}
          </p>
        </div>
        <div className="button-row">
          {meeting.status === "sending_soon" && (
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
      {meeting.status === "sending_soon" && meeting.sendScheduledAt && (
        <CountdownBar
          key={meeting.sendScheduledAt}
          deadline={meeting.sendScheduledAt}
          windowSeconds={meeting.sendWindowSeconds ?? 30}
          label={t("sendingStatus")}
          seconds={seconds}
        />
      )}
      <p className="visually-hidden" aria-live="polite">
        {stopped
          ? t("sendingStopped")
          : meeting.status === "sending"
            ? t("sending")
            : ""}
      </p>
    </section>
  );
}
