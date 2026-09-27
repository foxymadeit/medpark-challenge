import { useEffect, useState } from "react";

/** Live colours for the recording waveform: each voice gets a colour, and the same
 * voice gets its colour back when it speaks again. The browser has no speaker model,
 * so a voice is recognised by the average shape of its spectrum over the first second
 * after a pause. It is a hint for the person recording; the speakers in the minutes
 * come from the diarizer on the server after the recording. */

export const SPEECH_LEVEL = 12; // mean bar height (3 to 64) above which someone is speaking
export const PAUSE_MS = 700; // silence that ends a turn
export const LISTEN_MS = 1000; // speech collected before a new turn is matched to a voice
export const SAME_VOICE = 0.92; // correlation of spectrum shapes that counts as the same voice

export type VoiceState = {
  voice: number; // index of the colour on screen; -1 before anyone spoke
  voices: number[][]; // one average spectrum shape per voice heard so far
  silentMs: number;
  speaking: boolean;
  listening: number[][]; // spectra of the current turn until it is matched
};

export const initialVoices = (): VoiceState => ({
  voice: -1,
  voices: [],
  silentMs: PAUSE_MS,
  speaking: false,
  listening: [],
});

function shape(spectra: number[][]): number[] {
  const n = spectra[0]?.length ?? 0;
  const mean = Array.from({ length: n }, (_, i) => spectra.reduce((a, s) => a + s[i], 0) / spectra.length);
  const avg = mean.reduce((a, b) => a + b, 0) / Math.max(1, n);
  const centred = mean.map((v) => v - avg);
  const norm = Math.hypot(...centred) || 1;
  return centred.map((v) => v / norm);
}

const correlation = (a: number[], b: number[]) => a.reduce((sum, v, i) => sum + v * (b[i] ?? 0), 0);

export function stepVoices(s: VoiceState, levels: number[], dtMs: number): VoiceState {
  const loud = levels.reduce((a, b) => a + b, 0) / Math.max(1, levels.length) >= SPEECH_LEVEL;
  if (!loud) return { ...s, silentMs: s.silentMs + dtMs, speaking: false };
  const newTurn = !s.speaking && s.silentMs >= PAUSE_MS;
  const listening = newTurn ? [levels] : s.listening.length ? [...s.listening, levels] : [];
  if (!listening.length || listening.length * dtMs < LISTEN_MS)
    return { ...s, silentMs: 0, speaking: true, listening };
  // a second of the new turn: whose voice is it?
  const heard = shape(listening);
  let best = -1;
  let bestScore = SAME_VOICE;
  s.voices.forEach((v, i) => {
    const score = correlation(heard, v);
    if (score >= bestScore) [best, bestScore] = [i, score];
  });
  if (best < 0) return { voice: s.voices.length, voices: [...s.voices, heard], silentMs: 0, speaking: true, listening: [] };
  return { ...s, voice: best, silentMs: 0, speaking: true, listening: [] };
}

/** The voice index for the waveform colour, updated on every level frame (100 ms). */
export function useVoiceColours(levels: number[], recording: boolean): number {
  const [state, setState] = useState<VoiceState>(initialVoices);
  useEffect(() => {
    if (!recording) return;
    // The recorder's level frames are an external source; each one advances the voice tracker.
    // oxlint-disable-next-line react/set-state-in-effect
    setState((s) => stepVoices(s, levels, 100));
  }, [levels, recording]);
  return state.voice;
}
