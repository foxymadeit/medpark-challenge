import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import i18n from "../src/i18n/i18n";
import { routes } from "../src/router";
import { saveDemoSession } from "../src/auth/demoSession";
import { readStore, writeStore } from "../src/mock/store";
import ProcessingStages from "../src/components/ProcessingStages";
import type { Meeting } from "../src/types/meeting";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

function mount(path: string) {
  saveDemoSession();
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

/** A ready meeting shaped like the real backend's minutes payload. */
function seedReadyMeeting(extra: Partial<Meeting>) {
  const store = readStore();
  const m =
    store.meetings.find((x) => x.status === "ready") ?? store.meetings[0];
  Object.assign(m, {
    status: "ready",
    reviewState: "needs_review",
    documents: ["ro", "ru", "en"],
    checked: { verified: 11, total: 11 },
    minutesByLanguage: {
      en: {
        summary: "The board agreed a cardiac MRI.",
        decisions: [{ id: "D1", text: "Cardiac MRI before surgery" }],
        actionItems: [],
      },
      ro: {
        summary: "Consiliul a aprobat o RMN cardiacă.",
        decisions: [{ id: "D1", text: "RMN cardiacă înainte de intervenție" }],
        actionItems: [],
      },
    },
    ...extra,
  });
  writeStore(store);
  return m;
}

describe("real pipeline screens", () => {
  it("shows live stages with the count, the running step and clock-time ETAs", () => {
    render(
      <ProcessingStages
        stages={[
          {
            id: "transcribe",
            state: "done",
            finishedAt: "2026-09-26T12:13:40Z",
          },
          { id: "verify", state: "running", done: 31, total: 45 },
          { id: "render", state: "pending", etaAt: "2026-09-26T12:18:00Z" },
        ]}
      />,
    );
    expect(screen.getByText("31 of 45")).toBeTruthy();
    const current = screen.getByRole("listitem", { current: "step" });
    expect(current.textContent).toContain(
      "Checking each item against the transcript",
    );
    expect(within(current).getByText("now")).toBeTruthy();
    expect(screen.getByText(/^about /)).toBeTruthy();
  });

  it("holds sending until every unconfirmed item is kept or taken out", async () => {
    const user = userEvent.setup();
    const m = seedReadyMeeting({
      confirmItems: [
        {
          id: "C1",
          text: "Order replacement ECG leads",
          reason: "No owner was named.",
        },
        {
          id: "C2",
          text: "Share the ward rota",
          reason: "The deadline was not clear.",
        },
      ],
    });
    mount(`/meetings/${m.id}/minutes`);
    await screen.findByText("2 items need a person before sending");
    const next = screen.getByRole("button", { name: "Continue to sending" });
    expect((next as HTMLButtonElement).disabled).toBe(true);
    await user.click(
      screen.getByRole("button", {
        name: "Take out: Order replacement ECG leads",
      }),
    );
    await screen.findByText("Taken out");
    expect((next as HTMLButtonElement).disabled).toBe(true);
    await user.click(
      screen.getByRole("button", { name: "Keep: Share the ward rota" }),
    );
    await screen.findByText("Kept");
    expect(
      (
        screen.getByRole("button", {
          name: "Continue to sending",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
    expect(
      readStore()
        .meetings.find((x) => x.id === m.id)!
        .confirmItems!.map((c) => c.decision),
    ).toEqual(["remove", "keep"]);
  });

  it("switches the minutes language and links each language's PDF and DOCX", async () => {
    const user = userEvent.setup();
    const m = seedReadyMeeting({ confirmItems: [] });
    mount(`/meetings/${m.id}/minutes`);
    await screen.findByText("The board agreed a cardiac MRI.");
    await user.click(screen.getByRole("button", { name: "RO" }));
    await screen.findByText("Consiliul a aprobat o RMN cardiacă.");
    const docs = screen.getByRole("region", { name: "Documents" });
    const links = within(docs)
      .getAllByRole("link")
      .map((a) => a.getAttribute("href"));
    expect(links).toContain(`/api/meetings/${m.id}/documents/ro.pdf`);
    expect(links).toContain(`/api/meetings/${m.id}/documents/en.docx`);
    expect(within(docs).getByText("11 of 11 items")).toBeTruthy();
  });
});
