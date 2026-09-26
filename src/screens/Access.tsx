import { EyeIcon, EyeSlashIcon, WarningIcon } from '@phosphor-icons/react';
import { useId, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { demoAccounts, demoYou, YOU_ID } from '../mocks';
import { useStore } from '../store/AppStore';

/** Password with show/hide and a Caps Lock warning (the two most common login slips). */
function PasswordField({ label, placeholder, value, onChange, error, autoComplete }: { label: string; placeholder: string; value: string; onChange: (v: string) => void; error?: string; autoComplete: string }) {
  const { t } = useI18n();
  const id = useId();
  const [shown, setShown] = useState(false);
  const [caps, setCaps] = useState(false);
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => setCaps(e.getModifierState?.('CapsLock') ?? false);
  const describedBy = [error && `${id}-err`, caps && `${id}-caps`].filter(Boolean).join(' ') || undefined;
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <span className="input-wrap">
        <input
          id={id}
          className="input"
          type={shown ? 'text' : 'password'}
          placeholder={placeholder}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKey}
          onKeyUp={onKey}
          onBlur={() => setCaps(false)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
        <button type="button" className="icon-btn input-wrap__action" aria-label={shown ? t('login.hidePassword') : t('login.showPassword')} aria-pressed={shown} onClick={() => setShown((s) => !s)}>
          {shown ? <EyeSlashIcon size={18} aria-hidden /> : <EyeIcon size={18} aria-hidden />}
        </button>
      </span>
      {caps && (
        <p id={`${id}-caps`} className="note row" style={{ gap: 6 }}>
          <WarningIcon size={14} aria-hidden />
          {t('login.capsLock')}
        </p>
      )}
      {error && (
        <p id={`${id}-err`} className="field__error">
          {error}
        </p>
      )}
    </div>
  );
}

/** L—1 — what the site opens with: Log in or Sign up (and a shortcut back in when already signed in). */
export function Welcome() {
  const { t } = useI18n();
  const { account, signedIn, onboarded } = useStore();
  const navigate = useNavigate();
  return (
    <div className="card access-card welcome">
      {/* The greeting itself sits above the card (AccessLayout). */}
      <h1 className="lead welcome__lead">{t('welcome.lead')}</h1>
      <div className="stack" style={{ gap: 12 }}>
        <Button variant="ink" block onClick={() => navigate('/login')}>
          {t('login.submit')}
        </Button>
        <Button block onClick={() => navigate('/signup')}>
          {t('welcome.signUp')}
        </Button>
      </div>
      {account && signedIn && (
        <p className="access-alt">
          <Link to={onboarded ? '/new' : '/onboarding/1'} className="link-btn">
            {t('welcome.continueAs', { name: account.name })}
          </Link>
        </p>
      )}
    </div>
  );
}

/** L00 — first user becomes Admin, then onboarding. */
export function SignUp() {
  const { t } = useI18n();
  const { signUp } = useStore();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [errors, setErrors] = useState<Partial<Record<keyof typeof form, string>>>({});
  const [taken, setTaken] = useState(false);


  const submit = (e: FormEvent) => {
    e.preventDefault();
    const email = form.email.trim().toLowerCase();
    const next: typeof errors = {};
    if (form.name.trim().length < 2) next.name = t('signup.nameMissing');
    if (!email) next.email = t('login.emailMissing');
    else if (!isEmail(email)) next.email = t('common.emailInvalid');
    if (form.password.length < 8) next.password = form.password ? t('signup.passwordShort') : t('login.passwordMissing');
    // A demo address already has an account: send them to log in instead of creating a duplicate.
    const exists = !next.email && demoAccounts.some((a) => a.email.toLowerCase() === email);
    setTaken(exists);
    setErrors(next);
    if (Object.keys(next).length || exists) {
      const first = (Object.keys(next)[0] ?? (exists ? 'email' : undefined)) as keyof typeof form | undefined;
      if (first) document.querySelector<HTMLInputElement>(`[data-field="${first}"] input`)?.focus();
      return;
    }
    signUp(form.name.trim(), email);
    navigate('/onboarding/1');
  };

  const set = (k: keyof typeof form) => (v: string) => {
    setForm((f) => ({ ...f, [k]: v }));
    setErrors((er) => ({ ...er, [k]: undefined }));
    if (k === 'email') setTaken(false);
  };

  return (
    <form className="card access-card" onSubmit={submit} noValidate>
      <div className="page__head">
        <h1 className="t-h1">{t('signup.title')}</h1>
        <p className="lead">{t('signup.lead')}</p>
      </div>
      <div data-field="name">
        <TextField label={t('signup.fullName')} placeholder={t('signup.fullNamePh')} autoComplete="name" value={form.name} onChange={(e) => set('name')(e.target.value)} error={errors.name} />
      </div>
      <div data-field="email">
        <TextField label={t('signup.email')} placeholder={t('signup.emailPh')} type="email" autoComplete="email" value={form.email} onChange={(e) => set('email')(e.target.value)} error={errors.email} />
        {taken && (
          <p className="field__error" role="alert" style={{ marginTop: 8 }}>
            {t('signup.emailTaken')}{' '}
            <Link to="/login" className="link-btn">
              {t('signup.logIn')}
            </Link>
          </p>
        )}
      </div>
      <div data-field="password">
        <PasswordField label={t('signup.password')} placeholder={t('signup.passwordPh')} autoComplete="new-password" value={form.password} onChange={set('password')} error={errors.password} />
      </div>
      <Button type="submit" variant="ink" block disabled={!form.name.trim() || !form.email.trim() || !form.password}>
        {t('signup.submit')}
      </Button>
      <p className="access-alt">
        <span className="note">{t('signup.haveAccount')}</span>
        <Link to="/login" className="link-btn">
          {t('signup.logIn')}
        </Link>
      </p>
    </form>
  );
}

