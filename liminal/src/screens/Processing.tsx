import { CheckIcon, ShieldCheckIcon, WarningIcon } from '@phosphor-icons/react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { TranscriptLines } from '../components/Minutes';
import { ProgressBar } from '../components/ProgressBar';
import { useI18n } from '../i18n/I18nProvider';
import { speakerNamer } from '../lib/meeting';
import { processingStepsMs } from '../mocks';
import { useStore } from '../store/AppStore';

const STEPS = ['processing.step1', 'processing.step2', 'processing.step3'];

/**
 * 04 — MOCKED processing: timed steps with a live percentage.
 * While "Transcribing" runs, the transcript appears chunk by chunk so it can be read before review.
 * Ends in review (manual) or straight in sent (auto). `?fail` stops it after the first step, to show the error state.
 */
export function Processing() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { meetings, updateMeeting, sendMeeting, preferences, resolvePerson } = useStore();
  const meeting = meetings.find((m) => m.id === id);
  const [searchParams, setSearchParams] = useSearchParams();
  const [elapsed, setElapsed] = useState(0);
  const [run, setRun] = useState(0); // Try again starts the timer over
  const total = processingStepsMs.reduce((a, b) => a + b, 0);
  const failAt = searchParams.has('fail') ? processingStepsMs[0] : Infinity;
  const failed = elapsed >= failAt;
  const pane = useRef<HTMLDivElement>(null);
  const pinned = useRef(true); // follow new chunks only while the reader is at the bottom

  useEffect(() => {
    const started = performance.now();
    const timer = setInterval(() => setElapsed(Math.min(performance.now() - started, failAt)), 100);
    return () => clearInterval(timer);
  }, [run, failAt]);

  const retry = () => {
    setSearchParams({}, { replace: true });
    setElapsed(0);
    setRun((r) => r + 1);
  };

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
  const nameOf = speakerNamer(meeting, resolvePerson, t);

  return (
    <div className="page processing">
      <div className="vp-center">
        <div className="processing__box">
          <div className="page__head" style={{ alignItems: 'center', textAlign: 'center' }}>
            <h1 className="t-h1">{t(failed ? 'processing.failedTitle' : 'processing.title')}</h1>
            <p className="lead">{t('processing.lead', { title: meeting.title, n: meeting.durationMin })}</p>
          </div>

          {failed ? (
            <div className="form-alert" role="alert">
              <WarningIcon size={16} aria-hidden />
              <p>{t('processing.failedNote')}</p>
            </div>
          ) : (
            <div className="processing__progress">
              <ProgressBar value={elapsed / total} label={t('processing.progress')} />
              <span className="processing__pct" aria-hidden>
                {pct}%
              </span>
            </div>
          )}

          <ol className="steps" aria-live="polite">
            {STEPS.map((key, i) => (
              <li key={key} className={`step${i < step ? ' is-done' : i === step ? (failed ? ' is-failed' : ' is-active') : ''}`} aria-current={i === step ? 'step' : undefined}>
                {i < step ? (
                  <span className="step__check" aria-hidden>
                    <CheckIcon size={12} weight="bold" />
                  </span>
                ) : failed && i === step ? (
                  <WarningIcon size={16} aria-hidden className="step__fail" />
                ) : (
                  <span className="step__dot" aria-hidden />
                )}
                {t(key)}
                {i < step && <span className="sr-only"> — {t('processing.done')}</span>}
              </li>
            ))}
          </ol>

          {failed && (
            <div className="processing__actions">
              <Button onClick={() => navigate('/new')}>{t('processing.backToNew')}</Button>
              <Button variant="primary" onClick={retry}>
                {t('processing.retry')}
              </Button>
            </div>
          )}

          {!failed && <section className="card processing__live" aria-labelledby="proc-live">
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
          </section>}
        </div>
      </div>
      <div className="vp-center processing__note-row">
        <p className="processing__note note">
          <ShieldCheckIcon size={16} aria-hidden />
          {t('processing.note')}
        </p>
      </div>
    </div>
  );
}
