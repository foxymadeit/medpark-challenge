// EXAMPLE templates from Figma.
import type { Template } from '../types';
import { YOU_ID } from './people';

export const seedTemplates: Template[] = [
  { id: 't-tumor', color: 'violet', name: 'Tumor board', type: 'medical', participantIds: [YOU_ID, 'p-igor', 'p-elena', 'p-victor'] },
  { id: 't-cardio', color: 'rose', name: 'Cardiology board', type: 'medical', participantIds: [YOU_ID, 'p-igor', 'p-elena', 'p-victor', 'p-maria'] },
  { id: 't-exec', color: 'blue', name: 'Weekly executive sync', type: 'executive', participantIds: [YOU_ID, 'p-igor', 'p-elena', 'p-victor', 'p-maria'] },
  { id: 't-supply', color: 'amber', name: 'Supply planning', type: 'administrative', participantIds: [YOU_ID, 'p-victor', 'p-maria'] },
];
