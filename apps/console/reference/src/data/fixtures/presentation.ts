import type { Client, ViewState } from "../../types/domain";
import { opportunities, hospitalityMetrics } from "./index";
import { scaled, scopedOpps } from "../../lib/view";
export function sampleInquiryIndexes() {
  return [0, 1, 2, 3] as const;
}

export function trackedOutcomeNames() {
  return [
    "reserve_click",
    "private_event_submit",
    "contact_submit",
    "phone_click",
    "GBP call interactions",
  ] as const;
}

export function automationViews() {
  return ["Overview", "All automations"] as const;
}

export function automationStatusFilters() {
  return [
    "All statuses",
    "Needs attention",
    "Failed",
    "Incomplete data",
    "Healthy",
  ] as const;
}

export function clientOperationalHealthRows(c: Client) {
  return [
    ["GBP", c.gbp, "Integrations"],
    ["Analytics", c.integration, "Integrations"],
    [
      "Automations",
      c.gbp === "Disconnected" ? "Needs attention" : "Healthy",
      "Automations",
    ],
  ] as const;
}

export function outcomeChannelRows() {
  return [
    ["Reservation clicks", "Organic search", "Menu", 45, -8, "reserve_click"],
    [
      "Reservation clicks",
      "GBP / direct",
      "Home and other pages",
      87,
      -8,
      "reserve_click",
    ],
    [
      "Form submissions",
      "Organic / referral",
      "Private events",
      12,
      9,
      "private_event_submit",
    ],
    [
      "Other forms",
      "Organic / direct",
      "Contact and other pages",
      36,
      4,
      "contact_submit",
    ],
    [
      "Website phone clicks",
      "All website channels",
      "Home / Contact",
      106,
      12,
      "phone_click",
    ],
    [
      "GBP calls",
      "Google Business Profile",
      "Profile",
      515,
      21,
      "GBP call interactions",
    ],
  ] as const;
}

export function organicDemandQueries(c: Client) {
  return [
    c.category.toLowerCase() + " " + c.location.split(",")[0],
    c.category.toLowerCase() + " near me",
    c.category === "Electrician"
      ? "panel upgrade cost"
      : c.category + " services",
  ] as const;
}

export function restaurantRankingQueries() {
  return [
    "brunch little italy",
    "brunch san diego",
    "restaurant little italy",
    "private dining san diego",
    "mexican restaurant little italy",
  ] as const;
}

export function serviceRankingQueries(c: Client) {
  return [
    c.category.toLowerCase() + " near me",
    c.category.toLowerCase() + " " + c.location.split(",")[0],
    c.category === "Restaurant"
      ? "brunch near me"
      : c.category === "Electrician"
        ? "panel upgrade electrician"
        : "best " + c.category.toLowerCase(),
    c.category === "Restaurant"
      ? "private dining"
      : c.category.toLowerCase() + " cost",
    c.category.toLowerCase() + " services",
  ] as const;
}

export function profileAndSearchRows(state: ViewState) {
  const periodLabel = (source: string) =>
    `${source} · Last ${state.range} days`;
  return [
    ["GBP calls", scaled(515), periodLabel("GBP")],
    ["GBP website clicks", scaled(1201), periodLabel("GBP")],
    ["Direction requests", scaled(772), periodLabel("GBP")],
    [
      "Search impressions",
      scaled(hospitalityMetrics.gscImpressions),
      periodLabel("Search Console"),
    ],
  ] as const;
}

export function visibilityGridLines() {
  return [35, 75, 115] as const;
}

export function findingsAllTypesRows(c: Client) {
  return ["All types", ...new Set(scopedOpps(c).map((o) => o.type))] as const;
}

export function findingsAllPrioritiesRows() {
  return ["All priorities", "High", "Medium"] as const;
}

export function findingsAllClassificationsRows() {
  return [
    "All classifications",
    "Issue",
    "Growth Opportunity",
    "Optimization",
    "Data & Tracking",
  ] as const;
}

export function opportunitiesAllTypesRows() {
  return ["All types", ...new Set(opportunities.map((o) => o.type))] as const;
}

export function opportunitiesAllPrioritiesRows() {
  return ["All priorities", "High", "Medium"] as const;
}

export function administrativeSections() {
  return [
    "Clients / organizations",
    "Onboarding",
    "Users",
    "Platform / system",
  ] as const;
}

export function platformSettings() {
  return [
    ["Data sync", "Search and review sources operational"],
    ["Monitoring", "12 websites checked · 1 issue detected"],
    ["Reporting", "Monthly generation scheduled October 1"],
    ["Prototype version", "Refined agency and client architecture"],
  ] as const;
}

export function reportsAllReportsRows() {
  return [
    "All reports",
    "Ready",
    "Sent",
    "Upcoming",
    "Needs attention",
    "Missing data",
  ] as const;
}

export function reviewStatusFilters() {
  return [
    "All reviews",
    "Needs response",
    "Draft",
    "Awaiting approval",
    "Published",
    "Review requests",
  ] as const;
}

export function conversionPages(c: Client) {
  return [
    "Services",
    "Contact",
    c.category === "Restaurant" ? "Menu" : "Location",
  ] as const;
}

export function technicalFindings(c: Client) {
  return [
    {
      title:
        c.website === "SEO issue"
          ? "Broken internal service links"
          : "Internal links pass",
      text:
        c.website === "SEO issue"
          ? "4 links point to retired service URLs."
          : "No broken internal destinations detected.",
      type: "Internal linking",
      priority: c.website === "SEO issue" ? "High" : "Healthy",
    },
    {
      title: "Service markup can be completed",
      text: "2 service pages lack consistent service area fields.",
      type: "Structured data",
      priority: "Medium",
    },
    {
      title: "Canonical and indexing checks",
      text: "24 indexable pages use consistent canonical URLs. 2 utility pages are excluded.",
      type: "Technical SEO",
      priority: "Healthy",
    },
  ] as const;
}
