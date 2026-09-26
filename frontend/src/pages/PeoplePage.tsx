import { useState } from "react";
import { Link } from "react-router-dom";
import { FiPlay, FiUserCheck } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import {
  getPeople,
  getSpeakerClusters,
  getVoiceProfiles,
  getSpeakerSample,
  identifySpeakerCluster,
} from "../api/meetings";
import { notifyUpdate, useData } from "../hooks/useData";
import StatePanel from "../components/StatePanel";
import { DEMO_MODE } from "../api/config";
import Modal from "../components/Modal";
import Button from "../components/Button";

export default function PeoplePage() {
  const { t } = useTranslation();
  const people = useData(getPeople);
  const profiles = useData(getVoiceProfiles);
  const clusters = useData(getSpeakerClusters);
  const [identifying, setIdentifying] = useState<string>();
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  async function playSample(clusterId: string) {
    setActionError("");
    try {
      const sample = await getSpeakerSample(clusterId);
      if (!sample) throw new Error("sampleUnavailable");
      const url = URL.createObjectURL(sample);
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setActionError("sampleUnavailable");
      };
      await audio.play();
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "requestFailed",
      );
    }
  }
  if (!people.data || !profiles.data || !clusters.data)
    return (
      <StatePanel
        error={people.error || profiles.error || clusters.error}
        retry={() => {
          people.refresh();
          profiles.refresh();
          clusters.refresh();
        }}
      />
    );
  const staff = people.data;
  const profilePeople = profiles.data
    .map((profile) => staff.find((person) => person.id === profile.staffId))
    .filter((person) => person !== undefined);
  const unresolved = clusters.data.filter(
    (cluster) => cluster.status !== "voice_profile_ready",
  );
  const activeCluster = unresolved.find(
    (cluster) => cluster.id === identifying,
  );
  const choices = staff.filter((person) =>
    person.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <>
      <h1>{t("people")}</h1>
      {DEMO_MODE && <p className="muted">{t("voiceIdentityDemoNotice")}</p>}
      <section className="panel voice-profiles-card">
        <h2>{t("voiceProfiles")}</h2>
        <div className="voice-profile-list">
          {profilePeople.map((person) => (
            <div className="voice-profile-row" key={person.id}>
              <span className="avatar">
                {person.name
                  .replace("Dr. ", "")
                  .split(" ")
                  .map((part) => part[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              <div>
                <strong>{person.name}</strong>
                <small>
                  {person.role
                    ? t(person.role, { defaultValue: person.role })
                    : "—"}
                </small>
              </div>
              <span className="success">{t("voiceProfileReady")}</span>
              <span>{person.department ? t(person.department) : "—"}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel voices-identify-card">
        <h2>{t("voicesToIdentify")}</h2>
        {unresolved.map((cluster) => {
          const person = staff.find(
            (item) => item.id === cluster.identifiedStaffId,
          );
          return (
            <div className="unresolved-voice-row" key={cluster.id}>
              <div>
                <strong>{person?.name ?? cluster.label}</strong>
                <small>
                  {person
                    ? t("identifiedManually")
                    : DEMO_MODE
                      ? t("unnamedVoiceSource")
                      : ""}
                </small>
                {person && <small>{t("voiceProfileNotEnrolled")}</small>}
              </div>
              <span className="mono">
                {Math.floor(cluster.speakingSeconds / 60)}:
                {String(cluster.speakingSeconds % 60).padStart(2, "0")}
              </span>
              <Button
                disabled={!cluster.sampleAvailable}
                onClick={() => void playSample(cluster.id)}
              >
                <FiPlay /> {t("playSample")}
              </Button>
              {person ? (
                <Link
                  className="button primary"
                  to={`/people/${person.id}/enroll`}
                >
                  {t("enroll")}
                </Link>
              ) : (
                <Button
                  variant="primary"
                  onClick={() => setIdentifying(cluster.id)}
                >
                  <FiUserCheck /> {t("identifyPerson")}
                </Button>
              )}
            </div>
          );
        })}
      </section>
      {activeCluster && (
        <Modal
          title={t("identifyPerson")}
          onClose={() => setIdentifying(undefined)}
        >
          <p>
            <strong>{activeCluster.label}</strong>
          </p>
          <label className="form-field">
            {t("searchStaff")}
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div
            className="person-picker"
            role="listbox"
            aria-label={t("person")}
          >
            {choices.map((person) => (
              <button
                key={person.id}
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setActionError("");
                  try {
                    await identifySpeakerCluster(activeCluster.id, person.id);
                    setIdentifying(undefined);
                    clusters.refresh();
                    notifyUpdate();
                  } catch (reason) {
                    setActionError(
                      reason instanceof Error
                        ? reason.message
                        : "requestFailed",
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <strong>{person.name}</strong>
                <small>{person.role ?? "—"}</small>
              </button>
            ))}
          </div>
          {!choices.length && (
            <p className="muted">{t("personNotFoundAdmin")}</p>
          )}
        </Modal>
      )}
      {actionError && (
        <p className="error" role="alert">
          {t(actionError, { defaultValue: t("requestFailed") })}
        </p>
      )}
    </>
  );
}
