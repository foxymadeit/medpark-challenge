import {
  Document,
  HeadingLevel,
  ImageRun,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
} from "docx";
import type { Meeting, MinutesLanguage } from "../types/meeting";
import { serverDocument } from "./pdf";
import { formatTime } from "../utils";

function safeFilename(value: string) {
  return value
    .trim()
    .replace(/[^a-z0-9]+/gi, "_")
    .replace(/^_|_$/g, "");
}

export function minutesDocxFilename(meeting: Meeting) {
  return `${safeFilename(meeting.title)}_${meeting.createdAt.slice(0, 10)}_Minutes.docx`;
}

export async function createMinutesDocx(meeting: Meeting): Promise<Blob> {
  const logoResponse = await fetch("/assets/liminal-logo.svg");
  if (!logoResponse.ok) throw new Error("documentGenerationFailed");
  const logo = new Uint8Array(await logoResponse.arrayBuffer());
  const fallbackLogo = Uint8Array.from(
    atob(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+3MxZ5wAAAABJRU5ErkJggg==",
    ),
    (character) => character.charCodeAt(0),
  );
  const snapshots = meeting.participantSnapshots ?? [];
  const ownerName = (staffId: string | null | undefined) =>
    snapshots.find((participant) => participant.staffId === staffId)
      ?.nameAtMeeting ?? "Not assigned";
  const document = new Document({
    sections: [
      {
        children: [
          new Paragraph({
            children: [
              new ImageRun({
                data: logo,
                type: "svg",
                fallback: { data: fallbackLogo, type: "png" },
                transformation: { width: 91, height: 28 },
              }),
            ],
          }),
          new Paragraph({ text: meeting.title, heading: HeadingLevel.TITLE }),
          new Paragraph(
            `${new Date(meeting.createdAt).toLocaleDateString()} · ${meeting.type}`,
          ),
          new Paragraph({
            text: "Participants",
            heading: HeadingLevel.HEADING_1,
          }),
          ...snapshots.map(
            (participant) =>
              new Paragraph({
                children: [
                  new TextRun({ text: participant.nameAtMeeting, bold: true }),
                  new TextRun(
                    `, ${participant.roleTitleAtMeeting || "Role unavailable"}, ${participant.departmentAtMeeting}`,
                  ),
                ],
              }),
          ),
          new Paragraph({ text: "Summary", heading: HeadingLevel.HEADING_1 }),
          new Paragraph(meeting.summary ?? ""),
          new Paragraph({
            text: "Discussion",
            heading: HeadingLevel.HEADING_1,
          }),
          ...(meeting.transcript ?? []).map((segment) => {
            const speaker =
              snapshots.find(
                (participant) =>
                  participant.speakerId === segment.speakerId ||
                  participant.staffId === segment.speakerId,
              )?.nameAtMeeting ?? "Unknown speaker";
            return new Paragraph({
              children: [
                new TextRun({
                  text: `[${formatTime(segment.startSeconds)}] ${speaker}: `,
                  bold: true,
                }),
                new TextRun(segment.text),
              ],
            });
          }),
          new Paragraph({ text: "Decisions", heading: HeadingLevel.HEADING_1 }),
          ...(meeting.decisions ?? []).map(
            (decision, index) =>
              new Paragraph(`${index + 1}. ${decision.text}`),
          ),
          new Paragraph({
            text: "Action items",
            heading: HeadingLevel.HEADING_1,
          }),
          new Table({
            rows: [
              new TableRow({
                children: ["Task", "Owner", "Deadline"].map(
                  (text) =>
                    new TableCell({
                      children: [
                        new Paragraph({
                          children: [new TextRun({ text, bold: true })],
                        }),
                      ],
                    }),
                ),
              }),
              ...(meeting.actionItems ?? []).map(
                (item) =>
                  new TableRow({
                    children: [
                      item.task,
                      ownerName(item.ownerStaffId),
                      item.deadline ?? "No deadline",
                    ].map(
                      (text) =>
                        new TableCell({ children: [new Paragraph(text)] }),
                    ),
                  }),
              ),
            ],
          }),
          new Paragraph({
            text: "Meeting metadata",
            heading: HeadingLevel.HEADING_1,
          }),
          new Paragraph(`Meeting ID: ${meeting.id}`),
          new Paragraph(
            `Recording duration: ${formatTime(meeting.durationSeconds ?? 0)}`,
          ),
          new Paragraph(`Generated at: ${new Date().toISOString()}`),
        ],
      },
    ],
  });
  return Packer.toBlob(document);
}

export async function downloadMinutesDocx(
  meeting: Meeting,
  lang?: MinutesLanguage,
) {
  if (serverDocument(meeting, "docx", lang)) return;
  const blob = await createMinutesDocx(meeting);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = minutesDocxFilename(meeting);
  anchor.click();
  URL.revokeObjectURL(url);
}
