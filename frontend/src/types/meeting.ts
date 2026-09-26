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
}
export interface CreateMeetingInput {
  title: string;
  type: MeetingType;
  inputMode: "record" | "upload";
  participants?: Participant[];
}
export interface SystemState {
  local: boolean;
  lastCheckedAt?: string;
  host?: string;
  services: { id: string; available: boolean; description?: string }[];
  capabilities?: { autoModeAvailable: boolean };
}
