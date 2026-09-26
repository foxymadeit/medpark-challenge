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
export interface Participant {
  id: string;
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
  processingState?: ProcessingState;
  deliveryState?: DeliveryState;
  failureReference?: string;
  processingStartedAt?: string;
  processingEndsAt?: string;
  sendWindowSeconds?: number;
  reviewFlags?: string[];
  demoGenerated?: boolean;
}
export interface CreateMeetingInput {
  title: string;
  type: MeetingType;
  inputMode: "record" | "upload";
  participants: Participant[];
}
export interface SystemState {
  local: boolean;
  services: { id: string; available: boolean }[];
}
