import { invalidMinutes } from "../api/validation";
import type {
  CorrectionFeedback,
  Meeting,
  Participant,
} from "../types/meeting";
import { sampleMinutes, seedMeetings, seedPeople } from "./seed";
import { AUTO_COUNTDOWN_SECONDS } from "../api/config";
import { ApiError } from "../api/client";
export interface DemoStore {
  version: 2 | 3;
  meetings: Meeting[];
  people: Participant[];
  feedback: CorrectionFeedback[];
}
export const STORE_KEY = "secure-mom-v2";
export function advanceStore(
  store: DemoStore,
  now = Date.now(),
  countdown = AUTO_COUNTDOWN_SECONDS,
  autoModeAvailable = false,
): boolean {
  let changed = false;
  for (const m of store.meetings) {
    if (
      m.status === "ready" &&
      m.deliveryState === "failed" &&
      m.deliveryFailedAt &&
      now >= Date.parse(m.deliveryFailedAt) + 30_000
    ) {
      m.status = "sending";
      m.deliveryState = "sending";
      m.sendingStartedAt = new Date(
        Date.parse(m.deliveryFailedAt) + 30_000,
      ).toISOString();
      m.deliveryFailedAt = undefined;
      changed = true;
    }
    if (
      m.status === "processing" &&
      m.processingEndsAt &&
      m.processingStartedAt
    ) {
      const end = Date.parse(m.processingEndsAt);
      const start = Date.parse(m.processingStartedAt);
      const progress = Math.min(
        100,
        Math.max(0, Math.floor(((now - start) / (end - start)) * 100)),
      );
      if (m.progress !== progress) {
        m.progress = progress;
        changed = true;
      }
      if (now >= end) {
        Object.assign(m, sampleMinutes(m.participants, m.durationSeconds), {
          demoGenerated: true,
        });
        const auto = m.sendMode === "auto" && autoModeAvailable;
        m.status = auto && !invalidMinutes(m) ? "sending_soon" : "ready";
        m.processingState = "complete";
        m.reviewState = "needs_review";
        m.deliveryState = auto ? "scheduled" : "stopped";
        m.sendWindowSeconds = countdown;
        m.sendScheduledAt =
          m.status === "sending_soon"
            ? new Date(end + countdown * 1000).toISOString()
            : null;
        changed = true;
      }
    }
    if (m.status === "sending_soon") {
      if (invalidMinutes(m)) {
        m.status = "ready";
        m.sendScheduledAt = null;
        changed = true;
      } else if (m.sendScheduledAt && now >= Date.parse(m.sendScheduledAt)) {
        m.status = "sending";
        m.deliveryState = "sending";
        m.sendingStartedAt = m.sendScheduledAt;
        m.sendScheduledAt = null;
        changed = true;
      }
    }
    if (
      m.status === "sending" &&
      m.sendingStartedAt &&
      now >= Date.parse(m.sendingStartedAt) + 800
    ) {
      m.status = "sent";
      m.deliveryState = "sent";
      m.sentAt = new Date(Date.parse(m.sendingStartedAt) + 800).toISOString();
      changed = true;
    }
  }
  return changed;
}
export function readStore(): DemoStore {
  const raw = localStorage.getItem(STORE_KEY);
  let store: DemoStore;
  if (raw) {
    try {
      store = JSON.parse(raw);
    } catch {
      throw new ApiError("storage");
    }
    if (
      ![2, 3].includes(store.version) ||
      !Array.isArray(store.meetings) ||
      !Array.isArray(store.people)
    )
      throw new ApiError("storage");
  } else {
    store = {
      version: 3,
      meetings: seedMeetings(),
      people: structuredClone(seedPeople),
      feedback: [],
    };
    writeStore(store);
  }
  let migrated = false;
  if (store.version === 2) {
    store.version = 3;
    store.feedback = [];
    migrated = true;
  }
  store.feedback ??= [];
  for (const meeting of store.meetings) {
    for (const participant of meeting.participants) {
      participant.staffId ??= participant.id;
    }
    for (const action of meeting.actionItems ?? []) {
      if (action.ownerStaffId === undefined) {
        action.ownerStaffId =
          meeting.participants.find(
            (participant) => participant.id === action.ownerParticipantId,
          )?.staffId ?? null;
        migrated = true;
      }
    }
    if (!meeting.sendMode) {
      meeting.sendMode = "manual";
      meeting.reviewState =
        meeting.status === "processing" ? "not_ready" : "needs_review";
      if (meeting.status === "sending_soon") {
        meeting.status = "ready";
        meeting.deliveryState = "stopped";
        meeting.sendScheduledAt = null;
      }
      migrated = true;
    }
  }
  for (const person of [
    ...store.people,
    ...store.meetings.flatMap((m) => m.participants),
  ]) {
    if (person.id === "elena" && person.email === "admin@medpark.local") {
      person.email = "elena.ciobanu@medpark.local";
      migrated = true;
    }
  }
  if (advanceStore(store) || migrated) writeStore(store);
  return store;
}
export function writeStore(store: DemoStore) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  } catch {
    throw new ApiError("storage");
  }
}
export function mutate<T>(change: (store: DemoStore) => T): T {
  const store = readStore();
  const value = change(store);
  writeStore(store);
  return structuredClone(value);
}
export function findMeeting(store: DemoStore, id: string) {
  const meeting = store.meetings.find((m) => m.id === id);
  if (!meeting) throw new ApiError("notFound");
  return meeting;
}
export async function putAudio(id: string, blob: Blob): Promise<void> {
  const db = await openAudio();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("audio", "readwrite");
      tx.objectStore("audio").put(blob, id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(new ApiError("storage"));
      tx.onabort = () => reject(new ApiError("storage"));
    });
  } finally {
    db.close();
  }
}
export async function getAudio(id: string): Promise<Blob | undefined> {
  const db = await openAudio();
  try {
    return await new Promise((resolve, reject) => {
      const r = db.transaction("audio").objectStore("audio").get(id);
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(new ApiError("storage"));
    });
  } finally {
    db.close();
  }
}
function openAudio(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open("secure-mom-audio", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("audio");
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(new ApiError("storage"));
  });
}
