import type { Meeting, ProcessingStage, StageId } from "../types/meeting";

// About 15 minutes of work per 60 minutes of audio on the reference server
// (the challenge target), plus a minute of fixed start-up.
const WORK_PER_AUDIO_SECOND = 0.25;
const STARTUP_S = 60;
// Share of the audio stages (recognition and speakers run side by side) in
// the whole job, from the backend's own per-stage factors.
const AUDIO_SHARE = 0.15 / 0.19;
// What happens inside the server's single "minutes" stage (Figma M01), with
// the share of its time each step takes: reading the model's two long passes
// dominate, checking and rendering are quick.
const MINUTES_STEPS: [StageId, number][] = [
  ["extract", 0.45],
  ["verify", 0.05],
  ["write", 0.45],
  ["render", 0.05],
];

const at = (iso: string | undefined, fallback: number) =>
  iso ? Date.parse(iso) : fallback;
const iso = (ms: number) => new Date(ms).toISOString();

/** When the minutes should be ready: the server's estimate, else one made
 * from the audio length. */
export function expectedFinish(m: Meeting, now = Date.now()): number {
  if (m.processingEndsAt) return Date.parse(m.processingEndsAt);
  const start = at(m.processingStartedAt, now);
  return (
    start +
    (STARTUP_S + (m.durationSeconds ?? 0) * WORK_PER_AUDIO_SECOND) * 1000
  );
}

/** The full M01 list (transcribe, speakers, then the four minutes steps)
 * from the server's three stages. Inside "minutes" the running step is
 * estimated from elapsed time; a step is only shown finished once time says
 * so, and the last one never before the server does. */
export function displayStages(m: Meeting, now = Date.now()): ProcessingStage[] {
  const raw = m.stages ?? [];
  const minutes = raw.find((s) => s.id === "minutes");
  if (!minutes) return raw;
  const start = at(m.processingStartedAt, now);
  const end = Math.max(expectedFinish(m, now), start + 1000);
  const audioEnd = start + (end - start) * AUDIO_SHARE;
  const audio = raw
    .filter((s) => s.id !== "minutes")
    .map((s) =>
      s.state === "done" || s.state === "failed"
        ? s
        : { ...s, etaAt: iso(audioEnd) },
    );
  const mStart = at(minutes.startedAt, audioEnd);
  const span = Math.max(end - mStart, 1000);
  const frac = (now - mStart) / span;
  let cum = 0;
  let current = MINUTES_STEPS.length - 1;
  const bounds = MINUTES_STEPS.map(([, share]) => (cum += share));
  if (minutes.state === "running")
    current = Math.min(
      bounds.findIndex((b) => b > frac),
      MINUTES_STEPS.length - 1,
    );
  if (current < 0) current = MINUTES_STEPS.length - 1;
  const steps = MINUTES_STEPS.map(([id], i): ProcessingStage => {
    const etaAt = iso(mStart + span * bounds[i]);
    if (minutes.state === "done")
      return { id, state: "done", finishedAt: minutes.finishedAt };
    if (minutes.state === "pending") return { id, state: "pending", etaAt };
    if (i < current) return { id, state: "done" };
    if (i === current)
      return { id, state: minutes.state === "failed" ? "failed" : "running" };
    return { id, state: "pending", etaAt };
  });
  return [...audio, ...steps];
}
