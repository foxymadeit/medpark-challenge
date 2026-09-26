// EXAMPLE medical content from Figma — fictional patients and tasks.
import type { Task, TranscriptLine } from '../types';
import { YOU_ID } from './people';

export const cardioTranscript: TranscriptLine[] = [
  { at: '00:02:14', speakerId: YOU_ID, text: '[[Bed 8]]: I will repeat the echo [[tomorrow]] and we reduce the noradrenaline dose [[today]].' },
  { at: '00:07:40', speakerId: 'p-elena', text: 'Noted for [[bed 8]]. [[Room 204]] still has fever since [[Friday]].' },
  { at: '00:09:05', speakerId: 'p-igor', text: 'I will check antibiotic sensitivity for [[room 204]] by [[Monday]].' },
  { at: '00:12:31', speakerId: YOU_ID, text: 'Thank you, [[Dr. Rusu]]. Next review on [[28 Sep]].' },
];

/** Tasks with due dates as day offsets from the meeting date. */
export const cardioTasks: (Omit<Task, 'due' | 'id'> & { dueInDays: number })[] = [
  { ownerId: YOU_ID, patient: 'Bed 8', title: 'Repeat echo', dueInDays: 1 },
  { ownerId: YOU_ID, patient: 'Bed 8', title: 'Reduce noradrenaline dose', dueInDays: 0 },
  { ownerId: 'p-igor', patient: 'Room 204', title: 'Check antibiotic sensitivity', dueInDays: 2 },
];

export const execTranscript: TranscriptLine[] = [
  { at: '00:01:05', speakerId: YOU_ID, text: 'Budget for the [[ICU]] monitors is approved for [[October]].' },
  { at: '00:04:22', speakerId: 'p-maria', text: 'I will send the purchase order by [[Wednesday]].' },
];

export const execTasks: (Omit<Task, 'due' | 'id'> & { dueInDays: number })[] = [
  { ownerId: 'p-maria', patient: 'ICU', title: 'Send purchase order for monitors', dueInDays: 5 },
];

export const supplyTranscript: TranscriptLine[] = [
  { at: '00:00:40', speakerId: 'p-maria', text: 'Stock of sterile gloves in [[Room 110]] runs out on [[25 Sep]].' },
];

export const supplyTasks: (Omit<Task, 'due' | 'id'> & { dueInDays: number })[] = [
  { ownerId: 'p-maria', patient: 'Room 110', title: 'Reorder sterile gloves', dueInDays: 1 },
];

/**
 * MOCK low-confidence words: alternative readings the speech model considered.
 * Keyed by lowercase word/term. Words listed here get a dotted underline in Review.
 */
export const transcriptAlternatives: Record<string, string[]> = {
  echo: ['ECG', 'echocardiogram'],
  noradrenaline: ['norepinephrine', 'adrenaline'],
  reduce: ['review'],
  'bed 8': ['Bed 18', 'Bed 6'],
  'room 204': ['Room 214', 'Room 240'],
  friday: ['Tuesday'],
  sensitivity: ['susceptibility'],
  'dr. rusu': ['Dr. Russo', 'Dr. Rusnac'],
  '28 sep': ['18 Sep', '28 Oct'],
};
