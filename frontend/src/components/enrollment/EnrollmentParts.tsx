import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { Participant } from "../../types/meeting";
import { MINIMUM_CLEAR_SPEECH_SECONDS } from "../../pages/enrollment";
import Button from "../Button";

export type PassageLanguage = "en" | "ro" | "ru";

export function LanguageChoice({
  value,
  onChange,
  label,
}: {
  value: PassageLanguage;
  onChange: (value: PassageLanguage) => void;
  label: string;
}) {
  return (
    <fieldset className="language-choice">
      <legend>{label}</legend>
      {(["en", "ro", "ru"] as const).map((item) => (
        <button
          type="button"
          className={value === item ? "selected" : ""}
          onClick={() => onChange(item)}
          key={item}
        >
          {item.toUpperCase()}
        </button>
      ))}
    </fieldset>
  );
}

export function PersonCard({ person }: { person: Participant }) {
  return (
    <div className="person-card">
      <strong>{person.name}</strong>
      <small>{person.role ?? person.department}</small>
    </div>
  );
}

export function PersonHeader({
  person,
  language,
  onChange,
}: {
  person: Participant;
  language: PassageLanguage;
  onChange: () => void;
}) {
  const { t } = useTranslation();
  return (
    <header className="enrollment-person">
      <PersonCard person={person} />
      <span>{language.toUpperCase()}</span>
      <Button variant="quiet" onClick={onChange}>
        {t("change")}
      </Button>
    </header>
  );
}

export function SpeechProgress({ seconds }: { seconds: number }) {
  const { t } = useTranslation();
  return (
    <div className="speech-progress">
      <div>
        <strong>{t("clearSpeech")}</strong>
        <span>
          {seconds} s {t("ofTwenty")}
        </span>
      </div>
      <progress max={MINIMUM_CLEAR_SPEECH_SECONDS} value={seconds} />
    </div>
  );
}

export function EnrollmentMessage({
  icon,
  title,
  children,
}: {
  icon?: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="panel enrollment-flow enrollment-message">
      {icon && <div className="enrollment-state-icon">{icon}</div>}
      <h1>{title}</h1>
      {children}
    </section>
  );
}
