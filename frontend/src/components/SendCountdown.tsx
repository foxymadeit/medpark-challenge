import { useEffect, useRef, useState } from "react";
import { FiMail as EnvelopeSimple, FiPause as Pause } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { sendNow, stopScheduledSend } from "../api/meetings";
import { distribution } from "../api/config";
import { invalidMinutes } from "../api/validation";
import type { Meeting } from "../types/meeting";
import { notifyUpdate } from "../hooks/useData";
import Button from "./Button";
import { formatTime } from "../utils";
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
      await (stop ? stopScheduledSend(meeting.id) : sendNow(meeting.id));
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
                    list: meeting.distributionList.join(", "),
                    time: formatTime(seconds),
                  })
                : meeting.status === "sending"
                  ? t("sending")
                  : t("sendPaused")}
          </strong>
          <p>
            {stopped
              ? t("sendingStoppedDetail")
              : t("reviewWindow", { count: distribution[meeting.type].count })}
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
      {meeting.status === "sending_soon" && (
        <progress max={meeting.sendWindowSeconds ?? 30} value={seconds} />
      )}
    </section>
  );
}
