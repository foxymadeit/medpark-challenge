import { useI18n } from '../i18n/I18nProvider';
import { demoPeople, YOU_ID } from '../mocks';
import { draftParticipants } from './participants';
import { useStore } from '../store/AppStore';
import type { Meeting, Person } from '../types';

/** Title + participants for the meeting being set up (from the draft/template). */
export function useDraftMeeting() {
  const { t } = useI18n();
  const { draft, templates, people: directory, resolvePerson, account } = useStore();
  const template = templates.find((x) => x.id === draft.templateId);
  // Organizer + the participant chips; directory people resolve to their record, other names count as guests.
  const you = resolvePerson(account?.personId ?? YOU_ID);
  const chips = draftParticipants(draft, template, resolvePerson);
  const byName = (name: string) => [...directory, ...demoPeople].find((p) => p.name.toLowerCase() === name.toLowerCase());
  const people = [you, ...chips.map((c) => byName(c.name))].filter((p, i, all): p is Person => !!p && all.findIndex((x) => x?.id === p.id) === i);
  const guests = chips.filter((c) => !byName(c.name) && c.name.toLowerCase() !== you?.name.toLowerCase()).length;
  const typeLabel = t(`types.${draft.type}`);
  const title = draft.title?.trim() || template?.name || t(`newMeeting.defaultName.${draft.type}`);
  const count = people.length + guests;
  return { title, typeLabel, people, count, template };
}

/**
 * Name for a transcript speaker: the meeting's participant snapshot, else the directory,
 * else "Speaker n" for voices nobody could be matched to (numbered by first appearance).
 */
export function speakerNamer(meeting: Meeting, resolve: (id: string) => { name: string } | undefined, t: (key: string, vars?: Record<string, string | number>) => string) {
  const unknown = [...new Set(meeting.transcript.map((l) => l.speakerId))].filter((id) => !meeting.participants.some((p) => p.personId === id) && !resolve(id));
  return (pid: string) => meeting.participants.find((p) => p.personId === pid)?.name ?? resolve(pid)?.name ?? t('recording.speakerN', { n: unknown.indexOf(pid) + 1 });
}
