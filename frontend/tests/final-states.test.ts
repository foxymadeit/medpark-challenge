import { describe, expect, it } from "vitest";
import {
  clearSpeechSeconds,
  DEMO_SIMILARITY_PERCENT,
  ENROLLMENT_TARGET_SECONDS,
  MINIMUM_CLEAR_SPEECH_SECONDS,
  resultState,
} from "../src/pages/enrollment";
import { RECORDING_CHECKPOINT_SECONDS } from "../src/hooks/useRecorder";
import { createRttm, createTranscriptText } from "../src/api/exports";
import { createMinutesPdf } from "../src/api/pdf";
import { getMeeting, getRecording, updateMeeting } from "../src/api/meetings";
import { readStore } from "../src/mock/store";

describe("final enrollment state machine", () => {
  it("uses a 30 second target and a deterministic 20 second minimum", () => {
    expect(ENROLLMENT_TARGET_SECONDS).toBe(30);
    expect(MINIMUM_CLEAR_SPEECH_SECONDS).toBe(20);
    expect(clearSpeechSeconds(30.9)).toBe(30);
    expect(resultState(6, false)).toBe("not_enough_speech");
    expect(resultState(20, false)).toBe("checking");
  });

  it("uses the deterministic demo similarity warning above the 70% threshold", () => {
    expect(DEMO_SIMILARITY_PERCENT).toBe(78);
    expect(resultState(25, true)).toBe("similar_voice");
  });

  it("aligns local recording checkpoints to ten seconds", () => {
    expect(RECORDING_CHECKPOINT_SECONDS).toBe(10);
  });
});

describe("sent meeting exports", () => {
  it("creates real PDF, transcript TXT and valid basic RTTM content", () => {
    const meeting = readStore().meetings[0];
    const pdf = createMinutesPdf(meeting);
    const transcript = createTranscriptText(meeting);
    const rttm = createRttm({
      ...meeting,
      speakerTimeline: [
        { speakerId: "ana", startSeconds: 1.25, endSeconds: 4.75 },
      ],
    });
    expect(pdf.type).toBe("application/pdf");
    expect(pdf.size).toBeGreaterThan(100);
    expect(transcript).toContain("Dr. Ana Popescu");
    expect(rttm).toMatch(
      /^SPEAKER .* 1 1\.250 3\.500 <NA> <NA> ana <NA> <NA>$/,
    );
  });

  it("only reports a recording as available when local audio exists", async () => {
    expect(await getRecording("meeting-without-audio")).toBeUndefined();
  });
});

describe("failed delivery retry", () => {
  it("retries at 30 seconds and remains idempotent after success", async () => {
    const failedAt = new Date(Date.now());
    await updateMeeting("meeting-001", {
      status: "ready",
      deliveryState: "failed",
      deliveryFailedAt: failedAt.toISOString(),
    });
    expect((await getMeeting("meeting-001")).deliveryState).toBe("failed");
    const before = readStore();
    const { advanceStore } = await import("../src/mock/store");
    expect(advanceStore(before, failedAt.getTime() + 29_999)).toBe(false);
    expect(before.meetings[0].deliveryState).toBe("failed");
    expect(advanceStore(before, failedAt.getTime() + 30_000)).toBe(true);
    expect(before.meetings[0].deliveryState).toBe("sending");
    expect(advanceStore(before, failedAt.getTime() + 30_001)).toBe(false);
  });
});
