export const platformName = "LILOs";
export const developmentPhase = "Operational workspace";

export type WorkspaceState = {
  organizationName: string;
  organizationStatus: "active" | "onboarding" | "paused";
  assurance: "aal1" | "aal2";
  permissions: ReadonlySet<string>;
  entitlements: ReadonlySet<string>;
  readyProducts: ReadonlySet<string>;
  runtimeBlocks: ReadonlySet<string>;
};

export type NavigationItem = {
  key: string;
  label: string;
  permission: string;
  product?: string;
  href: string;
};

export const navigation: readonly NavigationItem[] = [
  {
    key: "overview",
    label: "Overview",
    permission: "organization.read",
    href: "#overview",
  },
  {
    key: "gbp",
    label: "Business Profile",
    permission: "gbp.read",
    product: "gbp",
    href: "#products",
  },
  {
    key: "reviews",
    label: "Reviews",
    permission: "reviews.read",
    product: "reviews",
    href: "#products",
  },
  {
    key: "leads",
    label: "Leads",
    permission: "leads.read",
    product: "leads",
    href: "#products",
  },
  {
    key: "content",
    label: "Content",
    permission: "content.read",
    product: "content",
    href: "#products",
  },
  {
    key: "seo",
    label: "SEO",
    permission: "seo.read",
    product: "seo",
    href: "#seo",
  },
  {
    key: "insights",
    label: "Insights",
    permission: "insights.read",
    product: "insights",
    href: "#insights",
  },
  {
    key: "admin",
    label: "Administration",
    permission: "organization.members.manage",
    href: "#administration",
  },
  { key: "audit", label: "Audit", permission: "audit.read", href: "#activity" },
];

export function visibleNavigation(state: WorkspaceState): NavigationItem[] {
  return navigation.filter(
    (item) =>
      state.permissions.has(item.permission) &&
      (!item.product || state.entitlements.has(item.product)),
  );
}

export function productState(
  state: WorkspaceState,
  product: string,
): "blocked" | "setup" | "ready" {
  if (state.runtimeBlocks.has(product) || state.organizationStatus === "paused")
    return "blocked";
  if (!state.entitlements.has(product) || !state.readyProducts.has(product))
    return "setup";
  return "ready";
}

export function requiresStepUp(
  state: WorkspaceState,
  minimum: "aal1" | "aal2",
): boolean {
  return minimum === "aal2" && state.assurance !== "aal2";
}
