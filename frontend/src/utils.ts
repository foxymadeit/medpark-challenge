import type { Meeting } from "./types/meeting";
export function formatTime(seconds: number) {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}
export function formatTimer(seconds: number) {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 3600)
    .toString()
    .padStart(2, "0")}:${formatTime(s % 3600)}`;
}

export function meetingUrl(m: Meeting) {
  const page =
    m.status === "sent"
      ? "sent"
      : m.status === "processing"
        ? "processing"
        : ["ready", "sending_soon", "sending"].includes(m.status)
          ? "minutes"
          : m.status === "failed"
            ? "processing"
            : m.inputMode === "upload"
              ? "upload"
              : "record";
  return `/meetings/${m.id}/${page}`;
}

export const speakerColor = (slot: number) =>
  ["#3e7acb", "#e6713c", "#2b9f7d", "#d49c18", "#b85f9b", "#7967b4"][slot] ??
  `hsl(${(slot * 137.508) % 360} 52% 42%)`;
