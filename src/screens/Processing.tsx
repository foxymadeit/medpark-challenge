import { CheckIcon, ShieldCheckIcon } from '@phosphor-icons/react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { TranscriptLines } from '../components/Minutes';
import { ProgressBar } from '../components/ProgressBar';
import { useI18n } from '../i18n/I18nProvider';
import { processingStepsMs } from '../mocks';
import { useStore } from '../store/AppStore';

const STEPS = ['processing.step1', 'processing.step2', 'processing.step3'];

/**
 * 04 — MOCKED processing: timed steps with a live percentage.
 * While "Transcribing" runs, the transcript appears chunk by chunk so it can be read before review.
 * Ends in review (manual) or straight in sent (auto).
 */
export function Processing() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { meetings, updateMeeting, sendMeeting, preferences, resolvePerson } = useStore();
  const meeting = meetings.find((m) => m.id === id);
  const [elapsed, setElapsed] = useState(0);
  const total = processingStepsMs.reduce((a, b) => a + b, 0);
  const pane = useRef<HTMLDivElement>(null);
  const pinned = useRef(true); // follow new chunks only while the reader is at the bottom

  useEffect(() => {
    const started = performance.now();
    const timer = setInterval(() => setElapsed(performance.now() - started), 100);
    return () => clearInterval(timer);
  }, []);

  const done = useRef(false);
  useEffect(() => {
    if (!meeting || elapsed < total || done.current) return;
    done.current = true; // one-shot: updateMeeting changes `meeting`, which re-runs this effect
    // Auto mode (Settings): the minutes go out as soon as they are written, no review, no countdown.
    if (preferences.reviewMode === 'auto') {
      sendMeeting(meeting.id);
      navigate(`/sent/${meeting.id}`, { replace: true });
      return;
    }
    updateMeeting(meeting.id, { status: 'needs_review' });
    navigate(`/review/${meeting.id}`, { replace: true });
  }, [elapsed, total, meeting, updateMeeting, sendMeeting, preferences.reviewMode, navigate]);

  // Chunks transcribed so far: spread over the first step, all of them after it.
  const lines = meeting?.transcript ?? [];
  const transcribeShare = Math.min(1, elapsed / processingStepsMs[0]);
  const shown = Math.min(lines.length, Math.floor(transcribeShare * lines.length) + (elapsed > 0 ? 1 : 0));

  useLayoutEffect(() => {
    const el = pane.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [shown]);

  if (!meeting) return <Navigate to="/new" replace />;

  let acc = 0;
  const current = processingStepsMs.findIndex((ms) => (acc += ms) > elapsed);
  const step = current === -1 ? STEPS.length - 1 : current;
  const pct = Math.min(100, Math.round((elapsed / total) * 100));
  const nameOf = (pid: string) => meeting.participants.find((p) => p.personId === pid)?.name ?? resolvePerson(pid)?.name ?? pid;

  return (
    <div className="page processing">
      <div className="processing__box">
        <div className="page__head" style={{ alignItems: 'center', textAlign: 'center' }}>
          <h1 className="t-h1">{t('processing.title')}</h1>
          <p className="lead">{t('processing.lead', { title: meeting.title, n: meeting.durationMin })}</p>
        </div>

        <div className="processing__progress">
          <ProgressBar value={elapsed / total} label={t('processing.progress')} />
          <span className="processing__pct" aria-hidden>
            {pct}%
          </span>
        </div>

        <ol className="steps" aria-live="polite">
          {STEPS.map((key, i) => (
            <li key={key} className={`step${i < step ? ' is-done' : i === step ? ' is-active' : ''}`} aria-current={i === step ? 'step' : undefined}>
              {i < step ? (
                <span className="step__check" aria-hidden>
                  <CheckIcon size={12} weight="bold" />
                </span>
              ) : (
                <span className="step__dot" aria-hidden />
              )}
              {t(key)}
              {i < step && <span className="sr-only"> — {t('processing.done')}</span>}
            </li>
          ))}
        </ol>

        <section className="card processing__live" aria-labelledby="proc-live">
          <div className="processing__live-head">
            <h2 id="proc-live" className="section-title">
              {t('processing.liveTitle')}
            </h2>
            <span className="note">{t('processing.chunks', { n: shown, total: lines.length })}</span>
          </div>
          <div
            ref={pane}
            className="processing__live-body"
            tabIndex={0}
            aria-label={t('processing.liveTitle')}
            onScroll={(e) => {
              const el = e.currentTarget;
              pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
            }}
          >
            <TranscriptLines lines={lines.slice(0, shown)} nameOf={nameOf} />
            {shown < lines.length && <p className="processing__typing note">{t('processing.listening')}</p>}
          </div>
        </section>
      </div>
      <p className="processing__note note">
        <ShieldCheckIcon size={16} aria-hidden />
        {t('processing.note')}
      </p>
    </div>
  );
}