/** L01 — mocked auth (any password). Demo accounts sign in with one click. */
export function LogIn() {
  const { t } = useI18n();
  const { account, demo, logIn, resolvePerson } = useStore();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: 'no-account' | 'receives-only' }>({});
  const showDemo = !account || demo;

  const finish = (address: string) => {
    const result = logIn(address);
    if (result === 'ok') return navigate('/new');
    setErrors({ form: result });
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const address = email.trim();
    const next: typeof errors = {};
    if (!address) next.email = t('login.emailMissing');
    else if (!isEmail(address)) next.email = t('common.emailInvalid');
    if (!password) next.password = t('login.passwordMissing');
    setErrors(next);
    if (next.email || next.password) return;
    finish(address);
  };

  return (
    <div className="stack access-stack">
      <form className="card access-card" onSubmit={submit} noValidate>
        <h1 className="t-h1">{t('login.title')}</h1>
        {errors.form && (
          <div className="form-alert" role="alert">
            <WarningIcon size={18} aria-hidden />
            <p>
              {errors.form === 'receives-only' ? t('login.receivesOnly') : t('login.noAccount')}
              {errors.form === 'no-account' && !account && (
                <>
                  {' '}
                  <Link to="/signup" className="link-btn">
                    {t('signup.title')}
                  </Link>
                </>
              )}
            </p>
          </div>
        )}
        <TextField
          label={t('signup.email')}
          placeholder={t('signup.emailPh')}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => (setEmail(e.target.value), setErrors((er) => ({ ...er, email: undefined, form: undefined })))}
          error={errors.email}
        />
        <PasswordField label={t('signup.password')} placeholder={t('login.passwordPh')} autoComplete="current-password" value={password} onChange={(v) => (setPassword(v), setErrors((er) => ({ ...er, password: undefined })))} error={errors.password} />
        {/* Inactive until both fields have something; format errors still show on submit. */}
        <Button type="submit" variant="ink" block disabled={!email.trim() || !password}>
          {t('login.submit')}
        </Button>
        {/* Always offered, even when an account already exists on this device. */}
        <p className="access-alt">
          <span className="note">{t('login.newHere')}</span>
          <Link to="/signup" className="link-btn">
            {t('welcome.signUp')}
          </Link>
        </p>
      </form>

      {showDemo && (
        <section className="demo-accounts" aria-labelledby="demo-h">
          <h2 id="demo-h" className="demo-accounts__title">
            {t('login.demoTitle')}
          </h2>
          {demoAccounts.map((a) => {
            const p = a.personId === YOU_ID ? { name: demoYou.name, access: 'admin' as const } : resolvePerson(a.personId);
            if (!p) return null;
            return (
              <button key={a.email} type="button" className="demo-accounts__item" onClick={() => finish(a.email)}>
                <Avatar name={p.name} />
                <span className="who__text" style={{ flex: 1 }}>
                  <span className="who__name">{p.name}</span>
                  <span className="who__sub">
                    {t(`accessTitle.${p.access}`)} · {a.email}
                  </span>
                </span>
              </button>
            );
          })}
        </section>
      )}
    </div>
  );
}
