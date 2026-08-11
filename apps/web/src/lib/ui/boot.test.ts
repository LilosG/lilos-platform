import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applyBootResult,
  setActiveOrganization,
  type BootRegions,
  type BootResult,
} from "./boot";

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

describe("setActiveOrganization", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the visible switcher synchronized with the governed active organization", () => {
    const switcher = { value: "lilos-growth-id" } as HTMLSelectElement;
    const name = { textContent: "" } as HTMLElement;
    const stored = new Map<string, string>();
    let replacedUrl = "";

    vi.stubGlobal("localStorage", {
      setItem: (key: string, value: string) => stored.set(key, value),
    });
    vi.stubGlobal("window", {
      location: {
        href: "https://app.lilos.invalid/settings?org=wheyland-id",
      },
      history: {
        replaceState: (_state: object, _unused: string, url: string) => {
          replacedUrl = url;
        },
      },
    });
    vi.stubGlobal("document", {
      getElementById: (id: string) => {
        if (id === "organization-switcher") return switcher;
        if (id === "active-organization-name") return name;
        return null;
      },
    });

    setActiveOrganization({
      organization_id: "wheyland-id",
      organization_name: "Wheyland Electric",
      organization_slug: "wheyland-electric",
      organization_status: "active",
      membership_id: "membership-id",
      membership_status: "active",
      membership_type: "owner",
    });

    expect(switcher.value).toBe("wheyland-id");
    expect(name.textContent).toBe("Wheyland Electric");
    expect(stored.get("selected_org_id")).toBe("wheyland-id");
    expect(replacedUrl).toBe("");
  });
});
