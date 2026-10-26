import { CheckIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { Button } from '../components/Button';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { useStore } from '../store/AppStore';

/** Account settings — opened from the avatar menu in the top bar. */
export function Settings() {
  const { t } = useI18n();
  const { account, updateAccount } = useStore();
  const [email, setEmail] = useState(account?.email ?? '');
  const [name, setName] = useState(account?.name ?? '');
  const [role, setRole] = useState(account?.role ?? '');
  const [department, setDepartment] = useState(account?.department ?? '');
  const [error, setError] = useState<string>();
  const [emailError, setEmailError] = useState<string>();
  const [saved, setSaved] = useState(false);

  if (!account) return null;
  const touch = () => setSaved(false);
  // The Save button only appears once something differs from what is stored.
  const dirty = name !== account.name || role !== (account.role ?? '') || department !== (account.department ?? '') || email !== account.email;

  const save = () => {
    const nameErr = name.trim() ? undefined : t('common.required');
    const mailErr = isEmail(email.trim()) ? undefined : t('common.emailInvalid');
    setError(nameErr);
    setEmailError(mailErr);
    if (nameErr || mailErr) return;
    updateAccount({
      name: name.trim(),
      role: role.trim(),
      department: department.trim(),
      email: email.trim(),
    });
    setSaved(true);
  };

  return (
    <div className="page settings">
      <div className="page__head" style={{ marginBottom: 32 }}>
        <h1 className="t-h1">{t('settings.title')}</h1>
        <p className="lead">{t('settings.lead')}</p>
      </div>

      <div className="settings__cols">
        <section className="card card--pad settings__section" aria-labelledby="set-profile">
          <h2 id="set-profile" className="section-title">
            {t('settings.profile')}
          </h2>
          {/* Fields 2 × 2: name | role, department | work email. */}
          <div className="settings__fields">
            <TextField editable label={t('signup.fullName')} value={name} onChange={(e) => (setName(e.target.value), touch())} error={error} autoComplete="name" />
            <TextField editable label={t('onboarding.about.role')} placeholder={t('onboarding.about.rolePh')} value={role} onChange={(e) => (setRole(e.target.value), touch())} />
            <TextField editable label={t('onboarding.about.department')} placeholder={t('onboarding.about.departmentPh')} value={department} onChange={(e) => (setDepartment(e.target.value), touch())} />
            <div className="stack" style={{ gap: 8 }}>
              <TextField
                editable
                type="email"
                autoComplete="email"
                label={t('settings.workEmail')}
                value={email}
                onChange={(e) => (setEmail(e.target.value), setEmailError(undefined), touch())}
                error={emailError}
                aria-describedby="set-email-note"
              />
              <p id="set-email-note" className="note">
                {t('settings.emailNote')}
              </p>
            </div>
          </div>
        </section>
      </div>

      <div className="page__actions">
        {saved && (
          <p className="row note" role="status">
            <CheckIcon size={16} aria-hidden />
            {t('settings.saved')}
          </p>
        )}
        {/* Appears only once something differs from what is saved. */}
        {dirty && (
          <Button variant="primary" icon={<CheckIcon size={20} aria-hidden />} onClick={save}>
            {t('settings.save')}
          </Button>
        )}
      </div>
    </div>
  );
}
