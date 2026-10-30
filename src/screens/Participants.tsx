import { PlusIcon, UsersThreeIcon, XIcon } from '@phosphor-icons/react';
import { useState, type FormEvent } from 'react';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { Dropdown } from '../components/Dropdown';
import { TextField } from '../components/TextField';
import { Avatar } from '../components/Avatar';
import { PageHeader } from '../components/PageHeader';
import { SearchBar } from '../components/SearchBar';
import { PersonProfileDialog } from '../components/PersonProfile';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { suggestByName } from '../lib/participants';
import { roleSuggestions } from '../mocks';
import { useStore } from '../store/AppStore';
import { ACCESS_LEVELS, type Access, type Person } from '../types';

/** Also used by the template editor, which passes onAdded to select the new person. */
export function AddParticipantModal({ onClose, onAdded, title, initialName = '' }: { onClose: () => void; onAdded?: (id: string, person: Omit<Person, 'id'>) => void; title?: string; initialName?: string }) {
  const { t } = useI18n();
  const { addPerson } = useStore();
  const [name, setName] = useState(initialName);
  const [role, setRole] = useState('');
  const [email, setEmail] = useState('');
  const [access, setAccess] = useState<Access>('receives');
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({});

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: typeof errors = {};
    if (!name.trim()) next.name = t('common.required');
    if (email.trim() && !isEmail(email)) next.email = t('common.emailInvalid');
    setErrors(next);
    if (Object.keys(next).length) return;
    const person = { name: name.trim(), role: role.trim(), email: email.trim() || undefined, access };
    const id = addPerson(person);
    onAdded?.(id, person);
    onClose();
  };


  return (
    <Dialog title={title ?? t('addParticipant.title')} onClose={onClose}>
      <form className="stack" style={{ gap: 'var(--sm-space-4)' }} onSubmit={submit} noValidate>
        <TextField label={t('addParticipant.name')} placeholder={t('addParticipant.namePh')} value={name} onChange={(e) => setName(e.target.value)} error={errors.name} />
        <div className="row" style={{ gap: 'var(--sm-space-4)', alignItems: 'flex-start' }}>
          <TextField label={t('addParticipant.role')} placeholder={t('addParticipant.rolePh')} value={role} onChange={(e) => setRole(e.target.value)} />
          <TextField label={t('addParticipant.email')} placeholder={t('addParticipant.emailPh')} type="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email} />
        </div>
        <fieldset className="stack access-options">
          <legend className="form-label">{t('addParticipant.access')}</legend>
          {/* Everyone gets the minutes; Organizer and Admin add rights on top. Admin includes Organizer. */}
          <label className="access-check is-fixed">
            <input type="checkbox" className="checkbox" checked disabled />
            <span className="who__text">
              <span className="who__name">{t('accessTitle.receives')}</span>
              <span className="who__sub">{t('access.receivesDesc')}</span>
            </span>
          </label>
          <label className="access-check">
            <input type="checkbox" className="checkbox" checked={access !== 'receives'} disabled={access === 'admin'} onChange={(e) => setAccess(e.target.checked ? 'organizer' : 'receives')} />
            <span className="who__text">
              <span className="who__name">{t('accessTitle.organizer')}</span>
              <span className="who__sub">{t('access.organizerDesc')}</span>
            </span>
          </label>
          <label className="access-check">
            <input type="checkbox" className="checkbox" checked={access === 'admin'} onChange={(e) => setAccess(e.target.checked ? 'admin' : 'organizer')} />
            <span className="who__text">
              <span className="who__name">{t('accessTitle.admin')}</span>
              <span className="who__sub">{t('access.adminDesc')}</span>
            </span>
          </label>
        </fieldset>
        <Button type="submit" variant="primary" block disabled={!name.trim()}>
          {t('addParticipant.submit')}
        </Button>
      </form>
    </Dialog>
  );
}

