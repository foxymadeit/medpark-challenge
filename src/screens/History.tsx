import { ArrowLeftIcon, DownloadSimpleIcon, FileAudioIcon, FilePdfIcon, LockSimpleIcon, MagnifyingGlassIcon, MicrophoneIcon, UploadSimpleIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { Avatar } from '../components/Avatar';
import { TranscriptLines } from '../components/Minutes';
import { StatusTag } from '../components/StatusTag';
import { MeetingTypeIcon } from '../components/MeetingTypeIcon';
import { useI18n } from '../i18n/I18nProvider';
import { dueRelative, formatDayMonth, formatFullDate, formatWeekdayDate } from '../lib/format';
import { speakerNamer } from '../lib/meeting';
import { downloadMomPdf } from '../lib/momPdf';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES, type Meeting, type MeetingType } from '../types';

const recordPath = (m: Meeting) =>
  m.status === 'needs_review' ? `/review/${m.id}` : m.status === 'processing' ? `/processing/${m.id}` : `/history/${m.id}`;

/** 08 — History list with search and type filter. */
export function History() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const { meetings } = useStore();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<MeetingType | 'all'>('all');
  const [pdfBusy, setPdfBusy] = useState<string | null>(null);

  const download = async (m: Meeting) => {
    setPdfBusy(m.id);
    try {
      await downloadMomPdf(m, t, lang);
    } finally {
      setPdfBusy(null);
    }
  };

  const q = query.trim().toLowerCase();
  const rows = meetings.filter((m) => (filter === 'all' || m.type === filter) && (!q || m.title.toLowerCase().includes(q)));

  return (
    <div className="page">
      <h1 className="t-h1">{t('history.title')}</h1>
      <div className="history-tools">
        <label className="search">
          <MagnifyingGlassIcon size={16} aria-hidden />
          <span className="sr-only">{t('history.search')}</span>
          <input type="search" placeholder={t('history.search')} value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <div className="chips" role="radiogroup" aria-label={t('history.filter')}>
          {(['all', ...MEETING_TYPES] as const).map((f) => (
            <button key={f} type="button" role="radio" aria-checked={filter === f} className="chip chip--sm" onClick={() => setFilter(f)}>
              {f !== 'all' && <MeetingTypeIcon type={f} />}
              {f === 'all' ? t('history.all') : t(`typesShort.${f}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="table-card">
        <table className="table">
          <colgroup>
            <col />
            <col style={{ width: 136 }} />
            <col style={{ width: 136 }} />
            <col style={{ width: 112 }} />
            <col style={{ width: 144 }} />
            <col style={{ width: 64 }} />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">{t('history.colMeeting')}</th>
              <th scope="col">{t('history.colType')}</th>
              <th scope="col">{t('history.colDate')}</th>
              <th scope="col">{t('history.colLength')}</th>
              <th scope="col">{t('history.colStatus')}</th>
              <th scope="col">
                <span className="sr-only">{t('record.download')}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => {
              const Icon = m.source === 'uploaded' ? UploadSimpleIcon : MicrophoneIcon;
              return (
                <tr key={m.id} className="is-clickable" onClick={() => navigate(recordPath(m))}>
                  <td>
                    <div className="who">
                      <Icon size={20} aria-hidden />
                      <div className="who__text">
                        <Link to={recordPath(m)} className="who__name row-link truncate" onClick={(e) => e.stopPropagation()}>
                          {m.title}
                        </Link>
                        <span className="who__sub">{m.source === 'uploaded' ? t('history.uploaded') : t('history.recorded')}</span>
                      </div>
                    </div>
                  </td>
                  <td className="t-body-md">{t(`typesShort.${m.type}`)}</td>
                  <td className="t-data-sm">{formatDayMonth(m.date, lang)}</td>
                  <td className="t-data-sm">{t('common.minutes', { n: m.durationMin })}</td>
                  <td>
                    <StatusTag status={m.status} />
                  </td>
                  <td>
                    {m.status === 'sent' && (
                      <button
                        type="button"
                        className="icon-btn icon-btn--lg"
                        aria-label={t('history.downloadPdf', { title: m.title })}
                        title={t('record.download')}
                        disabled={pdfBusy === m.id}
                        aria-busy={pdfBusy === m.id}
                        onClick={(e) => {
                          e.stopPropagation(); // don't open the record
                          void download(m);
                        }}
                      >
                        <FilePdfIcon size={20} aria-hidden />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {!rows.length && (
              <tr>
                <td colSpan={6} className="note">
                  {t('history.empty')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="note" style={{ marginTop: 16 }}>
        {t('history.hint')}
      </p>
    </div>
  );
}

/** 08b — Meeting record; roles frozen at the meeting date. */
export function HistoryRecord() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const { meetings, resolvePerson } = useStore();
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const meeting = meetings.find((m) => m.id === id);
  if (!meeting) return <Navigate to="/history" replace />;

  const nameOf = speakerNamer(meeting, resolvePerson, t);
  const fullDate = formatFullDate(meeting.date, lang);
  const type = t(`types.${meeting.type}`);

  return (
    <div className="page record">
      <Link to="/history" className="back-link">
        <ArrowLeftIcon size={16} aria-hidden />
        {t('record.back')}
      </Link>
      <div className="stack" style={{ gap: 4 }}>
        <h1 className="t-h1">{meeting.title}</h1>
        <p className="note">
          {meeting.status === 'sent'
            ? t('record.meta', { type, date: fullDate, n: meeting.durationMin, sent: meeting.sentTo ?? 0, total: meeting.participants.length })
            : t('record.metaUnsent', { type, date: fullDate, n: meeting.durationMin })}
        </p>
      </div>
      <p className="tile frozen-banner">
        <LockSimpleIcon size={16} aria-hidden />
        {t('record.banner', { date: fullDate })}
      </p>

      <div className="record__panes">
        <section className="card record__people" aria-labelledby="rec-people">
          <h2 id="rec-people" className="section-title record__people-head">
            {t('record.participants')}
          </h2>
          <ul className="record__list">
            {meeting.participants.map((p) => {
              const nowRole = resolvePerson(p.personId)?.role;
              const changed = !!nowRole && nowRole !== p.roleThen;
              return (
                <li key={p.personId} className="record__person">
                  <span className="who__text" style={{ flex: 1 }}>
                    <span className="who__name">{p.name}</span>
                    {p.roleThen && <span className="who__sub">{t('record.roleThen', { role: p.roleThen })}</span>}
                  </span>
                  {changed && <span className="tag">{t('record.now', { role: nowRole })}</span>}
                </li>
              );
            })}
          </ul>
        </section>

        <section className="card card--pad record__minutes" aria-labelledby="rec-minutes">
          <h2 id="rec-minutes" className="section-title">
            {t('record.minutes')}
          </h2>
          <table className="summary-table">
            <thead>
              <tr>
                <th scope="col">{t('review.task')}</th>
                <th scope="col">{t('review.owner')}</th>
                <th scope="col">{t('review.due')}</th>
              </tr>
            </thead>
            <tbody>
              {[...meeting.tasks]
                .sort((a, b) => a.due.localeCompare(b.due))
                .map((task) => (
                  <tr key={task.id}>
                    <td>
                      <span className="summary-table__patient">{t('review.patient', { name: task.patient })}</span>
                      <span className="t-body-md">{task.title}</span>
                    </td>
                    <td>
                      <span className="summary-table__owner">
                        <Avatar name={nameOf(task.ownerId)} />
                        <span className="who__name truncate" style={{ paddingTop: 5 }}>
                          {nameOf(task.ownerId)}
                        </span>
                      </span>
                    </td>
                    <td>
                      <span className="due">
                        <span className="due__rel">{(() => { const r = dueRelative(meeting.date, task.due); return r ? t(r.key, r.vars) : formatWeekdayDate(task.due, lang); })()}</span>
                        {dueRelative(meeting.date, task.due) && <span className="due__date">{formatWeekdayDate(task.due, lang)}</span>}
                      </span>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          <button type="button" className="link-btn no-print" onClick={() => setTranscriptOpen(true)}>
            <FileAudioIcon size={16} aria-hidden />
            {t('record.openTranscript')}
          </button>
        </section>
      </div>

      <div className="page__actions no-print">
        <Button
          variant="primary"
          icon={<DownloadSimpleIcon size={20} aria-hidden />}
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
          {pdfBusy ? t('pdf.preparing') : t('record.download')}
        </Button>
      </div>

      {transcriptOpen && (
        <Dialog title={t('review.transcript')} onClose={() => setTranscriptOpen(false)} wide>
          <p className="note">{t('review.highlighted')}</p>
          <TranscriptLines lines={meeting.transcript} nameOf={nameOf} />
        </Dialog>
      )}
    </div>
  );
}
