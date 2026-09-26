import { CheckIcon, PauseIcon, PlayIcon, StopIcon } from '@phosphor-icons/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { useI18n } from '../i18n/I18nProvider';
import { formatClock } from '../lib/format';
import { useDraftMeeting } from '../lib/meeting';
import { useRecorder } from '../lib/useRecorder';
import { detectedLanguages, diarizationTimeline } from '../mocks';
import { useStore } from '../store/AppStore';

const BARS = 72;
const TICK_MS = 100;
const UNMATCHED = '__unmatched__';

/** Speaker colour = order of first appearance in the (mocked) diarization → speaker/01…04. */
function speakerColours() {
  const order: string[] = [];
  for (const seg of diarizationTimeline) {
    const key = seg.speakerId ?? UNMATCHED;
    if (!order.includes(key)) order.push(key);
  }
  return Object.fromEntries(order.map((k, i) => [k, `var(--sm-speaker-${String((i % 4) + 1).padStart(2, '0')})`]));
}

/** MOCK diarization: which speaker is talking at `t` seconds (timeline loops). */
function speakerAt(t: number): string {
  const total = diarizationTimeline.reduce((s, x) => s + x.seconds, 0);
  let rem = t % total;
  for (const seg of diarizationTimeline) {
    if (rem < seg.seconds) return seg.speakerId ?? UNMATCHED;
    rem -= seg.seconds;
  }
  return diarizationTimeline[0].speakerId ?? UNMATCHED;
}

interface Bar {
  h: number;
  speaker: string | null;
}

