import { useCallback, useEffect, useRef, useState } from "react";
import { MAX_AUDIO_SECONDS } from "../api/audio";
export function useRecorder(
  onInterrupted?: (blob: Blob, seconds: number) => void,
  onCheckpoint?: (blob: Blob, seconds: number) => void,
) {
  const [state, setState] = useState<
    "idle" | "requesting" | "recording" | "paused" | "stopped"
  >("idle");
  const [seconds, setSeconds] = useState(0);
  const [levels, setLevels] = useState<number[]>(Array(48).fill(3));
  const [error, setError] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const raf = useRef(0);
  const elapsed = useRef(0);
  const since = useRef(0);
  const chunks = useRef<Blob[]>([]);
  const generation = useRef(0);
  const alive = useRef(true);
  const interrupted = useRef(onInterrupted);
  const checkpoint = useRef(onCheckpoint);
  useEffect(() => {
    interrupted.current = onInterrupted;
    checkpoint.current = onCheckpoint;
  }, [onInterrupted, onCheckpoint]);
  const secondsNow = useCallback(
    () =>
      elapsed.current +
      (recorder.current?.state === "recording"
        ? (performance.now() - since.current) / 1000
        : 0),
    [],
  );
  const clean = useCallback(() => {
    cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    void context.current?.close().catch(() => {});
    context.current = null;
  }, []);
  const stop = useCallback(async (): Promise<{
    blob: Blob;
    seconds: number;
  }> => {
    const r = recorder.current;
    if (!r || r.state === "inactive") throw new Error("noAudio");
    const duration = secondsNow();
    elapsed.current = duration;
    return new Promise((resolve, reject) => {
      r.onstop = () => {
        const blob = new Blob(chunks.current, {
          type: r.mimeType || "audio/webm",
        });
        clean();
        if (alive.current) {
          setState("stopped");
          setSeconds(duration);
        }
        if (blob.size) resolve({ blob, seconds: duration });
        else reject(new Error("invalidAudio"));
      };
      r.stop();
    });
  }, [clean, secondsNow]);
  const start = useCallback(async () => {
    if (recorder.current && recorder.current.state !== "inactive") return;
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError("unsupported");
      return;
    }
    const token = ++generation.current;
    setState("requesting");
    setError("");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current || token !== generation.current) {
        media.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = media;
      chunks.current = [];
      elapsed.current = 0;
      since.current = performance.now();
      setSeconds(0);
      const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
        (m) => MediaRecorder.isTypeSupported(m),
      );
      const r = new MediaRecorder(media, mime ? { mimeType: mime } : undefined);
      recorder.current = r;
      r.ondataavailable = (e) => {
        if (e.data.size) chunks.current.push(e.data);
        if (r.state === "recording" && chunks.current.length % 5 === 0) {
          checkpoint.current?.(
            new Blob(chunks.current, { type: r.mimeType }),
            secondsNow(),
          );
        }
      };
      r.onerror = () => {
        if (alive.current) setError("microphone");
        clean();
      };
      r.start(1000);
      setState("recording");
      const ctx = new AudioContext();
      context.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 128;
      ctx.createMediaStreamSource(media).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      let last = 0;
      const draw = (time: number) => {
        if (!alive.current) return;
        if (time - last > 100) {
          last = time;
          analyser.getByteFrequencyData(data);
          setLevels(
            Array.from(data.slice(0, 48), (v) =>
              r.state === "paused" ? 3 : Math.max(3, (v / 255) * 64),
            ),
          );
          setSeconds(secondsNow());
          if (secondsNow() >= MAX_AUDIO_SECONDS && r.state === "recording") {
            r.pause();
            elapsed.current = MAX_AUDIO_SECONDS;
            setState("paused");
            setError("recordLimit");
          }
        }
        raf.current = requestAnimationFrame(draw);
      };
      raf.current = requestAnimationFrame(draw);
    } catch {
      clean();
      if (alive.current && token === generation.current) {
        setError("microphone");
        setState("idle");
      }
    }
  }, [clean, secondsNow]);
  const pause = () => {
    const r = recorder.current;
    if (r?.state === "recording") {
      elapsed.current = secondsNow();
      r.pause();
      setState("paused");
    }
  };
  const resume = () => {
    const r = recorder.current;
    if (r?.state === "paused" && elapsed.current < MAX_AUDIO_SECONDS) {
      since.current = performance.now();
      r.resume();
      setState("recording");
    }
  };
  // Cleanup intentionally reads the active recorder, not a DOM ref.
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      // This is a lifecycle generation counter, not a rendered element ref.
      // oxlint-disable-next-line react-hooks/exhaustive-deps
      generation.current++;
      const r = recorder.current;
      if (r && r.state !== "inactive") {
        const duration = secondsNow();
        r.onstop = () => {
          const blob = new Blob(chunks.current, { type: r.mimeType });
          if (blob.size) interrupted.current?.(blob, duration);
        };
        r.stop();
      }
      clean();
    };
  }, [clean, secondsNow]);
  return { state, seconds, levels, error, start, stop, pause, resume };
}
