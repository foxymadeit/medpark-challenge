import { defaultParticipants } from '../mocks/defaultParticipants';
import type { Draft, DraftParticipant } from '../store/AppStore';
import type { Person, Template } from '../types';

/**
 * The participant chips on New meeting: what the organizer set, else the template's people,
 * else the defaults for the meeting type (src/mocks/defaultParticipants.ts).
 */
export function draftParticipants(draft: Draft, template: Template | undefined, resolve: (id: string) => Person | undefined): DraftParticipant[] {
  if (draft.participants) return draft.participants;
  if (template) return template.participantIds.map(resolve).filter((p): p is Person => !!p).map((p) => ({ name: p.name, role: p.role }));
  return defaultParticipants[draft.type].map((p) => ({ ...p }));
}
