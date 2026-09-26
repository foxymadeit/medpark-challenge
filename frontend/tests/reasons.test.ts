import { describe, expect, it } from "vitest";
import i18n from "../src/i18n/i18n";
import { explainProblems } from "../src/api/reasons";

describe("reasons for items that need a person", () => {
  it("turns the checks' messages into sentences in the reader's language", async () => {
    await i18n.changeLanguage("ro");
    expect(
      explainProblems(
        [
          "action without an owner",
          "deadline 'early next week' was not said in the cited lines: removed",
        ],
        i18n.t,
      ),
    ).toBe(
      "În ședință nu a fost numit un responsabil. Termenul nu a fost clar.",
    );
    await i18n.changeLanguage("en");
    expect(explainProblems(["number 45 is not in the evidence"], i18n.t)).toBe(
      "A number is not in the transcript.",
    );
  });

  it("shows an unknown message as the server wrote it", () => {
    expect(explainProblems(["something new"], i18n.t)).toBe("something new");
  });
});
