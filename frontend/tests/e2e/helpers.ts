import { expect, type Page } from "@playwright/test";

export const REAL = Boolean(process.env.E2E_BACKEND);
export const SHOTS = process.env.SHOTS_DIR;

// A short silent WAV, so the browser reads its duration the way it would a
// meeting recording.
export function silentWav(seconds = 2, rate = 16000): Buffer {
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

export async function shot(page: Page, name: string) {
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

export async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin@medpark.local");
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByLabel("Password").press("Enter");
  await page.waitForURL("**/meetings");
}

/** Upload a recording as a new meeting and wait until the minutes page. */
export async function uploadMeeting(
  page: Page,
  type: "medical" | "executive",
  onProcessing?: () => Promise<void>,
) {
  await login(page);
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
    await onProcessing?.();
  }
  await page.waitForURL(/\/minutes$/, { timeout: 30_000 });
}
