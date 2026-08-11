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
}

export function setPlatformNavigationVisible(visible: boolean): void {
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
  setPlatformNavigationVisible(
    platformStatus.kind === "ok" &&
      platformStatus.data.is_platform_administrator,
  );
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
