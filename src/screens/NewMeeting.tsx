import { CheckIcon, EnvelopeSimpleIcon, ListChecksIcon, MicrophoneIcon, PencilSimpleIcon, UploadSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { DatePicker } from '../components/DatePicker';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail, todayISO } from '../lib/format';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES } from '../types';

/** 01 — name, date, type, optional emails, then Record / Upload tiles (templates start from the Templates page). */
export function NewMeeting() {
  const { t } = useI18n();
  const { draft, setDraft, templates } = useStore();
  const navigate = useNavigate();
  const [emailInput, setEmailInput] = useState('');
  const [emailError, setEmailError] = useState<string>();
  const selectedTemplate = templates.find((x) => x.id === draft.templateId);
  // Until the user types a name, the template's name (or "Medical meeting") is used.
  const suggestedName = selectedTemplate?.name ?? t('newMeeting.untitled', { type: t(`types.${draft.type}`) });
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const startName = () => (setNameDraft(draft.title?.trim() || suggestedName), setEditingName(true));
  const commitName = () => {
    const v = nameDraft.trim();
    // Keeping the suggestion as-is stays "unnamed", so switching template still renames it.
    setDraft({ title: v && v !== suggestedName ? v : undefined });
    setEditingName(false);
  };

  const commitEmail = () => {
    const values = emailInput.split(/[\s,;]+/).filter(Boolean);
    if (!values.length) return;
    const bad = values.find((v) => !isEmail(v));
    if (bad) return setEmailError(t('common.emailInvalid'));
    setDraft({ emails: [...new Set([...draft.emails, ...values])] });
    setEmailInput('');
    setEmailError(undefined);
  };

  const onEmailKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      commitEmail();
    } else if (e.key === 'Backspace' && !emailInput && draft.emails.length) {
      setDraft({ emails: draft.emails.slice(0, -1) });
    }
  };

  return (
    <div className="page new-meeting">
      <div className="new-meeting__main">
        {/* The meeting's name is the headline; the pen (or a click on it) makes it editable. */}
        <div className="stack" style={{ gap: 4 }}>
          <p className="section-title">{t('newMeeting.name')}</p>
          {/* Name and date on one line; the date wraps below on narrow screens. */}
          <div className="headline-row">
            {editingName ? (
              <input
                autoFocus
                className="input headline-input"
                aria-label={t('newMeeting.name')}
                placeholder={suggestedName}
                value={nameDraft}
                maxLength={120}
                onChange={(e) => setNameDraft(e.target.value)}
                onFocus={(e) => e.target.select()}
                onBlur={commitName}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitName();
                  if (e.key === 'Escape') setEditingName(false);
                }}
              />
            ) : (
              <div className="headline">
                <h1 className="t-h1 headline__text" onClick={startName}>
                  {draft.title?.trim() || suggestedName}
                </h1>
                <button type="button" className="icon-btn edit-btn headline__pen" aria-label={t('newMeeting.rename')} title={t('newMeeting.rename')} onClick={startName}>
                  <PencilSimpleIcon size={20} aria-hidden />
                </button>
              </div>
            )}
            <DatePicker label={t('newMeeting.date')} value={draft.date ?? todayISO()} onChange={(v) => setDraft({ date: v === todayISO() ? undefined : v })} />
          </div>
          {/* Set from Templates → Start; shown so it's clear where type and participants came from. */}
          {selectedTemplate && (
            <span className="tag template-tag">
              <ListChecksIcon size={14} aria-hidden />
              {t('newMeeting.fromTemplate', { name: selectedTemplate.name })}
              <button type="button" className="emails-field__remove" aria-label={t('newMeeting.templateClear')} title={t('newMeeting.templateClear')} onClick={() => setDraft({ templateId: undefined })}>
                <XIcon size={12} aria-hidden />
              </button>
            </span>
          )}
        </div>

        <div className="stack" style={{ gap: 8 }}>
          <p className="t-strong" id="nm-type">
            {t('newMeeting.type')}
          </p>
          <div className="chips" role="radiogroup" aria-labelledby="nm-type" aria-describedby="nm-type-hint">
            {MEETING_TYPES.map((type) => {
              const on = draft.type === type;
              return (
                <button key={type} type="button" role="radio" aria-checked={on} className="chip" onClick={() => setDraft({ type })}>
                  {on && <CheckIcon size={16} aria-hidden />}
                  {t(`types.${type}`)}
                </button>
              );
            })}
          </div>
          {/* What the selected type changes: the vocabulary the minutes are written in. */}
          <p className="note" id="nm-type-hint" aria-live="polite">
            {t(`newMeeting.typeDesc.${draft.type}`)}
          </p>
        </div>

        <div className="stack" style={{ gap: 8 }}>
          <label className="t-strong" htmlFor="nm-emails">
            {t('newMeeting.emails')}
          </label>
          <div className="emails-field">
            <EnvelopeSimpleIcon size={20} aria-hidden />
            {draft.emails.map((email) => (
              <span key={email} className="tag emails-field__tag">
                {email}
                <button type="button" className="emails-field__remove" aria-label={t('newMeeting.removeEmail', { email })} onClick={() => setDraft({ emails: draft.emails.filter((x) => x !== email) })}>
                  <XIcon size={12} aria-hidden />
                </button>
              </span>
            ))}
            <input
              id="nm-emails"
              type="email"
              className="emails-field__input"
              placeholder={draft.emails.length ? '' : t('newMeeting.emailsPh')}
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              onKeyDown={onEmailKey}
              onBlur={commitEmail}
              aria-invalid={emailError ? true : undefined}
              aria-describedby={emailError ? 'nm-email-err' : undefined}
            />
          </div>
          {emailError && (
            <p id="nm-email-err" className="field__error">
              {emailError}
            </p>
          )}
        </div>

        <div className="start-options">
          <button type="button" className="start-tile start-tile--record" onClick={() => navigate('/recording')}>
            <MicrophoneIcon size={32} aria-hidden />
            <span className="start-tile__spacer" />
            <span className="t-h2">{t('newMeeting.record')}</span>
            {/* MOCK: mic status is not probed until recording starts. */}
            <span className="start-tile__status">
              <CheckIcon size={16} aria-hidden />
              {t('newMeeting.micOk')}
            </span>
          </button>
          <button type="button" className="start-tile start-tile--upload" onClick={() => navigate('/upload')}>
            <UploadSimpleIcon size={32} aria-hidden />
            <span className="start-tile__spacer" />
            <span className="t-h2">{t('newMeeting.upload')}</span>
            <span className="note">{t('newMeeting.uploadHint')}</span>
          </button>
        </div>
      </div>

    </div>
  );
}
