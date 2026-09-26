import { invalidMinutes } from "./validation";
import type {
  ActionItem,
  MinutesLanguage,
  ProcessingStage,
  StageId,
  CorrectionFeedback,
  CreateMeetingInput,
  Meeting,
  Participant,
  SystemState,
  VoiceProfile,
  DetectedSpeakerCluster,
  MeetingTemplate,
} from "../types/meeting";
import {
  AUTO_COUNTDOWN_SECONDS,
  AUTO_MODE_AVAILABLE,
  DEMO_MODE,
  distribution,
} from "./config";
import { ApiError, request } from "./client";
import {
  findMeeting,
  getAudio,
  mutate,
  putAudio,
  readStore,
} from "../mock/store";
const path = (id: string) => `/meetings/${encodeURIComponent(id)}`;
// The server names three pipeline stages and keeps them as a map; the UI
// shows them in order, pending ones included.
const SERVER_STAGES: [string, StageId][] = [
  ["asr", "transcribe"],
  ["diarize", "speakers"],
  ["minutes", "minutes"],
];
type ServerMeeting = Meeting & {
  processingStages?: Record<
    string,
    { state: ProcessingStage["state"]; startedAt?: string; endedAt?: string }
  >;
  needsConfirmation?: { id: string; text: string; problems?: string[] }[];
  documents?: MinutesLanguage[] | Partial<Record<MinutesLanguage, unknown>>;
};
/** Server meeting (backend/README.md, "Endpoints beyond the contract") to
 * the frontend model. Already-shaped fields pass through unchanged. */
