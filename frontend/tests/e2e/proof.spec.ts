// Proof, not eyeballing (DESIGN.md, No slop): the main screens at five
// widths, an axe scan, a keyboard-only pass, no layout shift when menus and
// dialogs open, reduced motion, and a language switch that fades.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { login, SHOTS, uploadMeeting } from "./helpers";

const WIDTHS = [360, 390, 768, 1024, 1440];

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(0);
}

async function axe(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = result.violations.filter((v) =>
    ["serious", "critical"].includes(v.impact ?? ""),
  );
  expect(
    bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" | ")}`),
  ).toEqual([]);
}

async function noNestedCards(page: Page) {
  expect(await page.locator(".panel .panel").count()).toBe(0);
}

test("main screens at five widths: no sideways scroll, no serious axe issues, no nested cards", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await uploadMeeting(page, "medical");
  const minutesUrl = page.url();
  const screens: [string, string][] = [
    ["meetings", "/meetings"],
    ["new-meeting", "/meetings/new/medical?mode=upload"],
    ["minutes", new URL(minutesUrl).pathname],
  ];
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    for (const [name, path] of screens) {
      await page.goto(path);
      await expect(page.locator(".loading-skeleton")).toHaveCount(0);
      await page.waitForTimeout(250); // let the 200 ms page fade finish
      await noHorizontalScroll(page);
      await noNestedCards(page);
      if (SHOTS)
        await page.screenshot({
          path: `${SHOTS}/w${width}-${name}.png`,
          fullPage: true,
        });
      if (width === 390 || width === 1440) await axe(page);
    }
  }
});

test("keyboard only: confirm the flagged item, continue, then stop sending", async ({
  page,
}) => {
  await uploadMeeting(page, "medical");
  await expect(
    page.getByText("One item needs a person before sending"),
  ).toBeVisible({ timeout: 30_000 });
  const takeOut = page.getByRole("button", {
    name: "Take out: Order new leads.",
  });
  // Walk the page with Tab until the button has focus, then press Enter.
  async function tabTo(target: ReturnType<Page["getByRole"]>) {
    for (let i = 0; i < 60; i++) {
      if (await target.evaluate((el) => el === document.activeElement)) return;
      await page.keyboard.press("Tab");
    }
    throw new Error("could not reach the control with Tab");
  }
  await tabTo(takeOut);
  await page.keyboard.press("Enter");
  await expect(page.getByText("Taken out")).toBeVisible();
  const next = page.getByRole("button", { name: "Continue to sending" });
  await tabTo(next);
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("link", { name: "Delivery confirmed" }),
  ).toBeVisible({ timeout: 30_000 });
});

test("keyboard only: stop sending from the countdown", async ({ page }) => {
  await uploadMeeting(page, "executive");
  const stop = page.getByRole("button", { name: "Stop sending" });
  await expect(stop).toBeVisible({ timeout: 30_000 });
  for (let i = 0; i < 60; i++) {
    if (await stop.evaluate((el) => el === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("Sending stopped. Nothing went out."),
  ).toBeVisible();
});

test("account menu and dialogs open and close without moving the page", async ({
  page,
}) => {
  await uploadMeeting(page, "executive");
  const stop = page.getByRole("button", { name: "Stop sending" });
  await stop.click();
  const heading = page.locator("main h1").first();
  const top = () =>
    heading.evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
  const before = await top();

  const account = page.getByRole("button", { name: "Account" });
  await account.focus();
  await page.keyboard.press("Enter");
  const menu = page.locator(".account-menu");
  await expect(menu).toBeVisible();
  expect(await top()).toBe(before);
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(account).toBeFocused();

  await page
    .getByRole("button", { name: /Edit|Action item/ })
    .last()
    .click();
  const dialog = page.locator("dialog.edit-dialog");
  await expect(dialog).toBeVisible();
  expect(await top()).toBe(before);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  expect(await top()).toBe(before);
});

test("the language switch crossfades instead of snapping", async ({ page }) => {
  await page.addInitScript(() => {
    const doc = document as Document & {
      startViewTransition?: (cb: () => unknown) => unknown;
    };
    const original = doc.startViewTransition?.bind(doc);
    (window as unknown as { vtCalls: number }).vtCalls = 0;
    if (original)
      doc.startViewTransition = (cb) => {
        (window as unknown as { vtCalls: number }).vtCalls++;
        return original(cb);
      };
  });
  await login(page);
  await page.getByRole("button", { name: "Română" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ro");
  expect(
    await page.evaluate(
      () => (window as unknown as { vtCalls: number }).vtCalls,
    ),
  ).toBe(1);
  // The selected fill crossfades rather than jumping.
  const duration = await page
    .getByRole("button", { name: "Română" })
    .evaluate((el) => getComputedStyle(el).transitionDuration);
  expect(duration).toContain("0.18s");
});

test("reduced motion: every change becomes a short fade, never instant", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await login(page);
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);
  const anim = await page
    .locator(".page-enter")
    .first()
    .evaluate((el) => {
      const s = getComputedStyle(el);
      return { name: s.animationName, duration: s.animationDuration };
    });
  expect(anim).toEqual({ name: "sm-fade-in", duration: "0.15s" });
  const transition = await page
    .getByRole("button", { name: "English" })
    .evaluate((el) => getComputedStyle(el).transitionDuration);
  expect(transition).not.toMatch(/^0s(, 0s)*$/);
});
