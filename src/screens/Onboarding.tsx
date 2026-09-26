import { CheckIcon, UserPlusIcon, XIcon } from '@phosphor-icons/react';
import { useState, type KeyboardEvent } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { ProgressBar } from '../components/ProgressBar';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { demoPeople, onboardingSuggestions } from '../mocks';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES, type MeetingType } from '../types';

function StepHeader({ n, title, lead }: { n: number; title: string; lead: string }) {
  const { t } = useI18n();
  return (
    <>
      <div className="onb__progress">
        <p className="t-plate c-secondary">{t('onboarding.step', { n })}</p>
        <ProgressBar value={n / 3} label={t('onboarding.step', { n })} />
      </div>
      <div className="page__head">
        <h1 className="t-h1">{title}</h1>
        <p className="lead">{lead}</p>
      </div>
    </>
  );
}

/** O01 — About you */
function AboutYou() {
  const { t } = useI18n();
  const { account, updateAccount } = useStore();
  const navigate = useNavigate();
  const [name, setName] = useState(account?.name ?? '');
  const [role, setRole] = useState(account?.role ?? '');
  const [department, setDepartment] = useState(account?.department ?? '');
  const [error, setError] = useState<string>();

  const next = () => {
    if (!name.trim()) return setError(t('common.required'));
    updateAccount({ name: name.trim(), role: role.trim(), department: department.trim() });
    navigate('/onboarding/2');
  };

  return (
    <form className="page onb" onSubmit={(e) => (e.preventDefault(), next())}>
      <div className="onb__column">
        <StepHeader n={1} title={t('onboarding.about.title')} lead={t('onboarding.about.lead')} />
        <div className="onb__body">
          <TextField label={t('onboarding.about.fullName')} value={name} onChange={(e) => setName(e.target.value)} error={error} autoComplete="name" />
          <TextField label={t('onboarding.about.role')} placeholder={t('onboarding.about.rolePh')} value={role} onChange={(e) => setRole(e.target.value)} autoComplete="organization-title" />
          <TextField label={t('onboarding.about.department')} placeholder={t('onboarding.about.departmentPh')} value={department} onChange={(e) => setDepartment(e.target.value)} />
        </div>
      </div>
      <div className="page__actions onb__actions">
        <Button type="submit" variant="primary">
          {t('common.continue')}
        </Button>
      </div>
    </form>
  );
}

