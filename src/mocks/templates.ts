// EXAMPLE templates from Figma.
import type { Template } from '../types';
import { YOU_ID } from './people';

export const seedTemplates: Template[] = [
  { id: 't-cardio', name: 'Cardiology board', type: 'medical', participantIds: [YOU_ID, 'p-igor', 'p-elena', 'p-victor', 'p-maria'] },
  { id: 't-tumor', name: 'Tumor board', type: 'medical', participantIds: [YOU_ID, 'p-igor', 'p-elena', 'p-victor'] },
  { id: 't-exec', name: 'Weekly executive sync', type: 'executive', participantIds: [YOU_ID, 'p-igor', 'p-elena', 'p-victor', 'p-maria'] },
  { id: 't-supply', name: 'Supply planning', type: 'administrative', participantIds: [YOU_ID, 'p-victor', 'p-maria'] },
];
