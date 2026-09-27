import { describe, expect, it } from "vitest";
import { initialVoices, stepVoices, type VoiceState } from "../src/hooks/useVoiceColours";

// Two synthetic voices with different spectrum shapes, and silence.
const low = Array.from({ length: 48 }, (_, i) => (i < 16 ? 50 : 8));
const high = Array.from({ length: 48 }, (_, i) => (i > 30 ? 50 : 8));
const quiet = Array(48).fill(3);

function run(s: VoiceState, frames: number[], times: number) {
  for (let i = 0; i < times; i++) s = stepVoices(s, frames, 100);
  return s;
}

describe("voice colours on the recording waveform", () => {
  it("gives Alex a colour, Charlie another, and Alex his colour back", () => {
    let s = run(initialVoices(), low, 12); // Alex speaks
    const alex = s.voice;
    s = run(s, quiet, 8); // pause
    s = run(s, high, 12); // Charlie speaks
    const charlie = s.voice;
    s = run(s, quiet, 8);
    s = run(s, low, 12); // Alex again
    expect(alex).toBe(0);
    expect(charlie).toBe(1);
    expect(s.voice).toBe(alex);
    expect(s.voices).toHaveLength(2);
  });

  it("keeps the colour through a short breath and during continuous speech", () => {
    let s = run(initialVoices(), low, 12);
    s = run(s, quiet, 3); // 0.3 s breath, not a new turn
    s = run(s, high, 12);
    expect(s.voice).toBe(0);
  });
});
