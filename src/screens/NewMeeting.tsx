import { CheckIcon, ListChecksIcon, MicrophoneIcon, PencilSimpleIcon, UploadSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DatePicker } from '../components/DatePicker';
import { EmailsField } from '../components/EmailsField';
import { useI18n } from '../i18n/I18nProvider';
import { todayISO } from '../lib/format';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES } from '../types';

/** 01 — name, date, type, optional emails, then Record / Upload tiles (templates start from the Templates page). */
export function NewMeeting() {
  const { t } = useI18n();
  const { draft, setDraft, templates } = useStore();
  const navigate = useNavigate();
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

        <EmailsField emails={draft.emails} onChange={(emails) => setDraft({ emails })} />

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
