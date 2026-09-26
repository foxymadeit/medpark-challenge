import { readdirSync, readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const SHOTS = process.env.SHOTS_DIR;
const MAIL_DIR = process.env.MAIL_DIR ?? "/tmp/liminal-mail";
const REAL = Boolean(process.env.E2E_BACKEND);

// A short silent WAV, so the browser reads its duration the way it would a
// meeting recording.
function silentWav(seconds = 2, rate = 16000): Buffer {
  const data = rate * seconds * 2;
  const b = Buffer.alloc(44 + data);
  b.write("RIFF", 0);
  b.writeUInt32LE(36 + data, 4);
  b.write("WAVEfmt ", 8);
  b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20);
  b.writeUInt16LE(1, 22);
  b.writeUInt32LE(rate, 24);
  b.writeUInt32LE(rate * 2, 28);
  b.writeUInt16LE(2, 32);
  b.writeUInt16LE(16, 34);
  b.write("data", 36);
  b.writeUInt32LE(data, 40);
  return b;
}

async function shot(page: Page, name: string) {
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

async function uploadMeeting(page: Page, type: "medical" | "executive") {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin@medpark.local");
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByLabel("Password").press("Enter");
  await page.waitForURL("**/meetings");
  await page.goto(`/meetings/new/${type}?mode=upload`);
  await expect(
    page.getByRole("checkbox", { name: /Send automatically/ }),
  ).toBeChecked();
  if (type === "medical") await shot(page, "01-new-meeting");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "meeting.wav",
    mimeType: "audio/wav",
    buffer: silentWav(),
  });
  await page.getByRole("button", { name: "Write the minutes" }).click();
  // The real backend's fake stages finish in under a second, so only the
  // mock (one stage per 0.7 s) holds the processing screen long enough.
  await page.waitForURL(/\/(processing|minutes)$/);
  if (!REAL) {
    await expect(
      page.getByRole("progressbar", { name: "Processing" }),
    ).toBeVisible();
    if (type === "medical") await shot(page, "02-processing");
  }
}

test("medical: flagged item, then confirm, then sent with the PDFs", async ({
  page,
}) => {
  await uploadMeeting(page, "medical");

  await expect(
    page.getByText("One item needs a person before sending"),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("No owner was named in the meeting.")).toBeVisible();
  await shot(page, "03-needs-confirmation");
  const next = page.getByRole("button", { name: "Continue to sending" });
  await expect(next).toBeDisabled();
  await page
    .getByRole("button", { name: "Take out: Order new leads." })
    .click();
  await expect(page.getByText("Taken out")).toBeVisible();
  await expect(next).toBeEnabled();

  const docs = page.getByRole("region", { name: "Documents" });
  await expect(docs.getByRole("link", { name: "PDF, Română" })).toHaveAttribute(
    "href",
    /documents\/ro\.pdf$/,
  );
  const href = await docs
    .getByRole("link", { name: "PDF, English" })
    .getAttribute("href");
  const pdf = await page.request.get(href!);
  expect(pdf.ok()).toBe(true);
  expect((await pdf.body()).subarray(0, 4).toString()).toBe("%PDF");

  const minutesLanguage = page.getByRole("group", { name: "Minutes language" });
  if (await minutesLanguage.count()) {
    await minutesLanguage.getByRole("button", { name: "RO" }).click();
    await expect(page.getByText(/Consiliul a aprobat/)).toBeVisible();
  }

  await next.click();
  await expect(
    page.getByRole("link", { name: "Delivery confirmed" }),
  ).toBeVisible({ timeout: 30_000 });
  await shot(page, "05-sent");
  if (REAL) {
    const mails = readdirSync(MAIL_DIR).map((f) =>
      readFileSync(`${MAIL_DIR}/${f}`, "latin1"),
    );
    expect(mails.length).toBeGreaterThan(0);
    expect(mails.some((m) => /MoM_[^"\s]*_ro\.pdf/.test(m))).toBe(true);
  }
});

test("executive: nothing flagged, the send window opens, stop returns it to review", async ({
  page,
}) => {
  await uploadMeeting(page, "executive");
  const stop = page.getByRole("button", { name: "Stop sending" });
  await expect(stop).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("progressbar", { name: "Sending status" }),
  ).toBeVisible();
  await shot(page, "04-countdown");
  await stop.click();
  await expect(stop).toHaveCount(0);
  await expect(page.getByText("Review before sending")).toBeVisible();
});

test("executive: the window runs out and the minutes go by themselves", async ({
  page,
}) => {
  await uploadMeeting(page, "executive");
  await expect(page.getByRole("button", { name: "Stop sending" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByRole("link", { name: "Delivery confirmed" }),
  ).toBeVisible({ timeout: 30_000 });
});
