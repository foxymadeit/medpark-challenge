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
} from "../src/api/meetings";
import { advanceStore, readStore, writeStore } from "../src/mock/store";
import { invalidMinutes } from "../src/api/validation";
import {
  validateAudioFile,
  validateDuration,
  MAX_AUDIO_BYTES,
} from "../src/api/audio";
import { speakerColor } from "../src/utils";
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
  it("creates a meeting, persists processing through reload, and sends after the configured window", async () => {
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
    expect(ready.status).toBe("sending_soon");
    expect(ready.summary).toBeTruthy();
    expect(ready.decisions?.length).toBe(3);
    expect(ready.actionItems?.length).toBe(3);
    vi.setSystemTime(Date.parse(ready.sendScheduledAt!) + 1);
    expect((await getMeeting(m.id)).status).toBe("sending");
    vi.setSystemTime(Date.parse(ready.sendScheduledAt!) + 801);
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
      "sent",
    );
  });
  it("honors a 15-second countdown and pauses when review data is unresolved", () => {
    const store = readStore();
    const m = store.meetings[0];
    m.status = "processing";
    m.processingStartedAt = now.toISOString();
    m.processingEndsAt = new Date(now.getTime() + 12000).toISOString();
    advanceStore(store, now.getTime() + 12000, 15);
    expect(m.status).toBe("sending_soon");
    expect(Date.parse(m.sendScheduledAt!)).toBe(now.getTime() + 27000);
    m.actionItems![0].ownerParticipantId = null;
    advanceStore(store, now.getTime() + 28000, 15);
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
  it("restarts only an active countdown on editing and keeps a stopped window stopped", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    const m = (await getMeetings())[0];
    await updateMeeting(m.id, {
      status: "sending_soon",
      sendScheduledAt: new Date(now.getTime() + 1000).toISOString(),
    });
    await updateMinutes(m.id, { summary: "Revised" });
    expect(Date.parse((await getMeeting(m.id)).sendScheduledAt!)).toBe(
      now.getTime() + 300000,
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
    for (const f of [
      { name: "file.exe", type: "audio/wav", size: 123 },
      { name: "file.mp3", type: "text/plain", size: 123 },
      { name: "file.m4a", type: "audio/mp4", size: 0 },
      { name: "file.wav", type: "audio/wav", size: MAX_AUDIO_BYTES + 1 },
    ])
      expect(() => validateAudioFile(f)).toThrow("invalidAudio");
  });
  it("rejects invalid or excessive durations", () => {
    for (const n of [0, -1, Infinity, NaN, 10801])
      expect(() => validateDuration(n)).toThrow("invalidAudio");
    expect(() => validateDuration(10800)).not.toThrow();
  });
  it("assigns stable, distinct colors to speaker slots", () => {
    const colors = Array.from({ length: 100 }, (_, i) => speakerColor(i));
    expect(new Set(colors).size).toBe(100);
    expect(speakerColor(2)).toBe(speakerColor(2));
  });
});
