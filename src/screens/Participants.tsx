import { UserPlusIcon, UsersThreeIcon, XIcon } from '@phosphor-icons/react';
import { useState, type FormEvent } from 'react';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { Dropdown } from '../components/Dropdown';
import { TextField } from '../components/TextField';
import { Avatar } from '../components/Avatar';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { roleSuggestions } from '../mocks';
import { useStore } from '../store/AppStore';
import { ACCESS_LEVELS, type Access, type Person } from '../types';

function AddParticipantModal({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const { addPerson } = useStore();
  const [name, setName] = useState('');
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
    addPerson({ name: name.trim(), role: role.trim(), email: email.trim() || undefined, access });
    onClose();
  };

  const accessLabel: Record<Access, [string, string]> = {
    receives: ['access.receivesOnly', 'access.receivesDesc'],
    organizer: ['access.organizer', 'access.organizerDesc'],
    admin: ['access.admin', 'access.adminDesc'],
  };

  return (
    <Dialog title={t('addParticipant.title')} onClose={onClose}>
      <form className="stack" style={{ gap: 16 }} onSubmit={submit} noValidate>
        <TextField label={t('addParticipant.name')} placeholder={t('addParticipant.namePh')} value={name} onChange={(e) => setName(e.target.value)} error={errors.name} />
        <div className="row" style={{ gap: 16, alignItems: 'flex-start' }}>
          <TextField label={t('addParticipant.role')} placeholder={t('addParticipant.rolePh')} value={role} onChange={(e) => setRole(e.target.value)} />
          <TextField label={t('addParticipant.email')} placeholder={t('addParticipant.emailPh')} type="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email} />
        </div>
        <fieldset className="stack access-options">
          <legend className="field__label">{t('addParticipant.access')}</legend>
          {ACCESS_LEVELS.map((a) => (
            <label key={a} className="radio-card">
              <input type="radio" className="radio" name="access" value={a} checked={access === a} onChange={() => setAccess(a)} />
              <span className="who__text">
                <span className="who__name">{t(accessLabel[a][0])}</span>
                <span className="who__sub">{t(accessLabel[a][1])}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <Button type="submit" variant="primary" block>
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
  const displayName = isYou ? t('participants.you', { name: person.name }) : person.name;

  const roles = [person.role, ...roleSuggestions].filter((r, i, a) => r && a.indexOf(r) === i);

  const setRole = (role: string) => {
    updatePerson(person.id, { role });
    if (isYou) updateAccount({ role });
  };

  return (
    <tr>
      <td>
        <div className="who">
          <Avatar name={person.name} />
          <div className="who__text">
            <span className="who__name truncate">{displayName}</span>
            {person.email && <span className="who__sub truncate">{person.email}</span>}
          </div>
        </div>
      </td>
      <td>
        {editable ? (
          <Dropdown label={t('participants.roleFor', { name: person.name })} value={person.role} options={roles.map((r) => ({ value: r, label: r }))} onChange={setRole} customLabel={t('participants.customRole')} customPlaceholder={t('participants.customRolePh')} width={240} />
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
            onChange={(v) => updatePerson(person.id, { access: v as Access })}
            width={200}
            disabled={isYou && soleAdmin} // the only Admin cannot demote themselves
            disabledReason={t('participants.soleAdmin')}
          />
        ) : (
          <span className="t-strong">{t(`access.${person.access}`)}</span>
        )}
      </td>
      <td>
        {!isYou && (
          <button type="button" className="icon-btn icon-btn--lg" aria-label={t('participants.remove', { name: person.name })} onClick={() => removePerson(person.id)}>
            <XIcon size={16} aria-hidden />
          </button>
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
  const onlyYou = people.length <= 1;
  const soleAdmin = people.filter((p) => p.access === 'admin').length <= 1;

  return (
    <div className="page">
      <div className={`page__head ${onlyYou ? 'participants__head--bare' : 'participants__head'}`}>
        <h1 className="t-h1">{t('participants.title')}</h1>
        {!onlyYou && <p className="lead">{t('participants.lead')}</p>}
      </div>

      <div className="table-card">
        <table className="table">
          <colgroup>
            <col />
            <col style={{ width: 256 }} />
            <col style={{ width: 216 }} />
            <col style={{ width: 64 }} />
          </colgroup>
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
            {people.map((p) => (
              <ParticipantRow key={p.id} person={p} editable={!onlyYou} soleAdmin={soleAdmin} />
            ))}
          </tbody>
        </table>
      </div>

      {onlyYou ? (
        <div className="empty-state">
          <UsersThreeIcon size={32} aria-hidden />
          <h2 className="t-h2">{t('participants.emptyTitle')}</h2>
          <p className="lead">{t('participants.emptyLead')}</p>
          <Button variant="primary" icon={<UserPlusIcon size={20} aria-hidden />} onClick={() => setAdding(true)} className="empty-state__cta">
            {t('participants.add')}
          </Button>
        </div>
      ) : (
        <div className="page__actions">
          <Button variant="primary" icon={<UserPlusIcon size={20} aria-hidden />} onClick={() => setAdding(true)}>
            {t('participants.add')}
          </Button>
        </div>
      )}

      {adding && <AddParticipantModal onClose={() => setAdding(false)} />}
    </div>
  );
}
