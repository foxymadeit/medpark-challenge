import { CheckIcon, DownloadSimpleIcon, PaperPlaneTiltIcon } from '@phosphor-icons/react';
import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { useI18n } from '../i18n/I18nProvider';
import { formatDayMonth } from '../lib/format';
import { downloadMomPdf } from '../lib/momPdf';
import { useStore } from '../store/AppStore';

/** ms per recipient; the ring around the badge fills over all of them. */
const STEP_MS = 3600;

/**
 * 07 — Sent. MOCK sending animation: a paper plane in a ring that fills green over the send,
 * then the green check pops in. Reduced motion shows the final state straight away.
 */
export function Sent() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { meetings, resolvePerson } = useStore();
  const meeting = meetings.find((m) => m.id === id);
  const [pdfBusy, setPdfBusy] = useState(false);
  const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  const people = (meeting?.participants ?? []).map((p) => ({ ...p, email: p.email ?? resolvePerson(p.personId)?.email }));
  const withEmail = people.filter((p) => p.email);
  const [ticked, setTicked] = useState(reduced ? withEmail.length : 0);
  const done = ticked >= withEmail.length;

  useEffect(() => {
    if (done) return;
    const timer = window.setTimeout(() => setTicked((n) => n + 1), STEP_MS);
    return () => window.clearTimeout(timer);
  }, [ticked, done]);

  if (!meeting) return <Navigate to="/history" replace />;

  return (
    <div className="page sent">
      <div className="sent__done">
        {/* Progress ring around the badge fills green over the whole send, then the check pops in. */}
        <span className={`sent__badge-wrap${done ? ' is-done' : ''}`} aria-hidden>
          <svg className="sent__ring" viewBox="0 0 80 80" width="80" height="80">
            <circle cx="40" cy="40" r="37" className="sent__ring-track" />
            <circle cx="40" cy="40" r="37" className="sent__ring-fill" pathLength={100} style={{ animationDuration: `${withEmail.length * STEP_MS}ms` }} />
          </svg>
          <span className={`sent__badge${done ? ' is-done' : ''}`}>
            {done ? <CheckIcon size={28} className="sent__check-icon" /> : <PaperPlaneTiltIcon size={26} className="sent__plane" />}
          </span>
        </span>
        <div className="page__head" style={{ alignItems: 'center', textAlign: 'center' }}>
          <h1 className="t-h1" role="status" aria-live="polite">
            {done ? t('sent.title', { count: meeting.sentTo ?? withEmail.length }) : t('sent.sending')}
          </h1>
          <p className="lead">{done ? t('sent.lead', { date: formatDayMonth(meeting.date, lang) }) : t('sent.sendingLead', { count: withEmail.length })}</p>
        </div>


        {done && (
          <div className="sent__after">
            <button
              type="button"
              className="link-btn"
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
            <Button variant="ink" onClick={() => navigate('/history')}>
              {t('sent.toHistory')}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
