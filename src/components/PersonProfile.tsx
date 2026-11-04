import { CheckIcon, PencilSimpleIcon, UsersThreeIcon, XIcon } from '@phosphor-icons/react';
import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { formatDayMonth, isEmail } from '../lib/format';
import { useStore } from '../store/AppStore';
import { Avatar } from './Avatar';
import { Button } from './Button';
import { Dialog } from './Dialog';
import { Dropdown } from './Dropdown';
import { ACCESS_LEVELS, type Access } from '../types';

/** One fact row with a pen: view → inline input → ✓ saves (dimmed until changed), Esc / ✕ cancels. */
function EditableFact({ label, value, display, type = 'text', placeholder, validate, onSave }: { label: string; value: string; display: ReactNode; type?: string; placeholder?: string; validate?: (v: string) => string | undefined; onSave: (v: string) => void }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState<string>();
  const cancel = () => (setDraft(value), setError(undefined), setEditing(false));
  const save = () => {
    const v = draft.trim();
    if (v === value) return cancel();
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
          <span className="stack" style={{ gap: 'var(--sm-space-1)' }}>
            <span className="row" style={{ gap: 'var(--sm-space-1)' }}>
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
              {/* ✓ appears only once the value actually changed. */}
              {draft.trim() !== value && (
                <button type="button" className="icon-btn icon-btn--confirm" aria-label={t('common.save')} onClick={save}>
                  <CheckIcon size={16} aria-hidden />
                </button>
              )}
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
  const { account, people, resolvePerson, templates, meetings, updatePerson, updateAccount } = useStore();
  const [pendingAccess, setPendingAccess] = useState<Access | null>(null); // raising access waits for a yes
  const person = resolvePerson(personId);
  if (!person) return null;
  const isMe = person.id === account?.personId;
  // Access can be changed by an Admin, as on the Participants page; the only Admin can't demote themselves.
  const viewerIsAdmin = !!account && resolvePerson(account.personId)?.access === 'admin';
  const soleAdmin = person.access === 'admin' && people.filter((p) => p.access === 'admin').length <= 1;
  const changeAccess = (v: Access) => (v === 'receives' ? updatePerson(person.id, { access: v }) : setPendingAccess(v));

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
                {person.email}
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
          <dd>
            {viewerIsAdmin ? (
              <Dropdown
                label={t('participants.accessFor', { name: person.name })}
                value={person.access}
                options={ACCESS_LEVELS.map((a) => ({ value: a, label: t(`access.${a}`) }))}
                onChange={(v) => changeAccess(v as Access)}
                width={200}
                disabled={soleAdmin}
                disabledReason={t('participants.soleAdmin')}
              />
            ) : (
              t(`access.${person.access}`)
            )}
          </dd>
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
      {/* Giving Organizer or Admin rights asks first (same wording as on the Participants page). */}
      {pendingAccess && (
        <div className="stack" style={{ gap: 'var(--sm-space-3)' }} role="group" aria-label={t('participants.accessTitle', { access: t(`accessTitle.${pendingAccess}`) })}>
          <p className="lead" style={{ margin: 0 }}>
            {t('participants.accessLead', { name: person.name, access: t(`accessTitle.${pendingAccess}`) })}
          </p>
          <p className="note" style={{ margin: 0 }}>
            {t(`access.${pendingAccess}Desc`)}
          </p>
          <div className="row" style={{ justifyContent: 'flex-end', gap: 'var(--sm-space-3)' }}>
            <Button variant="ghost" onClick={() => setPendingAccess(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="primary" onClick={() => (updatePerson(person.id, { access: pendingAccess }), setPendingAccess(null))}>
              {t('participants.accessConfirm')}
            </Button>
          </div>
        </div>
      )}
      {showManage && (
        <Button icon={<UsersThreeIcon size={20} aria-hidden />} onClick={() => navigate('/participants')}>
          {t('profile.manage')}
        </Button>
      )}
    </Dialog>
  );
}

/** Profile preview for someone who isn't in the directory yet (a name typed on New meeting): what we know about them. */
export function GuestProfileDialog({ name, role, email, onClose }: { name: string; role?: string; email?: string; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Dialog title={t('profile.title')} onClose={onClose}>
      <div className="profile__head">
        <Avatar name={name} />
        <span className="who__text">
          <span className="profile__name">
            <span className="t-h2">{name}</span>
          </span>
          {role && <span className="who__sub">{role}</span>}
        </span>
      </div>
      <dl className="profile__facts">
        <div>
          <dt>{t('profile.email')}</dt>
          <dd className={email ? undefined : 'c-secondary'}>{email ?? t('review.noEmail')}</dd>
        </div>
        <div>
          <dt>{t('profile.role')}</dt>
          <dd>{role || <span className="c-secondary">{t('profile.noRole')}</span>}</dd>
        </div>
        <div>
          <dt>{t('profile.access')}</dt>
          <dd>{t('profile.guest')}</dd>
        </div>
      </dl>
      {!email && <p className="note">{t('profile.guestNote')}</p>}
    </Dialog>
  );
}
