import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  FiCheck as Check,
  FiMic as Microphone,
  FiSquare as Stop,
  FiAlertTriangle as Warning,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { enrollVoice, getPeople } from "../api/meetings";
import { DEMO_MODE, departments } from "../api/config";
import { useData } from "../hooks/useData";
import { useRecorder } from "../hooks/useRecorder";
import StatePanel from "../components/StatePanel";
import Button from "../components/Button";
import { formatTime } from "../utils";
import type { MeetingType } from "../types/meeting";
import {
  EnrollmentMessage,
  LanguageChoice,
  PersonCard,
  PersonHeader,
  SpeechProgress,
  type PassageLanguage,
} from "../components/enrollment";
import {
  clearSpeechSeconds,
  DEMO_SIMILARITY_PERCENT,
  ENROLLMENT_TARGET_SECONDS,
  resultState,
  type EnrollmentState,
} from "./enrollment";
const passages: Record<PassageLanguage, string> = {
  en: "Today our team reviews the plan for the coming week. We will speak clearly, listen carefully, and agree on the next steps for every patient.",
  ro: "Astăzi echipa noastră verifică planul pentru săptămâna următoare. Vom vorbi clar, vom asculta cu atenție și vom stabili pașii următori pentru fiecare pacient.",
  ru: "Сегодня наша команда рассматривает план на следующую неделю. Мы будем говорить ясно, внимательно слушать и согласуем дальнейшие шаги для каждого пациента.",
};

