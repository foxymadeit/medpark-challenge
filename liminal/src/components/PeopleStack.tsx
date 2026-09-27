import { useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { useStore } from '../store/AppStore';
import type { Person } from '../types';
import { Avatar } from './Avatar';
import { PersonProfileDialog } from './PersonProfile';

/** Overlapping avatars (hover = name, click = profile) + the first two names. */
export function PeopleStack({ ids, max = 5, names = true }: { ids: string[]; max?: number; names?: boolean }) {
  const { t } = useI18n();
  const { account, resolvePerson } = useStore();
  const [profileId, setProfileId] = useState<string | null>(null);
  const people = ids.map(resolvePerson).filter((p): p is Person => !!p);
  const label = (p: Person) => (p.id === account?.personId ? t('common.meName', { name: p.name }) : p.name);
  const shown = people.slice(0, 2).map(label);
  const rest = people.length - shown.length;
  const hidden = people.length - Math.min(people.length, max);
  return (
    <div className="people-stack">
      <span className="avatar-stack">
        {people.slice(0, max).map((p) => (
          <button key={p.id} type="button" className="avatar-tip" data-name={label(p)} aria-label={t('profile.open', { name: label(p) })} onClick={() => setProfileId(p.id)}>
            <Avatar name={p.name} />
          </button>
        ))}
        {hidden > 0 && !names && <span className="avatar avatar--more">+{hidden}</span>}
      </span>
      {names && (
        <span className="note truncate">
          {shown.join(', ')}
          {rest > 0 && ` ${t('templates.more', { n: rest })}`}
        </span>
      )}
      {profileId && <PersonProfileDialog personId={profileId} onClose={() => setProfileId(null)} />}
    </div>
  );
}
