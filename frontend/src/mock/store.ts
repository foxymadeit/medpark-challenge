import { invalidMinutes } from "../api/validation";
import type {
  CorrectionFeedback,
  Meeting,
  Participant,
  VoiceProfile,
  DetectedSpeakerCluster,
  MeetingTemplate,
  UserAccount,
  StaffProfile,
  StaffRoleAssignment,
  DistributionList,
} from "../types/meeting";
import { sampleMinutes, seedMeetings, seedPeople } from "./seed";
import { AUTO_COUNTDOWN_SECONDS } from "../api/config";
import { ApiError } from "../api/client";
import { AUDIO_SHARE } from "../api/stages";
export interface DemoStore {
  version: 2 | 3 | 4 | 5 | 6;
  meetings: Meeting[];
  people: Participant[];
  feedback: CorrectionFeedback[];
  voiceProfiles: VoiceProfile[];
  speakerClusters: DetectedSpeakerCluster[];
  templates: MeetingTemplate[];
  accounts: UserAccount[];
  staffProfiles: StaffProfile[];
  staffRoles: StaffRoleAssignment[];
  distributionLists: DistributionList[];
}
export const STORE_KEY = "secure-mom-v2";
function seedGovernance() {
  const createdAt = new Date().toISOString();
  return {
    staffProfiles: seedPeople.map((person) => ({
      id: person.id,
      name: person.name,
      email: person.email ?? "",
      active: person.active !== false,
      createdAt,
      createdBy: "demo-admin",
    })),
    staffRoles: seedPeople.map((person) => ({
      id: `role-${person.id}-current`,
      staffId: person.id,
      title: person.role ?? "Staff",
      department: person.department ?? "administrative",
      validFrom: "2026-01-01",
      validTo: null,
      createdBy: "demo-admin",
    })),
    accounts: [
      {
        id: "demo-admin",
        username: "admin@medpark.local",
        email: "admin@medpark.local",
        role: "admin" as const,
        active: true,
        createdAt,
        createdBy: "system",
      },
    ],
    distributionLists: [
      {
        id: "medical-board",
        name: "Medical board",
        email: "medical-board@medpark.local",
        active: true,
      },
      {
        id: "executive-team",
        name: "Executive team",
        email: "executive-team@medpark.local",
        active: true,
      },
      {
        id: "admin-office",
        name: "Administrative office",
        email: "admin-office@medpark.local",
        active: true,
      },
    ],
  } satisfies Pick<
    DemoStore,
    "accounts" | "staffProfiles" | "staffRoles" | "distributionLists"
  >;
}
function seedTemplates(): MeetingTemplate[] {
  const now = new Date().toISOString();
  const make = (
    id: string,
    name: string,
    meetingType: MeetingTemplate["meetingType"],
    participantStaffIds: string[],
    label: string,
    topics: string[],
  ): MeetingTemplate => ({
    id,
    name,
    meetingType,
    defaultTitle: name,
    participantStaffIds,
    agendaTopics: topics.map((text, order) => ({
      id: `${id}-${order}`,
      text,
      order,
    })),
    recurrence: { type: "custom", label },
    active: true,
    createdBy: "demo-admin",
    createdAt: now,
    updatedAt: now,
  });
  return [
    make(
      "tumor-board",
      "Tumor board",
      "medical",
      ["ana", "elena", "igor"],
      "Every Monday · 09:00",
      ["New oncology cases", "Surgery planning", "Treatment decisions"],
    ),
    make("icu-handover", "ICU handover", "medical", ["elena", "ana"], "Daily", [
      "Critical patients",
      "Medication changes",
      "Pending tests",
    ]),
    make(
      "executive-sync",
      "Weekly executive sync",
      "executive",
      ["elena", "victor"],
      "Fridays",
      ["Operating priorities", "Staffing", "Risks"],
    ),
    make(
      "supply-planning",
      "Supply planning",
      "administrative",
      ["victor"],
      "Monthly",
      ["Stock levels", "Contracts", "Delivery dates"],
    ),
  ];
}
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
        // the server's three stages, so the demo shows the same six steps
        const split = start + (end - start) * AUDIO_SHARE;
        const audioDone = now >= split;
        m.stages = [
          { id: "transcribe", state: audioDone ? "done" : "running" },
          { id: "speakers", state: audioDone ? "done" : "running" },
          {
            id: "minutes",
            state: audioDone ? "running" : "pending",
            startedAt: new Date(split).toISOString(),
          },
        ];
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
        // "stopped" means a person pressed Stop; a manual meeting has no delivery yet
        m.deliveryState = auto ? "scheduled" : undefined;
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
      if (m.delivery) {
        m.delivery.status = "sent";
        m.delivery.sentAt = m.sentAt;
      }
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
      ![2, 3, 4, 5, 6].includes(store.version) ||
      !Array.isArray(store.meetings) ||
      !Array.isArray(store.people)
    )
      throw new ApiError("storage");
  } else {
    store = {
      version: 6,
      meetings: seedMeetings(),
      people: structuredClone(seedPeople),
      feedback: [],
      voiceProfiles: seedPeople
        .filter((person) => person.enrolled)
        .map((person) => ({
          id: `voice-${person.id}`,
          staffId: person.id,
          status: person.enrollmentKind ?? "prototype",
          languages: ["en", "ro", "ru"],
          createdAt: new Date().toISOString(),
        })),
      speakerClusters: [
        {
          id: "cluster-meeting-001-speaker-4",
          meetingId: "meeting-001",
          speakerId: "speaker-4",
          label: "Speaker 4",
          speakingSeconds: 72,
          sampleAvailable: false,
          identifiedStaffId: null,
          status: "unidentified",
        },
      ],
      templates: seedTemplates(),
      ...seedGovernance(),
    };
    writeStore(store);
  }
  let migrated = false;
  if (store.version === 2) {
    store.version = 3;
    store.feedback = [];
    migrated = true;
  }
  if (store.version === 3) {
    store.version = 4;
    store.voiceProfiles = store.people
      .filter((person) => person.enrolled)
      .map((person) => ({
        id: `voice-${person.id}`,
        staffId: person.id,
        status: person.enrollmentKind ?? "prototype",
        createdAt: new Date().toISOString(),
      }));
    store.speakerClusters = [
      {
        id: "cluster-meeting-001-speaker-4",
        meetingId: "meeting-001",
        speakerId: "speaker-4",
        label: "Speaker 4",
        speakingSeconds: 72,
        sampleAvailable: false,
        identifiedStaffId: null,
        status: "unidentified",
      },
    ];
    migrated = true;
  }
  if (store.version === 4) {
    store.version = 5;
    store.templates = seedTemplates();
    migrated = true;
  }
  if (store.version === 5) {
    store.version = 6;
    Object.assign(store, seedGovernance());
    migrated = true;
  }
  store.voiceProfiles ??= [];
  store.speakerClusters ??= [];
  store.templates ??= seedTemplates();
  store.feedback ??= [];
  const governance = seedGovernance();
  store.accounts ??= governance.accounts;
  store.staffProfiles ??= governance.staffProfiles;
  store.staffRoles ??= governance.staffRoles;
  store.distributionLists ??= governance.distributionLists;
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
    if (!meeting.participantSnapshots) {
      meeting.participantSnapshots = meeting.participants.map(
        (participant) => ({
          staffId: participant.staffId ?? participant.id,
          nameAtMeeting: participant.name,
          emailAtMeeting: participant.email ?? "",
          roleTitleAtMeeting: participant.role ?? "",
          departmentAtMeeting: participant.department ?? meeting.type,
          speakerId: participant.speakerId,
        }),
      );
      migrated = true;
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