/** 02 / 02b — live recording with waveform coloured by current speaker. */
export function Recording() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const { createMeetingFromDraft } = useStore();
  const { title, typeLabel, people, count } = useDraftMeeting();
  const rec = useRecorder();
  const colours = useMemo(speakerColours, []);
  const [bars, setBars] = useState<Bar[]>(() => Array.from({ length: BARS }, () => ({ h: 4, speaker: null })));
  const [talk, setTalk] = useState<Record<string, number>>({}); // seconds per speaker
  const elapsedRef = useRef(0);
  elapsedRef.current = rec.elapsed;
  const paused = rec.state === 'paused';
  const current = rec.state === 'recording' ? speakerAt(rec.elapsed) : null;

  // Start the microphone once.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void rec.start();
  }, [rec]);

  // Waveform + talk-time sampling.
  useEffect(() => {
    if (rec.state !== 'recording') return;
    const id = setInterval(() => {
      const speaker = speakerAt(elapsedRef.current);
      const level = rec.getLevel();
      setBars((b) => [...b.slice(1), { h: Math.round(8 + level * 48), speaker }]);
      setTalk((m) => ({ ...m, [speaker]: (m[speaker] ?? 0) + TICK_MS / 1000 }));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [rec.state, rec.getLevel]);

  const stop = async () => {
    await rec.stop();
    const id = createMeetingFromDraft('recorded', Math.round(rec.elapsed / 60), undefined, title);
    navigate(`/processing/${id}`);
  };

  // Participants: heard (by first appearance), unmatched voice, then not heard yet.
  const order = Object.keys(colours);
  const heard = people.filter((p) => talk[p.id]).sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  const notHeard = people.filter((p) => !talk[p.id]);
  const minutes = (s: number) => t('common.minutes', { n: Math.max(1, Math.ceil(s / 60)) });
  // Language names are capitalised on chips; RO/RU write them lowercase mid-sentence.
  const langName = lang === 'en' ? t(`lang.${detectedLanguages[0]}Name`) : t(`lang.${detectedLanguages[0]}Name`).toLocaleLowerCase(lang);

  return (
    <div className="page recording">
      <section className="recorder" aria-label={title}>
        <div className="stack recorder__meeting">
          <h1 className="t-h1">{title}</h1>
          <p className="note">
            {typeLabel} · {t('common.participantsCount', { count })}
          </p>
        </div>
        <p className="recorder__state t-plate" role="status">
          {paused ? <PauseIcon size={16} aria-hidden /> : <span className="rec-dot" aria-hidden />}
          <span className={paused ? 'c-secondary' : ''}>{paused ? t('recording.paused') : t('recording.recording')}</span>
        </p>
        <p className={`recorder__timer${paused ? ' is-paused' : ''}`} aria-label={t('recording.elapsed')} role="timer">
          {formatClock(rec.elapsed)}
        </p>
        <div className="waveform" role="img" aria-label={t('recording.waveform')}>
          {bars.map((b, i) => (
            <span
              key={i}
              className="waveform__bar"
              style={{
                height: b.h,
                background: paused || !b.speaker ? 'var(--sm-ink-tertiary)' : colours[b.speaker],
                opacity: paused || !b.speaker ? 0.35 : i >= BARS - 6 ? 0.5 : 1,
              }}
            />
          ))}
        </div>
        <div className="recorder__actions">
          {paused ? (
            <>
              <Button icon={<StopIcon size={20} aria-hidden />} onClick={stop}>
                {t('recording.stop')}
              </Button>
              <Button variant="primary" icon={<PlayIcon size={20} aria-hidden />} onClick={rec.resume}>
                {t('recording.resume')}
              </Button>
            </>
          ) : (
            <>
              <Button icon={<PauseIcon size={20} aria-hidden />} onClick={rec.pause}>
                {t('recording.pause')}
              </Button>
              <Button variant="primary" icon={<StopIcon size={20} aria-hidden />} onClick={stop}>
                {t('recording.stop')}
              </Button>
            </>
          )}
        </div>
        <p className={`recorder__note note${rec.micError ? ' c-danger' : ''}`} role={rec.micError ? 'alert' : undefined}>
          {rec.micError ? t('recording.micError') : paused ? t('recording.notePaused') : t('recording.noteLive')}
        </p>
      </section>

      <aside className="card live-details" aria-label={t('recording.voices')}>
        <div className="stack" style={{ gap: 12 }}>
          <h2 className="section-title">{t('recording.languages')}</h2>
          <div className="chips">
            {detectedLanguages.map((l, i) => (
              <span key={l} className={`chip chip--lang${i === 0 ? ' is-active' : ''}`}>
                {t(`lang.${l}Name`)}
              </span>
            ))}
          </div>
          <p className="note" aria-live="polite">
            {paused ? t('recording.pausedNote') : t('recording.nowSpeaking', { lang: langName })}
          </p>
        </div>
        <div className="stack" style={{ gap: 16 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 className="section-title">{t('recording.voices')}</h2>
            <span className="t-data-sm c-secondary">{t('recording.ofTotal', { n: heard.length, total: people.length })}</span>
          </div>
          <ul className="voices">
            {heard.map((p) => (
              <li key={p.id} className="voice">
                <span className="voice__dot" style={{ background: colours[p.id] ?? 'var(--sm-ink-tertiary)' }} aria-hidden />
                <span className="who__text">
                  <span className="who__name">{p.name}</span>
                  <span className="who__sub">{p.role}</span>
                </span>
                <span className="voice__status">
                  {current === p.id && <span className="t-body-sm">{t('recording.speaking')}</span>}
                  <span className="t-data-sm c-secondary">{minutes(talk[p.id])}</span>
                  <CheckIcon size={16} aria-hidden />
                </span>
              </li>
            ))}
            {talk[UNMATCHED] && (
              <li className="voice">
                <span className="voice__dot" style={{ background: colours[UNMATCHED] }} aria-hidden />
                <span className="who__text">
                  <span className="who__name">{t('recording.speakerN', { n: Object.keys(colours).indexOf(UNMATCHED) + 1 })}</span>
                  <span className="who__sub">{t('recording.unmatched')}</span>
                </span>
                <span className="voice__status">
                  {current === UNMATCHED && <span className="t-body-sm">{t('recording.speaking')}</span>}
                  <span className="t-data-sm c-secondary">{minutes(talk[UNMATCHED])}</span>
                </span>
              </li>
            )}
            {notHeard.map((p) => (
              <li key={p.id} className="voice voice--silent">
                <span className="voice__dot voice__dot--empty" aria-hidden />
                <span className="who__text">
                  <span className="who__name">{p.name}</span>
                  <span className="who__sub">{p.role}</span>
                </span>
                <span className="voice__status t-body-sm c-tertiary">{t('recording.notHeard')}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
