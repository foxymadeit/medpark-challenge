import { describe, expect, it } from "vitest";
import { auditAction } from "../src/api/meetings";

describe("audit trail wording", () => {
  it("says in plain words what each entry was", () => {
    expect(
      auditAction({ method: "POST", route: "/api/meetings/{meeting_id}/send" }),
    ).toBe("audit_send");
    expect(
      auditAction({
        method: "GET",
        route: "/api/meetings/{meeting_id}/recording",
      }),
    ).toBe("audit_listen");
    expect(
      auditAction({
        method: "POST",
        route: "/api/meetings/{meeting_id}/recording",
      }),
    ).toBe("audit_recording");
    expect(
      auditAction({
        method: "GET",
        route: "/api/meetings/{meeting_id}/documents/{name}",
      }),
    ).toBe("audit_document");
    expect(
      auditAction({
        method: "POST",
        route: "/api/meetings/{meeting_id}/stop-send",
      }),
    ).toBe("audit_stop");
    expect(auditAction({ method: "PATCH", route: "/api/whatever" })).toBe(
      "audit_other",
    );
  });
});
