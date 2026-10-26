// Default participants per meeting type, pre-filled on New meeting. Not a separate list:
// they are the people marked `default: true` in the directory (./directory.ts) — edit them there.
import type { MeetingType } from '../types';
import { directory } from './directory';

export interface DefaultParticipant {
  name: string;
  role: string;
}

const defaultsFor = (type: MeetingType): DefaultParticipant[] => directory.filter((d) => d.meetingType === type && d.default).map((d) => ({ name: d.name, role: d.role }));

export const defaultParticipants: Record<MeetingType, DefaultParticipant[]> = {
  medical: defaultsFor('medical'),
  executive: defaultsFor('executive'),
  administrative: defaultsFor('administrative'),
};
