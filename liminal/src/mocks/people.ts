// EXAMPLE DATA — not real people. The directory itself lives in ./directory.ts; this file shapes it for the app.
import type { Person } from '../types';
import { directory, emailFor, YOU_ID } from './directory';

export { YOU_ID } from './directory';

const toPerson = (d: (typeof directory)[number]): Person => ({ id: d.id, name: d.name, email: emailFor(d.name), role: d.role, access: d.access });

const you = directory.find((d) => d.id === YOU_ID)!;

/** Everyone in the directory except the signed-up user (templates, history and the demo transcript refer to them by id). */
export const demoPeople: Person[] = directory.filter((d) => d.id !== YOU_ID).map(toPerson);

/** Rows pre-filled on onboarding step 3 ("Who gets the minutes?"). */
export const onboardingSuggestions = ['p-igor', 'p-elena'];

/** Extra roles offered in the inline role dropdown (after the current role). */
export const roleSuggestions = ['Nurse', 'Resident'];

/** Stand-in for the signed-up user inside seeded history (frozen snapshot name). */
export const demoYou = { name: you.name, email: emailFor(you.name), role: you.role };

/** Demo logins shown on the Log in page (any password). Loads the full demo dataset in a fresh browser. */
export const demoAccounts: { personId: string; email: string }[] = [
  { personId: YOU_ID, email: demoYou.email }, // Admin
  { personId: 'p-igor', email: emailFor('Dr. Igor Rusu') }, // Organizer
];

/** Directory used by the demo dataset: the Admin plus every colleague. */
export const demoDirectory = (): Person[] => [{ ...toPerson(you), access: 'admin' }, ...demoPeople];
