import { describe, expect, it } from "vitest";
import { applyBootResult, type BootRegions, type BootResult } from "./boot";

function element(hidden: boolean): HTMLElement {
  return { hidden, textContent: "" } as HTMLElement;
}

function regions(): BootRegions {
  return {
    notConfigured: element(true),
    loading: element(false),
    error: element(true),
    empty: element(true),
    content: element(true),
  };
}

describe("applyBootResult", () => {
  it("reveals authenticated content and clears the loading state", () => {
    const bootRegions = regions();
    const result: BootResult = {
      kind: "ok",
      context: {
        organizationId: "organization-id",
        organizationName: "Wheyland Electric",
        organizationStatus: "active",
        membershipType: "owner",
      },
      organizations: [],
    };

    expect(applyBootResult(bootRegions, result)).toBe(true);
    expect(bootRegions.content.hidden).toBe(false);
    expect(bootRegions.loading.hidden).toBe(true);
    expect(bootRegions.notConfigured.hidden).toBe(true);
    expect(bootRegions.error.hidden).toBe(true);
    expect(bootRegions.empty.hidden).toBe(true);
  });

  it("keeps authenticated content hidden when boot fails", () => {
    const bootRegions = regions();

    expect(
      applyBootResult(bootRegions, {
        kind: "error",
        message: "Workspace failed to load.",
      }),
    ).toBe(false);
    expect(bootRegions.content.hidden).toBe(true);
    expect(bootRegions.loading.hidden).toBe(true);
    expect(bootRegions.error.hidden).toBe(false);
    expect(bootRegions.error.textContent).toBe("Workspace failed to load.");
  });
});
