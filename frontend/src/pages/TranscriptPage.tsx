import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMeeting } from "../hooks/useMeeting";
import { useData } from "../hooks/useData";
import { getRecording, getTranscript } from "../api/meetings";
import type { Meeting } from "../types/meeting";
import MeetingHeader from "../components/MeetingHeader";
import StatePanel from "../components/StatePanel";
import InputField from "../components/InputField";
import SpeakerLabel from "../components/SpeakerLabel";
import { formatTime } from "../utils";
export default function TranscriptPage() {
  const { data, error, refresh } = useMeeting();
  if (!data) return <StatePanel error={error} retry={refresh} />;
  return <Transcript meeting={data} />;
}
function Transcript({ meeting: m }: { meeting: Meeting }) {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const at = Number(params.get("at"));
  const [query, setQuery] = useState("");
  const [speaker, setSpeaker] = useState("");
  const [audio, setAudio] = useState("");
  const { data, error, refresh } = useData(
    useCallback(() => getTranscript(m.id), [m.id]),
    0,
  );
  useEffect(() => {
    let active = true;
    let url = "";
    void getRecording(m.id)
      .then((blob) => {
        if (blob && active) {
          url = URL.createObjectURL(blob);
          setAudio(url);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [m.id]);
  useEffect(() => {
    if (data && params.has("at"))
      document
        .getElementById(
          `segment-${data.reduce((best, s) => (Math.abs(s.startSeconds - at) < Math.abs(best.startSeconds - at) ? s : best), data[0])?.id}`,
        )
        ?.scrollIntoView({ block: "center" });
  }, [data, at, params]);
  const segments =
    data?.filter(
      (s) =>
        (!speaker || s.speakerId === speaker) &&
        s.text.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
    ) ?? [];
  return (
    <>
      <MeetingHeader
        meeting={m}
        stage={m.status === "sent" ? "sent" : "minutes"}
      />
      <Link className="back-link" to={`/meetings/${m.id}/minutes`}>
        {t("backMinutes")}
      </Link>
      <div className="transcript-toolbar">
        <InputField
          label={t("searchTranscript")}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label className="form-field">
          {t("speakers")}
          <select value={speaker} onChange={(e) => setSpeaker(e.target.value)}>
            <option value="">{t("allSpeakers")}</option>
            {m.participants.map((p) => (
              <option value={p.id} key={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {audio && (
          <audio
            controls
            src={audio}
            aria-label={t("recording")}
            onLoadedMetadata={(e) => {
              if (params.has("at")) e.currentTarget.currentTime = at;
            }}
          />
        )}
      </div>
      {m.demoGenerated && <p className="sample-note">{t("sampleContent")}</p>}
      {!data ? (
        <StatePanel error={error} retry={refresh} />
      ) : (
        <div className="panel transcript-panel">
          {segments.length ? (
            segments.map((s) => (
              <article
                key={s.id}
                id={`segment-${s.id}`}
                className={`transcript-segment ${params.has("at") && Math.abs(s.startSeconds - at) < 1 ? "highlight" : ""}`}
              >
                <span className="mono">{formatTime(s.startSeconds)}</span>
                <div>
                  <SpeakerLabel
                    person={m.participants.find((p) => p.id === s.speakerId)}
                    slot={Math.max(
                      0,
                      m.participants.findIndex((p) => p.id === s.speakerId),
                    )}
                  />
                  <p>{s.text}</p>
                </div>
                <small>{s.language?.toUpperCase()}</small>
              </article>
            ))
          ) : (
            <p className="empty-inline">{t("noResults")}</p>
          )}
        </div>
      )}
    </>
  );
}
