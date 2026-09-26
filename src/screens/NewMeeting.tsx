import { ArrowRightIcon, CheckIcon, EnvelopeSimpleIcon, ListChecksIcon, MicrophoneIcon, PencilSimpleIcon, UploadSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useState, type KeyboardEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { isEmail } from '../lib/format';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES } from '../types';

/** 01 — type chips, optional template & emails, then Record / Upload tiles. */
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
          <p className="section-title">{t('newMeeting.title')}</p>
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

      <aside className="templates-side" aria-labelledby="nm-tpl">
        <div className="stack" style={{ gap: 4 }}>
          <h2 id="nm-tpl" className="section-title">
            {t('newMeeting.templatesTitle')}
          </h2>
          <p className="note">{t('newMeeting.templatesLead')}</p>
        </div>
        <ul className="templates-side__list">
          {templates.slice(0, 3).map((tpl) => {
            const on = draft.templateId === tpl.id;
            return (
              <li key={tpl.id}>
                <button
                  type="button"
                  className="templates-side__item"
                  aria-pressed={on}
                  title={on ? t('newMeeting.templateClear') : undefined}
                  onClick={() => setDraft(on ? { templateId: undefined } : { templateId: tpl.id, type: tpl.type })}
                >
                  {on ? (
                    <span className="templates-side__check" aria-hidden>
                      <CheckIcon size={12} weight="bold" />
                    </span>
                  ) : (
                    <ListChecksIcon size={20} aria-hidden />
                  )}
                  <span className="who__text" style={{ flex: 1 }}>
                    <span className="who__name">{tpl.name}</span>
                    <span className="who__sub">
                      {on ? t('newMeeting.templateSelected') : `${t(`types.${tpl.type}`)} · ${t('common.participantsCount', { count: tpl.participantIds.length })}`}
                    </span>
                  </span>
                  {on ? <XIcon size={16} aria-hidden /> : <ArrowRightIcon size={16} aria-hidden />}
                </button>
              </li>
            );
          })}
        </ul>
        <Link to="/templates" className="link-btn">
          {t('newMeeting.allTemplates')}
        </Link>
      </aside>
    </div>
  );
}
