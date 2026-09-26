import { DEMO_SESSION_KEY, saveDemoSession } from "../src/auth/demoSession";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import i18n from "../src/i18n/i18n";
import { routes } from "../src/router";
import { getMeeting, getMeetings, updateMeeting } from "../src/api/meetings";
import { readStore, writeStore } from "../src/mock/store";
import { notifyUpdate } from "../src/hooks/useData";
beforeEach(async () => {
  await i18n.changeLanguage("en");
});
function mount(path = "/meetings", auth = true) {
  if (auth) saveDemoSession();
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}
describe("application flows", () => {
  it("keeps the signed-out page free of participant data and supports keyboard login", async () => {
    const user = userEvent.setup();
    mount("/login", false);
    expect(screen.queryByText(/Secure MOM/i)).toBeNull();
    expect(screen.queryByText("Elena Ciobanu")).toBeNull();
    expect(screen.queryByText("Dr. Ana Popescu")).toBeNull();
    const username = screen.getByLabelText("Username");
    const password = screen.getByLabelText("Password");
    await user.clear(username);
    await user.type(username, "admin@medpark.local");
    await user.type(password, "wrong{Enter}");
    await screen.findByRole("alert");
    expect((password as HTMLInputElement).value).toBe("");
    await user.type(password, "test-only-demo-password{Enter}");
    await screen.findByRole("heading", { name: "Start a meeting" });
  });
  it("protects routes, rejects invalid credentials, accepts normalized demo username and logs out", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    mount("/meetings", false);
    await screen.findByRole("heading", { name: "Sign in" });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("alert");
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: " ADMIN@MEDPARK.LOCAL " },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "test-only-demo-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("heading", { name: "Start a meeting" });
    expect(sessionStorage.getItem(DEMO_SESSION_KEY)).not.toBeNull();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByText("Administrator")).toBeTruthy();
    expect(screen.getByText("admin@medpark.local")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Account" }).textContent).toBe(
      "AD",
    );
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    await screen.findByRole("heading", { name: "Sign in" });
    expect(sessionStorage.getItem(DEMO_SESSION_KEY)).toBeNull();
  });
  it("creates an upload meeting without assuming room participants", async () => {
    mount();
    await screen.findByRole("heading", { name: "Start a meeting" });
    fireEvent.click(screen.getByRole("link", { name: /Medical Sends to/ }));
    await screen.findByRole("heading", { name: "Medical meeting" });
    expect(screen.queryByRole("combobox")).toBeNull();
    fireEvent.click(
      screen.getByRole("button", { name: /Upload a recording WAV/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Drop the recording here" });
    const m = (await getMeetings())[0];
    expect(m.type).toBe("medical");
    expect(m.title).toContain("Medical meeting");
    expect(m.participants).toEqual([]);
    expect(m.inputMode).toBe("upload");
  });
  it("switches language, persists it, and leaves the original transcript untouched", async () => {
    mount("/meetings/meeting-001/transcript?at=728");
    await screen.findByText(/Да, я подтвержу/);
    const raw = screen.getByText(/Да, я подтвержу/).textContent;
    fireEvent.click(screen.getByRole("button", { name: "Română" }));
    await screen.findByLabelText("Caută în transcriere");
    expect(localStorage.getItem("secure-mom-language")).toBe("ro");
    expect(screen.getByText(/Да, я подтвержу/).textContent).toBe(raw);
    expect(document.documentElement.lang).toBe("ro");
    fireEvent.click(screen.getByRole("button", { name: "Русский" }));
    await screen.findByLabelText("Поиск в транскрипции");
    expect(screen.getByText(/Да, я подтвержу/).textContent).toBe(raw);
  });
  it("edits summary and an action item, and persists completion across pages", async () => {
    mount("/meetings/meeting-001/minutes");
    await screen.findByRole("heading", { name: "Summary" });
    fireEvent.click(screen.getByRole("button", { name: "Edit Summary" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Summary" }), {
      target: { value: "The updated summary." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("The updated summary.");
    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Task"), {
      target: { value: "Updated task" },
    });
    fireEvent.change(within(dialog).getByLabelText("Owner"), {
      target: { value: "elena" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await screen.findByText("Updated task");
    fireEvent.click(screen.getByRole("checkbox", { name: "Updated task" }));
    await waitFor(async () =>
      expect((await getMeeting("meeting-001")).actionItems?.[0].completed).toBe(
        true,
      ),
    );
  });
  it("requires manual review and supports explicit send with a simulated receipt", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response('<svg xmlns="http://www.w3.org/2000/svg"></svg>', {
            status: 200,
            headers: { "Content-Type": "image/svg+xml" },
          }),
      ),
    );
    await updateMeeting("meeting-001", {
      status: "ready",
      sendMode: "manual",
      reviewState: "needs_review",
      sendScheduledAt: null,
    });
    mount("/meetings/meeting-001/minutes");
    fireEvent.click(
      await screen.findByRole("button", { name: "Mark review complete" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Preview email" }),
    );
    await screen.findByText("Email preview");
    expect(screen.getByText(/Minutes\.docx$/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    // Send goes straight to the delivery page (ISSUE-003)
    await screen.findByRole(
      "heading",
      { name: "Delivery confirmed" },
      { timeout: 3000 },
    );
    await screen.findByText(
      "Demo delivery simulated locally. No email was sent.",
    );
    expect(screen.queryByRole("button", { name: "Send now" })).toBeNull();
    expect((await getMeeting("meeting-001")).delivery).toMatchObject({
      status: "sent",
      attachmentFilename: expect.stringMatching(/Minutes\.docx$/),
    });
  });
  it("keeps voice profiles separate from unidentified speaker clusters", async () => {
    mount("/people");
    await screen.findByRole("heading", { name: "People" });
    expect(
      screen.getByRole("heading", { name: "Voice profiles" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Voices to identify" }),
    ).toBeTruthy();
    expect(screen.getByText("Speaker 4")).toBeTruthy();
    expect(screen.queryByText("Victor Munteanu")).toBeNull();
    expect(
      screen
        .getByRole("button", { name: "Play sample" })
        .hasAttribute("disabled"),
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Identify person" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Victor Munteanu")).toBeTruthy();
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Victor Munteanu/ }),
    );
    await screen.findByText("Identified manually");
    expect(screen.getByText("Voice profile not enrolled")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Enroll a voice" }).getAttribute("href"),
    ).toBe("/people/victor/enroll");
  });
  it("handles history search and missing meetings without a blank page", async () => {
    const view = mount("/history");
    await screen.findByLabelText("Search meetings, people or words said");
    expect(view.container.querySelector(".department-tile")).toBeNull();
    fireEvent.change(
      screen.getByLabelText("Search meetings, people or words said"),
      { target: { value: "no such meeting" } },
    );
    await screen.findByText("No matching results");
    view.unmount();
    mount("/meetings/missing/minutes");
    await screen.findByText("This item was not found. Return to meetings.");
  });
  it("renders real templates and prefills New Meeting without starting recording", async () => {
    mount("/templates");
    await screen.findByRole("heading", { name: "Templates" });
    expect(screen.getByText("Tumor board")).toBeTruthy();
    expect(screen.getAllByText("AP").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "New template" })).toBeTruthy();
    fireEvent.click(screen.getAllByRole("link", { name: "Start" })[0]);
    await screen.findByDisplayValue("Tumor board");
    expect(screen.getByText(/Dr. Ana Popescu/)).toBeTruthy();
    expect(screen.getByText(/New oncology cases/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Pause" })).toBeNull();
  });
  it("provides admin-only governance routes and working account creation", async () => {
    mount("/admin/users");
    await screen.findByRole("heading", { name: "Users" });
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "staff.user" },
    });
    fireEvent.change(screen.getByLabelText("Email (optional)"), {
      target: { value: "staff.user@medpark.local" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await screen.findByText("staff.user");
  });
  it("shows background processing completion when returning to meetings", async () => {
    mount();
    await screen.findByRole("heading", { name: "Start a meeting" });
    await updateMeeting("meeting-001", {
      status: "processing",
      processingStartedAt: new Date(Date.now() - 13000).toISOString(),
      processingEndsAt: new Date(Date.now() - 1000).toISOString(),
    });
    act(() => notifyUpdate());
    await waitFor(() =>
      expect(screen.getAllByText("Ready for review").length).toBeGreaterThan(0),
    );
  });
});

describe("upload and empty/error states", () => {
  it("accepts a checked dropped file, supports remove/replace and starts processing", async () => {
    const { createMeeting, getPeople } = await import("../src/api/meetings");
    const m = await createMeeting({
      title: "Upload test",
      type: "medical",
      inputMode: "upload",
      participants: await getPeople(),
    });
    const createURL = vi.fn(() => "blob:test-audio");
    vi.stubGlobal(
      "URL",
      class extends URL {
        static createObjectURL = createURL;
        static revokeObjectURL = vi.fn();
      },
    );
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
    mount(`/meetings/${m.id}/upload`);
    const drop = (
      await screen.findByRole("heading", { name: "Drop the recording here" })
    ).closest("section")!;
    fireEvent.drop(drop, {
      dataTransfer: {
        files: [
          new File(["audio fixture"], "meeting.mp3", { type: "audio/mpeg" }),
        ],
      },
    });
    await screen.findByText("Uploaded and checked");
    expect(
      screen
        .getByRole("button", { name: "Write the minutes" })
        .hasAttribute("disabled"),
    ).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.queryByText("Uploaded and checked")).toBeNull();
    fireEvent.drop(drop, {
      dataTransfer: {
        files: [
          new File(["replacement"], "replacement.m4a", { type: "audio/mp4" }),
        ],
      },
    });
    await screen.findByText("replacement.m4a");
    fireEvent.click(screen.getByRole("button", { name: "Write the minutes" }));
    await screen.findByText("Audio prepared");
    expect((await getMeeting(m.id)).status).toBe("processing");
    expect((await getMeeting(m.id)).audioFilename).toBe("replacement.m4a");
  });
  it("rejects a misleading upload before metadata decoding", async () => {
    mount("/meetings/meeting-001/upload");
    const drop = (
      await screen.findByRole("heading", { name: "Drop the recording here" })
    ).closest("section")!;
    fireEvent.drop(drop, {
      dataTransfer: {
        files: [new File(["bad"], "meeting.mp3", { type: "text/html" })],
      },
    });
    await screen.findByText(/Not an audio file/);
    expect(screen.queryByText("Uploaded and checked")).toBeNull();
  });
});

describe("final Figma states", () => {
  it("renders a real 404 and returns to meetings", async () => {
    mount("/route-that-does-not-exist");
    await screen.findByRole("heading", { name: "This page isn't here" });
    fireEvent.click(screen.getByRole("link", { name: "Back to meetings" }));
    await screen.findByRole("heading", { name: "Start a meeting" });
  });
  it("signs out after inactivity, preserves meetings, and shows the timeout notice", async () => {
    vi.useFakeTimers();
    const count = readStore().meetings.length;
    mount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30 * 60 * 1000);
    });
    expect(screen.getByText(/signed out after 30 minutes/)).toBeTruthy();
    expect(readStore().meetings).toHaveLength(count);
    expect(sessionStorage.getItem(DEMO_SESSION_KEY)).toBeNull();
  });
  it("activity resets the inactivity timer", async () => {
    vi.useFakeTimers();
    mount();
    await act(async () => vi.advanceTimersByTime(29 * 60 * 1000));
    fireEvent.keyDown(window, { key: "Tab" });
    await act(async () => vi.advanceTimersByTime(2 * 60 * 1000));
    expect(screen.queryByText(/signed out after 30 minutes/)).toBeNull();
    expect(sessionStorage.getItem(DEMO_SESSION_KEY)).not.toBeNull();
  });
  it("shows queued and failed processing states with deterministic retry", async () => {
    await updateMeeting("meeting-001", {
      status: "processing",
      processingState: "queued",
    });
    let view = mount("/meetings/meeting-001/processing");
    await screen.findByRole("heading", {
      name: "Waiting for another meeting to finish",
    });
    view.unmount();
    await updateMeeting("meeting-001", {
      status: "failed",
      processingState: "failed",
      failureReference: "PROC-DEMO",
    });
    view = mount("/meetings/meeting-001/processing");
    await screen.findByText("PROC-DEMO", { exact: false });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(async () =>
      expect((await getMeeting("meeting-001")).processingState).toBe("running"),
    );
    view.unmount();
  });
  it("renders the dedicated sending stopped and delivery failure states", async () => {
    await updateMeeting("meeting-001", {
      status: "ready",
      deliveryState: "stopped",
      reviewState: "needs_review",
      sendScheduledAt: null,
    });
    let view = mount("/meetings/meeting-001/minutes");
    await screen.findByText("Review before sending");
    expect(screen.queryByRole("progressbar")).toBeNull();
    view.unmount();
    await updateMeeting("meeting-001", {
      status: "ready",
      deliveryState: "failed",
      reviewState: "reviewed",
    });
    view = mount("/meetings/meeting-001/minutes");
    await screen.findByRole("heading", {
      name: "Minutes are ready but weren't sent",
    });
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Send now" }));
    await waitFor(async () =>
      expect((await getMeeting("meeting-001")).deliveryState).toBe("sending"),
    );
    view.unmount();
  });
  it("shows the first-day state without empty dashboard sections", async () => {
    const store = readStore();
    store.meetings = [];
    writeStore(store);
    mount();
    expect(
      await screen.findAllByRole("heading", { name: "No meetings yet" }),
    ).toHaveLength(2);
    expect(screen.queryByText("Your action items")).toBeNull();
    expect(screen.queryByText("Recent meetings")).toBeNull();
  });
});

describe("major route translations", () => {
  for (const language of ["en", "ro", "ru"]) {
    it(`renders major screens in ${language} without missing interface keys`, async () => {
      await i18n.changeLanguage(language);
      const routes = [
        ["/meetings", "startMeeting"],
        ["/action-items", "actions"],
        ["/history", "history"],
        ["/people", "people"],
        ["/system", "system"],
        ["/meetings/meeting-001/minutes", "summary"],
        ["/meetings/meeting-002/sent", "deliveryConfirmed"],
      ];
      for (const [route, key] of routes) {
        const view = mount(route);
        expect(
          await screen.findByRole("heading", {
            name: i18n.t(key),
            exact: true,
          }),
        ).toBeTruthy();
        expect(document.documentElement.lang).toBe(language);
        view.unmount();
      }
    });
  }
});
