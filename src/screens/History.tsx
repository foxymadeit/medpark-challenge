import { ArrowLeftIcon, DownloadSimpleIcon, FilePdfIcon, ListChecksIcon, LockSimpleIcon, MicrophoneIcon, UploadSimpleIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { Avatar } from '../components/Avatar';
import { TranscriptLines } from '../components/Minutes';
import { TextField } from '../components/TextField';
import { SummaryPoints } from '../components/SummaryPoints';
import { StatusTag } from '../components/StatusTag';
import { Segmented } from '../components/Segmented';
import { MeetingTypeIcon } from '../components/MeetingTypeIcon';
import { PageHeader } from '../components/PageHeader';
import { SearchBar } from '../components/SearchBar';
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
    <div className="page page--fit">
      <PageHeader title={t('history.title')} />
      <SearchBar value={query} onChange={setQuery} placeholder={t('history.search')}>
        {/* Same toggle as the interface-language switch: warm track, raised white pill. */}
        <Segmented<MeetingType | 'all'>
          label={t('history.filter')}
          variant="auto"
          value={filter}
          onChange={setFilter}
          options={(['all', ...MEETING_TYPES] as const).map((f) => ({
            value: f,
            label: f === 'all' ? t('history.all') : t(`types.${f}`),
            icon: f === 'all' ? undefined : <MeetingTypeIcon type={f} />,
          }))}
        />
      </SearchBar>

      <div className="table-card">
        <table className="table table--history">
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
                        <Link to={recordPath(m)} className="who__name row-link history__title" onClick={(e) => e.stopPropagation()}>
                          {m.title}
                        </Link>
                        <span className="who__sub history__source">{m.source === 'uploaded' ? t('history.uploaded') : t('history.recorded')}</span>
                      </div>
                    </div>
                  </td>
                  <td className="t-body-md">{t(`types.${m.type}`)}</td>
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
    </div>
  );
}

/** 08b — Meeting record; roles frozen at the meeting date. */
export function HistoryRecord() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const { meetings, resolvePerson, saveTemplate } = useStore();
  const navigate = useNavigate();
  const [tab, setTab] = useState<'mom' | 'transcript'>('mom'); // MoM first
  const [pdfBusy, setPdfBusy] = useState(false);
  const meeting = meetings.find((m) => m.id === id);
  const [tplName, setTplName] = useState<string | null>(null); // null = dialog closed
  if (!meeting) return <Navigate to="/history" replace />;

  const saveAsTemplate = () => {
    if (!tplName?.trim()) return;
    saveTemplate({
      name: tplName.trim(),
      type: meeting.type,
      // Only people in the directory can be template members (not one-off email guests).
      participantIds: meeting.participants.map((p) => p.personId).filter((pid) => resolvePerson(pid)),
    });
    navigate('/templates');
  };

  const nameOf = speakerNamer(meeting, resolvePerson, t);
  const fullDate = formatFullDate(meeting.date, lang);
  const type = t(`types.${meeting.type}`);

  return (
    <div className="page record page--fit">
      <Link to="/history" className="back-link">
        <ArrowLeftIcon size={16} aria-hidden />
        {t('record.back')}
      </Link>
      <div className="stack" style={{ gap: 'var(--sm-space-1)' }}>
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

      <div className="review__tabs no-print">
        <Segmented<'mom' | 'transcript'>
          label={t('review.view')}
          variant="auto"
          value={tab}
          onChange={setTab}
          options={[
            { value: 'mom', label: t('review.tabMom') },
            { value: 'transcript', label: t('review.transcript') },
          ]}
        />
      </div>

      {tab === 'transcript' ? (
        // Read-only, like the Transcript tab on Review.
        <section className="card card--pad record__transcript" aria-labelledby="rec-transcript">
          <h2 id="rec-transcript" className="section-title">
            {t('review.transcript')}
          </h2>
          <TranscriptLines lines={meeting.transcript} nameOf={nameOf} />
        </section>
      ) : (
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
            {t('review.summary')}
          </h2>
          <SummaryPoints points={meeting.summary ?? []} />
          <h3 className="review__sub-title record__tasks-title">{t('review.tasks')}</h3>
          <table className="summary-table">
            <thead>
              <tr>
                <th scope="col">
                  {/* "Action items" is already the heading above; keep the column name for screen readers only. */}
                  <span className="sr-only">{t('review.task')}</span>
                </th>
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
                      <span className="summary-table__patient">{task.patient}</span>
                      <span className="t-body-md">{task.title}</span>
                    </td>
                    <td>
                      <span className="summary-table__owner">
                        <Avatar name={nameOf(task.ownerId)} />
                        <span className="who__name truncate" style={{ paddingTop: 'var(--sm-space-1)' }}>
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
        </section>
      </div>
      )}

      {/* Centred on the window (vp-center), not on the content area. */}
      <div className="page__actions vp-center no-print">
        <div className="vp-center__group">
          <Button icon={<ListChecksIcon size={20} aria-hidden />} onClick={() => setTplName(meeting.title)}>
            {t('record.saveTemplate')}
          </Button>
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
      </div>

      {tplName !== null && (
        <Dialog title={t('record.saveTemplate')} onClose={() => setTplName(null)}>
          <form className="stack" style={{ gap: 'var(--sm-space-4)' }} onSubmit={(e) => (e.preventDefault(), saveAsTemplate())}>
            <p className="note">{t('record.saveTemplateLead', { count: meeting.participants.filter((p) => resolvePerson(p.personId)).length })}</p>
            <TextField editable label={t('templates.name')} value={tplName} onChange={(e) => setTplName(e.target.value)} />
            <Button type="submit" variant="primary" block disabled={!tplName.trim()}>
              {t('templates.save')}
            </Button>
          </form>
        </Dialog>
      )}
    </div>
  );
}
