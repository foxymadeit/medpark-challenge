import { CheckIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { Segmented } from '../components/Segmented';
import { TextField } from '../components/TextField';
import { LANGS, useI18n, type Lang } from '../i18n/I18nProvider';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES, type MeetingType, type Preferences } from '../types';

// Language names are shown in their own language so everyone can find theirs.
const NATIVE: Record<Lang, string> = { en: 'English', ro: 'Română', ru: 'Русский' };

/** Account settings — opened from the avatar menu in the top bar. */
export function Settings() {
  const { t, lang, setLang } = useI18n();
  const navigate = useNavigate();
  const { account, draft, preferences, updateAccount, updatePreferences, resetDemo } = useStore();
  const [name, setName] = useState(account?.name ?? '');
  const [role, setRole] = useState(account?.role ?? '');
  const [department, setDepartment] = useState(account?.department ?? '');
  const [uiLang, setUiLang] = useState<Lang>(lang);
  const [type, setType] = useState<MeetingType>(account?.meetingTypes[0] ?? draft.type);
  const [prefs, setPrefs] = useState<Preferences>(preferences);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  if (!account) return null;
  const touch = () => setSaved(false);

  const save = () => {
    if (!name.trim()) return setError(t('common.required'));
    setError(undefined);
    updateAccount({
      name: name.trim(),
      role: role.trim(),
      department: department.trim(),
      meetingTypes: [type, ...account.meetingTypes.filter((m) => m !== type)],
    });
    updatePreferences(prefs);
    setLang(uiLang);
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
          <h2 id="set-profile" className="t-h3">
            {t('settings.profile')}
          </h2>
          <TextField label={t('signup.fullName')} value={name} onChange={(e) => (setName(e.target.value), touch())} error={error} autoComplete="name" />
          <TextField label={t('onboarding.about.role')} placeholder={t('onboarding.about.rolePh')} value={role} onChange={(e) => (setRole(e.target.value), touch())} />
          <TextField label={t('onboarding.about.department')} placeholder={t('onboarding.about.departmentPh')} value={department} onChange={(e) => (setDepartment(e.target.value), touch())} />
          <div className="stack" style={{ gap: 8 }}>
            <TextField label={t('signup.email')} value={account.email} readOnly aria-describedby="set-email-note" className="settings__readonly" />
            <p id="set-email-note" className="note">
              {t('settings.emailNote')}
            </p>
          </div>
        </section>

        <div className="stack" style={{ gap: 16 }}>
          <section className="card card--pad settings__section" aria-labelledby="set-prefs">
            <h2 id="set-prefs" className="t-h3">
              {t('settings.preferences')}
            </h2>
            <div className="field">
              <span className="field__label">{t('common.language')}</span>
              <Segmented<Lang> label={t('common.language')} variant="fill" value={uiLang} onChange={(v) => (setUiLang(v), touch())} options={LANGS.map((l) => ({ value: l, label: NATIVE[l] }))} />
            </div>
            <div className="field">
              <span className="field__label" id="set-type">
                {t('settings.defaultType')}
              </span>
              <div className="chips" role="radiogroup" aria-labelledby="set-type">
                {MEETING_TYPES.map((m) => (
                  <button key={m} type="button" role="radio" aria-checked={type === m} className="chip" onClick={() => (setType(m), touch())}>
                    {type === m && <CheckIcon size={16} aria-hidden />}
                    {t(`types.${m}`)}
                  </button>
                ))}
              </div>
              <p className="note">{t('settings.defaultTypeHint')}</p>
            </div>
            <div className="field">
              <span className="field__label">{t('settings.reviewMode')}</span>
              <Segmented<Preferences['reviewMode']>
                label={t('settings.reviewMode')}
                variant="fill"
                value={prefs.reviewMode}
                onChange={(v) => (setPrefs((p) => ({ ...p, reviewMode: v })), touch())}
                options={[
                  { value: 'manual', label: t('review.manual') },
                  { value: 'auto', label: t('review.auto') },
                ]}
              />
              <p className="note">{t('settings.reviewModeHint')}</p>
            </div>
            <div className="field">
              <span className="field__label">{t('settings.countdown')}</span>
              <Segmented<string>
                label={t('settings.countdown')}
                variant="fill"
                value={String(prefs.autoSendSeconds)}
                onChange={(v) => (setPrefs((p) => ({ ...p, autoSendSeconds: Number(v) })), touch())}
                options={['15', '30', '60'].map((n) => ({ value: n, label: t('settings.seconds', { n }) }))}
              />
            </div>
          </section>

          <section className="card card--pad settings__section" aria-labelledby="set-notif">
            <h2 id="set-notif" className="t-h3">
              {t('settings.notifications')}
            </h2>
            <label className="settings__check">
              <input type="checkbox" className="checkbox" checked={prefs.notifyReady} onChange={(e) => (setPrefs((p) => ({ ...p, notifyReady: e.target.checked })), touch())} />
              <span className="who__text">
                <span className="who__name">{t('settings.notifyReady')}</span>
                <span className="who__sub">{t('settings.notifyReadyDesc')}</span>
              </span>
            </label>
          </section>

          <section className="tile settings__section settings__demo" aria-labelledby="set-demo">
            <div className="stack" style={{ gap: 4, flex: 1 }}>
              <h2 id="set-demo" className="t-h3">
                {t('settings.demo')}
              </h2>
              <p className="note">{t('settings.demoLead')}</p>
            </div>
            <Button onClick={() => setConfirmReset(true)}>{t('settings.reset')}</Button>
          </section>
        </div>
      </div>

      <div className="page__actions">
        {saved && (
          <p className="row note" role="status">
            <CheckIcon size={16} aria-hidden />
            {t('settings.saved')}
          </p>
        )}
        <Button variant="primary" onClick={save}>
          {t('settings.save')}
        </Button>
      </div>

      {confirmReset && (
        <Dialog title={t('settings.resetTitle')} onClose={() => setConfirmReset(false)}>
          <p className="lead">{t('settings.demoLead')}</p>
          <div className="row" style={{ justifyContent: 'flex-end', gap: 16 }}>
            <Button variant="ghost" onClick={() => setConfirmReset(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                resetDemo();
                navigate('/signup');
              }}
            >
              {t('settings.resetConfirm')}
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
