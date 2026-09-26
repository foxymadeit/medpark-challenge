import { CheckIcon, DownloadSimpleIcon } from '@phosphor-icons/react';
import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { ProgressBar } from '../components/ProgressBar';
import { useI18n } from '../i18n/I18nProvider';
import { formatDayMonth } from '../lib/format';
import { downloadMomPdf } from '../lib/momPdf';
import { useStore } from '../store/AppStore';

/** ms per recipient; the bar fills over all of them. */
const STEP_MS = 3600;

/**
 * 07 — Sent. MOCK sending: the meeting name and a green bar that fills linearly (as on processing),
 * then the green check pops in above. Reduced motion shows the final state straight away.
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
  // Linear progress over the whole send, like the processing screen.
  const total = Math.max(1, withEmail.length) * STEP_MS;
  const [elapsed, setElapsed] = useState(reduced ? total : 0);
  const done = elapsed >= total;

  useEffect(() => {
    if (done) return;
    const started = performance.now() - elapsed;
    const timer = window.setInterval(() => setElapsed(Math.min(total, performance.now() - started)), 100);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done, total]);

  if (!meeting) return <Navigate to="/history" replace />;

  return (
    <div className="page sent">
      <div className="sent__done">
        {/* Nothing here while sending (space kept so the text doesn't jump); the green check pops in when the bar is full. */}
        <span className="sent__slot" aria-hidden>
          {done && (
            <span className="sent__badge is-done">
              <CheckIcon size={28} className="sent__check-icon" />
            </span>
          )}
        </span>
        <div className="page__head" style={{ alignItems: 'center', textAlign: 'center' }}>
          <h1 className="t-h1">
            {meeting.title}
          </h1>
          <p className="lead" role="status" aria-live="polite">{done ? t('sent.doneLead', { count: meeting.sentTo ?? withEmail.length, date: formatDayMonth(meeting.date, lang) }) : t('sent.sendingLead', { count: withEmail.length })}</p>
        </div>
        {!done && (
          <div className="processing__progress sent__progress">
            {/* Symbolic: a bar that fills, no percentage. */}
            <ProgressBar value={elapsed / total} label={t('sent.sending')} />
          </div>
        )}


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
