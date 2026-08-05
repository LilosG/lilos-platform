export const platformName = "LILOs";

export type NavigationItem = {
  key: string;
  label: string;
  href: string;
};

/**
 * Navigation is always rendered. Authorization is enforced server-side on every
 * request a section makes; the client never precomputes visibility from a
 * permission set it cannot legitimately hold before the user picks a section.
 */
export const navigation: readonly NavigationItem[] = [
  { key: "overview", label: "Overview", href: "#overview" },
  { key: "gbp", label: "Business Profile", href: "/gbp" },
  { key: "reviews", label: "Reviews", href: "/reviews" },
  { key: "leads", label: "Leads", href: "/leads" },
  { key: "content", label: "Content", href: "/content" },
  { key: "seo", label: "SEO", href: "/seo" },
  { key: "insights", label: "Insights", href: "#products" },
  { key: "admin", label: "Administration", href: "#administration" },
];

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
