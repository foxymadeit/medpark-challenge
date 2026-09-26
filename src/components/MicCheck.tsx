import { CheckIcon, PlayIcon, StopIcon, WarningIcon, WaveformIcon } from '@phosphor-icons/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { useStore } from '../store/AppStore';
import { Dropdown, type DropdownOption } from './Dropdown';

/** MOCK: shown until the browser reveals real device names (it only does after mic permission). */
const MOCK_MICS: DropdownOption[] = [
  { value: 'mock-external', label: 'External microphone (USB)' },
  { value: 'mock-builtin', label: 'Built-in microphone' },
  { value: 'mock-headset', label: 'Bluetooth headset' },
];

const TEST_MS = 4000;
const METER_BARS = 12;

type Phase = 'idle' | 'listening' | 'playing' | 'done';

/**
 * Microphone choice + a quick check before recording:
 * 4 s with a live level meter, then the clip plays back so you hear yourself.
 * If the mic is blocked, the meter is simulated and playback is skipped (demo keeps working).
 */
export function MicCheck() {
  const { t } = useI18n();
  const { preferences, updatePreferences } = useStore();
  const [mics, setMics] = useState<DropdownOption[]>(MOCK_MICS);
  const [phase, setPhase] = useState<Phase>('idle');
  const [level, setLevel] = useState(0);
  const [blocked, setBlocked] = useState(false);
  const micId = mics.some((m) => m.value === preferences.micId) ? preferences.micId! : mics[0].value;

  const stream = useRef<MediaStream | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const frame = useRef(0);
  const timer = useRef(0);
  const audio = useRef<HTMLAudioElement | null>(null);

  const loadMics = useCallback(async () => {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      const real = all.filter((d) => d.kind === 'audioinput' && d.label && d.deviceId !== 'default' && d.deviceId !== 'communications');
      if (real.length) setMics(real.map((d) => ({ value: d.deviceId, label: d.label })));
    } catch {
      /* keep the mock list */
    }
  }, []);

  useEffect(() => {
    void loadMics();
  }, [loadMics]);

  const cleanup = useCallback(() => {
    cancelAnimationFrame(frame.current);
    clearTimeout(timer.current);
    stream.current?.getTracks().forEach((tr) => tr.stop());
    void ctx.current?.close().catch(() => {});
    audio.current?.pause();
    stream.current = null;
    ctx.current = null;
    audio.current = null;
    setLevel(0);
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const stop = () => {
    cleanup();
    setPhase('idle');
  };

  const start = async () => {
    cleanup();
    setPhase('listening');
    setBlocked(false);
    try {
      const real = !micId.startsWith('mock-');
      const s = await navigator.mediaDevices.getUserMedia({ audio: real ? { deviceId: { exact: micId } } : true });
      stream.current = s;
      void loadMics(); // names become available now
      const audioCtx = new AudioContext();
      const node = audioCtx.createAnalyser();
      node.fftSize = 1024;
      audioCtx.createMediaStreamSource(s).connect(node);
      ctx.current = audioCtx;
      const buf = new Uint8Array(new ArrayBuffer(node.fftSize));
      const tick = () => {
        node.getByteTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += ((v - 128) / 128) ** 2;
        setLevel(Math.min(1, Math.sqrt(sum / buf.length) * 4));
        frame.current = requestAnimationFrame(tick);
      };
      tick();
      const chunks: Blob[] = [];
      const rec = new MediaRecorder(s);
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = () => {
        cancelAnimationFrame(frame.current);
        s.getTracks().forEach((tr) => tr.stop());
        setLevel(0);
        const clip = new Audio(URL.createObjectURL(new Blob(chunks, { type: rec.mimeType })));
        audio.current = clip;
        clip.onended = () => setPhase('done');
        setPhase('playing');
        clip.play().catch(() => setPhase('done'));
      };
      rec.start();
      timer.current = window.setTimeout(() => rec.state !== 'inactive' && rec.stop(), TEST_MS);
    } catch {
      // Blocked or no device: simulate a voice on the meter so the check still reads.
      setBlocked(true);
      let sim = 0.3;
      const tick = () => {
        sim = Math.min(1, Math.max(0.1, sim + (Math.random() - 0.5) * 0.25));
        setLevel(sim * (0.3 + 0.7 * Math.random()));
        frame.current = requestAnimationFrame(tick);
      };
      tick();
      timer.current = window.setTimeout(() => {
        cancelAnimationFrame(frame.current);
        setLevel(0);
        setPhase('done');
      }, TEST_MS);
    }
  };

  const busy = phase === 'listening' || phase === 'playing';
  const lit = Math.round(level * METER_BARS);

  return (
    <div className="mic-check">
      <div className="mic-check__row">
        <Dropdown
          label={t('mic.choose')}
          value={micId}
          options={mics}
          disabled={busy}
          onChange={(v) => {
            updatePreferences({ micId: v });
            setPhase('idle');
          }}
        />
        <button type="button" className="btn btn--secondary mic-check__test" onClick={busy ? stop : start}>
          {busy ? <StopIcon size={16} aria-hidden /> : <WaveformIcon size={16} aria-hidden />}
          {busy ? t('mic.stopTest') : t('mic.test')}
        </button>
      </div>
      {phase !== 'idle' && (
        <div className="mic-check__status" role="status" aria-live="polite">
          {phase === 'listening' && (
            <>
              <span className="mic-meter" aria-hidden>
                {Array.from({ length: METER_BARS }, (_, i) => (
                  <span key={i} className={`mic-meter__bar${i < lit ? ' is-on' : ''}`} />
                ))}
              </span>
              <span>{t('mic.listening')}</span>
            </>
          )}
          {phase === 'playing' && (
            <>
              <PlayIcon size={14} aria-hidden />
              <span>{t('mic.playing')}</span>
            </>
          )}
          {phase === 'done' && (
            <>
              {blocked ? <WarningIcon size={14} aria-hidden /> : <CheckIcon size={14} aria-hidden className="mic-check__ok" />}
              <span>{blocked ? t('mic.blocked') : t('mic.done')}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
