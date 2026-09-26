import { EnvelopeSimpleIcon, UsersThreeIcon } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { formatDayMonth } from '../lib/format';
import { useStore } from '../store/AppStore';
import { Avatar } from './Avatar';
import { Button } from './Button';
import { Dialog } from './Dialog';

/** Read-only profile card: contact, access, the templates they're in and their meetings. */
export function PersonProfileDialog({ personId, onClose }: { personId: string; onClose: () => void }) {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const { account, resolvePerson, templates, meetings } = useStore();
  const person = resolvePerson(personId);
  if (!person) return null;

  const inTemplates = templates.filter((tpl) => tpl.participantIds.includes(personId));
  const attended = meetings.filter((m) => m.participants.some((p) => p.personId === personId)).sort((a, b) => b.date.localeCompare(a.date));
  const last = attended[0];

  return (
    <Dialog title={t('profile.title')} onClose={onClose}>
      <div className="profile__head">
        <Avatar name={person.name} />
        <span className="who__text">
          <span className="profile__name">
            <span className="t-h2">{person.name}</span>
            {person.id === account?.personId && <span className="tag tag--me">{t('common.me')}</span>}
          </span>
          {person.role && <span className="who__sub">{person.role}</span>}
        </span>
      </div>
      <dl className="profile__facts">
        <div>
          <dt>{t('profile.email')}</dt>
          <dd>
            {person.email ? (
              <a className="link-btn" href={`mailto:${person.email}`}>
                <EnvelopeSimpleIcon size={16} aria-hidden /> {person.email}
              </a>
            ) : (
              <span className="c-secondary">{t('review.noEmail')}</span>
            )}
          </dd>
        </div>
        <div>
          <dt>{t('profile.access')}</dt>
          <dd>{t(`access.${person.access}`)}</dd>
        </div>
        <div>
          <dt>{t('profile.templates')}</dt>
          <dd>{inTemplates.length ? inTemplates.map((tpl) => tpl.name).join(', ') : <span className="c-secondary">{t('profile.noTemplates')}</span>}</dd>
        </div>
        <div>
          <dt>{t('profile.meetings')}</dt>
          <dd>
            {last ? (
              <>
                {t('profile.meetingsCount', { count: attended.length })}
                <span className="note"> · {t('profile.last', { title: last.title, date: formatDayMonth(last.date, lang) })}</span>
              </>
            ) : (
              <span className="c-secondary">{t('profile.noMeetings')}</span>
            )}
          </dd>
        </div>
      </dl>
      <Button icon={<UsersThreeIcon size={20} aria-hidden />} onClick={() => navigate('/participants')}>
        {t('profile.manage')}
      </Button>
    </Dialog>
  );
}