export default function EnrollVoicePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { data, error, refresh } = useData(getPeople, 0);
  const [state, setState] = useState<EnrollmentState>(id ? "ready" : "pick");
  const [personId, setPersonId] = useState(id ?? "");
  const [department, setDepartment] = useState<MeetingType>("medical");
  const [language, setLanguage] = useState<PassageLanguage>("en");
  const [search, setSearch] = useState("");
  const [sample, setSample] = useState<{ blob: Blob; seconds: number }>();
  const [busy, setBusy] = useState(false);
  const rec = useRecorder();
  const person = data?.find((item) => item.id === personId);
  const candidates = useMemo(
    () =>
      (data ?? []).filter(
        (item) =>
          item.department === department &&
          item.name.toLowerCase().includes(search.trim().toLowerCase()),
      ),
    [data, department, search],
  );
  const speech = clearSpeechSeconds(sample?.seconds ?? rec.seconds);

  useEffect(() => {
    if (rec.error === "microphone") setState("microphone_blocked");
  }, [rec.error]);
  useEffect(() => {
    if (state === "recording" && rec.seconds >= ENROLLMENT_TARGET_SECONDS)
      void finishRecording();
    // Recorder time is the external clock that triggers the 30 second stop.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [rec.seconds, state]);
  if (!data) return <StatePanel error={error} retry={refresh} />;

  function resetRecording(next: EnrollmentState = "ready") {
    setSample(undefined);
    setState(next);
  }
  async function startRecording() {
    setSample(undefined);
    await rec.start();
    if (!rec.error) setState("recording");
  }
  async function finishRecording() {
    if (busy || rec.state !== "recording") return;
    setBusy(true);
    try {
      const output = await rec.stop();
      setSample(output);
      const next = resultState(output.seconds, personId === "igor");
      setState(next);
      if (next === "checking") {
        await new Promise((resolve) => setTimeout(resolve, 800));
        await save(output);
      }
    } finally {
      setBusy(false);
    }
  }
  async function save(output = sample) {
    if (!output || !personId) return;
    await enrollVoice(personId, output.blob);
    setState("saved");
    refresh();
  }

  if (state === "pick")
    return (
      <section className="panel enrollment-flow enrollment-pick">
        <header>
          <div>
            <h1>{t("enroll")}</h1>
            <span className="optional-chip">{t("optional")}</span>
          </div>
          <p>{t("enrollExplanation")}</p>
          {DEMO_MODE && <p className="muted">{t("prototypeNotice")}</p>}
        </header>
        <label className="form-field">
          {t("department")}
          <select
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value as MeetingType);
              setPersonId("");
            }}
          >
            {departments.map((item) => (
              <option key={item} value={item}>
                {t(item)}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          {t("person")}
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchPerson")}
          />
        </label>
        <div className="person-picker" role="listbox" aria-label={t("person")}>
          {candidates.map((item) => (
            <button
              type="button"
              role="option"
              aria-selected={personId === item.id}
              key={item.id}
              onClick={() => setPersonId(item.id)}
            >
              <span>
                <strong>{item.name}</strong>
                <small>{t(item.role ?? item.department ?? "medical")}</small>
              </span>
              <span className={item.enrolled ? "success" : "muted"}>
                {t(item.enrolled ? "enrolled" : "notEnrolled")}
              </span>
            </button>
          ))}
        </div>
        <LanguageChoice
          value={language}
          onChange={setLanguage}
          label={t("passageLanguage")}
        />
        <div className="button-row">
          <Button
            variant="primary"
            disabled={!personId}
            onClick={() => setState("ready")}
          >
            <Microphone size={18} />
            {t("recordVoice")}
          </Button>
          <Link className="button secondary" to="/people">
            {t("cancel")}
          </Link>
        </div>
      </section>
    );

  if (!person)
    return (
      <StatePanel
        error="notFound"
        retry={() => {
          setPersonId("");
          setState("pick");
        }}
      />
    );
  if (state === "microphone_blocked")
    return (
      <EnrollmentMessage icon={<Microphone />} title={t("microphoneBlocked")}>
        <ol>
          <li>{t("micStep1")}</li>
          <li>{t("micStep2")}</li>
          <li>{t("micStep3")}</li>
        </ol>
        <div className="button-row">
          <Button
            variant="primary"
            onClick={() => {
              resetRecording();
              void startRecording();
            }}
          >
            {t("tryAgain")}
          </Button>
          <Link className="button secondary" to="/people">
            {t("cancel")}
          </Link>
        </div>
      </EnrollmentMessage>
    );
  if (state === "not_enough_speech")
    return (
      <EnrollmentMessage
        icon={<Warning />}
        title={t("notEnoughSpeech", { seconds: speech })}
      >
        <p>{t("speechAdvice")}</p>
        <SpeechProgress seconds={speech} />
        <div className="button-row">
          <Button variant="primary" onClick={() => resetRecording()}>
            {t("recordAgain")}
          </Button>
          <Link className="button secondary" to="/people">
            {t("cancel")}
          </Link>
        </div>
      </EnrollmentMessage>
    );
  if (state === "similar_voice") {
    const match = data.find((item) => item.id === "ana") ?? data[0];
    return (
      <EnrollmentMessage
        icon={<Warning />}
        title={t("similarVoice", { name: match.name })}
      >
        <p>{t("similarVoiceDetail")}</p>
        <div className="voice-comparison">
          <PersonCard person={person} />
          <strong>
            {DEMO_SIMILARITY_PERCENT}%<small>{t("alike")}</small>
          </strong>
          <PersonCard person={match} />
        </div>
        <p className="muted">
          {t("similarityThreshold")}
          {DEMO_MODE ? ` · ${t("prototypeNotice")}` : ""}
        </p>
        <div className="button-row">
          <Button onClick={() => resetRecording()}>{t("recordAgain")}</Button>
          <Button variant="primary" onClick={() => void save()}>
            {t("saveAnyway")}
          </Button>
        </div>
      </EnrollmentMessage>
    );
  }
  if (state === "checking")
    return (
      <EnrollmentMessage title={t("checkingRecording")}>
        <div className="checking-steps">
          <p>
            <Check /> {t("clearSpeechDuration", { seconds: speech })}
          </p>
          <p>
            <Check /> {t("voiceprintMade")}
          </p>
          <p className="muted">{t("comparingVoices")}</p>
        </div>
        {DEMO_MODE && <p className="muted">{t("prototypeNotice")}</p>}
      </EnrollmentMessage>
    );
  if (state === "saved")
    return (
      <EnrollmentMessage icon={<Check />} title={t("voiceSavedTitle")}>
        <p>{t("namedFromNow", { name: person.name })}</p>
        <dl className="enrollment-facts">
          <div>
            <dt>{t("clearSpeech")}</dt>
            <dd>{speech} s</dd>
          </div>
          <div>
            <dt>{t("passageLanguage")}</dt>
            <dd>{language.toUpperCase()}</dd>
          </div>
        </dl>
        <div className="button-row">
          <Button
            onClick={() => {
              setPersonId("");
              resetRecording("pick");
            }}
          >
            {t("enrollSomeoneElse")}
          </Button>
          <Button
            onClick={() => {
              setLanguage("ru");
              resetRecording();
            }}
          >
            {t("addRussianToo")}
          </Button>
          <Button variant="primary" onClick={() => navigate("/people")}>
            {t("done")}
          </Button>
        </div>
      </EnrollmentMessage>
    );

  return (
    <section
      className={`panel enrollment-flow ${state === "recording" ? "enrollment-reading" : ""}`}
    >
      <PersonHeader
        person={person}
        language={language}
        onChange={() => setState("pick")}
      />
      {state === "ready" ? (
        <>
          <h2>{t("readyToRecord")}</h2>
          <p>{t("recordInstruction")}</p>
          <div className="passage-placeholder">{t("passagePlaceholder")}</div>
          <p className="mic-working">
            <span /> {t("microphoneWorking")}
          </p>
          <Button variant="primary" onClick={() => void startRecording()}>
            <Microphone size={20} />
            {t("record")}
          </Button>
        </>
      ) : (
        <>
          <p className="recording-indicator">{t("recording")}</p>
          <div className="enrollment-timer mono">
            {formatTime(rec.seconds)} <small>{t("ofThirty")}</small>
          </div>
          <blockquote>{passages[language]}</blockquote>
          <SpeechProgress seconds={clearSpeechSeconds(rec.seconds)} />
          <div className="button-row">
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => void finishRecording()}
            >
              <Stop size={20} />
              {t("stop")}
            </Button>
            <Button
              onClick={async () => {
                if (rec.state === "recording") await rec.stop();
                resetRecording();
              }}
            >
              {t("startOver")}
            </Button>
          </div>
          {DEMO_MODE && <p className="muted">{t("demoSpeechActivity")}</p>}
        </>
      )}
    </section>
  );
}