/** O02 — Your meetings (multi-select; first picked = default type) */
function YourMeetings() {
  const { t } = useI18n();
  const { account, updateAccount } = useStore();
  const navigate = useNavigate();
  const [picked, setPicked] = useState<MeetingType[]>(account?.meetingTypes.length ? account.meetingTypes : ['medical', 'executive']);

  const toggle = (type: MeetingType) => setPicked((p) => (p.includes(type) ? p.filter((x) => x !== type) : [...p, type]));

  return (
    <div className="page onb">
      <div className="onb__column">
        <StepHeader n={2} title={t('onboarding.meetings.title')} lead={t('onboarding.meetings.lead')} />
        <div className="onb__body">
          <p className="t-strong" id="meet-q">
            {t('onboarding.meetings.question')}
          </p>
          <div className="chips" role="group" aria-labelledby="meet-q">
            {MEETING_TYPES.map((type) => (
              <button key={type} type="button" className="chip" aria-pressed={picked.includes(type)} onClick={() => toggle(type)}>
                {picked.includes(type) && <CheckIcon size={16} aria-hidden />}
                {t(`types.${type}`)}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="page__actions onb__actions">
        <Button onClick={() => navigate('/onboarding/1')}>{t('common.back')}</Button>
        <Button
          variant="primary"
          disabled={!picked.length}
          onClick={() => {
            updateAccount({ meetingTypes: picked });
            navigate('/onboarding/3');
          }}
        >
          {t('common.continue')}
        </Button>
      </div>
    </div>
  );
}

interface Row {
  id: string;
  name: string;
  role: string;
  email: string;
}

/** O03 — Who gets the minutes? (inline table) */
function WhoGetsMinutes() {
  const { t } = useI18n();
  const { addPerson, finishOnboarding } = useStore();
  const navigate = useNavigate();
  const [rows, setRows] = useState<Row[]>(() =>
    onboardingSuggestions
      .map((id) => demoPeople.find((p) => p.id === id)!)
      .map((p) => ({ id: p.id, name: p.name, role: p.role, email: p.email ?? '' })),
  );
  const [draft, setDraft] = useState({ name: '', role: '', email: '' });
  const [error, setError] = useState<string>();

  const add = () => {
    if (!draft.name.trim()) return setError(t('common.required'));
    if (draft.email && !isEmail(draft.email)) return setError(t('common.emailInvalid'));
    setRows((r) => [...r, { id: `new-${Date.now()}`, name: draft.name.trim(), role: draft.role.trim(), email: draft.email.trim() }]);
    setDraft({ name: '', role: '', email: '' });
    setError(undefined);
    document.getElementById('onb-new-name')?.focus();
  };

  const onEnter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      add();
    }
  };

  const done = (save: boolean) => {
    if (save)
      for (const r of rows)
        addPerson({ id: r.id.startsWith('new-') ? undefined : r.id, name: r.name, role: r.role, email: r.email || undefined, access: 'receives' });
    finishOnboarding();
    navigate('/participants');
  };

  return (
    <div className="page onb">
      <div className="onb__column onb__column--wide">
        <StepHeader n={3} title={t('onboarding.people.title')} lead={t('onboarding.people.lead')} />
        <div className="onb__body onb__body--tight">
          <div className="table-card">
            <table className="table table--compact">
              <colgroup>
                <col />
                <col style={{ width: 216 }} />
                <col style={{ width: 256 }} />
                <col style={{ width: 48 }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">{t('onboarding.people.colName')}</th>
                  <th scope="col">{t('onboarding.people.colRole')}</th>
                  <th scope="col">{t('onboarding.people.colEmail')}</th>
                  <th scope="col">
                    <span className="sr-only">{t('onboarding.people.add')}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="who__name truncate">{r.name}</td>
                    <td className="t-body-md c-secondary truncate">{r.role}</td>
                    <td className="t-data-sm c-secondary truncate">{r.email}</td>
                    <td>
                      <button type="button" className="icon-btn" aria-label={t('onboarding.people.remove', { name: r.name })} onClick={() => setRows((x) => x.filter((y) => y.id !== r.id))}>
                        <XIcon size={16} aria-hidden />
                      </button>
                    </td>
                  </tr>
                ))}
                <tr className="add-row">
                  <td>
                    <input id="onb-new-name" className="input input--inline" aria-label={t('onboarding.people.colName')} placeholder={t('onboarding.people.namePh')} value={draft.name} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} onKeyDown={onEnter} aria-invalid={error ? true : undefined} aria-describedby="onb-hint" />
                  </td>
                  <td>
                    <input className="input input--inline" aria-label={t('onboarding.people.colRole')} placeholder={t('onboarding.people.rolePh')} value={draft.role} onChange={(e) => setDraft((d) => ({ ...d, role: e.target.value }))} onKeyDown={onEnter} />
                  </td>
                  <td>
                    <input className="input input--inline" type="email" aria-label={t('onboarding.people.colEmail')} placeholder={t('onboarding.people.emailPh')} value={draft.email} onChange={(e) => setDraft((d) => ({ ...d, email: e.target.value }))} onKeyDown={onEnter} />
                  </td>
                  <td>
                    <button type="button" className="icon-btn icon-btn--solid" aria-label={t('onboarding.people.add')} onClick={add}>
                      <UserPlusIcon size={16} aria-hidden />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          {error && <p className="field__error">{error}</p>}
          <p id="onb-hint" className="note">
            {t('onboarding.people.hint')}
          </p>
        </div>
      </div>
      <div className="page__actions onb__actions">
        <Button onClick={() => done(false)}>{t('onboarding.people.skip')}</Button>
        <Button variant="primary" onClick={() => done(true)}>
          {t('common.continue')}
        </Button>
      </div>
    </div>
  );
}

export function Onboarding() {
  const { step } = useParams();
  if (step === '1') return <AboutYou />;
  if (step === '2') return <YourMeetings />;
  if (step === '3') return <WhoGetsMinutes />;
  return <Navigate to="/onboarding/1" replace />;
}
