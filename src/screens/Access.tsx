import { ShieldCheckIcon } from '@phosphor-icons/react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { demoAccounts, demoYou, YOU_ID } from '../mocks';
import { useStore } from '../store/AppStore';

/** L00 — first user becomes Admin, then onboarding. */
export function SignUp() {
  const { t } = useI18n();
  const { account, signUp } = useStore();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [errors, setErrors] = useState<Partial<Record<keyof typeof form, string>>>({});

  // Only the very first user signs up here; after that it's log in.
  // (Checked on arrival only — right after signUp() the account exists and we're navigating on.)
  const [hadAccount] = useState(() => !!account);
  if (hadAccount) return <Navigate to="/login" replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next: typeof errors = {};
    if (!form.name.trim()) next.name = t('common.required');
    if (!isEmail(form.email)) next.email = t('common.emailInvalid');
    if (form.password.length < 8) next.password = t('signup.passwordShort');
    setErrors(next);
    if (Object.keys(next).length) return;
    signUp(form.name.trim(), form.email.trim());
    navigate('/onboarding/1');
  };

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <form className="card access-card" onSubmit={submit} noValidate>
      <div className="page__head">
        <h1 className="t-h1">{t('signup.title')}</h1>
        <p className="lead">{t('signup.lead')}</p>
      </div>
      <TextField label={t('signup.fullName')} placeholder={t('signup.fullNamePh')} autoComplete="name" value={form.name} onChange={set('name')} error={errors.name} />
      <TextField label={t('signup.email')} placeholder={t('signup.emailPh')} type="email" autoComplete="email" value={form.email} onChange={set('email')} error={errors.email} />
      <TextField label={t('signup.password')} placeholder={t('signup.passwordPh')} type="password" autoComplete="new-password" value={form.password} onChange={set('password')} error={errors.password} />
      <Button type="submit" variant="primary" block>
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

/** L01 — mocked auth (any password). Demo accounts are offered in a fresh browser. */
export function LogIn() {
  const { t } = useI18n();
  const { account, demo, logIn, resolvePerson } = useStore();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string>();
  const showDemo = !account || demo;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!isEmail(email)) return setError(t('common.emailInvalid'));
    const result = logIn(email);
    if (result === 'receives-only') return setError(t('login.receivesOnly'));
    if (result === 'no-account') return setError(t('login.noAccount'));
    navigate('/new');
  };

  return (
    <div className="stack access-stack">
      <form className="card access-card" onSubmit={submit} noValidate>
        <h1 className="t-h1">{t('login.title')}</h1>
        <TextField label={t('signup.email')} placeholder={t('signup.emailPh')} type="email" autoComplete="email" value={email} onChange={(e) => (setEmail(e.target.value), setError(undefined))} error={error} />
        <TextField label={t('signup.password')} placeholder={t('login.passwordPh')} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" variant="primary" block>
          {t('login.submit')}
        </Button>
        <p className="access-alt">
          <ShieldCheckIcon size={16} aria-hidden />
          <span className="note">{t('login.network')}</span>
        </p>
        {!account && (
          <p className="access-alt">
            <span className="note">{t('login.newHere')}</span>
            <Link to="/signup" className="link-btn">
              {t('signup.title')}
            </Link>
          </p>
        )}
      </form>

      {showDemo && (
        <section className="tile demo-accounts" aria-labelledby="demo-h">
          <div className="stack" style={{ gap: 2 }}>
            <h2 id="demo-h" className="t-plate c-secondary">
              {t('login.demoTitle')}
            </h2>
            <p className="note">{t('login.demoHint')}</p>
          </div>
          {demoAccounts.map((a) => {
            const p = a.personId === YOU_ID ? { name: demoYou.name, access: 'admin' as const } : resolvePerson(a.personId);
            if (!p) return null;
            return (
              <button
                key={a.email}
                type="button"
                className="demo-accounts__item"
                onClick={() => {
                  setEmail(a.email);
                  setError(undefined);
                  document.querySelector<HTMLButtonElement>('.access-card button[type=submit]')?.focus();
                }}
              >
                <Avatar name={p.name} />
                <span className="who__text" style={{ flex: 1 }}>
                  <span className="who__name">{p.name}</span>
                  <span className="who__sub">
                    {t(`access.${p.access}`)} · {a.email}
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
