import { speakerColor } from "../utils";
import { useTranslation } from "react-i18next";
import type { Participant } from "../types/meeting";
export default function SpeakerLabel({
  person,
  slot = 0,
}: {
  person?: Participant;
  slot?: number;
}) {
  const { t } = useTranslation();
  return (
    <span className="speaker-label">
      <span
        className="speaker-dot"
        style={{ background: speakerColor(person?.speakerSlot ?? slot) }}
      />
      {person?.name ?? t("speaker", { number: slot + 1 })}
    </span>
  );
}
