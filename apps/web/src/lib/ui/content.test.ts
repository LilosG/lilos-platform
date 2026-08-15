import { describe, expect, it } from "vitest";
import { actionLabel, emptyStateContent, errorContent } from "./content";

describe("content standards", () => {
  it("keeps action language stable through completion", () => {
    expect(actionLabel("publish")).toBe("Publish");
    expect(actionLabel("publish", "working")).toBe("Publishing…");
    expect(actionLabel("publish", "complete")).toBe("Published");
  });

  it("requires a complete single-action empty state", () => {
    expect(
      emptyStateContent({
        heading: "No reviews yet",
        situation: "Google has not returned a review for this location.",
        action: { label: "Check connection", href: "/integrations" },
      }),
    ).toEqual({
      heading: "No reviews yet",
      situation: "Google has not returned a review for this location.",
      action: { label: "Check connection", href: "/integrations" },
    });
  });

  it("requires errors to explain recovery", () => {
    expect(
      errorContent({
        operation: "publish content",
        happened: "GitHub rejected the publishing request.",
        recovery: "Reconnect GitHub, then retry publishing.",
        recoveryLabel: "Manage integration",
        recoveryHref: "/integrations",
      }),
    ).toEqual({
      title: "Could not publish content",
      description: "GitHub rejected the publishing request. Reconnect GitHub, then retry publishing.",
      recovery: { label: "Manage integration", href: "/integrations" },
    });
  });
});

