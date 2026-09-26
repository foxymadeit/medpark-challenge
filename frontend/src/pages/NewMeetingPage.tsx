import { useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  FiCheck as Check,
  FiMic as Microphone,
  FiUpload as UploadSimple,
  FiUserPlus as UserPlus,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { createMeeting, getPeople } from "../api/meetings";
import { departments, distribution } from "../api/config";
import type { MeetingType } from "../types/meeting";
import { useData } from "../hooks/useData";
import DepartmentTile from "../components/DepartmentTile";
import DepartmentDoor from "../components/DepartmentDoor";
import RouteProgress from "../components/RouteProgress";
import InputField from "../components/InputField";
import Button from "../components/Button";
import AddPerson from "../components/AddPerson";
import StatePanel from "../components/StatePanel";
export default function NewMeetingPage() {
  const { t, i18n } = useTranslation();
  const [search] = useSearchParams();
  const { department } = useParams();
  const chosen = department ?? search.get("type");
  const type = departments.includes(chosen as MeetingType)
    ? (chosen as MeetingType)
    : null;
  const navigate = useNavigate();
  const { data: people, error, refresh } = useData(getPeople, 0);
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState<"record" | "upload">(
    search.get("mode") === "upload" ? "upload" : "record",
  );
  const [selected, setSelected] = useState<string[]>(["ana", "elena", "igor"]);
  const [add, setAdd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  if (!type)
    return (
      <>
        <h1>{t("selectDepartment")}</h1>
        <div className="department-doors">
          {departments.map((d) => (
            <DepartmentDoor
              key={d}
              type={d}
              mode={search.get("mode") ?? undefined}
            />
          ))}
        </div>
      </>
    );
  if (!people) return <StatePanel error={error} retry={refresh} />;
  return (
    <>
      <Link className="back-link" to="/meetings">
        {t("meetings")}
      </Link>
      <div className="meeting-heading">
        <div className="meeting-heading-title">
          <DepartmentTile type={type} />
          <div>
            <h1>{t("meetingFor", { department: t(type) })}</h1>
            <p>{t("routing", distribution[type])}</p>
          </div>
        </div>
        <RouteProgress stage="record" upload={mode === "upload"} />
      </div>
      <div className="input-choices">
        {(["record", "upload"] as const).map((m) => (
          <button
            type="button"
            key={m}
            className={`panel input-choice ${mode === m ? "selected" : ""}`}
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
          >
            {m === "record" ? (
              <Microphone size={32} strokeWidth={2.5} />
            ) : (
              <UploadSimple size={32} strokeWidth={2.5} />
            )}
            {mode === m && (
              <span className="selection-check">
                <Check size={18} />
              </span>
            )}
            <h2>{t(m === "record" ? "recordRoom" : "uploadRecording")}</h2>
            <p>{t(m === "record" ? "micDescription" : "audioFormats")}</p>
          </button>
        ))}
      </div>
      <div className="setup-fields">
        <InputField
          label={t("optionalTitle")}
          maxLength={120}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t("titlePlaceholder")}
        />
        <div>
          <label>{t("roomPeople")}</label>
          <div className="people-chips">
            {people.map((p) => (
              <button
                key={p.id}
                className={`chip ${selected.includes(p.id) ? "selected" : ""}`}
                aria-pressed={selected.includes(p.id)}
                onClick={() =>
                  setSelected((s) =>
                    s.includes(p.id)
                      ? s.filter((id) => id !== p.id)
                      : [...s, p.id],
                  )
                }
              >
                {selected.includes(p.id) && <Check size={14} />} {p.name}
              </button>
            ))}
            <Button variant="quiet" onClick={() => setAdd(true)}>
              <UserPlus size={20} />
              {t("add")}
            </Button>
          </div>
        </div>
      </div>
      <div className="page-footer">
        {failure && (
          <p className="error" role="alert">
            {t(failure, { defaultValue: t("requestFailed") })}
          </p>
        )}
        <Button
          variant="primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const m = await createMeeting({
                title:
                  title.trim() ||
                  `${t("meetingFor", { department: t(type) })} — ${new Date().toLocaleDateString(i18n.language, { day: "numeric", month: "short", year: "numeric" })}`,
                type,
                inputMode: mode,
                participants: people.filter((p) => selected.includes(p.id)),
              });
              navigate(
                `/meetings/${m.id}/${mode === "record" ? "record" : "upload"}`,
              );
            } catch (e) {
              setFailure(e instanceof Error ? e.message : "requestFailed");
            } finally {
              setBusy(false);
            }
          }}
        >
          {mode === "record" ? (
            <Microphone size={20} />
          ) : (
            <UploadSimple size={20} />
          )}{" "}
          {t(mode === "record" ? "startRecording" : "continue")}
        </Button>
      </div>
      {add && (
        <AddPerson
          onClose={() => setAdd(false)}
          onAdded={(p) => {
            setSelected((s) => [...s, p.id]);
            setAdd(false);
            refresh();
          }}
        />
      )}
    </>
  );
}
