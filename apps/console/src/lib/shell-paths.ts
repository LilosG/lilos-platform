export const clientAreaPath = (slug: string, areaPath: string) =>
  `/clients/${slug}/${areaPath}`;
/** "opportunities/abc/" -> "opportunities/"; the screen family survives a client switch. */
export function areaFamily(workspacePath: string): string {
  const first = workspacePath.replace(/^\/|\/$/g, "").split("/", 1)[0];
  return first ? `${first}/` : "";
}
export const areaOfPath: Record<string, string> = {
  "": "Overview",
  "local-search": "Local Search",
  reviews: "Reviews",
  "website-content": "Website & Content",
  leads: "Leads",
  opportunities: "Opportunities",
  automations: "Automations",
  reports: "Reports",
  integrations: "Integrations",
  settings: "Settings",
};
