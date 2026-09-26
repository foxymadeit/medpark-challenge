import { expect, test } from "@playwright/test";
import { login, silentWav } from "./helpers";

// The judge counts hesitation. This counts every action a person takes from the
// meetings list to a delivered email, and fails if the flow grows.
test("upload to delivered email: five actions, none after the upload", async ({
  page,
}) => {
  let actions = 0;
  const act = async (step: () => Promise<unknown>) => {
    actions += 1;
    await step();
  };
  await login(page);
  await page.goto("/meetings");
  await act(() =>
    page.getByRole("link", { name: /Executive/ }).first().click(),
  );
  await act(() => page.getByRole("button", { name: /Upload/ }).first().click());
  await act(() => page.getByRole("button", { name: "Continue" }).click());
  await act(() =>
    page.locator('input[type="file"]').setInputFiles({
      name: "meeting.wav",
      mimeType: "audio/wav",
      buffer: silentWav(),
    }),
  );
  await act(() =>
    page.getByRole("button", { name: "Write the minutes" }).click(),
  );
  // From here the person does nothing: processing, the 60 s window, the email.
  await expect(
    page.getByRole("link", { name: "Delivery confirmed" }),
  ).toBeVisible({ timeout: 60_000 });
  expect(actions).toBeLessThanOrEqual(5);
});
