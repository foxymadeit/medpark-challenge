import { useI18n } from '../i18n/I18nProvider';
import { uid } from '../lib/format';
import { useStore } from '../store/AppStore';
import type { Meeting, ParticipantSnapshot, Person } from '../types';
import { AddPersonRow } from './AddPersonRow';
import { Avatar } from './Avatar';

/**
 * Who was in the meeting, and so who gets the MoM (Review, right of the MoM card): avatar, name, email.
 * "+ Add participant" is the list's last cell (same size as a person, also in the 2–3 column layout): a saved
 * contact (suggested as you type, people already here left out), a new name, or just an email (a guest, format checked).
 */
export function ParticipantsPanel({ meeting, onChange }: { meeting: Meeting; onChange: (participants: ParticipantSnapshot[]) => void }) {
  const { t } = useI18n();
  const { people } = useStore();
  const list = meeting.participants;
  const isIn = (p: Person) => list.some((x) => x.personId === p.id || (!!p.email && x.email?.toLowerCase() === p.email.toLowerCase()));

  return (
    <aside className="card people-panel" aria-labelledby="rv-people">
      <h2 id="rv-people" className="people-panel__title">
        {t('common.participantsCount', { count: list.length })}
      </h2>
      <ul className="people-panel__list">
        {list.map((p) => (
          <li key={p.personId} className="people-panel__person">
            <Avatar name={p.name} />
            <span className="who__text">
              <span className="people-panel__name truncate">{p.name}</span>
              <span className="people-panel__email truncate" title={p.email}>
                {p.email ?? t('review.noEmail')}
              </span>
            </span>
          </li>
        ))}
        <li>
          <AddPersonRow
            pool={people.filter((p) => !isIn(p))}
            known={[...people, ...list]}
            onPick={(p) => onChange([...list, { personId: p.id, name: p.name, email: p.email, roleThen: p.role }])}
            onCreate={(typed) => onChange([...list, { personId: uid('guest'), roleThen: '', ...typed }])}
          />
        </li>
      </ul>
    </aside>
  );
}
