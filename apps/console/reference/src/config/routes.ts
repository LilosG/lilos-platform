import type { ProductArea } from "../types/domain";
import { clients } from "../data/fixtures/clients";
export const portfolioNavigation = [
  ["dashboard", "◫", "Dashboard"],
  ["clients", "▦", "Clients"],
  ["opportunities", "✧", "Opportunities"],
  ["reports", "▤", "Reports"],
  ["automations", "⌁", "Automations"],
  ["integrations", "⊞", "Integrations"],
  ["administration", "⚙", "Administration"],
] as const;
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
export const localTabs = [
  "Overview",
  "Rankings",
  "Google Business Profile",
  "Search Console",
  "Pages",
  "Technical",
];
export const websiteTabs = [
  "Overview",
  "Pages",
  "Content",
  "Technical",
  "Conversions",
];
export const slugify = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-$/, "");
export function route(
  page = "dashboard",
  clientId?: string | null,
  area: string = "Overview",
  section = "Overview",
): string {
  if (!clientId) return page === "dashboard" ? "/" : `/${page}/`;
  const client = clients.find((c) => c.id === clientId || c.slug === clientId);
  if (!client) throw new Error(`Unknown client: ${clientId}`);
  const base = `/clients/${client.slug}/`;
  return (
    base +
    (area === "Overview" ? "" : `${slugify(area)}/`) +
    (section === "Overview" ? "" : `${slugify(section)}/`)
  );
}
export const clientBySlug = (slug: string) =>
  clients.find((c) => c.slug === slug);
export const routeInventory = [
  "/administration/onboarding/",
  "/administration/users/",
  "/administration/platform/",
  "/",
  ...portfolioNavigation.slice(1).map(([p]) => route(p)),
  "/attention/",
  "/activity/",
  ...clients.flatMap((c) =>
    clientNavigation.flatMap((g) =>
      g.items.flatMap(([area]) =>
        (area === "Local Search"
          ? localTabs
          : area === "Website & Content"
            ? websiteTabs
            : ["Overview"]
        ).map((tab) => route("client", c.id, area, tab)),
      ),
    ),
  ),
];
export const administrationTabs = [
  "Clients / organizations",
  "Onboarding",
  "Users",
  "Platform / system",
] as const;
export function administrationRoute(tab: string): string {
  return (
    route("administration") +
    (tab === administrationTabs[0]
      ? ""
      : tab === "Platform / system"
        ? "platform/"
        : slugify(tab) + "/")
  );
}
