import { CheckIcon, DownloadSimpleIcon, ListChecksIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { formatDayMonth } from '../lib/format';
import { downloadMomPdf } from '../lib/momPdf';
import { useStore } from '../store/AppStore';

/** 07 — Sent + offer "Save as template". */
export function Sent() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { meetings, saveTemplate, resolvePerson } = useStore();
  const meeting = meetings.find((m) => m.id === id);
  const [name, setName] = useState(meeting?.title ?? '');
  const [error, setError] = useState<string>();
  const [pdfBusy, setPdfBusy] = useState(false);

  if (!meeting) return <Navigate to="/history" replace />;

  const save = () => {
    if (!name.trim()) return setError(t('common.required'));
    saveTemplate({
      name: name.trim(),
      type: meeting.type,
      // Only people in the directory can be template members (not one-off email guests).
      participantIds: meeting.participants.map((p) => p.personId).filter((pid) => resolvePerson(pid)),
    });
    navigate('/templates');
  };

  return (
    <div className="page sent">
      <div className="sent__done">
        <span className="sent__check" aria-hidden>
          <CheckIcon size={24} />
        </span>
        <div className="page__head" style={{ alignItems: 'center', textAlign: 'center' }}>
          <h1 className="t-h1" role="status">
            {t('sent.title', { count: meeting.sentTo ?? meeting.participants.length })}
          </h1>
          <p className="lead">{t('sent.lead', { date: formatDayMonth(meeting.date, lang) })}</p>
          <button
            type="button"
            className="link-btn sent__download"
            disabled={pdfBusy}
            aria-busy={pdfBusy}
            onClick={async () => {
              setPdfBusy(true);
              try {
                await downloadMomPdf(meeting, t, lang);
              } finally {
                setPdfBusy(false);
              }
            }}
          >
            <DownloadSimpleIcon size={16} aria-hidden />
            {pdfBusy ? t('pdf.preparing') : t('sent.download')}
          </button>
        </div>
        <form className="card card--pad stack" style={{ gap: 16, width: '100%' }} onSubmit={(e) => (e.preventDefault(), save())}>
          <div className="stack" style={{ gap: 4 }}>
            <h2 className="section-title">{t('sent.saveTitle')}</h2>
            <p className="note">{t('sent.saveLead')}</p>
          </div>
          <TextField editable label={t('sent.name')} value={name} onChange={(e) => setName(e.target.value)} error={error} />
        </form>
      </div>
      <div className="page__actions page__actions--stack">
        <Button variant="primary" icon={<ListChecksIcon size={20} aria-hidden />} onClick={save} disabled={!name.trim()}>
          {t('sent.save')}
        </Button>
        <Button variant="ghost" onClick={() => navigate('/history')}>
          {t('sent.notNow')}
        </Button>
      </div>
    </div>
  );
}
