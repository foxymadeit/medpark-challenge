// EXAMPLE meeting history from Figma. Roles in `participants` are frozen "role then".
import type { Meeting, ParticipantSnapshot, Task, TranscriptLine } from '../types';
import { addDays } from '../lib/format';
import { cardioSummary, cardioTasks, cardioTranscript, execSummary, execTasks, execTranscript, supplySummary, supplyTasks, supplyTranscript } from './minutes';
import { demoPeople, demoYou, YOU_ID } from './people';

const snap = (id: string, roleThen?: string): ParticipantSnapshot => {
  if (id === YOU_ID) return { personId: id, name: demoYou.name, email: demoYou.email, roleThen: roleThen ?? demoYou.role };
  const p = demoPeople.find((x) => x.id === id)!;
  return { personId: id, name: p.name, email: p.email, roleThen: roleThen ?? p.role };
};

export function materialiseTasks(
  date: string,
  meetingId: string,
  list: (Omit<Task, 'due' | 'id'> & { dueInDays: number })[],
): Task[] {
  return list.map(({ dueInDays, ...t }, i) => ({ ...t, id: `${meetingId}-task-${i}`, due: addDays(date, dueInDays) }));
}

function meeting(m: Omit<Meeting, 'tasks' | 'transcript' | 'summary'>, transcript: TranscriptLine[], tasks: typeof cardioTasks, summary = cardioSummary): Meeting {
  return { ...m, transcript, summary, tasks: materialiseTasks(m.date, m.id, tasks) };
}

const all5 = [YOU_ID, 'p-igor', 'p-elena', 'p-victor', 'p-maria'];

export const seedMeetings: Meeting[] = [
  meeting(
    { id: 'm-2609', title: 'Cardiology board', type: 'medical', date: '2026-09-26', durationMin: 48, source: 'recorded', status: 'needs_review', participants: all5.map((id) => snap(id)) },
    cardioTranscript,
    cardioTasks,
  ),
  meeting(
    { id: 'm-2509', title: 'Weekly executive sync', type: 'executive', date: '2026-09-25', durationMin: 35, source: 'recorded', status: 'sent', sentTo: 5, participants: all5.map((id) => snap(id)) },
    execTranscript,
    execTasks,
    execSummary,
  ),
  meeting(
    {
      id: 'm-2409',
      title: 'board_audio_0924.m4a',
      type: 'medical',
      date: '2026-09-24',
      durationMin: 42,
      source: 'uploaded',
      fileName: 'board_audio_0924.m4a',
      status: 'sent',
      sentTo: 5,
      // Roles as they were then — two have changed since (shows "Now: …").
      participants: [snap(YOU_ID, 'Cardiologist'), snap('p-igor'), snap('p-elena', 'Nurse'), snap('p-victor'), snap('p-maria')],
    },
    cardioTranscript,
    cardioTasks,
  ),
  meeting(
    { id: 'm-2309', title: 'Supply planning', type: 'administrative', date: '2026-09-23', durationMin: 22, source: 'recorded', status: 'sent', sentTo: 3, participants: [YOU_ID, 'p-victor', 'p-maria'].map((id) => snap(id)) },
    supplyTranscript,
    supplyTasks,
    supplySummary,
  ),
  meeting(
    { id: 'm-2209', title: 'Tumor board', type: 'medical', date: '2026-09-22', durationMin: 41, source: 'uploaded', fileName: 'tumor_board.m4a', status: 'processing', participants: [YOU_ID, 'p-igor', 'p-elena', 'p-victor'].map((id) => snap(id)) },
    cardioTranscript,
    cardioTasks,
  ),
];
