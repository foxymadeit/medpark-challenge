import { CheckIcon, EnvelopeSimpleIcon, PencilSimpleIcon, UsersThreeIcon, XIcon } from '@phosphor-icons/react';
import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { formatDayMonth, isEmail } from '../lib/format';
import { useStore } from '../store/AppStore';
import { Avatar } from './Avatar';
import { Button } from './Button';
import { Dialog } from './Dialog';

/** One fact row with a pen: view → inline input → ✓ saves (dimmed until changed), Esc / ✕ cancels. */
function EditableFact({ label, value, display, type = 'text', placeholder, validate, onSave }: { label: string; value: string; display: ReactNode; type?: string; placeholder?: string; validate?: (v: string) => string | undefined; onSave: (v: string) => void }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState<string>();
  const cancel = () => (setDraft(value), setError(undefined), setEditing(false));
  const save = () => {
    const v = draft.trim();
    const err = validate?.(v);
    if (err) return setError(err);
    onSave(v);
    setEditing(false);
  };
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {editing ? (
          <span className="stack" style={{ gap: 4 }}>
            <span className="row" style={{ gap: 4 }}>
              <input
                autoFocus
                type={type}
                className="input input--inline"
                aria-label={label}
                placeholder={placeholder}
                aria-invalid={error ? true : undefined}
                value={draft}
                onChange={(e) => (setDraft(e.target.value), setError(undefined))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') save();
                  if (e.key === 'Escape') (e.stopPropagation(), cancel());
                }}
              />
              <button type="button" className="icon-btn icon-btn--confirm" aria-label={t('common.save')} disabled={draft.trim() === value} onClick={save}>
                <CheckIcon size={16} aria-hidden />
              </button>
              <button type="button" className="icon-btn" aria-label={t('common.cancel')} onClick={cancel}>
                <XIcon size={16} aria-hidden />
              </button>
            </span>
            {error && <span className="field__error">{error}</span>}
          </span>
        ) : (
          <span className="profile__value">
            <span style={{ minWidth: 0 }}>{display}</span>
            <button type="button" className="icon-btn edit-btn" aria-label={t('profile.editField', { field: label })} title={t('profile.editField', { field: label })} onClick={() => (setDraft(value), setEditing(true))}>
              <PencilSimpleIcon size={16} aria-hidden />
            </button>
          </span>
        )}
      </dd>
    </div>
  );
}

/** Profile card: contact, access, the templates they're in and their meetings. */
export function PersonProfileDialog({ personId, onClose, showManage = true }: { personId: string; onClose: () => void; showManage?: boolean }) {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const { account, resolvePerson, templates, meetings, updatePerson, updateAccount } = useStore();
  const person = resolvePerson(personId);
  if (!person) return null;
  const isMe = person.id === account?.personId;

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
            {isMe && <span className="tag tag--me">{t('common.me')}</span>}
          </span>
          {person.role && <span className="who__sub">{person.role}</span>}
        </span>
      </div>
      <dl className="profile__facts">
        <EditableFact
          label={t('profile.email')}
          type="email"
          placeholder={t('addParticipant.emailPh')}
          value={person.email ?? ''}
          validate={(v) => (v && !isEmail(v) ? t('common.emailInvalid') : undefined)}
          onSave={(v) => {
            updatePerson(person.id, { email: v || undefined });
            if (isMe && v) updateAccount({ email: v });
          }}
          display={
            person.email ? (
              <a className="link-btn" href={`mailto:${person.email}`}>
                <EnvelopeSimpleIcon size={16} aria-hidden /> {person.email}
              </a>
            ) : (
              <span className="c-secondary">{t('review.noEmail')}</span>
            )
          }
        />
        <EditableFact
          label={t('profile.role')}
          placeholder={t('addParticipant.rolePh')}
          value={person.role ?? ''}
          onSave={(v) => {
            updatePerson(person.id, { role: v });
            if (isMe) updateAccount({ role: v });
          }}
          display={person.role || <span className="c-secondary">{t('profile.noRole')}</span>}
        />
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
      {showManage && (
        <Button icon={<UsersThreeIcon size={20} aria-hidden />} onClick={() => navigate('/participants')}>
          {t('profile.manage')}
        </Button>
      )}
    </Dialog>
  );
}
