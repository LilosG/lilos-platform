import {
  fetchMyOrganizations,
  fetchMyPlatformAdministratorStatus,
  fetchPrincipal,
} from "../workspace";
import { getCurrentSession, signOut } from "../session";
import { readPublicConfig } from "../config";
import { selectDefaultOrganization } from "../dashboard-logic";
import { describeFailure } from "./errors";
import { goToLogin } from "./regions";

export type BootRegions = {
  notConfigured: HTMLElement;
  loading: HTMLElement;
  error: HTMLElement;
  empty: HTMLElement;
  content: HTMLElement;
};

export type BootContext = {
  organizationId: string;
  organizationName: string;
  organizationStatus: string;
  membershipType: string;
};

export type BootResult =
  | { kind: "not-configured" }
  | { kind: "redirected-to-login" }
  | { kind: "error"; message: string }
  | { kind: "empty" }
  | {
      kind: "ok";
      context: BootContext;
      organizations: import("../workspace").MyOrganization[];
    };

function wireSignOut(): void {
  const button = document.getElementById("sign-out-button");
  button?.addEventListener("click", async () => {
    await signOut();
    goToLogin();
  });
}

let _platformAdminGrant = false;
let _meetsPlatformAdminAssurance = false;
let _onOrganizationChanged: ((orgId: string) => void) | null = null;
let _activeOrganizationId = "";

export type PlatformAdminCapability = {
  is_platform_administrator: boolean;
  meets_required_assurance: boolean;
};

export function setPlatformAdminStatus(
  capability: PlatformAdminCapability,
): void {
  _platformAdminGrant = capability.is_platform_administrator;
  _meetsPlatformAdminAssurance = capability.meets_required_assurance;
}

export function isPlatformAdmin(): boolean {
  return _platformAdminGrant;
}

export function hasPlatformAdminGrant(): boolean {
  return _platformAdminGrant;
}

export function meetsPlatformAdminRequiredAssurance(): boolean {
  return _meetsPlatformAdminAssurance;
}

export function canUsePlatformAdministration(): boolean {
  return _platformAdminGrant && _meetsPlatformAdminAssurance;
}

export function onOrganizationChanged(handler: (orgId: string) => void): void {
  _onOrganizationChanged = handler;
}

function _updateAdminNavigation(): void {
  // Admin navigation mirrors the authoritative platform-administrator
  // grant checked by /administration and /onboarding — never a frontend
  // membership-type allowlist.  The Admin group starts hidden (AppShell
  // renders it with the hidden attribute) and is only made visible when
  // the backend confirms an active platform-administrator grant.
  setPlatformNavigationVisible(_platformAdminGrant);
}

export function setProductNavigationVisibility(
  entitledKeys: Set<string>,
): void {
  if (typeof document === "undefined") return;
  // Platform administrators see the full product suite regardless of the
  // current organization's entitlements.
  if (_platformAdminGrant) {
    for (const item of document.querySelectorAll<HTMLElement>(
      "li[data-nav-product]",
    )) {
      item.hidden = false;
    }
    return;
  }
  // Product navigation fails closed: items start hidden (AppShell renders
  // them with the hidden attribute) and are only revealed when the
  // authoritative entitlement response confirms the product is selected.
  for (const item of document.querySelectorAll<HTMLElement>(
    "li[data-nav-product]",
  )) {
    const link = item.querySelector<HTMLAnchorElement>("a[data-nav-key]");
    const key = link?.getAttribute("data-nav-key");
    item.hidden = !key || !entitledKeys.has(key);
  }
}

export function applyShellPrincipal(
  principal: import("../workspace").PrincipalSummary,
): void {
  const label = document.getElementById("current-user-label");
  const initial = document.getElementById("current-user-initial");
  const assurance = document.getElementById("current-assurance-label");
  if (label) {
    label.textContent = "Your account";
  }
  if (initial) {
    initial.textContent = "L";
  }
  if (assurance) {
    assurance.textContent = principal.assurance_level;
  }
}

export function applyShellAudience(membershipType: string): void {
  const audience = document.getElementById("active-workspace-audience");
  const role = document.getElementById("current-workspace-role");
  const isAgency = ["internal", "partner", "support"].includes(membershipType);
  const audienceLabel = isAgency ? "Agency workspace" : "Client workspace";
  if (audience) audience.textContent = audienceLabel;
  if (role) role.textContent = audienceLabel;
  _updateAdminNavigation();
}

export function setPlatformNavigationVisible(visible: boolean): void {
  if (typeof document === "undefined") return;
  const adminGroup = document.querySelector<HTMLElement>(
    '[data-navigation-group="admin"]',
  );
  if (adminGroup) adminGroup.hidden = !visible;
}

export function populateSwitcher(
  organizations: import("../workspace").MyOrganization[],
  onSelect: (org: import("../workspace").MyOrganization) => void,
): void {
  const select = document.getElementById(
    "organization-switcher",
  ) as HTMLSelectElement | null;
  if (!select) return;
  select.replaceChildren();
  for (const organization of organizations) {
    const option = document.createElement("option");
    option.value = organization.organization_id;
    option.textContent = organization.organization_name;
    select.append(option);
  }
  select.hidden = organizations.length <= 1;
  select.addEventListener("change", () => {
    const chosen = organizations.find(
      (item) => item.organization_id === select.value,
    );
    if (chosen) void onSelect(chosen);
  });
}

