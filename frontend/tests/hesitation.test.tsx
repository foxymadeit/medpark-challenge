// Each test here is a place where a person paused in the browser QA pass
// (26 Sep): the screen must now say what happens next, and the next step
// must be there.
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import i18n from "../src/i18n/i18n";
import { routes } from "../src/router";
import { getMeeting, updateMeeting } from "../src/api/meetings";
import { readStore, writeStore } from "../src/mock/store";
import type { Meeting } from "../src/types/meeting";
import { countByType } from "../src/api/routing";
import { personName } from "../src/utils";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

function mount(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return { router, ...render(<RouterProvider router={router} />) };
}

/** meeting-001, changed in place in the demo store. */
function seed(extra: Partial<Meeting>) {
  const store = readStore();
  const m = store.meetings.find((x) => x.id === "meeting-001")!;
  Object.assign(m, extra);
  writeStore(store);
  return m;
}

describe("sending after a stop", () => {
  it("offers Send now right where the countdown was", async () => {
    seed({
      status: "ready",
      sendMode: "manual",
      deliveryState: "stopped",
      reviewState: "needs_review",
      sendScheduledAt: null,
    });
    mount("/meetings/meeting-001/minutes");
    await screen.findByText("Sending stopped. Nothing went out.");
    fireEvent.click(screen.getByRole("button", { name: "Send now" }));
    await waitFor(async () =>
      expect((await getMeeting("meeting-001")).status).toBe("sending"),
    );
  });

  it("previews the real email and never blocks on a participant without an address", async () => {
    const m = seed({ status: "ready", reviewState: "reviewed" });
    m.participants[2] = { ...m.participants[2], email: undefined };
    seed({ participants: m.participants, participantSnapshots: undefined });
    mount("/meetings/meeting-001/email");
    // the email is official Romanian whatever the interface language
    await screen.findByText(
      /^Proces-verbal al ședinței Consiliului Medical din \d{1,2} (ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|septembrie|octombrie|noiembrie|decembrie) \d{4}$/,
    );
    const to = screen.getByText("To").closest("div")!;
    expect(within(to).getByText(/Dr\. Igor Rusu/).textContent).toContain(
      "No copy: no email",
    );
    expect(within(to).getByText(/Dr\. Ana Popescu/).textContent).toContain(
      "ana.popescu@medpark.local",
    );
    expect(screen.queryByText(/valid email address/)).toBeNull();
    const body = screen.getByRole("region", { name: "Message" }).textContent!;
    expect(body.startsWith("Stimați membri ai Consiliului Medical,")).toBe(
      true,
    );
    expect(body).toContain("Regulamentul (UE) 2024/1689");
    expect(body.endsWith("Cu stimă,\nSecretariatul Consiliului Medical")).toBe(
      true,
    );
    // the meeting's own words travel in the PDFs, never in the email
    expect(body).not.toContain("Book the cardiac MRI for bed 12");
    expect(body).not.toMatch(/Summary|Decisions|Owner|Minutes/);
    expect(
      (screen.getByRole("button", { name: "Send" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });
});

describe("the meeting-type check", () => {
  it("says where the minutes go after each choice and counts only open items", async () => {
    const user = userEvent.setup();
    seed({
      type: "medical",
      status: "ready",
      reviewState: "needs_review",
      confirmItems: [
        { id: "C1", text: "Order new leads.", reason: "No owner was named." },
        {
          id: "meeting-type",
          text: "Meeting type: medical",
          reason: "",
          detectedType: "executive",
        },
      ],
    });
    mount("/meetings/meeting-001/minutes");
    await screen.findByText("2 items need a person before sending");
    const typeSection = screen.getByRole("group", { name: "Meeting type" });
    within(typeSection).getByText(
      "Set to go to the Medical board. The first 3 minutes sound like a meeting for the Executive board.",
    );
    await user.click(
      within(typeSection).getByRole("button", {
        name: "Send to Executive board",
      }),
    );
    await within(typeSection).findByText("Sent to Executive board");
    within(typeSection).getByText(
      "Now going to the Executive board, as the first 3 minutes suggested.",
    );
    await screen.findByText("One item needs a person before sending");
    await user.click(
      screen.getByRole("button", { name: "Keep: Order new leads." }),
    );
    await screen.findByText("All settled");
  });

  it("keeps the chosen board in plain words", async () => {
    const user = userEvent.setup();
    seed({
      type: "medical",
      status: "ready",
      confirmItems: [
        {
          id: "meeting-type",
          text: "Meeting type: medical",
          reason: "",
          detectedType: "executive",
        },
      ],
    });
    mount("/meetings/meeting-001/minutes");
    await user.click(
      await screen.findByRole("button", { name: "Keep Medical board" }),
    );
    await screen.findByText("Kept Medical board");
  });
});

describe("the send window after settling flagged items", () => {
  it("opens the window instead of sending at once, and stopping it leaves Send now", async () => {
    const user = userEvent.setup();
    seed({
      status: "ready",
      sendMode: "auto",
      sendWindowSeconds: 60,
      reviewState: "needs_review",
      confirmItems: [
        { id: "C1", text: "Order new leads.", reason: "No owner was named." },
      ],
    });
    mount("/meetings/meeting-001/minutes");
    await user.click(
      await screen.findByRole("button", { name: "Keep: Order new leads." }),
    );
    await user.click(
      screen.getByRole("button", { name: "Continue to sending" }),
    );
    await screen.findByText(/Sending to the Medical board in/);
    expect((await getMeeting("meeting-001")).status).toBe("ready");
    await user.click(screen.getByRole("button", { name: "Stop sending" }));
    await screen.findByText("Sending stopped. Nothing went out.");
    expect(screen.getByRole("button", { name: "Send now" })).toBeTruthy();
    expect((await getMeeting("meeting-001")).status).toBe("ready");
  });
});

describe("while and before sending", () => {
  it("says Sending while the mail goes, not the review bar", async () => {
    seed({ status: "sending", deliveryState: "sending" });
    mount("/meetings/meeting-001/minutes");
    await screen.findByText("Sending to the Medical board…");
    expect(screen.queryByText("Review complete")).toBeNull();
    expect(screen.queryByText(/explicit send/)).toBeNull();
  });

  it("asks to fix an owner only when an action lacks one or a deadline", async () => {
    const soon = new Date(Date.now() + 45_000).toISOString();
    const m = seed({
      status: "sending_soon",
      sendMode: "auto",
      sendScheduledAt: soon,
      sendWindowSeconds: 60,
    });
    let view = mount("/meetings/meeting-001/minutes");
    await screen.findByText(/Sending to the Medical board in/);
    expect(screen.queryByText(/before it goes/)).toBeNull();
    view.unmount();
    m.actionItems![0] = { ...m.actionItems![0], deadline: null };
    seed({ actionItems: m.actionItems });
    view = mount("/meetings/meeting-001/minutes");
    await screen.findByText(/before it goes/);
    view.unmount();
  });
});

describe("processing", () => {
  it("says Starting until the server reports a place in the queue", async () => {
    await updateMeeting("meeting-001", {
      status: "processing",
      processingState: "queued",
    });
    let view = mount("/meetings/meeting-001/processing");
    await screen.findByText("Starting…");
    expect(
      screen.queryByText("Waiting for another meeting to finish"),
    ).toBeNull();
    view.unmount();
    await updateMeeting("meeting-001", { queuePosition: 1 });
    view = mount("/meetings/meeting-001/processing");
    await screen.findByText("Waiting for another meeting to finish");
    view.unmount();
  });
});

describe("new meeting", () => {
  it("opens the file picker from the Upload card, then goes straight to Write the minutes", async () => {
    vi.stubGlobal(
      "Audio",
      class {
        duration = 120;
        onloadedmetadata: (() => void) | null = null;
        onerror: (() => void) | null = null;
        preload = "";
        set src(_value: string) {
          queueMicrotask(() => this.onloadedmetadata?.());
        }
        removeAttribute() {}
        load() {}
      },
    );
    const picker = vi
      .spyOn(HTMLInputElement.prototype, "click")
      .mockImplementation(() => {});
    const { router } = mount("/meetings/new/medical");
    fireEvent.click(
      await screen.findByRole("button", { name: /Upload a recording/ }),
    );
    expect(picker).toHaveBeenCalledTimes(1);
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    fireEvent.change(input, {
      target: {
        files: [new File(["x"], "meeting.mp3", { type: "audio/mpeg" })],
      },
    });
    await screen.findByText("meeting.mp3", {}, { timeout: 5000 });
    expect(router.state.location.pathname).toMatch(/\/upload$/);
    expect(
      (
        screen.getByRole("button", {
          name: "Write the minutes",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });

  it("names the device neutrally", async () => {
    mount("/meetings/new/medical");
    await screen.findByText("Uses this device’s microphone.");
    expect(screen.queryByText(/laptop/)).toBeNull();
  });
});

describe("system page", () => {
  for (const language of ["en", "ro", "ru"]) {
    it(`names each service once, in ${language}, and describes automatic sending as it is`, async () => {
      await i18n.changeLanguage(language);
      mount("/system");
      await screen.findByRole("heading", { name: i18n.t("system") });
      const names = [...document.querySelectorAll(".service-row strong")].map(
        (r) => r.textContent,
      );
      expect(new Set(names).size).toBe(names.length);
      expect(names).not.toContain("llm");
      if (language !== "en")
        for (const english of ["Minutes writer", "Minutes", "Local mail"])
          expect(names).not.toContain(english);
      const auto = screen.getByRole("heading", {
        name: i18n.t("autoMode"),
      }).parentElement!;
      expect(auto.textContent).not.toMatch(/Future|Opțiune viitoare|Будущая/);
      expect(auto.textContent).toMatch(/60/);
    });
  }
});

describe("routing", () => {
  it("counts recipients in the old and the new /api/routing shapes", () => {
    expect(
      countByType([
        ["medical", ["medical-board@x", "admin-board@x"]],
        ["executive", { name: "Executive board", recipients: ["exec@x"] }],
        ["administrative", { name: "Administrative board", recipients: 3 }],
        ["unknown", ["x@x"]],
      ]),
    ).toEqual({ medical: 2, executive: 1, administrative: 3 });
  });
});

describe("detected speakers", () => {
  it("read as Participant N in the interface language; given names stay", async () => {
    const detected = { name: "Participant 3", speakerNumber: 3 };
    expect(personName(detected, i18n.t)).toBe("Participant 3");
    await i18n.changeLanguage("ro");
    expect(personName(detected, i18n.t)).toBe("Participantul 3");
    await i18n.changeLanguage("ru");
    expect(personName({ name: "", speakerNumber: 3 }, i18n.t)).toBe(
      "Участник 3",
    );
    expect(
      personName({ name: "Dr. Ana Popescu", speakerNumber: 3 }, i18n.t),
    ).toBe("Dr. Ana Popescu");
    expect(personName({ name: "Elena Ciobanu" }, i18n.t)).toBe("Elena Ciobanu");
  });
});
