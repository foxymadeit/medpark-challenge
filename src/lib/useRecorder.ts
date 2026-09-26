import { useCallback, useEffect, useRef, useState } from 'react';

export type RecorderState = 'idle' | 'recording' | 'paused' | 'stopped';

/**
 * Real microphone capture via MediaRecorder + Web Audio AnalyserNode.
 * If the mic is unavailable/blocked, `micError` is set and `getLevel()` falls
 * back to a simulated signal so the demo keeps working.
 */
export function useRecorder() {
  const [state, setState] = useState<RecorderState>('idle');
  const [micError, setMicError] = useState(false);
  const [elapsed, setElapsed] = useState(0); // seconds, only counts while recording

  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const ctx = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const buf = useRef<Uint8Array<ArrayBuffer> | null>(null);
  const sim = useRef(0.2);

  /** `deviceId` = the mic picked on New meeting; mock ids fall back to the default mic. */
  const start = useCallback(async (deviceId?: string) => {
    setState('recording');
    try {
      const device = deviceId && !deviceId.startsWith('mock-') ? { deviceId: { exact: deviceId } } : {};
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, ...device } });
      stream.current = s;
      const audioCtx = new AudioContext();
      const node = audioCtx.createAnalyser();
      node.fftSize = 1024;
      audioCtx.createMediaStreamSource(s).connect(node);
      ctx.current = audioCtx;
      analyser.current = node;
      buf.current = new Uint8Array(new ArrayBuffer(node.fftSize));
      const rec = new MediaRecorder(s);
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      rec.start(1000);
      recorder.current = rec;
    } catch {
      setMicError(true);
    }
  }, []);

  const pause = useCallback(() => {
    if (recorder.current?.state === 'recording') recorder.current.pause();
    void ctx.current?.suspend();
    setState('paused');
  }, []);

  const resume = useCallback(() => {
    if (recorder.current?.state === 'paused') recorder.current.resume();
    void ctx.current?.resume();
    setState('recording');
  }, []);

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop());
    void ctx.current?.close().catch(() => {});
    stream.current = null;
    ctx.current = null;
    analyser.current = null;
  }, []);

  /** Stops and returns the recorded audio (null when the mic was unavailable). */
  const stop = useCallback((): Promise<Blob | null> => {
    setState('stopped');
    const rec = recorder.current;
    if (!rec || rec.state === 'inactive') {
      release();
      return Promise.resolve(null);
    }
    return new Promise((resolve) => {
      rec.onstop = () => {
        release();
        resolve(new Blob(chunks.current, { type: rec.mimeType }));
      };
      rec.stop();
    });
  }, [release]);

  /** 0..1 loudness (RMS) of the current audio frame. */
  const getLevel = useCallback((): number => {
    const node = analyser.current;
    if (node && buf.current) {
      node.getByteTimeDomainData(buf.current);
      let sum = 0;
      for (const v of buf.current) sum += ((v - 128) / 128) ** 2;
      return Math.min(1, Math.sqrt(sum / buf.current.length) * 4);
    }
    // Simulated speech: a slow loudness envelope with jagged syllable peaks.
    sim.current = Math.min(1, Math.max(0.15, sim.current + (Math.random() - 0.5) * 0.3));
    return sim.current * (0.15 + 0.85 * Math.random() ** 2);
  }, []);

  // Elapsed timer.
  useEffect(() => {
    if (state !== 'recording') return;
    const started = performance.now() - elapsed * 1000;
    const id = setInterval(() => setElapsed((performance.now() - started) / 1000), 250);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  // Release the mic if the page unmounts mid-recording.
  useEffect(() => () => release(), [release]);

  return { state, micError, elapsed, start, pause, resume, stop, getLevel };
}
