import { expect, test } from "@playwright/test";
import { shot, uploadMeeting } from "./helpers";

test("the moderator names, merges and retitles before sending", async ({
  page,
}) => {
  await uploadMeeting(page, "medical");
  const people = page.getByRole("complementary").filter({ hasText: "People" });

  await people.getByRole("button", { name: "Name for Participant 2" }).click();
  const name = people.getByRole("textbox", { name: "Name for Participant 2" });
  await name.fill("Ana Rusu");
  await name.press("Enter");
  await expect(
    people.getByRole("button", { name: "Name for Ana Rusu" }),
  ).toBeVisible();
  await shot(page, "10-named");

  await people.getByRole("button", { name: "Merge Ana Rusu into" }).click();
  await people
    .getByRole("combobox", { name: "Merge Ana Rusu into" })
    .selectOption({ label: "Participant 1" });
  await people.getByRole("button", { name: "Merge", exact: true }).click();
  await expect(people.getByText("Ana Rusu")).toHaveCount(0);

  await page.getByRole("button", { name: "Edit title" }).click();
  const title = page.getByRole("textbox", { name: "Meeting title" });
  await title.fill("Consiliul medical, 26 septembrie");
  await title.press("Enter");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Consiliul medical, 26 septembrie",
    }),
  ).toBeVisible();
});
