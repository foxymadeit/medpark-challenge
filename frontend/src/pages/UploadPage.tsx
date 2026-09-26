import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Check,
  FileAudio,
  UploadSimple,
  Warning,
  X,
} from "@phosphor-icons/react";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { inspectAudio } from "../api/audio";
import { startProcessing, uploadRecording } from "../api/meetings";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import Button from "../components/Button";
import { formatTime } from "../utils";
export default function UploadPage() {
  const { t } = useTranslation();
  const { data: m, error, refresh } = useMeeting();
  const [file, setFile] = useState<File>();
  const [duration, setDuration] = useState(0);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [candidateName, setCandidateName] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const sequence = useRef(0);
  const navigate = useNavigate();
  async function choose(f?: File) {
    const n = ++sequence.current;
    setFile(undefined);
    setDuration(0);
    setFailure("");
    if (!f) return;
    setCandidateName(f.name);
    setChecking(true);
    try {
      const seconds = await inspectAudio(f);
      if (n === sequence.current) {
        setFile(f);
        setDuration(seconds);
      }
    } catch (error) {
      if (n === sequence.current)
        setFailure(error instanceof Error ? error.message : "audioUnreadable");
    } finally {
      if (n === sequence.current) setChecking(false);
    }
  }
  if (!m) return <StatePanel error={error} retry={refresh} />;
  return (
    <>
      <MeetingHeader meeting={m} stage="record" />
      <section className="panel upload-problems-card">
        <h1>{t("uploadRecording")}</h1>
        <section
          className={`dropzone ${drag ? "dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            void choose(e.dataTransfer.files[0]);
          }}
        >
          <UploadSimple size={24} weight="bold" />
          <h2>{t("dropAudio")}</h2>
          <p>{t("audioFormats")}</p>
          <input
            ref={input}
            hidden
            type="file"
            accept=".wav,.mp3,.m4a,.flac,audio/wav,audio/mpeg,audio/mp4,audio/flac,audio/x-flac"
            onChange={(e) => void choose(e.target.files?.[0])}
          />
          <Button
            disabled={busy || checking}
            onClick={() => input.current?.click()}
          >
            {t("chooseFile")}
          </Button>
        </section>
        {checking && <p role="status">{t("checking")}</p>}
        {failure && (
          <div className="upload-file-row invalid" role="alert">
            <Warning size={20} />
            <div>
              <strong>{candidateName}</strong>
              <p>{t(failure, { defaultValue: t("audioUnreadable") })}</p>
            </div>
            <Button variant="quiet" onClick={() => void choose()}>
              {t("remove")}
            </Button>
          </div>
        )}
        {file && (
          <div className="upload-file-row valid">
            <FileAudio size={20} />
            <div>
              <strong>{file.name}</strong>
              <p className="mono">
                {formatTime(duration)} · {(file.size / 1024 / 1024).toFixed(1)}{" "}
                MB
              </p>
            </div>
            <Check size={18} className="success" aria-label={t("checked")} />
            <span className="visually-hidden">{t("checked")}</span>
            <Button
              variant="quiet"
              disabled={busy}
              aria-label={t("remove")}
              onClick={() => {
                void choose();
                if (input.current) input.current.value = "";
              }}
            >
              <X size={20} />
            </Button>
          </div>
        )}
        {!file && m.audioFilename && (
          <p>
            {m.audioFilename} · {t("uploaded")}
          </p>
        )}
        <div className="page-footer">
          <Button
            variant="primary"
            disabled={busy || checking || (!file && !m.durationSeconds)}
            onClick={async () => {
              setBusy(true);
              try {
                if (file) await uploadRecording(m.id, file, duration);
                await startProcessing(m.id);
                navigate(`/meetings/${m.id}/processing`);
              } catch (e) {
                setFailure(e instanceof Error ? e.message : "requestFailed");
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("writeMinutes")}
          </Button>
        </div>
      </section>
    </>
  );
}
