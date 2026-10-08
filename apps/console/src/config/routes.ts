import { AREAS, type PortfolioArea } from "../lib/present";
export type ProductArea =
  | "Overview"
  | "Local Search"
  | "Reviews"
  | "Website & Content"
  | "Leads"
  | "Opportunities"
  | "Automations"
  | "Reports"
  | "Integrations"
  | "Settings";
export const portfolioNavigation = [
  ["dashboard", "◫", "Dashboard"],
  ["clients", "▦", "Clients"],
  ["opportunities", "✧", "Opportunities"],
  ["reports", "▤", "Reports"],
  ["automations", "⌁", "Automations"],
  ["integrations", "⊞", "Integrations"],
] as const;
export type PortfolioPage =
  | (typeof portfolioNavigation)[number][0]
  | "administration"
  | "attention"
  | "activity";
export const clientNavigation: {
  label: string;
  items: [ProductArea, string][];
}[] = [
  { label: "", items: [["Overview", "◫"]] },
  {
    label: "GROWTH",
    items: [
      ["Local Search", "▥"],
      ["Reviews", "☆"],
      ["Website & Content", "▤"],
      ["Leads", "↗"],
    ],
  },
  {
    label: "OPERATIONS",
    items: [
      ["Opportunities", "✧"],
      ["Automations", "⌁"],
      ["Reports", "▤"],
    ],
  },
  {
    label: "MANAGE",
    items: [
      ["Integrations", "⊞"],
      ["Settings", "⚙"],
    ],
  },
];
export const slugify = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-$/, "");
export const portfolioRoute = (page = "dashboard") =>
  page === "dashboard" ? "/" : `/${page}/`;
export const clientRoute = (slug: string, area: ProductArea = "Overview") =>
  `/clients/${slug}/` + (area === "Overview" ? "" : `${slugify(area)}/`);
/** Every area that has no screen yet resolves to one typed state, never to fake content. */
export const clientAreaSlugs: Record<string, ProductArea> = {
  reports: "Reports",
  settings: "Settings",
};
export type NotBuilt =
  | { scope: "portfolio"; area: PortfolioArea }
  | { scope: "client"; area: keyof typeof clientAreaSlugs };
export const notBuiltTitle = (target: NotBuilt) =>
  target.scope === "portfolio"
    ? AREAS[target.area]
    : clientAreaSlugs[target.area];
export const portfolioAreas = Object.keys(AREAS) as PortfolioArea[];
