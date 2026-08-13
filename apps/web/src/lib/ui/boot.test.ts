import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applyShellAudience,
  applyShellPrincipal,
  applyBootResult,
  canUsePlatformAdministration,
  hasPlatformAdminGrant,
  isPlatformAdmin,
  meetsPlatformAdminRequiredAssurance,
  setPlatformNavigationVisible,
  setPlatformAdminStatus,
  setProductNavigationVisibility,
  setActiveOrganization,
  type BootRegions,
  type BootResult,
  type PlatformAdminCapability,
} from "./boot";

const NO_ADMIN: PlatformAdminCapability = {
  is_platform_administrator: false,
  meets_required_assurance: false,
};
const GRANT_NO_ASSURANCE: PlatformAdminCapability = {
  is_platform_administrator: true,
  meets_required_assurance: false,
};
const FULL_ADMIN: PlatformAdminCapability = {
  is_platform_administrator: true,
  meets_required_assurance: true,
};

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
    // Membership type alone does not grant Admin navigation — only an
    // active platform-administrator grant does.
    setPlatformNavigationVisible(false);
    expect(admin.hidden).toBe(true);
    setPlatformNavigationVisible(true);
    expect(admin.hidden).toBe(false);
  });

  it("does not escalate admin navigation from membership type alone", () => {
    const admin = element(false);
    vi.stubGlobal("document", {
      getElementById: () => null,
      querySelector: () => admin,
    });
    // Start with no platform-admin grant.
    setPlatformAdminStatus(NO_ADMIN);

    // Internal membership does NOT show Admin nav.
    applyShellAudience("internal");
    expect(admin.hidden).toBe(true);

    // Partner membership does NOT show Admin nav.
    applyShellAudience("partner");
    expect(admin.hidden).toBe(true);

    // Client membership does NOT show Admin nav.
    applyShellAudience("client");
    expect(admin.hidden).toBe(true);

    // Platform-admin grant DOES show Admin nav.
    setPlatformAdminStatus(FULL_ADMIN);
    applyShellAudience("internal");
    expect(admin.hidden).toBe(false);

    // Revoking platform-admin hides it again.
    setPlatformAdminStatus(NO_ADMIN);
    applyShellAudience("internal");
    expect(admin.hidden).toBe(true);
  });
});

describe("setProductNavigationVisibility", () => {
  it("hides non-entitled product links for client users", () => {
    const gbpItem = documentItem(true, "gbp");
    const reviewsItem = documentItem(true, "reviews");
    const automationsItem = documentItem(true, "automations");
    const settingsItem = documentItem(false);
    vi.stubGlobal("document", {
      querySelectorAll: (selector: string) => {
        if (selector === "li[data-nav-product]") {
          return [gbpItem, reviewsItem, automationsItem];
        }
        return [];
      },
    });
    // Client user — only entitled to GBP.
    setPlatformAdminStatus(NO_ADMIN);
    setProductNavigationVisibility(new Set(["gbp"]));

    expect(gbpItem.hidden).toBe(false);
    expect(reviewsItem.hidden).toBe(true);
    expect(automationsItem.hidden).toBe(true);
    // Non-product items (settings) are unaffected.
    expect(settingsItem.hidden).toBe(false);
  });

  it("reveals all products for platform administrators", () => {
    const gbpItem = documentItem(true, "gbp");
    const reviewsItem = documentItem(true, "reviews");
    vi.stubGlobal("document", {
      querySelectorAll: (selector: string) => {
        if (selector === "li[data-nav-product]") {
          return [gbpItem, reviewsItem];
        }
        return [];
      },
    });
    // Platform admin — all products should be revealed.
    setPlatformAdminStatus(FULL_ADMIN);
    setProductNavigationVisibility(new Set([]));

    expect(gbpItem.hidden).toBe(false);
    expect(reviewsItem.hidden).toBe(false);
  });

  it("keeps products hidden when entitlement loading fails (fail closed)", () => {
    const gbpItem = documentItem(true, "gbp");
    vi.stubGlobal("document", {
      querySelectorAll: (selector: string) => {
        if (selector === "li[data-nav-product]") {
          return [gbpItem];
        }
        return [];
      },
    });
    // Client user — no entitled products (simulating API failure).
    setPlatformAdminStatus(NO_ADMIN);
    setProductNavigationVisibility(new Set([]));

    expect(gbpItem.hidden).toBe(true);
  });
});

