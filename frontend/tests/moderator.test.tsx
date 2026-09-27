import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import i18n from "../src/i18n/i18n";
import { routes } from "../src/router";
import { readStore, writeStore } from "../src/mock/store";
import {
  mergeParticipant,
  nameProblem,
  renameMeeting,
  renameParticipant,
} from "../src/api/meetings";
import type { Meeting } from "../src/types/meeting";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

/** A ready meeting with three detected voices; voice 2 owns the action. */
function seed(extra: Partial<Meeting> = {}): Meeting {
  const store = readStore();
  const m = store.meetings[0];
  Object.assign(m, {
    status: "ready",
    reviewState: "needs_review",
    confirmItems: [],
    participants: [1, 2, 3].map((n) => ({
      id: `v${n}`,
      name: `Participant ${n}`,
      speakerNumber: n,
      speakerId: `Speaker ${n}`,
      speakerSlot: n - 1,
      speakingSeconds: n * 10,
    })),
    transcript: [
      {
        id: "s1",
        speakerId: "Speaker 1",
        startSeconds: 0,
        endSeconds: 2,
        text: "Bună ziua.",
      },
      {
        id: "s2",
        speakerId: "Speaker 2",
        startSeconds: 2,
        endSeconds: 4,
        text: "Trimit raportul.",
      },
    ],
    actionItems: [
      {
        id: "A1",
        task: "Send the report.",
        ownerParticipantId: "v2",
        deadline: null,
        completed: false,
      },
    ],
    ...extra,
  });
  writeStore(store);
  return m;
}
const stored = (id: string) => readStore().meetings.find((m) => m.id === id)!;

function mount(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

describe("the moderator names people and retitles before sending", () => {
  it("checks a name before it goes to the server", () => {
    const m = seed();
    expect(nameProblem(m, "v1", "  ")).toBe("required");
    expect(nameProblem(m, "v1", "x".repeat(81))).toBe("required");
    expect(nameProblem(m, "v1", "Participant 7")).toBe("nameIsNumber");
    expect(nameProblem(m, "v1", "участник 2")).toBe("nameIsNumber");
    m.participants[1].name = "Ana Rusu";
    expect(nameProblem(m, "v1", "ana rusu")).toBe("nameTaken");
    expect(nameProblem(m, "v2", "Ana Rusu")).toBe("");
    expect(nameProblem(m, "v1", " Ion  Popa ")).toBe("");
  });

  it("renames, merges and retitles in the demo store, never after sending", async () => {
    const m = seed();
    await renameParticipant(m.id, "v2", "  Ana   Rusu ");
    expect(stored(m.id).participants[1].name).toBe("Ana Rusu");
    expect(stored(m.id).participantSnapshots?.[1].nameAtMeeting).toBe(
      "Ana Rusu",
    );
    await mergeParticipant(m.id, "v2", "v1");
    const merged = stored(m.id);
    expect(merged.participants.map((p) => p.id)).toEqual(["v1", "v3"]);
    expect(merged.participants[0].speakingSeconds).toBe(30);
    expect(merged.actionItems?.[0].ownerParticipantId).toBe("v1");
    expect(merged.transcript?.map((s) => s.speakerId)).toEqual([
      "Speaker 1",
      "Speaker 1",
    ]);
    await renameMeeting(m.id, "  Consiliul medical, 26 septembrie ");
    expect(stored(m.id).title).toBe("Consiliul medical, 26 septembrie");
    seed({ status: "sent" });
    await expect(renameParticipant(m.id, "v1", "Ion")).rejects.toThrow(
      "alreadySent",
    );
    await expect(mergeParticipant(m.id, "v3", "v1")).rejects.toThrow(
      "alreadySent",
    );
    await expect(renameMeeting(m.id, "Too late")).rejects.toThrow(
      "alreadySent",
    );
  });

  it("names a participant from the People list with the keyboard", async () => {
    const m = seed();
    mount(`/meetings/${m.id}/minutes`);
    fireEvent.click(
      await screen.findByRole("button", { name: "Name for Participant 2" }),
    );
    const input = screen.getByRole("textbox", {
      name: "Name for Participant 2",
    });
    fireEvent.change(input, { target: { value: "Participant 3" } });
    fireEvent.submit(input.closest("form")!);
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Type the person's name, not a participant number.",
    );
    fireEvent.change(input, { target: { value: "Ana Rusu" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() =>
      expect(stored(m.id).participants[1].name).toBe("Ana Rusu"),
    );
    expect(
      await screen.findByRole("button", { name: "Name for Ana Rusu" }),
    ).toBeTruthy();
    // Esc closes the form without saving
    fireEvent.click(screen.getByRole("button", { name: "Name for Ana Rusu" }));
    fireEvent.keyDown(
      screen.getByRole("textbox", { name: "Name for Ana Rusu" }),
      {
        key: "Escape",
      },
    );
    expect(
      screen.queryByRole("textbox", { name: "Name for Ana Rusu" }),
    ).toBeNull();
  });

  it("merges one participant into another from the People list", async () => {
    const m = seed();
    mount(`/meetings/${m.id}/minutes`);
    fireEvent.click(
      await screen.findByRole("button", { name: "Merge Participant 3 into" }),
    );
    fireEvent.change(screen.getByLabelText("Merge Participant 3 into"), {
      target: { value: "v1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Merge" }));
    await waitFor(() =>
      expect(stored(m.id).participants.map((p) => p.id)).toEqual(["v1", "v2"]),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Name for Participant 3" }),
      ).toBeNull(),
    );
  });

  it("retitles the meeting from the minutes header", async () => {
    const m = seed();
    mount(`/meetings/${m.id}/minutes`);
    fireEvent.click(await screen.findByRole("button", { name: "Edit title" }));
    const input = screen.getByRole("textbox", { name: "Meeting title" });
    fireEvent.change(input, {
      target: { value: " Consiliul medical, 26 septembrie " },
    });
    fireEvent.submit(input.closest("form")!);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Consiliul medical, 26 septembrie",
      }),
    ).toBeTruthy();
    expect(stored(m.id).title).toBe("Consiliul medical, 26 septembrie");
  });

  it("offers no naming once the minutes are sent", async () => {
    const m = seed({ status: "sent", deliveryState: "sent" });
    mount(`/meetings/${m.id}/minutes`);
    await screen.findAllByText("Participant 1");
    expect(screen.queryByRole("button", { name: /^Name for/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit title" })).toBeNull();
  });
});
