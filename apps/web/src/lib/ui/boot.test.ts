import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applyShellAudience,
  applyShellPrincipal,
  applyBootResult,
  setPlatformNavigationVisible,
  setActiveOrganization,
  type BootRegions,
  type BootResult,
} from "./boot";

describe("shell presentation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses a safe account label instead of exposing the auth identifier", () => {
    const label = element(false);
    const initial = element(false);
    const assurance = element(false);
    vi.stubGlobal("document", {
      getElementById: (id: string) =>
        id === "current-user-label"
          ? label
          : id === "current-user-initial"
            ? initial
            : id === "current-assurance-label"
              ? assurance
              : null,
    });
    applyShellPrincipal({
      platform_user_id: "profile-id",
      auth_user_id: "private-auth-id",
      user_status: "active",
      assurance_level: "aal1",
    });
    expect(label.textContent).toBe("Your account");
    expect(label.textContent).not.toContain("private-auth-id");
    expect(initial.textContent).toBe("L");
  });

  it("distinguishes agency and client workspaces without granting access", () => {
    const audience = element(false);
    const role = element(false);
    const admin = element(false);
    vi.stubGlobal("document", {
      getElementById: (id: string) =>
        id === "active-workspace-audience"
          ? audience
          : id === "current-workspace-role"
            ? role
            : null,
      querySelector: () => admin,
    });
    applyShellAudience("owner");
    expect(audience.textContent).toBe("Client workspace");
    applyShellAudience("internal");
    expect(role.textContent).toBe("Agency workspace");
    setPlatformNavigationVisible(false);
    expect(admin.hidden).toBe(true);
    setPlatformNavigationVisible(true);
    expect(admin.hidden).toBe(false);
  });
});

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
