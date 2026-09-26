import { CheckIcon, ShieldCheckIcon } from '@phosphor-icons/react';
import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { ProgressBar } from '../components/ProgressBar';
import { useI18n } from '../i18n/I18nProvider';
import { processingStepMs } from '../mocks';
import { useStore } from '../store/AppStore';

const STEPS = ['processing.step1', 'processing.step2', 'processing.step3'];

/** 04 — MOCKED processing: 3 timed steps, then the review screen. */
export function Processing() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { meetings, updateMeeting } = useStore();
  const meeting = meetings.find((m) => m.id === id);
  const [elapsed, setElapsed] = useState(0);
  const total = STEPS.length * processingStepMs;

  useEffect(() => {
    const started = performance.now();
    const timer = setInterval(() => setElapsed(performance.now() - started), 100);
    return () => clearInterval(timer);
  }, []);

  const done = useRef(false);
  useEffect(() => {
    if (!meeting || elapsed < total || done.current) return;
    done.current = true; // one-shot: updateMeeting changes `meeting`, which re-runs this effect
    updateMeeting(meeting.id, { status: 'needs_review' });
    navigate(`/review/${meeting.id}`, { replace: true });
  }, [elapsed, total, meeting, updateMeeting, navigate]);

  if (!meeting) return <Navigate to="/new" replace />;
  const current = Math.min(STEPS.length - 1, Math.floor(elapsed / processingStepMs));

  return (
    <div className="page processing">
      <div className="processing__box">
        <div className="page__head" style={{ alignItems: 'center', textAlign: 'center' }}>
          <h1 className="t-h1">{t('processing.title')}</h1>
          <p className="lead">{t('processing.lead', { title: meeting.title, n: meeting.durationMin })}</p>
        </div>
        <ProgressBar value={elapsed / total} label={t('processing.progress')} />
        <ol className="steps" aria-live="polite">
          {STEPS.map((key, i) => (
            <li key={key} className={`step${i < current ? ' is-done' : i === current ? ' is-active' : ''}`} aria-current={i === current ? 'step' : undefined}>
              {i < current ? <CheckIcon size={16} aria-hidden /> : <span className="step__dot" aria-hidden />}
              {t(key)}
            </li>
          ))}
        </ol>
      </div>
      <p className="processing__note note">
        <ShieldCheckIcon size={16} aria-hidden />
        {t('processing.note')}
      </p>
    </div>
  );
}
