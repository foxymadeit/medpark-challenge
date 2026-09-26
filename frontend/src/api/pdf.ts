import type { Meeting } from "../types/meeting";

function clean(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[^\x20-\x7e]/g, "?")
    .replace(/[()\\]/g, "\\$&");
}

export function createMinutesPdf(meeting: Meeting) {
  const lines = [
    meeting.title,
    "",
    "Summary",
    meeting.summary ?? "",
    "",
    "Decisions",
    ...(meeting.decisions ?? []).map((item) => `- ${item.text}`),
    "",
    "Action items",
    ...(meeting.actionItems ?? []).map((item) => `- ${item.task}`),
  ].flatMap((line) => clean(line).match(/.{1,88}(?:\s|$)|.{1,88}/g) ?? [""]);
  const text = lines
    .map(
      (line, index) =>
        `BT /F1 11 Tf 56 ${790 - index * 16} Td (${line.trim()}) Tj ET`,
    )
    .join("\n");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets
    .slice(1)
    .map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`)
    .join("");
  pdf += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new Blob([pdf], { type: "application/pdf" });
}

export function downloadMinutesPdf(meeting: Meeting) {
  const blob = createMinutesPdf(meeting);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${
    meeting.title
      .replace(/[^a-z0-9]+/gi, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase() || "minutes"
  }.pdf`;
  link.click();
  URL.revokeObjectURL(url);
}
