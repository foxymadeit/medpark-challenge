import { useI18n } from '../i18n/I18nProvider';
import { YOU_ID } from '../mocks';
import { useStore } from '../store/AppStore';
import type { Person } from '../types';

/** Title + participants for the meeting being set up (from the draft/template). */
export function useDraftMeeting() {
  const { t } = useI18n();
  const { draft, templates, resolvePerson, account } = useStore();
  const template = templates.find((x) => x.id === draft.templateId);
  const ids = template?.participantIds ?? [account?.personId ?? YOU_ID];
  const people = ids.map(resolvePerson).filter((p): p is Person => !!p);
  const typeLabel = t(`types.${draft.type}`);
  const title = template?.name ?? t('newMeeting.untitled', { type: typeLabel });
  const count = people.length + draft.emails.length;
  return { title, typeLabel, people, count, template };
}
