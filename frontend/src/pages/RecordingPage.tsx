import { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  FiMic as Microphone,
  FiPause as Pause,
  FiPlay as Play,
  FiSquare as Stop,
  FiWifiOff as WifiSlash,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { useRecorder } from "../hooks/useRecorder";
import { saveRecording, startProcessing, updateMeeting } from "../api/meetings";
import { DEMO_MODE } from "../api/config";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import SpeakerLabel from "../components/SpeakerLabel";
import { speakerColor } from "../utils";
import Waveform from "../components/Waveform";
import Button from "../components/Button";
import { formatTime, formatTimer } from "../utils";
import type { Meeting } from "../types/meeting";
export default function RecordingPage() {
  const result = useMeeting();
  if (!result.data)
    return <StatePanel error={result.error} retry={result.refresh} />;
  return <Recorder key={result.data.id} initial={result.data} />;
}
function Recorder({ initial: m }: { initial: Meeting }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<{ blob: Blob; seconds: number }>();
  const [timeline, setTimeline] = useState(m.speakerTimeline ?? []);
  const auto = useRef(false);
  const checkpointSave = useRef(Promise.resolve());
  const rec = useRecorder(
    (blob, seconds) => {
      void saveRecording(m.id, blob)
        .then(() =>
          updateMeeting(m.id, {
            durationSeconds: seconds,
            status: "stopped",
            endedAt: new Date().toISOString(),
          }),
        )
        .catch(() => {});
    },
    (blob, seconds) => {
      checkpointSave.current = checkpointSave.current
        .then(() => saveRecording(m.id, blob))
        .then(() =>
          updateMeeting(m.id, {
            durationSeconds: seconds,
            status: "recording",
          }),
        )
        .then(() => {})
        .catch(() => setError("storage"));
    },
  );
  const { start } = rec;
  useEffect(() => {
    if (!auto.current && m.status === "draft") {
      auto.current = true;
      void start();
    }
    return () => {
      auto.current = false;
    };
  }, [m.status, start]);
  const active = rec.state === "recording" || rec.state === "paused";
  const slot = m.participants.length
    ? Math.floor(rec.seconds / 8) % m.participants.length
    : 0;
  useEffect(() => {
    if (rec.state !== "recording" || !DEMO_MODE || !m.participants.length)
      return;
    const p = m.participants[slot];
    const end = Math.floor(rec.seconds);
    if (end < 1) return; // The recorder clock is an external source; persist its speaker events.
    // oxlint-disable-next-line react/set-state-in-effect
    setTimeline((current) => {
      const next = [...current];
      const last = next.at(-1);
      if (last?.speakerId === p.id)
        next[next.length - 1] = { ...last, endSeconds: end };
      else
        next.push({
          speakerId: p.id,
          startSeconds: Math.max(0, end - 1),
          endSeconds: end,
        });
      return next;
    });
  }, [rec.seconds, rec.state, m.participants, slot]);
  const live = useRef({ timeline, seconds: rec.seconds });
  useEffect(() => {
    live.current = { timeline, seconds: rec.seconds };
  }, [timeline, rec.seconds]);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      void updateMeeting(m.id, {
        status: "recording",
        startedAt: m.startedAt ?? new Date().toISOString(),
        speakerTimeline: live.current.timeline,
        durationSeconds: live.current.seconds,
      }).catch(() => setError("storage"));
    }, 2000);
    return () => clearInterval(timer);
  }, [m.id, m.startedAt, active]);
  async function finish() {
    setBusy(true);
    setError("");
    try {
      const output = saved ?? (await rec.stop());
      setSaved(output);
      await checkpointSave.current;
      await saveRecording(m.id, output.blob);
      const participants = m.participants.map((p) => ({
        ...p,
        speakingSeconds: timeline
          .filter((s) => s.speakerId === p.id)
          .reduce((sum, s) => sum + s.endSeconds - s.startSeconds, 0),
      }));
      await updateMeeting(m.id, {
        status: "uploaded",
        durationSeconds: output.seconds,
        endedAt: new Date().toISOString(),
        speakerTimeline: timeline,
        participants,
      });
      await startProcessing(m.id);
      navigate(`/meetings/${m.id}/processing`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "requestFailed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <MeetingHeader meeting={m} stage="record" />
      {error && active && (
        <div className="offline-banner" role="status">
          <WifiSlash size={20} />
          {t("serviceNotAnswering")}
        </div>
      )}
      <div className="recording-grid">
        <section className="panel recorder-panel">
          <p className={active ? "recording-indicator" : ""}>
            {t(
              rec.state === "paused"
                ? "paused"
                : active
                  ? "recording"
                  : m.status === "stopped"
                    ? "stopped"
                    : "record",
            )}
          </p>
          <div className="record-timer mono">{formatTimer(rec.seconds)}</div>
          {active && <p className="checkpoint-note">{t("savedCheckpoint")}</p>}
          <Waveform levels={rec.levels} />
          <div className="button-row spread">
            {active || saved ? (
              <Button
                variant="primary"
                disabled={busy || rec.seconds < 0.1}
                onClick={() => void finish()}
              >
                <Stop size={20} />
                {t(saved ? "retry" : "stopWrite")}
              </Button>
            ) : (
              <Button
                variant="primary"
                disabled={rec.state === "requesting"}
                onClick={() => void rec.start()}
              >
                <Microphone size={20} />
                {t(rec.error ? "retry" : "startRecording")}
              </Button>
            )}
            {active && (
              <Button onClick={rec.state === "paused" ? rec.resume : rec.pause}>
                {rec.state === "paused" ? (
                  <Play size={20} />
                ) : (
                  <Pause size={20} />
                )}{" "}
                {t(rec.state === "paused" ? "resume" : "pause")}
              </Button>
            )}
          </div>
          {["stopped", "recording"].includes(m.status) &&
            !active &&
            !saved &&
            m.durationSeconds && (
              <>
                <p>{t("recordInterrupted")}</p>
                <Button
                  onClick={async () => {
                    try {
                      await startProcessing(m.id);
                      navigate(`/meetings/${m.id}/processing`);
                    } catch {
                      setError("requestFailed");
                    }
                  }}
                >
                  {t("writeMinutes")}
                </Button>
              </>
            )}
          {(rec.error || (error && !active)) && (
            <div role="alert" className="error">
              <p>
                {t(error || rec.error, { defaultValue: t("requestFailed") })}
              </p>
              <Link className="text-link" to={`/meetings/${m.id}/upload`}>
                {t("uploadRecording")}
              </Link>
            </div>
          )}
        </section>
        <section className="panel speaking-panel">
          <h2>{t("nowSpeaking")}</h2>
          {DEMO_MODE && active && m.participants.length ? (
            <>
              <div className="current-speaker">
                <SpeakerLabel person={m.participants[slot]} slot={slot} />
              </div>
              <p className="muted">{t("speakerSimulation")}</p>
              <hr />
              {m.participants.map((p, i) => (
                <div
                  key={p.id}
                  className={`speaker-row ${i === slot && active ? "active" : ""}`}
                >
                  <SpeakerLabel person={p} slot={i} />
                  <span className="mono">
                    {formatTime(
                      timeline
                        .filter((s) => s.speakerId === p.id)
                        .reduce(
                          (sum, s) => sum + s.endSeconds - s.startSeconds,
                          0,
                        ),
                    )}
                  </span>
                </div>
              ))}
            </>
          ) : (
            <p>{t("waitingSpeakers")}</p>
          )}
        </section>
      </div>
      {error && active && (
        <div className="offline-toast" role="status">
          <WifiSlash size={18} />
          {t("recordingSafeToast")}
        </div>
      )}
      {DEMO_MODE && (
        <section className="panel timeline-panel">
          <div className="section-heading">
            <h2>{t("whoWhen")}</h2>
            <small>{t("lastTen")}</small>
          </div>
          {m.participants.map((p, i) => (
            <div key={p.id} className="speaker-lane">
              <SpeakerLabel person={p} slot={i} />
              <div className="lane-track">
                {timeline
                  .filter(
                    (s) =>
                      s.speakerId === p.id &&
                      s.endSeconds >= Math.max(0, rec.seconds - 600),
                  )
                  .map((s, j) => (
                    <span
                      key={j}
                      style={{
                        background: speakerColor(i),
                        left: `${Math.max(0, ((s.startSeconds - Math.max(0, rec.seconds - 600)) / Math.max(60, Math.min(600, rec.seconds))) * 100)}%`,
                        width: `${Math.min(100, ((s.endSeconds - Math.max(s.startSeconds, rec.seconds - 600)) / Math.max(60, Math.min(600, rec.seconds))) * 100)}%`,
                      }}
                    />
                  ))}
              </div>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