export function setActiveOrganization(
  organization: import("../workspace").MyOrganization,
): void {
  if (organization.organization_id) {
    _activeOrganizationId = organization.organization_id;
    localStorage.setItem("selected_org_id", organization.organization_id);
    const url = new URL(window.location.href);
    if (url.searchParams.get("org") !== organization.organization_id) {
      url.searchParams.set("org", organization.organization_id);
      window.history.replaceState({}, "", url.toString());
    }
  }
  const switcher = document.getElementById(
    "organization-switcher",
  ) as HTMLSelectElement | null;
  if (switcher) switcher.value = organization.organization_id;
  const nameEl = document.getElementById("active-organization-name");
  if (nameEl) nameEl.textContent = organization.organization_name;
  applyShellAudience(organization.membership_type);
  if (_onOrganizationChanged)
    _onOrganizationChanged(organization.organization_id);
}

export async function bootWorkspace(
  productContext: string,
): Promise<BootResult> {
  if (!readPublicConfig()) {
    return { kind: "not-configured" };
  }

  const session = await getCurrentSession();
  if (session.status !== "signed-in") {
    goToLogin();
    return { kind: "redirected-to-login" };
  }

  const principal = await fetchPrincipal();
  if (principal.kind === "unauthenticated") {
    goToLogin();
    return { kind: "redirected-to-login" };
  }
  if (principal.kind !== "ok") {
    return {
      kind: "error",
      message: describeFailure(principal, productContext),
    };
  }

  applyShellPrincipal(principal.data);
  const signOutButton = document.getElementById("sign-out-button");
  if (signOutButton) signOutButton.hidden = false;
  wireSignOut();

  const [organizations, platformStatus] = await Promise.all([
    fetchMyOrganizations(),
    fetchMyPlatformAdministratorStatus(),
  ]);
  setPlatformAdminStatus({
    is_platform_administrator:
      platformStatus.kind === "ok" &&
      platformStatus.data.is_platform_administrator,
    meets_required_assurance:
      platformStatus.kind === "ok" &&
      platformStatus.data.meets_required_assurance,
  });
  if (organizations.kind === "unauthenticated") {
    goToLogin();
    return { kind: "redirected-to-login" };
  }
  if (organizations.kind !== "ok") {
    return {
      kind: "error",
      message: describeFailure(organizations, productContext),
    };
  }
  if (organizations.data.length === 0) {
    return { kind: "empty" };
  }

  const initial = selectDefaultOrganization(organizations.data);
  if (!initial) {
    return { kind: "empty" };
  }

  setActiveOrganization(initial);

  // Register a callback so organization switching recalculates product
  // navigation visibility from the newly-selected organization's entitlements.
  // The callback fails closed: products are hidden until the new entitlement
  // response arrives, and a stale response from an earlier switch is discarded.
  onOrganizationChanged(async (targetOrgId) => {
    // Hide all product items while the new entitlement state resolves.
    if (!_platformAdminGrant) {
      for (const item of document.querySelectorAll<HTMLElement>(
        "li[data-nav-product]",
      )) {
        item.hidden = true;
      }
    }
    const { fetchEntitledProducts: fetchProducts } =
      await import("../workspace");
    const products = await fetchProducts(targetOrgId);
    // Discard stale responses from a different active organization.
    if (_activeOrganizationId !== targetOrgId) return;
    if (products.kind === "ok") {
      setProductNavigationVisibility(
        new Set(
          products.data.filter((p) => p.entitled).map((p) => p.product_key),
        ),
      );
    }
    // On failure, product items remain hidden (fail closed).
  });

  // Fetch entitled products for the initial organization.
  const { fetchEntitledProducts } = await import("../workspace");
  const products = await fetchEntitledProducts(initial.organization_id);
  if (products.kind === "ok") {
    setProductNavigationVisibility(
      new Set(
        products.data.filter((p) => p.entitled).map((p) => p.product_key),
      ),
    );
  }

  return {
    kind: "ok",
    context: {
      organizationId: initial.organization_id,
      organizationName: initial.organization_name,
      organizationStatus: initial.organization_status,
      membershipType: initial.membership_type,
    },
    organizations: organizations.data,
  };
}

export function applyBootResult(
  regions: BootRegions,
  result: BootResult,
): result is {
  kind: "ok";
  context: BootContext;
  organizations: import("../workspace").MyOrganization[];
} {
  switch (result.kind) {
    case "not-configured":
      showRegion(regions, regions.notConfigured);
      return false;
    case "redirected-to-login":
      return false;
    case "error":
      regions.error.textContent = result.message;
      showRegion(regions, regions.error);
      return false;
    case "empty":
      showRegion(regions, regions.empty);
      return false;
    case "ok":
      showRegion(regions, regions.content);
      return true;
  }
  function showRegion(r: BootRegions, visible: HTMLElement): void {
    r.notConfigured.hidden = true;
    r.loading.hidden = true;
    r.error.hidden = true;
    r.empty.hidden = true;
    r.content.hidden = true;
    visible.hidden = false;
  }
}
