import { describe, expect, it } from "vitest";
import { createMinutesPdf } from "../src/api/pdf";
import { seedMeetings } from "../src/mock/seed";

describe("minutes PDF export", () => {
  it("creates a real local PDF document", async () => {
    const pdf = createMinutesPdf(seedMeetings()[0]);
    expect(pdf.type).toBe("application/pdf");
    expect(pdf.size).toBeGreaterThan(500);
    expect(await pdf.text()).toMatch(/^%PDF-1\.4/);
  });
});
