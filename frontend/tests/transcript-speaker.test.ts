import { describe, expect, it } from "vitest";
import { speaks } from "../src/utils";

describe("transcript speakers", () => {
  it("finds the participant by the diarizer's label, as the server stores it", () => {
    const people = [
      { id: "m1-voice-1", speakerId: "Speaker 1" },
      { id: "m1-voice-4", speakerId: "Speaker 4" },
    ];
    expect(people.find((p) => speaks(p, "Speaker 4"))?.id).toBe("m1-voice-4");
  });

  it("still finds demo participants by their own id, and nobody for an empty label", () => {
    expect(speaks({ id: "p2" }, "p2")).toBe(true);
    expect(speaks({ id: "p2", speakerId: "" }, "")).toBe(false);
  });
});
