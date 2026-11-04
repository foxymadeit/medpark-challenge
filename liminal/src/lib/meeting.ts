import { useI18n } from '../i18n/I18nProvider';
import { demoPeople, YOU_ID } from '../mocks';
import { draftParticipants } from './participants';
import { useStore } from '../store/AppStore';
import type { Lang } from '../i18n/I18nProvider';
import type { Meeting, Person } from '../types';
import { formatDayMonth } from './format';

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

type Resolve = (id: string) => { name: string } | undefined;
type T = (key: string, vars?: Record<string, string | number>) => string;

/**
 * Who a speaker id is, worked out once per meeting: `nameOf` gives the meeting's participant snapshot, else the
 * directory, else "Speaker n" for voices nobody could be matched to (numbered by first appearance); `badgeOf` gives
 * such a voice's avatar ("S1" on its speaker colour, --sm-speaker-01…04 repeating), undefined for known people.
 */
export function speakers(meeting: Meeting, resolve: Resolve, t: T) {
  const unknown = [...new Set(meeting.transcript.map((l) => l.speakerId))].filter((id) => !meeting.participants.some((p) => p.personId === id) && !resolve(id));
  return {
    nameOf: (pid: string) => meeting.participants.find((p) => p.personId === pid)?.name ?? resolve(pid)?.name ?? t('recording.speakerN', { n: unknown.indexOf(pid) + 1 }),
    badgeOf: (pid: string) => {
      const i = unknown.indexOf(pid);
      return i < 0 ? undefined : { label: `S${i + 1}`, fill: `var(--sm-speaker-${String((i % 4) + 1).padStart(2, '0')})` };
    },
  };
}

/** Just the names (screens that show no speaker avatars). */
export const speakerNamer = (meeting: Meeting, resolve: Resolve, t: T) => speakers(meeting, resolve, t).nameOf;

/** The meeting's heading everywhere it's shown as a document: "Cardiology board · 26 Sep" (review screen, MoM preview, PDF). */
/** The summary as it goes out: its points as one running text (a point without closing punctuation gets a full stop). */
export const summaryProse = (points: string[]) => points.map((p) => (/[.!?…]$/.test(p.trim()) ? p.trim() : `${p.trim()}.`)).join(' ');

export const meetingHeading = (meeting: Pick<Meeting, 'title' | 'date'>, lang: Lang, format = formatDayMonth) => `${meeting.title} · ${format(meeting.date, lang)}`;
