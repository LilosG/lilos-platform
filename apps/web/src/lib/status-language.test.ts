import { describe, expect, it } from "vitest";

import {
  sentimentLabel,
  statusLabel,
  statusTone,
  websiteStatusPresentation,
} from "./status-language";

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

describe("website status presentation", () => {
  it("states the capability that is true for a newly provisioned website", () => {
    // Every website starts pending_verification and the crawler never reads
    // the field. A lone amber "Pending verification" chip read as a fault and
    // sent operators hunting for a step that does not exist.
    const presentation = websiteStatusPresentation("pending_verification");
    expect(presentation.label).toBe("Ready to crawl");
    expect(presentation.tone).toBe("ready");
    expect(presentation.note).toContain("Crawling works now");
    // It must say the outstanding evidence resolves itself.
    expect(presentation.note).toContain("no");
    expect(presentation.note).toContain("verification step");
  });

  it("does not dress up a paused website as ready", () => {
    const presentation = websiteStatusPresentation("paused");
    expect(presentation.tone).toBe("setup");
    expect(presentation.label).toBe("Needs attention");
    expect(presentation.note).toContain("will not run");
  });

  it("distinguishes a verified website from an unverified one", () => {
    expect(websiteStatusPresentation("active").label).toBe("Ready");
    expect(websiteStatusPresentation("active").note).toContain("confirmed");
    expect(websiteStatusPresentation("pending_verification").label).not.toBe(
      websiteStatusPresentation("active").label,
    );
  });

  it("keeps archived out of the ready tone", () => {
    expect(websiteStatusPresentation("archived").tone).toBe("neutral");
  });

  it("falls back to the shared label and tone for anything unmodelled", () => {
    const presentation = websiteStatusPresentation("some_new_status");
    expect(presentation.label).toBe("Some New Status");
    expect(presentation.tone).toBe("setup");
  });
});
