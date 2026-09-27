// EXAMPLE medical content from Figma — fictional patients and tasks.
// Speaker ids starting with 'voice-' are voices the diarisation could not match to a participant.
import type { Task, TranscriptLine } from '../types';
import { YOU_ID } from './people';

export const cardioTranscript: TranscriptLine[] = [
  { at: '00:00:12', speakerId: YOU_ID, text: 'Good morning. We have six patients to go through, so let us keep it short.' },
  { at: '00:00:31', speakerId: 'p-elena', text: 'Night shift was calm. Two admissions from the emergency department, both stable.' },
  { at: '00:01:02', speakerId: YOU_ID, text: 'Let us start with [[bed 3]]. How is the blood pressure after the new beta blocker?' },
  { at: '00:01:20', speakerId: 'p-elena', text: 'Around 130 over 80 since yesterday evening. Heart rate in the seventies.' },
  { at: '00:01:44', speakerId: 'p-victor', text: 'Good. I would keep the dose and plan the discharge for [[Wednesday]] if the labs are fine.' },
  { at: '00:02:14', speakerId: YOU_ID, text: '[[Bed 8]]: I will repeat the echo [[tomorrow]] and we reduce the noradrenaline dose [[today]].' },
  { at: '00:02:52', speakerId: 'p-igor', text: 'From the anaesthesia side the reduction is fine. I will watch the lactate every four hours.' },
  { at: '00:03:30', speakerId: 'p-elena', text: 'The family of [[bed 8]] asked for an update. Can someone call them after the round?' },
  { at: '00:03:47', speakerId: YOU_ID, text: 'I will call them myself before noon.' },
  { at: '00:04:15', speakerId: 'p-victor', text: '[[Bed 12]] is two days after the bypass. Drains are almost dry, I want to remove them [[tomorrow]] morning.' },
  { at: '00:04:58', speakerId: 'p-elena', text: 'Pain is under control with paracetamol. She walked to the window yesterday.' },
  { at: '00:05:36', speakerId: YOU_ID, text: 'Great progress. Physiotherapy twice a day from now on, please.' },
  { at: '00:06:10', speakerId: 'p-maria', text: 'A quick note: the second echo machine is back from service, so the waiting list should get shorter.' },
  { at: '00:06:42', speakerId: YOU_ID, text: 'Thank you, Maria. That helps with [[bed 8]] as well.' },
  // A voice the system could not match to any participant (e.g. a lab colleague who stepped in).
  { at: '00:07:05', speakerId: 'voice-1', text: 'Sorry to interrupt, the potassium for [[bed 3]] came back at 5.4.' },
  { at: '00:07:40', speakerId: 'p-elena', text: 'Noted for [[bed 8]]. [[Room 204]] still has fever since [[Friday]].' },
  { at: '00:08:12', speakerId: 'p-victor', text: 'Cultures from [[room 204]] came back this morning, a gram negative in the blood.' },
  { at: '00:09:05', speakerId: 'p-igor', text: 'I will check antibiotic sensitivity for [[room 204]] by [[Monday]].' },
  { at: '00:09:40', speakerId: YOU_ID, text: 'Until then we continue the current antibiotic and repeat the CRP every day.' },
  { at: '00:10:02', speakerId: 'voice-1', text: 'I will send the full panel to the ward by [[noon]].' },
  { at: '00:10:18', speakerId: 'p-elena', text: '[[Bed 5]] is asking again about going home. The INR was 2.4 today.' },
  { at: '00:10:51', speakerId: 'p-victor', text: 'That is in range. If it stays there [[tomorrow]] we can discharge with a follow-up in two weeks.' },
  { at: '00:11:26', speakerId: 'p-maria', text: 'Discharge letters need to go through the new system from October, please remember.' },
  { at: '00:11:58', speakerId: YOU_ID, text: 'Understood. Any other concerns before we close?' },
  { at: '00:12:10', speakerId: 'p-igor', text: 'Nothing from me.' },
  { at: '00:12:31', speakerId: YOU_ID, text: 'Thank you, [[Dr. Rusu]]. Next review on [[28 Sep]].' },
];

/** MOCK AI summary: key points of the meeting, in order. */
export const cardioSummary: string[] = [
  'Six patients reviewed. Night shift was calm; two admissions from the emergency department, both stable.',
  'Bed 3: blood pressure around 130/80 on the new beta blocker; dose kept, discharge planned for Wednesday if labs are fine. Potassium came back at 5.4.',
  'Bed 8: noradrenaline to be reduced today and the echo repeated tomorrow; lactate checked every four hours. Dr. Popescu will call the family before noon.',
  'Bed 12: two days after bypass, pain controlled; drains out tomorrow morning, physiotherapy twice a day.',
  'Room 204: gram-negative bacteraemia; current antibiotic continues with daily CRP until sensitivity is known on Monday.',
  'Bed 5: INR 2.4; discharge tomorrow with follow-up in two weeks if it stays in range. Discharge letters move to the new system from October.',
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

export const execSummary: string[] = ['Budget for the ICU monitors is approved for October.', 'Purchase order to be sent by Wednesday.'];

export const execTasks: (Omit<Task, 'due' | 'id'> & { dueInDays: number })[] = [
  { ownerId: 'p-maria', patient: 'ICU', title: 'Send purchase order for monitors', dueInDays: 5 },
];

export const supplyTranscript: TranscriptLine[] = [
  { at: '00:00:40', speakerId: 'p-maria', text: 'Stock of sterile gloves in [[Room 110]] runs out on [[25 Sep]].' },
];

export const supplySummary: string[] = ['Sterile gloves in Room 110 run out on 25 Sep; reorder needed.'];

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
