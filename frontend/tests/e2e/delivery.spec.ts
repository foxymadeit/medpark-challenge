import { readdirSync, readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { REAL, shot, uploadMeeting } from "./helpers";

const MAIL_DIR = process.env.MAIL_DIR ?? "/tmp/liminal-mail";

test("medical: flagged item, then confirm, then sent with the PDFs", async ({
  page,
}) => {
  await uploadMeeting(page, "medical", () => shot(page, "02-processing"));

  await expect(
    page.getByText("One item needs a person before sending"),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText("No owner was named in the meeting."),
  ).toBeVisible();
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

  const minutesLanguage = page.getByRole("group", { name: "Minutes in:" });
  if (await minutesLanguage.count()) {
    await minutesLanguage.getByRole("button", { name: "Română" }).click();
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
  await expect(
    page.getByText("Sending stopped. Nothing went out."),
  ).toBeVisible();
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