function ParticipantRow({ person, editable, soleAdmin }: { person: Person; editable: boolean; soleAdmin: boolean }) {
  const { t } = useI18n();
  const { updatePerson, removePerson, updateAccount, account } = useStore();
  const isYou = person.id === account?.personId;
  const [confirming, setConfirming] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [pendingAccess, setPendingAccess] = useState<Access | null>(null);
  const displayName = isYou ? t('common.meName', { name: person.name }) : person.name;

  const roles = [person.role, ...roleSuggestions].filter((r, i, a) => r && a.indexOf(r) === i);

  const setRole = (role: string) => {
    updatePerson(person.id, { role });
    if (isYou) updateAccount({ role });
  };

  return (
    <tr className="row-hover">
      <td>
        {/* Avatar + name open the profile, where email and role can be edited. */}
        <button type="button" className="who who--button" aria-label={t('profile.open', { name: displayName })} onClick={() => setProfileOpen(true)}>
          <Avatar name={person.name} />
          <span className="who__text">
            <span className="who__name truncate">{displayName}</span>
            <span className="who__sub truncate">{person.email ?? t('review.noEmail')}</span>
          </span>
        </button>
        {profileOpen && <PersonProfileDialog personId={person.id} onClose={() => setProfileOpen(false)} showManage={false} />}
      </td>
      <td>
        {editable ? (
          <Dropdown label={t('participants.roleFor', { name: person.name })} value={person.role} options={roles.map((r) => ({ value: r, label: r }))} onChange={setRole} customLabel={t('participants.customRole')} customPlaceholder={t('participants.customRolePh')} width="100%" />
        ) : (
          <span className="t-body-md c-secondary">{person.role}</span>
        )}
      </td>
      <td>
        {editable ? (
          <Dropdown
            label={t('participants.accessFor', { name: person.name })}
            value={person.access}
            options={ACCESS_LEVELS.map((a) => ({ value: a, label: t(`access.${a}`) }))}
            // Giving Organizer or Admin rights asks first; lowering to Participant applies at once.
            onChange={(v) => (v === 'receives' ? updatePerson(person.id, { access: 'receives' }) : setPendingAccess(v as Access))}
            width="100%"
            disabled={isYou && soleAdmin} // the only Admin cannot demote themselves
            disabledReason={t('participants.soleAdmin')}
          />
        ) : (
          <span className="t-strong">{t(`access.${person.access}`)}</span>
        )}
      </td>
      <td>
        {!isYou && (
          <button type="button" className="icon-btn" aria-label={t('participants.remove', { name: person.name })} onClick={() => setConfirming(true)}>
            <XIcon size={16} aria-hidden />
          </button>
        )}
        {pendingAccess && (
          <Dialog title={t('participants.accessTitle', { access: t(`accessTitle.${pendingAccess}`) })} onClose={() => setPendingAccess(null)}>
            <p className="lead">{t('participants.accessLead', { name: person.name, access: t(`accessTitle.${pendingAccess}`) })}</p>
            <p className="note">{t(`access.${pendingAccess}Desc`)}</p>
            <div className="row" style={{ justifyContent: 'flex-end', gap: 'var(--sm-space-3)' }}>
              <Button variant="ghost" onClick={() => setPendingAccess(null)}>
                {t('common.cancel')}
              </Button>
              <Button variant="primary" onClick={() => (updatePerson(person.id, { access: pendingAccess }), setPendingAccess(null))}>
                {t('participants.accessConfirm')}
              </Button>
            </div>
          </Dialog>
        )}
        {confirming && (
          <Dialog title={t('participants.removeTitle')} onClose={() => setConfirming(false)}>
            <p className="lead">{t('participants.removeLead', { name: person.name })}</p>
            <div className="row" style={{ justifyContent: 'flex-end', gap: 'var(--sm-space-3)' }}>
              <Button variant="ghost" onClick={() => setConfirming(false)}>
                {t('common.cancel')}
              </Button>
              <Button variant="danger" onClick={() => (removePerson(person.id), setConfirming(false))}>
                {t('participants.removeConfirm')}
              </Button>
            </div>
          </Dialog>
        )}
      </td>
    </tr>
  );
}

/** P01 (only Admin) / P03 (inline role & access) + P02 modal. */
export function Participants() {
  const { t } = useI18n();
  const { people } = useStore();
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState('');
  const [pickedId, setPickedId] = useState<string>(); // a suggestion picked: just that person
  const onlyYou = people.length <= 1;
  // Search: first name or surname starting with what's typed (the same rule as every name suggestion), or the start
  // of the email once there's an @. The suggestions under the field and the table follow the same rule.
  const q = query.trim().toLowerCase();
  const matches = q.includes('@') ? people.filter((p) => p.email?.toLowerCase().startsWith(q)) : suggestByName(people, q, () => false, people.length);
  const shown = pickedId ? people.filter((p) => p.id === pickedId) : q ? people.filter((p) => matches.includes(p)) : people;
  const soleAdmin = people.filter((p) => p.access === 'admin').length <= 1;

  return (
    <div className="page page--fit">
      <PageHeader
        title={t('participants.title')}
        aside={
          !onlyYou && (
            <Button variant="primary" icon={<PlusIcon size={20} aria-hidden />} onClick={() => setAdding(true)}>
              {t('participants.add')}
            </Button>
          )
        }
      />
      {!onlyYou && (
        <SearchBar
          value={query}
          onChange={(v) => (setQuery(v), setPickedId(undefined))}
          placeholder={t('participants.search')}
          options={pickedId ? [] : matches.slice(0, 5).map((p) => ({ id: p.id, name: p.name, sub: p.email }))}
          onPick={(o) => (setQuery(o.name), setPickedId(o.id))}
        />
      )}

      <div className="table-card">
        <table className="table table--people">
          <thead>
            <tr>
              <th scope="col">{t('participants.colWho')}</th>
              <th scope="col">{t('participants.colRole')}</th>
              <th scope="col">{t('participants.colAccess')}</th>
              <th scope="col">
                <span className="sr-only">{t('participants.remove', { name: '' })}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((p) => (
              <ParticipantRow key={p.id} person={p} editable={!onlyYou} soleAdmin={soleAdmin} />
            ))}
            {!shown.length && (
              <tr>
                <td colSpan={4} className="note">
                  {t('participants.noMatch', { query: query.trim() })}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {onlyYou ? (
        <div className="vp-center">
          {/* Centred on the window (vp-center), not on the content area. */}
          <div className="empty-state">
            <UsersThreeIcon size={32} aria-hidden />
            <h2 className="t-h2">{t('participants.emptyTitle')}</h2>
            <p className="lead">{t('participants.emptyLead')}</p>
            <Button variant="primary" icon={<PlusIcon size={20} aria-hidden />} onClick={() => setAdding(true)} className="empty-state__cta">
              {t('participants.add')}
            </Button>
          </div>
        </div>
      ) : null}

      {adding && <AddParticipantModal onClose={() => setAdding(false)} />}
    </div>
  );
}
