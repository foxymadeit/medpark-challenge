import { describe, expect, it } from "vitest";
import { orderCandidates, type GlossaryCandidate } from "../src/api/meetings";

const c = (
  heard: string,
  count: number,
  approved = false,
): GlossaryCandidate => ({
  heard,
  corrected: `${heard}-fixed`,
  count,
  meetingIds: ["m1"],
  lang: "ro",
  approved,
});

describe("words people corrected", () => {
  it("puts the waiting ones first, most frequent first, without changing the list", () => {
    const list = [c("rare", 1), c("added", 9, true), c("often", 4)];
    expect(orderCandidates(list).map((x) => x.heard)).toEqual([
      "often",
      "rare",
      "added",
    ]);
    expect(list.map((x) => x.heard)).toEqual(["rare", "added", "often"]);
  });
});
