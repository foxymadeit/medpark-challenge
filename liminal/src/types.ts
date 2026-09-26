import type { ColorKey } from './lib/colors';

export type Access = 'receives' | 'organizer' | 'admin';
export type MeetingType = 'medical' | 'executive' | 'administrative';
export type MeetingStatus = 'processing' | 'needs_review' | 'sent';
export type MeetingSource = 'recorded' | 'uploaded';

export const MEETING_TYPES: MeetingType[] = ['medical', 'executive', 'administrative'];
export const ACCESS_LEVELS: Access[] = ['receives', 'organizer', 'admin'];

export interface Person {
  id: string;
  name: string;
  email?: string;
  role: string;
  access: Access;
}

export interface Account {
  personId: string;
  name: string;
  email: string;
  role: string;
  department: string;
  meetingTypes: MeetingType[];
  preferences?: Preferences;
}

export interface Preferences {
  /** auto = minutes are sent as soon as processing finishes, without review. */
  reviewMode: 'manual' | 'auto';
  /** Chosen microphone (a browser deviceId, or a mock id before permission). */
  micId?: string;
}

export interface Template {
  id: string;
  name: string;
  type: MeetingType;
  participantIds: string[];
  /** Colour picked in the editor (palette key); older templates fall back to a colour from their name. */
  color?: ColorKey;
}

/** One transcript utterance. Keywords are wrapped in [[double brackets]]. */
export interface TranscriptLine {
  at: string; // "00:02:14"
  speakerId: string;
  text: string;
  /** Present once the reviewer corrected a word; replaces `text` for display. */
  tokens?: TranscriptToken[];
  /** Set when the whole sentence was rewritten in review. */
  edited?: boolean;
}

/** kw = highlighted term (patient, bed, room, name, date); space/punct are not clickable. */
export interface TranscriptToken {
  kind: 'kw' | 'word' | 'punct' | 'space';
  text: string;
  fixed?: boolean;
  /** Language the reviewer flagged for this word (training signal for the speech model). */
  lang?: SpokenLang;
}

/** Languages a word can be flagged as (the interface languages). */
export type SpokenLang = 'ro' | 'ru' | 'en';
export const SPOKEN_LANGS: SpokenLang[] = ['ro', 'ru', 'en'];

export interface Task {
  id: string;
  ownerId: string;
  patient: string; // "Bed 8", "Room 204"
  title: string;
  due: string; // ISO date
}

/** Participant as recorded at the meeting date — frozen once sent. */
export interface ParticipantSnapshot {
  personId: string;
  name: string;
  roleThen: string;
  email?: string;
}

export interface Meeting {
  id: string;
  title: string;
  type: MeetingType;
  date: string; // ISO date
  durationMin: number;
  source: MeetingSource;
  fileName?: string;
  status: MeetingStatus;
  participants: ParticipantSnapshot[];
  transcript: TranscriptLine[];
  /** Key points of the meeting (the MoM summary), shown above the tasks. */
  summary: string[];
  tasks: Task[];
  sentTo?: number;
}