function element(hidden: boolean): HTMLElement {
  return { hidden, textContent: "" } as HTMLElement;
}

function documentItem(hidden = false, navKey?: string): HTMLElement {
  const link = navKey
    ? ({
        getAttribute: (attr: string) =>
          attr === "data-nav-key" ? navKey : null,
      } as HTMLAnchorElement)
    : null;
  return {
    hidden,
    querySelector: () => link,
  } as unknown as HTMLElement;
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
      querySelector: () => null,
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

describe("platform-admin capability model", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setPlatformAdminStatus(NO_ADMIN);
  });

  function stubDocument(): void {
    vi.stubGlobal("document", {
      getElementById: () => null,
      querySelector: () => null,
    });
  }

  it("returns false for all capabilities by default before boot status is set", () => {
    stubDocument();
    expect(isPlatformAdmin()).toBe(false);
    expect(hasPlatformAdminGrant()).toBe(false);
    expect(meetsPlatformAdminRequiredAssurance()).toBe(false);
    expect(canUsePlatformAdministration()).toBe(false);
  });

  it("no grant: grant=false, assurance irrelevant, usable=false", () => {
    stubDocument();
    setPlatformAdminStatus(NO_ADMIN);
    expect(hasPlatformAdminGrant()).toBe(false);
    expect(meetsPlatformAdminRequiredAssurance()).toBe(false);
    expect(canUsePlatformAdministration()).toBe(false);
  });

  it("grant + insufficient assurance: grant=true, assurance=false, usable=false", () => {
    stubDocument();
    setPlatformAdminStatus(GRANT_NO_ASSURANCE);
    expect(hasPlatformAdminGrant()).toBe(true);
    expect(meetsPlatformAdminRequiredAssurance()).toBe(false);
    expect(canUsePlatformAdministration()).toBe(false);
  });

  it("grant + sufficient assurance: usable=true", () => {
    stubDocument();
    setPlatformAdminStatus(FULL_ADMIN);
    expect(hasPlatformAdminGrant()).toBe(true);
    expect(meetsPlatformAdminRequiredAssurance()).toBe(true);
    expect(canUsePlatformAdministration()).toBe(true);
  });

  it("capability resets correctly when boot status changes", () => {
    stubDocument();
    setPlatformAdminStatus(FULL_ADMIN);
    expect(canUsePlatformAdministration()).toBe(true);
    setPlatformAdminStatus(GRANT_NO_ASSURANCE);
    expect(canUsePlatformAdministration()).toBe(false);
    expect(hasPlatformAdminGrant()).toBe(true);
    setPlatformAdminStatus(NO_ADMIN);
    expect(canUsePlatformAdministration()).toBe(false);
    expect(hasPlatformAdminGrant()).toBe(false);
  });

  it("membership type does not affect any capability value", () => {
    const admin = element(false);
    vi.stubGlobal("document", {
      getElementById: () => null,
      querySelector: () => admin,
    });
    // Start clean: no platform-admin grant.
    setPlatformAdminStatus(NO_ADMIN);
    expect(canUsePlatformAdministration()).toBe(false);

    // Internal membership alone does NOT imply any capability.
    applyShellAudience("internal");
    expect(hasPlatformAdminGrant()).toBe(false);
    expect(canUsePlatformAdministration()).toBe(false);

    // Partner membership alone does NOT imply any capability.
    applyShellAudience("partner");
    expect(canUsePlatformAdministration()).toBe(false);

    // Client membership alone does NOT imply any capability.
    applyShellAudience("client");
    expect(canUsePlatformAdministration()).toBe(false);

    // Full platform-admin capability is authoritative, independent of membership.
    setPlatformAdminStatus(FULL_ADMIN);
    applyShellAudience("client");
    expect(canUsePlatformAdministration()).toBe(true);
  });

  it("low-assurance grant yields grant visibility but not usable capability (MFA path)", () => {
    stubDocument();
    setPlatformAdminStatus(GRANT_NO_ASSURANCE);
    // Admin navigation (grant-based) is visible…
    expect(isPlatformAdmin()).toBe(true);
    // …but the privileged Settings capability is NOT usable until MFA.
    expect(canUsePlatformAdministration()).toBe(false);
    // The caller has the grant and lacks assurance: the frontend must
    // show the MFA path instead of a dead-end operator control.
    expect(
      hasPlatformAdminGrant() && !meetsPlatformAdminRequiredAssurance(),
    ).toBe(true);
  });
});
