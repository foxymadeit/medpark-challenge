import { describe, expect, it } from "vitest";
import { displayStages, expectedFinish } from "../src/api/stages";
import type { Meeting } from "../src/types/meeting";

const T0 = Date.parse("2026-09-26T12:00:00Z");
const base = {
  id: "m",
  title: "t",
  type: "medical",
  status: "processing",
  createdAt: "2026-09-26T11:00:00Z",
  inputMode: "upload",
  participants: [],
  distributionList: [],
  sendMode: "auto",
  durationSeconds: 3600,
  processingStartedAt: new Date(T0).toISOString(),
} as Meeting;

describe("processing stages and ETA", () => {
  it("estimates about 15 minutes per hour of audio when the server gives no ETA", () => {
    expect((expectedFinish(base, T0) - T0) / 60000).toBeCloseTo(16, 0);
  });

  it("expands the server's minutes stage into the four M01 steps", () => {
    const m = {
      ...base,
      processingEndsAt: new Date(T0 + 20 * 60000).toISOString(),
      stages: [
        { id: "transcribe", state: "done" },
        { id: "speakers", state: "done" },
        {
          id: "minutes",
          state: "running",
          startedAt: new Date(T0 + 10 * 60000).toISOString(),
        },
      ],
    } as Meeting;
    // 47 % into the minutes stage: finding facts done, checking now.
    const s = displayStages(m, T0 + 14.7 * 60000);
    expect(s.map((x) => x.id)).toEqual([
      "transcribe",
      "speakers",
      "extract",
      "verify",
      "write",
      "render",
    ]);
    expect(s.map((x) => x.state)).toEqual([
      "done",
      "done",
      "done",
      "running",
      "pending",
      "pending",
    ]);
    expect(Date.parse(s[5].etaAt!)).toBe(T0 + 20 * 60000);
  });

  it("never marks the last step done before the server does", () => {
    const m = {
      ...base,
      processingEndsAt: new Date(T0 + 60000).toISOString(),
      stages: [
        { id: "transcribe", state: "done" },
        { id: "speakers", state: "done" },
        { id: "minutes", state: "running" },
      ],
    } as Meeting;
    const s = displayStages(m, T0 + 10 * 60000);
    expect(s.at(-1)!.state).toBe("running");
  });
});
