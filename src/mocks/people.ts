// EXAMPLE DATA from Figma — not real people. Replace with the hospital directory.
import type { Person } from '../types';

/** The signed-up user always gets this id. */
export const YOU_ID = 'p-you';

/** Colleagues referenced by templates, history and the demo transcript. */
export const demoPeople: Person[] = [
  { id: 'p-igor', name: 'Dr. Igor Rusu', email: 'igor.rusu@medpark.md', role: 'Anesthesiologist', access: 'organizer' },
  { id: 'p-elena', name: 'Elena Ciobanu', email: 'elena.ciobanu@medpark.md', role: 'Head Nurse, ICU', access: 'receives' },
  { id: 'p-victor', name: 'Dr. Victor Lungu', email: 'victor.lungu@medpark.md', role: 'Surgeon', access: 'receives' },
  { id: 'p-maria', name: 'Maria Rotaru', email: 'maria.rotaru@medpark.md', role: 'Hospital Administrator', access: 'organizer' },
];

/** Rows pre-filled on onboarding step 3 ("Who gets the minutes?"). */
export const onboardingSuggestions = ['p-igor', 'p-elena'];

/** Extra roles offered in the inline role dropdown (after the current role). */
export const roleSuggestions = ['Nurse', 'Resident'];

/** Stand-in for the signed-up user inside seeded history (frozen snapshot name). */
export const demoYou = { name: 'Dr. Ana Popescu', email: 'ana.popescu@medpark.md', role: 'Head of Cardiology' };

/** Demo logins shown on the Log in page (any password). Loads the full demo dataset in a fresh browser. */
export const demoAccounts: { personId: string; email: string }[] = [
  { personId: YOU_ID, email: demoYou.email }, // Admin
  { personId: 'p-igor', email: 'igor.rusu@medpark.md' }, // Organizer
];

/** Directory used by the demo dataset: the Admin plus every colleague. */
export const demoDirectory = (): Person[] => [{ id: YOU_ID, name: demoYou.name, email: demoYou.email, role: demoYou.role, access: 'admin' }, ...demoPeople];
