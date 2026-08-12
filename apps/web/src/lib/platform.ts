export const platformName = "LILOs";

export type NavigationItem = {
  key: string;
  label: string;
  href: string;
  icon?: string;
};

export type NavigationGroup = {
  heading: string;
  items: readonly NavigationItem[];
};

/**
 * Navigation is always rendered in grouped sections. Authorization is enforced
 * server-side on every request a section makes; the client never precomputes
 * visibility from a permission set it cannot legitimately hold before the user
 * picks a section.
 */
export const navigationGroups: readonly NavigationGroup[] = [
  {
    heading: "Workspace",
    items: [{ key: "overview", label: "Overview", href: "/", icon: "home" }],
  },
  {
    heading: "Operations",
    items: [
      { key: "gbp", label: "Business Profile", href: "/gbp", icon: "building" },
      { key: "reviews", label: "Reviews", href: "/reviews", icon: "star" },
      { key: "leads", label: "Leads", href: "/leads", icon: "inbox" },
      { key: "content", label: "Content", href: "/content", icon: "document" },
      { key: "seo", label: "SEO", href: "/seo", icon: "search" },
      { key: "automations", label: "Automations", href: "/automations", icon: "settings" },
      { key: "insights", label: "Insights", href: "/insights", icon: "chart" },
    ],
  },
  {
    heading: "Manage",
    items: [
      {
        key: "settings",
        label: "Settings",
        href: "/settings",
        icon: "settings",
      },
      {
        key: "integrations",
        label: "Integrations",
        href: "/integrations",
        icon: "plug",
      },
    ],
  },
  {
    heading: "Admin",
    items: [
      {
        key: "admin",
        label: "Administration",
        href: "/administration",
        icon: "shield",
      },
      {
        key: "onboarding",
        label: "Client Onboarding",
        href: "/onboarding",
        icon: "plus",
      },
    ],
  },
];

/** Flat list for backward compatibility with existing tests. */
export const navigation: readonly NavigationItem[] = navigationGroups.flatMap(
  (group) => group.items,
);

export type ReadinessOutcomeStatus = "ready" | "blocked" | "not_entitled";

export function readinessLabel(status: ReadinessOutcomeStatus): string {
  switch (status) {
    case "ready":
      return "ready";
    case "blocked":
      return "blocked";
    case "not_entitled":
      return "setup";
  }
}

export function requiresStepUp(
  assurance: "aal1" | "aal2",
  minimum: "aal1" | "aal2",
): boolean {
  return minimum === "aal2" && assurance !== "aal2";
}
