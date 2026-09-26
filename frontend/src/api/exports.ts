import type { Meeting } from "../types/meeting";

function safeName(value: string) {
  return (
    value
      .replace(/[^a-z0-9]+/gi, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase() || "meeting"
  );
}

export function createTranscriptText(meeting: Meeting) {
  const people = new Map(meeting.participants.map((p) => [p.id, p.name]));
  return (meeting.transcript ?? [])
    .map((segment) => {
      const start = new Date(segment.startSeconds * 1000)
        .toISOString()
        .slice(11, 19);
      return `[${start}] ${people.get(segment.speakerId ?? "") ?? "Unknown speaker"}: ${segment.text}`;
    })
    .join("\n");
}

export function createRttm(meeting: Meeting) {
  const file = safeName(meeting.title);
  return (meeting.speakerTimeline ?? [])
    .filter((segment) => segment.endSeconds > segment.startSeconds)
    .map((segment) => {
      const duration = segment.endSeconds - segment.startSeconds;
      return `SPEAKER ${file} 1 ${segment.startSeconds.toFixed(3)} ${duration.toFixed(3)} <NA> <NA> ${segment.speakerId} <NA> <NA>`;
    })
    .join("\n");
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadText(
  value: string,
  filename: string,
  type = "text/plain;charset=utf-8",
) {
  downloadBlob(new Blob([value], { type }), filename);
}

export { safeName };
