export type MeetingType = "medical" | "executive" | "administrative";
export type MeetingStatus =
  | "draft"
  | "recording"
  | "uploaded"
  | "processing"
  | "sending_soon"
  | "ready"
  | "sending"
  | "sent"
  | "stopped"
  | "failed";
export type ProcessingState = "queued" | "running" | "failed" | "complete";
export type DeliveryState =
  "scheduled" | "stopped" | "sending" | "sent" | "failed";
export type SendMode = "manual" | "auto";
export type ReviewState = "not_ready" | "needs_review" | "reviewed";
export interface CorrectionFeedback {
  meetingId: string;
  field: string;
  before: string;
  after: string;
  sourceTimestamp?: number;
  createdAt: string;
}
export interface Participant {
  id: string;
  staffId?: string;
  name: string;
  email?: string;
  role?: string;
  department?: MeetingType;
  speakerId?: string;
  speakerSlot?: number;
  enrolled?: boolean;
  speakingSeconds?: number;
  enrollmentKind?: "prototype" | "verified";
  active?: boolean;
}
export type AccountRole = "admin" | "staff";
export interface UserAccount {
  id: string;
  username: string;
  email?: string;
  role: AccountRole;
  staffProfileId?: string;
  active: boolean;
  createdAt: string;
  createdBy: string;
}
export interface StaffProfile {
  id: string;
  name: string;
  email: string;
  active: boolean;
  createdAt: string;
  createdBy: string;
}
export interface StaffRoleAssignment {
  id: string;
  staffId: string;
  title: string;
  department: string;
  validFrom: string;
  validTo: string | null;
  createdBy: string;
}
export interface DistributionList {
  id: string;
  name: string;
  email: string;
  active: boolean;
}
export interface MeetingParticipantSnapshot {
  staffId: string;
  nameAtMeeting: string;
  emailAtMeeting: string;
  roleTitleAtMeeting: string;
  departmentAtMeeting: string;
  speakerId?: string;
}
export interface MeetingDelivery {
  id: string;
  meetingId: string;
  subject: string;
  body: string;
  recipients: Pick<
    MeetingParticipantSnapshot,
    "staffId" | "nameAtMeeting" | "emailAtMeeting"
  >[];
  attachmentFilename: string;
  status: "draft" | "sending" | "sent" | "failed";
  sentAt?: string;
}
export interface MeetingArtifact {
  id: string;
  meetingId: string;
  type:
    | "minutes_docx"
    | "minutes_pdf"
    | "transcript_txt"
    | "speakers_rttm"
    | "recording";
  filename: string;
  createdAt: string;
}
export interface VoiceProfile {
  id: string;
  staffId: string;
  status: "prototype" | "verified";
  languages?: ("en" | "ro" | "ru")[];
  createdAt: string;
}
export type SpeakerIdentityState =
  "unidentified" | "identified_without_voice_profile" | "voice_profile_ready";
export interface DetectedSpeakerCluster {
  id: string;
  meetingId: string;
  speakerId: string;
  label: string;
  speakingSeconds: number;
  sampleAvailable: boolean;
  identifiedStaffId: string | null;
  status: SpeakerIdentityState;
}
export interface AgendaTopic {
  id: string;
  text: string;
  order: number;
}
export interface MeetingTemplate {
  id: string;
  name: string;
  meetingType: MeetingType;
  defaultTitle?: string;
  participantStaffIds: string[];
  agendaTopics: AgendaTopic[];
  recurrence?: {
    type: "daily" | "weekly" | "monthly" | "custom";
    label: string;
    weekday?: number;
    time?: string;
  };
  active: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}
export interface TranscriptSegment {
  id: string;
  speakerId: string | null;
  startSeconds: number;
  endSeconds: number;
  text: string;
  language?: "ro" | "ru" | "en" | "mixed";
}
export interface Decision {
  id: string;
  text: string;
}
export interface ActionItem {
  id: string;
  task: string;
  ownerParticipantId: string | null;
  ownerStaffId?: string | null;
  deadline: string | null;
  sourceTimestampSeconds?: number;
  completed: boolean;
}
export type MinutesLanguage = "ro" | "ru" | "en";
export type StageId =
  | "transcribe"
  | "speakers"
  | "extract"
  | "verify"
  | "write"
  | "render"
  | "minutes"
  | "send";
export interface ProcessingStage {
  id: StageId;
  state: "pending" | "running" | "done" | "failed";
  done?: number;
  total?: number;
  startedAt?: string;
  finishedAt?: string;
  etaAt?: string;
}
export interface ConfirmItem {
  id: string;
  text: string;
  reason: string;
  /** The checks' own messages, translated for the reader at display time. */
  problems?: string[];
  decision?: "keep" | "remove";
}
export interface LocalizedMinutes {
  summary: string;
  decisions: Decision[];
  actionItems: { id: string; task: string }[];
}
export interface SpeakerSegment {
  speakerId: string;
  startSeconds: number;
  endSeconds: number;
}
export interface Meeting {
  id: string;
  title: string;
  type: MeetingType;
  status: MeetingStatus;
  createdAt: string;
  startedAt?: string;
  endedAt?: string;
  inputMode: "record" | "upload";
  audioFilename?: string;
  durationSeconds?: number;
  audioBytes?: number;
  participants: Participant[];
  participantSnapshots?: MeetingParticipantSnapshot[];
  distributionList: string[];
  progress?: number;
  summary?: string;
  decisions?: Decision[];
  actionItems?: ActionItem[];
  transcript?: TranscriptSegment[];
  speakerTimeline?: SpeakerSegment[];
  sendScheduledAt?: string | null;
  sentAt?: string | null;
  sendingStartedAt?: string;
  deliveryFailedAt?: string;
  processingState?: ProcessingState;
  deliveryState?: DeliveryState;
  failureReference?: string;
  processingStartedAt?: string;
  processingEndsAt?: string;
  sendWindowSeconds?: number;
  reviewFlags?: string[];
  demoGenerated?: boolean;
  sendMode: SendMode;
  reviewState?: ReviewState;
  templateId?: string;
  agendaTopics?: AgendaTopic[];
  delivery?: MeetingDelivery;
  artifacts?: MeetingArtifact[];
  stages?: ProcessingStage[];
  confirmItems?: ConfirmItem[];
  minutesByLanguage?: Partial<Record<MinutesLanguage, LocalizedMinutes>>;
  documents?: MinutesLanguage[];
  checked?: { verified: number; total: number };
}
export interface CreateMeetingInput {
  title: string;
  type: MeetingType;
  inputMode: "record" | "upload";
  participants?: Participant[];
  templateId?: string;
  agendaTopics?: AgendaTopic[];
  sendMode?: SendMode;
}
export interface SystemState {
  local: boolean;
  lastCheckedAt?: string;
  host?: string;
  services: { id: string; available: boolean; description?: string }[];
  capabilities?: { autoModeAvailable: boolean };
}