export function fromServer(raw: ServerMeeting): Meeting {
  const { processingStages, needsConfirmation, documents, ...m } = raw;
  const out: Meeting = { ...m };
  if (processingStages && !m.stages)
    out.stages = SERVER_STAGES.map(([key, id]) => ({
      id,
      state: processingStages[key]?.state ?? "pending",
      startedAt: processingStages[key]?.startedAt,
      finishedAt: processingStages[key]?.endedAt,
    }));
  if (needsConfirmation && !m.confirmItems)
    out.confirmItems = needsConfirmation.map((c) => ({
      id: c.id,
      text: c.text,
      reason: (c.problems ?? []).join(". "),
      problems: c.problems,
    }));
  if (documents)
    out.documents = Array.isArray(documents)
      ? documents
      : (["ro", "ru", "en"] as const).filter((l) => l in documents);
  return out;
}
async function meetingRequest(
  url: string,
  options?: RequestInit,
): Promise<Meeting> {
  return fromServer(await request<ServerMeeting>(url, options));
}
// A 3-hour, 500 MB recording on a slow hospital network needs far more than
// the 20 s default.
const UPLOAD_TIMEOUT_MS = 15 * 60 * 1000;
export async function getCapabilities(): Promise<{
  autoModeAvailable: boolean;
}> {
  return DEMO_MODE
    ? { autoModeAvailable: AUTO_MODE_AVAILABLE }
    : request("/capabilities");
}
/** Keep or take out an item the checks could not confirm. */
export async function decideConfirmation(
  id: string,
  itemId: string,
  keep: boolean,
): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(
      `${path(id)}/confirmations/${encodeURIComponent(itemId)}`,
      {
        method: "POST",
        body: JSON.stringify({ action: keep ? "keep" : "remove" }),
      },
    );
  return mutate((s) => {
    const m = findMeeting(s, id);
    const item = m.confirmItems?.find((c) => c.id === itemId);
    if (!item) throw new ApiError("notFound");
    item.decision = keep ? "keep" : "remove";
    return m;
  });
}
/** Server-rendered minutes (Medpark template, PDF/A or DOCX). */
export function documentUrl(
  id: string,
  lang: MinutesLanguage,
  kind: "pdf" | "docx",
): string {
  return `/api${path(id)}/documents/${lang}.${kind}`;
}
export async function getMeetings(): Promise<Meeting[]> {
  return DEMO_MODE
    ? readStore().meetings
    : (await request<ServerMeeting[]>("/meetings")).map(fromServer);
}
export async function getMeeting(id: string): Promise<Meeting> {
  return DEMO_MODE ? findMeeting(readStore(), id) : meetingRequest(path(id));
}
export async function createMeeting(
  input: CreateMeetingInput,
): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest("/meetings", {
      method: "POST",
      body: JSON.stringify(input),
    });
  return mutate((s) => {
    const participants = (input.participants ?? []).map((p, i) => ({
      ...p,
      staffId: p.staffId ?? p.id,
      speakerSlot: i,
      speakerId: p.id,
      speakingSeconds: 0,
    }));
    const m: Meeting = {
      ...input,
      id: crypto.randomUUID(),
      title: input.title.trim().slice(0, 120),
      status: "draft",
      sendMode: AUTO_MODE_AVAILABLE ? (input.sendMode ?? "manual") : "manual",
      reviewState: "not_ready",
      createdAt: new Date().toISOString(),
      participants,
      participantSnapshots: participants.map((participant) => ({
        staffId: participant.staffId,
        nameAtMeeting: participant.name,
        emailAtMeeting: participant.email ?? "",
        roleTitleAtMeeting: participant.role ?? "",
        departmentAtMeeting: participant.department ?? input.type,
        speakerId: participant.speakerId,
      })),
      distributionList: [distribution[input.type].list],
      templateId: input.templateId,
      agendaTopics: structuredClone(input.agendaTopics ?? []),
    };
    s.meetings.unshift(m);
    return m;
  });
}
export async function updateMeeting(
  id: string,
  changes: Partial<Meeting>,
): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(path(id), {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  return mutate((s) => {
    const meeting = findMeeting(s, id);
    Object.assign(meeting, changes, { id });
    if (changes.deliveryState === "failed" && !meeting.deliveryFailedAt)
      meeting.deliveryFailedAt = new Date().toISOString();
    return meeting;
  });
}
export async function saveRecording(id: string, blob: Blob): Promise<void> {
  if (!blob.size) throw new ApiError("invalidAudio");
  if (DEMO_MODE) await putAudio(id, blob);
  else {
    const body = new FormData();
    body.append("audio", blob, "recording.webm");
    await request(`${path(id)}/recording`, {
      method: "POST",
      body,
      signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
    });
  }
}
export async function uploadRecording(
  id: string,
  file: File,
  durationSeconds: number,
): Promise<void> {
  if (DEMO_MODE) {
    await putAudio(id, file);
    await updateMeeting(id, {
      audioFilename: file.name,
      audioBytes: file.size,
      durationSeconds,
      status: "uploaded",
    });
  } else {
    const body = new FormData();
    body.append("audio", file);
    await request(`${path(id)}/upload`, {
      method: "POST",
      body,
      signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
    });
  }
}
export async function getRecording(id: string): Promise<Blob | undefined> {
  if (DEMO_MODE) return getAudio(id);
  const r = await fetch(`/api${path(id)}/recording`, {
    credentials: "include",
  });
  if (!r.ok) return undefined;
  return r.blob();
}
export async function startProcessing(id: string): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(`${path(id)}/process`, { method: "POST" });
  return mutate((s) => {
    const m = findMeeting(s, id);
    if (!m.durationSeconds) throw new ApiError("invalidAudio");
    return Object.assign(m, {
      status: "processing" as const,
      processingState: "running" as const,
      progress: 0,
      processingStartedAt: new Date().toISOString(),
      processingEndsAt: new Date(Date.now() + 12000).toISOString(),
      sendScheduledAt: null,
      reviewState: "not_ready" as const,
    });
  });
}
export async function getProcessingState(id: string): Promise<Meeting> {
  return DEMO_MODE ? getMeeting(id) : meetingRequest(`${path(id)}/processing`);
}
export async function updateMinutes(
  id: string,
  changes: Pick<Partial<Meeting>, "summary" | "decisions">,
): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(`${path(id)}/minutes`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  return mutate((s) => {
    const m = findMeeting(s, id);
    if (["sent", "sending"].includes(m.status))
      throw new ApiError("alreadySent");
    Object.assign(m, changes);
    restartWindow(m);
    return m;
  });
}
function restartWindow(m: Meeting) {
  if (invalidMinutes(m)) {
    m.status = "ready";
    m.sendScheduledAt = null;
  } else if (
    m.status === "sending_soon" &&
    m.sendMode === "auto" &&
    AUTO_MODE_AVAILABLE
  ) {
    m.sendScheduledAt = new Date(
      Date.now() + AUTO_COUNTDOWN_SECONDS * 1000,
    ).toISOString();
    m.sendWindowSeconds = AUTO_COUNTDOWN_SECONDS;
  }
}
export async function updateActionItem(
  id: string,
  actionId: string,
  changes: Partial<ActionItem>,
): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(
      `${path(id)}/actions/${encodeURIComponent(actionId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(changes),
      },
    );
  return mutate((s) => {
    const m = findMeeting(s, id);
    const a = m.actionItems?.find((a) => a.id === actionId);
    if (!a) throw new ApiError("notFound");
    if (changes.task !== undefined && !changes.task.trim())
      throw new ApiError("required");
    if (
      ["sent", "sending"].includes(m.status) &&
      Object.keys(changes).some((k) => k !== "completed")
    )
      throw new ApiError("alreadySent");
    const owner =
      changes.ownerParticipantId === undefined
        ? undefined
        : changes.ownerParticipantId === null
          ? null
          : m.participants.find(
              (participant) => participant.id === changes.ownerParticipantId,
            );
    Object.assign(a, changes, {
      id: actionId,
      ...(owner === undefined ? {} : { ownerStaffId: owner?.staffId ?? null }),
    });
    restartWindow(m);
    return m;
  });
}
export async function toggleActionItem(id: string, actionId: string) {
  const m = await getMeeting(id);
  const a = m.actionItems?.find((a) => a.id === actionId);
  if (!a) throw new ApiError("notFound");
  return updateActionItem(id, actionId, { completed: !a.completed });
}
export async function stopScheduledSend(id: string): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(`${path(id)}/stop-send`, { method: "POST" });
  return mutate((s) => {
    const m = findMeeting(s, id);
    if (m.status === "sending_soon") {
      m.status = "ready";
      m.sendMode = "manual";
      m.reviewState = "needs_review";
      m.deliveryState = "stopped";
      m.sendScheduledAt = null;
    }
    return m;
  });
}
export async function sendNow(id: string): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(`${path(id)}/send`, {
      method: "POST",
      headers: { "Idempotency-Key": `minutes-${id}` },
    });
  return mutate((s) => {
    const m = findMeeting(s, id);
    if (["sent", "sending"].includes(m.status)) return m;
    if (
      !["ready", "sending_soon"].includes(m.status) ||
      invalidMinutes(m) ||
      !m.participants.length ||
      !m.distributionList.length ||
      m.reviewState !== "reviewed"
    )
      throw new ApiError("unresolved");
    m.status = "sending";
    m.deliveryState = "sending";
    m.failureReference = undefined;
    m.deliveryFailedAt = undefined;
    m.sendingStartedAt = new Date().toISOString();
    m.sendScheduledAt = null;
    m.reviewState = "reviewed";
    return m;
  });
}
export async function markReviewed(id: string): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(`${path(id)}/review`, { method: "POST" });
  return mutate((store) => {
    const meeting = findMeeting(store, id);
    if (
      meeting.status !== "ready" ||
      invalidMinutes(meeting) ||
      !meeting.participants.length ||
      !meeting.distributionList.length
    )
      throw new ApiError("unresolved");
    meeting.reviewState = "reviewed";
    return meeting;
  });
}
export async function updateParticipants(
  id: string,
  participants: Participant[],
): Promise<Meeting> {
  if (!DEMO_MODE)
    return meetingRequest(`${path(id)}/participants`, {
      method: "PATCH",
      body: JSON.stringify({ participants }),
    });
  return mutate((s) => {
    const meeting = findMeeting(s, id);
    meeting.participants = participants.map((participant, index) => ({
      ...participant,
      speakerId: participant.speakerId ?? participant.id,
      speakerSlot: participant.speakerSlot ?? index,
    }));
    meeting.participantSnapshots = meeting.participants.map((participant) => ({
      staffId: participant.staffId ?? participant.id,
      nameAtMeeting: participant.name,
      emailAtMeeting: participant.email ?? "",
      roleTitleAtMeeting: participant.role ?? "",
      departmentAtMeeting: participant.department ?? meeting.type,
      speakerId: participant.speakerId,
    }));
    return meeting;
  });
}
export async function saveCorrectionFeedback(
  feedback: Omit<CorrectionFeedback, "createdAt">,
): Promise<void> {
  const value = { ...feedback, createdAt: new Date().toISOString() };
  if (!DEMO_MODE) {
    await request(`${path(feedback.meetingId)}/feedback`, {
      method: "POST",
      body: JSON.stringify(value),
    });
    return;
  }
  mutate((store) => {
    store.feedback.push(value);
    return value;
  });
}
export async function getTranscript(id: string) {
  if (DEMO_MODE) return (await getMeeting(id)).transcript ?? [];
  return request<NonNullable<Meeting["transcript"]>>(`${path(id)}/transcript`);
}
export async function getPeople(): Promise<Participant[]> {
  return DEMO_MODE
    ? readStore().people.filter((person) => person.active !== false)
    : request("/people");
}
export async function getTemplates(): Promise<MeetingTemplate[]> {
  return DEMO_MODE
    ? readStore().templates.filter((template) => template.active)
    : request("/templates");
}
export async function getTemplate(id: string): Promise<MeetingTemplate> {
  if (!DEMO_MODE) return request(`/templates/${encodeURIComponent(id)}`);
  const template = readStore().templates.find((item) => item.id === id);
  if (!template) throw new ApiError("notFound");
  return structuredClone(template);
}
export async function saveTemplate(
  input: Omit<
    MeetingTemplate,
    "id" | "createdAt" | "updatedAt" | "createdBy"
  > & { id?: string },
  accountRole: "admin" | "staff",
): Promise<MeetingTemplate> {
  if (accountRole !== "admin") throw new ApiError("unauthorized");
  const participantIds = [...new Set(input.participantStaffIds)];
  if (
    !input.name.trim() ||
    participantIds.length !== input.participantStaffIds.length
  )
    throw new ApiError("required");
  if (!DEMO_MODE)
    return request(
      input.id ? `/templates/${encodeURIComponent(input.id)}` : "/templates",
      {
        method: input.id ? "PATCH" : "POST",
        body: JSON.stringify({ ...input, participantStaffIds: participantIds }),
      },
    );
  return mutate((store) => {
    if (
      participantIds.some(
        (id) => !store.people.some((person) => person.id === id),
      )
    )
      throw new ApiError("notFound");
    const now = new Date().toISOString();
    const existing = input.id
      ? store.templates.find((item) => item.id === input.id)
      : undefined;
    const value: MeetingTemplate = {
      ...input,
      id: existing?.id ?? crypto.randomUUID(),
      name: input.name.trim(),
      participantStaffIds: participantIds,
      createdBy: existing?.createdBy ?? "demo-admin",
      createdAt: existing?.createdAt ?? now,
      updatedAt: now,
    };
    if (existing) Object.assign(existing, value);
    else store.templates.push(value);
    return value;
  });
}
export async function saveMeetingAsTemplate(
  meeting: Meeting,
  accountRole: "admin" | "staff",
): Promise<MeetingTemplate> {
  return saveTemplate(
    {
      name: `${meeting.title} template`,
      meetingType: meeting.type,
      defaultTitle: meeting.title,
      participantStaffIds: [
        ...new Set(
          meeting.participantSnapshots?.map(
            (participant) => participant.staffId,
          ) ??
            meeting.participants.map(
              (participant) => participant.staffId ?? participant.id,
            ),
        ),
      ],
      agendaTopics: structuredClone(meeting.agendaTopics ?? []),
      active: true,
    },
    accountRole,
  );
}
export async function deactivateTemplate(
  id: string,
  accountRole: "admin" | "staff",
): Promise<MeetingTemplate> {
  if (accountRole !== "admin") throw new ApiError("unauthorized");
  if (!DEMO_MODE)
    return request(`/templates/${encodeURIComponent(id)}/deactivate`, {
      method: "POST",
    });
  return mutate((store) => {
    const template = store.templates.find((item) => item.id === id);
    if (!template) throw new ApiError("notFound");
    template.active = false;
    template.updatedAt = new Date().toISOString();
    return template;
  });
}
export async function getVoiceProfiles(): Promise<VoiceProfile[]> {
  return DEMO_MODE ? readStore().voiceProfiles : request("/voice-profiles");
}
export async function getSpeakerClusters(): Promise<DetectedSpeakerCluster[]> {
  return DEMO_MODE ? readStore().speakerClusters : request("/speaker-clusters");
}
export async function getSpeakerSample(
  clusterId: string,
): Promise<Blob | undefined> {
  if (DEMO_MODE) return undefined;
  const response = await fetch(
    `/api/speaker-clusters/${encodeURIComponent(clusterId)}/sample`,
    { credentials: "include" },
  );
  if (response.status === 404) return undefined;
  if (!response.ok) throw new ApiError("requestFailed");
  return response.blob();
}
export async function identifySpeakerCluster(
  clusterId: string,
  staffId: string,
): Promise<DetectedSpeakerCluster> {
  if (!DEMO_MODE)
    return request(
      `/speaker-clusters/${encodeURIComponent(clusterId)}/identify`,
      {
        method: "POST",
        body: JSON.stringify({ staffId }),
      },
    );
  return mutate((store) => {
    const cluster = store.speakerClusters.find((item) => item.id === clusterId);
    const person = store.people.find((item) => item.id === staffId);
    if (!cluster || !person) throw new ApiError("notFound");
    cluster.identifiedStaffId = staffId;
    cluster.status = store.voiceProfiles.some(
      (profile) => profile.staffId === staffId,
    )
      ? "voice_profile_ready"
      : "identified_without_voice_profile";
    return cluster;
  });
}
export async function enrollVoice(id: string, blob: Blob): Promise<void> {
  if (!blob.size) throw new ApiError("invalidAudio");
  if (!DEMO_MODE) {
    const body = new FormData();
    body.append("audio", blob, "voice.webm");
    return request(`/people/${encodeURIComponent(id)}/voice-enrollment`, {
      method: "POST",
      body,
    });
  }
  await putAudio(`voice-${id}`, blob);
  mutate((s) => {
    const p = s.people.find((p) => p.id === id);
    if (!p) throw new ApiError("notFound");
    p.enrolled = true;
    p.enrollmentKind = "prototype";
    if (!s.voiceProfiles.some((profile) => profile.staffId === id))
      s.voiceProfiles.push({
        id: `voice-${id}`,
        staffId: id,
        status: "prototype",
        createdAt: new Date().toISOString(),
      });
    for (const cluster of s.speakerClusters.filter(
      (item) => item.identifiedStaffId === id,
    ))
      cluster.status = "voice_profile_ready";
    return p;
  });
}
export async function getSystem(): Promise<SystemState> {
  return DEMO_MODE
    ? {
        local: true,
        lastCheckedAt: new Date().toISOString(),
        host: "demo-local",
        services: [
          {
            id: "asr",
            available: true,
            description: "Simulated local speech-to-text service",
          },
          {
            id: "speakers",
            available: true,
            description: "Simulated local speaker timing service",
          },
          {
            id: "automation",
            available: true,
            description: "Simulated local minutes service",
          },
          {
            id: "mail",
            available: true,
            description: "Simulated internal mail service",
          },
          {
            id: "storage",
            available: true,
            description: "Demo browser storage; no hospital capacity claim",
          },
        ],
        capabilities: { autoModeAvailable: AUTO_MODE_AVAILABLE },
      }
    : request("/system");
}
