import { defaultParticipants } from '../mocks/defaultParticipants';
import { directory } from '../mocks/directory';
import type { Draft, DraftParticipant } from '../store/AppStore';
import type { Meeting, MeetingType, Person, Template } from '../types';

/**
 * The participant chips on New meeting: what the organizer set, else the template's people,
 * else the defaults for the meeting type (src/mocks/defaultParticipants.ts).
 */
export function draftParticipants(draft: Draft, template: Template | undefined, resolve: (id: string) => Person | undefined): DraftParticipant[] {
  if (draft.participants) return draft.participants;
  if (template) return template.participantIds.map(resolve).filter((p): p is Person => !!p).map((p) => ({ name: p.name, role: p.role }));
  return defaultParticipants[draft.type].map((p) => ({ ...p }));
}

/** Words of a name without titles ("Dr. Ana Popescu" → ana, popescu). */
const nameWords = (name: string) =>
  name
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => !/^(dr|prof)\.?$/.test(w));

/**
 * People whose first name or surname starts with what's typed ("a" → Ana, Andrei; not Maria),
 * first-name matches first. Titles like "Dr." are ignored; role and email aren't searched.
 */
export function suggestByName<T extends { name: string }>(pool: T[], query: string, exclude: (p: T) => boolean, limit = 6): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const rank = (name: string) => (nameWords(name)[0]?.startsWith(q) ? 0 : nameWords(name).some((w) => w.startsWith(q)) ? 1 : 2);
  return pool
    .filter((p) => !exclude(p) && rank(p.name) < 2)
    .sort((a, b) => rank(a.name) - rank(b.name) || nameWords(a.name).join(' ').localeCompare(nameWords(b.name).join(' ')))
    .slice(0, limit);
}

/**
 * People to suggest for a meeting type (template editor), best first: who came most often to past meetings of
 * that type, then the type's default people in the directory, then the rest of that type by name.
 */
export function suggestForType(type: MeetingType, meetings: Meeting[], people: Person[], exclude: (id: string) => boolean, limit: number): Person[] {
  const attended = new Map<string, number>();
  for (const m of meetings) if (m.type === type) for (const p of m.participants) attended.set(p.personId, (attended.get(p.personId) ?? 0) + 1);
  const entry = new Map(directory.map((d) => [d.id, d]));
  const ofType = (p: Person) => entry.get(p.id)?.meetingType === type;
  const rank = (p: Person) => [-(attended.get(p.id) ?? 0), ofType(p) && entry.get(p.id)?.default ? 0 : 1];
  return people
    .filter((p) => !exclude(p.id) && (attended.has(p.id) || ofType(p)))
    .sort((a, b) => {
      const [ra, rb] = [rank(a), rank(b)];
      return ra[0] - rb[0] || ra[1] - rb[1] || nameWords(a.name).join(' ').localeCompare(nameWords(b.name).join(' '));
    })
    .slice(0, Math.max(0, limit));
}
