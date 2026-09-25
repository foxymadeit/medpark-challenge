import {
  Check,
  Clock,
  EnvelopeSimple,
  Microphone,
  PencilSimple,
  Warning,
  X,
} from "@phosphor-icons/react";
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
      <Icon size={14} weight="bold" />
      {t(status)}
    </span>
  );
}
