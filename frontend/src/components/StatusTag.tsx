import {
  FiCheck as Check,
  FiClock as Clock,
  FiMail as EnvelopeSimple,
  FiMic as Microphone,
  FiEdit2 as PencilSimple,
  FiAlertTriangle as Warning,
  FiX as X,
} from "react-icons/fi";
import { useTranslation } from "react-i18next";
import type { MeetingStatus } from "../types/meeting";
export default function StatusTag({ status }: { status: MeetingStatus }) {
  const { t } = useTranslation();
  const Icon =
    status === "sent"
      ? Check
      : status === "recording"
        ? Microphone
        : status === "failed"
          ? Warning
          : status === "draft"
            ? PencilSimple
            : status === "stopped"
              ? X
              : ["sending_soon", "sending"].includes(status)
                ? EnvelopeSimple
                : Clock;
  return (
    <span className={`status-tag ${status}`}>
      <Icon size={14} strokeWidth={2.5} />
      {t(status)}
    </span>
  );
}
