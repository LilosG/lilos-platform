import { describe, expect, it } from "vitest";

import { sentimentLabel, statusLabel, statusTone } from "./status-language";

describe("client-facing status language", () => {
  it.each([
    ["pending_verification", "Pending verification"],
    ["never_synced", "Not yet synced"],
    ["setup_required", "Needs attention"],
  ])("maps %s to the shared client label", (status, expected) => {
    expect(statusLabel(status)).toBe(expected);
    expect(statusLabel(status)).not.toContain("_");
  });

  it("normalizes unmapped contract values without exposing separators", () => {
    expect(statusLabel("ownership_pending")).toBe("Ownership Pending");
  });

  it("describes absent review classification honestly", () => {
    expect(sentimentLabel("unknown")).toBe("Not classified");
    expect(sentimentLabel(null)).toBe("Not classified");
  });

  it("uses the shared attention tone for setup and unsynced states", () => {
    expect(statusTone("setup_required")).toBe("missing");
    expect(statusTone("never_synced")).toBe("missing");
  });
});
