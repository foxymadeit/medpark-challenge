import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Microphone, Stop } from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { enrollVoice, getPeople } from "../api/meetings";
import { DEMO_MODE } from "../api/config";
import { useData } from "../hooks/useData";
import { useRecorder } from "../hooks/useRecorder";
import StatePanel from "../components/StatePanel";
import AddPerson from "../components/AddPerson";
import Waveform from "../components/Waveform";
import Button from "../components/Button";
import { formatTime } from "../utils";
export default function EnrollVoicePage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const { data, error, refresh } = useData(getPeople, 0);
  const [person, setPerson] = useState(id ?? "");
  const [adding, setAdding] = useState(false);
  const [blob, setBlob] = useState<Blob>();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [saved, setSaved] = useState(false);
  const rec = useRecorder();
  const recording = rec.state === "recording";
  if (!data) return <StatePanel error={error} retry={refresh} />;
  return (
    <section className="panel enrollment-panel">
      <h1>{t("enroll")}</h1>
      <label className="form-field">
        {t("name")}
        <select
          value={person}
          disabled={recording}
          onChange={(e) => {
            setPerson(e.target.value);
            setSaved(false);
            setBlob(undefined);
          }}
        >
          <option value="">—</option>
          {data.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <Button
        variant="quiet"
        disabled={recording}
        onClick={() => setAdding(true)}
      >
        {t("add")}
      </Button>
      <h2>{t("readAloud")}</h2>
      <blockquote>
        Astăzi discutăm planul pentru săptămâna viitoare. Сегодня мы обсуждаем
        план на следующую неделю. Today we discuss the plan for next week.
      </blockquote>
      {DEMO_MODE && <p className="muted">{t("prototypeNotice")}</p>}
      <div className="enrollment-recorder">
        <Button
          variant={recording ? "danger" : "secondary"}
          disabled={!person || busy || rec.state === "requesting"}
          aria-label={t(recording ? "stop" : "startRecording")}
          onClick={async () => {
            setFailure("");
            setSaved(false);
            try {
              if (recording) {
                const result = await rec.stop();
                setBlob(result.blob);
              } else {
                setBlob(undefined);
                await rec.start();
              }
            } catch {
              setFailure("microphone");
            }
          }}
        >
          {recording ? <Stop size={20} /> : <Microphone size={20} />}
        </Button>
        <span className="mono">{formatTime(rec.seconds)}</span>
        <Waveform levels={rec.levels} />
      </div>
      {(failure || rec.error) && (
        <p className="error" role="alert">
          {t(failure || rec.error)}
        </p>
      )}
      {saved && (
        <p className="success" role="status">
          {t("voiceSaved")}
        </p>
      )}
      <div className="button-row">
        <Button
          variant="primary"
          disabled={!blob || !person || busy || recording || saved}
          onClick={async () => {
            if (!blob) return;
            setBusy(true);
            try {
              await enrollVoice(person, blob);
              setSaved(true);
            } catch {
              setFailure("requestFailed");
            } finally {
              setBusy(false);
            }
          }}
        >
          {t("saveVoice")}
        </Button>
        <Link className="button secondary" to="/people">
          {t("people")}
        </Link>
      </div>
      {adding && (
        <AddPerson
          onClose={() => setAdding(false)}
          onAdded={(p) => {
            setPerson(p.id);
            setAdding(false);
            refresh();
          }}
        />
      )}
    </section>
  );
}
