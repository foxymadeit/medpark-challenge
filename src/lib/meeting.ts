import { useI18n } from '../i18n/I18nProvider';
import { YOU_ID } from '../mocks';
import { useStore } from '../store/AppStore';
import type { Meeting, Person } from '../types';

/** Title + participants for the meeting being set up (from the draft/template). */
export function useDraftMeeting() {
  const { t } = useI18n();
  const { draft, templates, resolvePerson, account } = useStore();
  const template = templates.find((x) => x.id === draft.templateId);
  const ids = template?.participantIds ?? [account?.personId ?? YOU_ID];
  const people = ids.map(resolvePerson).filter((p): p is Person => !!p);
  const typeLabel = t(`types.${draft.type}`);
  const title = draft.title?.trim() || template?.name || t(`newMeeting.defaultName.${draft.type}`);
  const count = people.length + draft.emails.length;
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
