import { describe, expect, it, vi } from "vitest";
import {
  createMeeting,
  getMeeting,
  getMeetings,
  getPeople,
  startProcessing,
  updateMeeting,
  updateMinutes,
  updateActionItem,
  toggleActionItem,
  stopScheduledSend,
  sendNow,
  getTranscript,
  addPerson,
  enrollVoice,
  getRecording,
  saveRecording,
  markReviewed,
  updateParticipants,
  saveCorrectionFeedback,
  getSystem,
  getTemplates,
  saveTemplate,
} from "../src/api/meetings";
import { advanceStore, readStore, writeStore } from "../src/mock/store";
import { invalidMinutes } from "../src/api/validation";
import {
  validateAudioFile,
  validateDuration,
  MAX_AUDIO_BYTES,
} from "../src/api/audio";
import { speakerColor } from "../src/utils";
import {
  assignStaffRole,
  getAdminData,
  saveAccount,
  saveStaffProfile,
} from "../src/api/admin";
const now = new Date("2026-09-25T12:00:00Z");
async function create() {
  const people = await getPeople();
  return createMeeting({
    title: "Test board",
    type: "medical",
    inputMode: "upload",
    participants: people,
  });
}
describe("demo workflow with no network", () => {
  it("enforces admin governance in the API adapter and preserves role history", async () => {
    await expect(
      saveStaffProfile(
        { name: "Blocked", email: "blocked@medpark.local" },
        "staff",
      ),
    ).rejects.toThrow("permissionDenied");
    await expect(
      saveAccount({ username: "blocked", role: "staff" }, "staff"),
    ).rejects.toThrow("permissionDenied");
    const person = await saveStaffProfile(
      { name: "Dr. Maria Lungu", email: "maria.lungu@medpark.local" },
      "admin",
    );
    const first = await assignStaffRole(
      {
        staffId: person.id,
        title: "Resident",
        department: "Cardiology",
        validFrom: "2026-01-01",
      },
      "admin",
    );
    await assignStaffRole(
      {
        staffId: person.id,
        title: "Cardiologist",
        department: "Cardiology",
        validFrom: "2026-09-01",
      },
      "admin",
    );
    const data = await getAdminData();
    expect(data.staffRoles.find((role) => role.id === first.id)?.validTo).toBe(
      "2026-09-01",
    );
  });
  it("keeps participant identity and role snapshots immutable", async () => {
    const meeting = await create();
    const original = meeting.participantSnapshots?.find(
      (participant) => participant.staffId === "ana",
    );
    const store = readStore();
    const currentAna = store.people.find((person) => person.id === "ana")!;
    currentAna.name = "Updated directory name";
    currentAna.role = "Updated current role";
    writeStore(store);
    expect(
      (await getMeeting(meeting.id)).participantSnapshots?.find(
        (participant) => participant.staffId === "ana",
      ),
    ).toEqual(original);
  });
  it("creates a meeting, persists processing, and waits for explicit review and send", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const network = vi.fn(() => {
      throw Error("Unexpected network request");
    });
    vi.stubGlobal("fetch", network);
    const m = await create();
    await updateMeeting(m.id, { durationSeconds: 120, status: "uploaded" });
    await startProcessing(m.id);
    vi.setSystemTime(now.getTime() + 6000);
    expect((await getMeeting(m.id)).progress).toBe(50);
    const persisted = JSON.parse(localStorage.getItem("secure-mom-v2")!);
    expect(
      persisted.meetings.find((x: { id: string }) => x.id === m.id).status,
    ).toBe("processing");
    vi.setSystemTime(now.getTime() + 12001);
    const ready = await getMeeting(m.id);
    expect(ready.status).toBe("ready");
    expect(ready.reviewState).toBe("needs_review");
    expect(ready.sendScheduledAt).toBeNull();
    expect(ready.summary).toBeTruthy();
    expect(ready.decisions?.length).toBe(3);
    expect(ready.actionItems?.length).toBe(3);
    vi.setSystemTime(now.getTime() + 3600000);
    expect((await getMeeting(m.id)).status).toBe("ready");
    await markReviewed(m.id);
    await sendNow(m.id);
    vi.setSystemTime(Date.now() + 801);
    const sent = await getMeeting(m.id);
    expect(sent.status).toBe("sent");
    expect(sent.sendScheduledAt).toBeNull();
    expect((await sendNow(m.id)).sentAt).toBe(sent.sentAt);
    expect(network).not.toHaveBeenCalled();
  });
  it("continues processing while off-page and after a closed-tab interval", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const m = await create();
    await updateMeeting(m.id, { durationSeconds: 5 });
    await startProcessing(m.id);
    vi.setSystemTime(now.getTime() + 3600000);
    expect((await getMeetings()).find((x) => x.id === m.id)?.status).toBe(
      "ready",
    );
  });
  it("defaults to Manual, keeps Auto unavailable, and persists participants and correction feedback", async () => {
    const meeting = await createMeeting({
      title: "Manual review",
      type: "medical",
      inputMode: "upload",
    });
    expect(meeting.sendMode).toBe("manual");
    expect((await getSystem()).capabilities?.autoModeAvailable).toBe(false);
    const people = await getPeople();
    const updated = await updateParticipants(meeting.id, [people[0]]);
    expect(updated.participants.map((person) => person.id)).toEqual([
      people[0].id,
    ]);
    await saveCorrectionFeedback({
      meetingId: meeting.id,
      field: "summary",
      before: "Draft",
      after: "Corrected",
    });
    expect(readStore().feedback.at(-1)).toMatchObject({
      meetingId: meeting.id,
      field: "summary",
      after: "Corrected",
    });
  });
  it("enforces template write permissions and keeps meeting setup snapshots independent", async () => {
    const template = (await getTemplates())[0];
    await expect(
      saveTemplate(
        { ...template, id: template.id, name: "Forbidden" },
        "staff",
      ),
    ).rejects.toThrow("unauthorized");
    const updated = await saveTemplate(
      { ...template, id: template.id, name: "Updated tumor board" },
      "admin",
    );
    const people = await getPeople();
    const meeting = await createMeeting({
      title: updated.defaultTitle ?? updated.name,
      type: updated.meetingType,
      inputMode: "upload",
      participants: updated.participantStaffIds
        .map((id) => people.find((person) => person.id === id)!)
        .filter(Boolean),
      templateId: updated.id,
      agendaTopics: updated.agendaTopics,
    });
    await saveTemplate(
      { ...updated, id: updated.id, agendaTopics: [] },
      "admin",
    );
    expect(meeting.templateId).toBe(updated.id);
    expect(meeting.agendaTopics).toEqual(updated.agendaTopics);
  });
  it("honors a 15-second countdown and pauses when review data is unresolved", () => {
    const store = readStore();
    const m = store.meetings[0];
    m.status = "processing";
    m.processingStartedAt = now.toISOString();
    m.processingEndsAt = new Date(now.getTime() + 12000).toISOString();
    m.sendMode = "auto";
    advanceStore(store, now.getTime() + 12000, 15, true);
    expect(m.status).toBe("sending_soon");
    expect(Date.parse(m.sendScheduledAt!)).toBe(now.getTime() + 27000);
    m.actionItems![0].ownerParticipantId = null;
    advanceStore(store, now.getTime() + 28000, 15, true);
    expect(m.status).toBe("ready");
    expect(m.sendScheduledAt).toBeNull();
    expect(invalidMinutes(m)).toBe(true);
  });
  it("stops automatic sending permanently until send-now, and never resends", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const m = (await getMeetings())[0];
    await updateMeeting(m.id, {
      status: "sending_soon",
      sendScheduledAt: new Date(now.getTime() + 15000).toISOString(),
    });
    await stopScheduledSend(m.id);
    vi.setSystemTime(now.getTime() + 60000);
    expect((await getMeeting(m.id)).status).toBe("ready");
    await markReviewed(m.id);
    const sent = await sendNow(m.id);
    expect(sent.status).toBe("sending");
    await expect(
      updateMinutes(m.id, { summary: "During delivery" }),
    ).rejects.toThrow("alreadySent");
    vi.setSystemTime(Date.now() + 801);
    await stopScheduledSend(m.id);
    expect((await getMeeting(m.id)).status).toBe("sent");
    await expect(
      updateMinutes(m.id, { summary: "Already sent" }),
    ).rejects.toThrow("alreadySent");
  });
  it("edits tasks/summary/decisions without rewriting the multilingual transcript", async () => {
    const m = (await getMeetings())[0];
    const raw = await getTranscript(m.id);
    await updateMinutes(m.id, {
      summary: "Revised summary",
      decisions: [{ id: "d", text: "Revised decision" }],
    });
    await updateActionItem(m.id, "a1", {
      task: "A revised task",
      ownerParticipantId: "elena",
      deadline: "2026-10-02",
    });
    await toggleActionItem(m.id, "a1");
    const saved = await getMeeting(m.id);
    expect(saved.summary).toBe("Revised summary");
    expect(saved.decisions?.[0].text).toBe("Revised decision");
    expect(saved.actionItems?.[0]).toMatchObject({
      task: "A revised task",
      completed: true,
      sourceTimestampSeconds: 724,
    });
    expect(await getTranscript(m.id)).toEqual(raw);
    await expect(updateActionItem(m.id, "a1", { task: "  " })).rejects.toThrow(
      "required",
    );
  });
  it("rejects sending without a known owner or required deadline", async () => {
    const m = (await getMeetings())[0];
    await updateActionItem(m.id, "a1", { ownerParticipantId: "unknown" });
    await expect(sendNow(m.id)).rejects.toThrow("unresolved");
    await updateActionItem(m.id, "a1", {
      ownerParticipantId: "ana",
      deadline: null,
    });
    await expect(sendNow(m.id)).rejects.toThrow("unresolved");
  });
  it("does not restart an unavailable automatic countdown and keeps a stopped window stopped", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const m = (await getMeetings())[0];
    await updateMeeting(m.id, {
      status: "sending_soon",
      sendMode: "auto",
      sendScheduledAt: new Date(now.getTime() + 1000).toISOString(),
    });
    await updateMinutes(m.id, { summary: "Revised" });
    expect(Date.parse((await getMeeting(m.id)).sendScheduledAt!)).toBe(
      now.getTime() + 1000,
    );
    await stopScheduledSend(m.id);
    await updateActionItem(m.id, "a1", { deadline: "2026-10-01" });
    expect((await getMeeting(m.id)).sendScheduledAt).toBeNull();
  });
  it("saves audio and voice enrollment locally, labeled as prototype", async () => {
    const m = await create();
    const blob = new Blob(["audio fixture"], { type: "audio/webm" });
    await saveRecording(m.id, blob);
    expect(await getRecording(m.id)).toBeDefined();
    const p = await addPerson({ name: "Test staff member" });
    await enrollVoice(p.id, blob);
    expect((await getPeople()).find((x) => x.id === p.id)).toMatchObject({
      enrolled: true,
      enrollmentKind: "prototype",
    });
  });
  it("does not overwrite corrupt persisted data", () => {
    localStorage.setItem("secure-mom-v2", "broken");
    expect(() => readStore()).toThrow("storage");
    expect(localStorage.getItem("secure-mom-v2")).toBe("broken");
  });
  it("persists stopped and failed states without silently retrying", () => {
    const store = readStore();
    store.meetings[0].status = "failed";
    store.meetings[1].status = "stopped";
    writeStore(store);
    expect(
      readStore()
        .meetings.slice(0, 2)
        .map((m) => m.status),
    ).toEqual(["failed", "stopped"]);
  });
});
describe("audio validation and speaker identity", () => {
  it("checks extension, MIME, nonzero size and max bytes", () => {
    expect(() =>
      validateAudioFile({ name: "meeting.wav", type: "audio/wav", size: 123 }),
    ).not.toThrow();
    expect(() =>
      validateAudioFile({
        name: "meeting.flac",
        type: "audio/flac",
        size: 123,
      }),
    ).not.toThrow();
    for (const f of [
      { name: "file.exe", type: "audio/wav", size: 123 },
      { name: "file.mp3", type: "text/plain", size: 123 },
      { name: "file.m4a", type: "audio/mp4", size: 0 },
      { name: "file.wav", type: "audio/wav", size: MAX_AUDIO_BYTES + 1 },
    ])
      expect(() => validateAudioFile(f)).toThrow();
  });
  it("rejects invalid or excessive durations", () => {
    for (const n of [0, -1, Infinity, NaN, 10801])
      expect(() => validateDuration(n)).toThrow();
    expect(() => validateDuration(10800)).not.toThrow();
  });
  it("assigns stable, distinct colors to speaker slots", () => {
    const colors = Array.from({ length: 100 }, (_, i) => speakerColor(i));
    expect(new Set(colors).size).toBe(100);
    expect(speakerColor(2)).toBe(speakerColor(2));
  });
});
