import type {
  ClientOverview,
  ClientRow,
  PortfolioOverview,
} from "../server/command-center";
import {
  attentionView,
  fmt,
  healthLabel,
  healthSub,
  initials,
  opportunityTitle,
  priorityText,
  show,
  signed,
  systemLabel,
  systemStatusText,
  when,
  workflowDone,
  workflowNoun,
  type Shown,
} from "./present";
import { clientRoute } from "../config/routes";
type Attention = PortfolioOverview["attention"][number];
type Opportunity = PortfolioOverview["opportunities"][number];
export interface AttentionRow {
  id: string;
  title: string;
  impact: string;
  next: string;
  severity: "critical" | "high" | "medium";
  severityLabel: string;
  clientName: string;
  clientHref: string;
  actionHref: string;
  time: string;
}
export function attentionRows(items: Attention[], now: Date): AttentionRow[] {
  return items.map((item, index) => {
    const view = attentionView(item);
    return {
      id: `attention-${index}`,
      title: view.title,
      impact: view.impact,
      next: view.next,
      severity: item.severity,
      severityLabel: view.severityLabel,
      clientName: item.organization_name,
      clientHref: clientRoute(item.organization_slug),
      actionHref: `/clients/${item.organization_slug}/${view.area}/`,
      time: item.occurred_at ? when(item.occurred_at, now) : "Open",
    };
  });
}
export interface OpportunityRowView {
  id: string;
  title: string;
  clientName: string;
  clientHref: string;
  href: string;
  classification: string;
  priority: string;
}
export function opportunityRows(items: Opportunity[]): OpportunityRowView[] {
  return items.map((item) => ({
    id: item.id,
    title: opportunityTitle(item),
    clientName: item.organization_name,
    clientHref: clientRoute(item.organization_slug),
    href: `/clients/${item.organization_slug}/opportunities/${item.id}/`,
    classification: item.classification,
    priority: priorityText(item.priority),
  }));
}
export interface ClientRowView {
  id: string;
  slug: string;
  name: string;
  mark: string;
  href: string;
  sub: string;
  search: string;
  visibility: Shown;
  rank: Shown;
  organic: Shown;
  organicDelta: string | null;
  leads: Shown;
  leadsDelta: string | null;
  reviews: {
    state: ClientRow["reviews"]["availability"];
    rating: string;
    note: string;
  };
  health: string;
  healthSub: string;
  lastActivity: string;
  nextTitle: string;
  nextWhen: string;
  filters: {
    needsAttention: boolean;
    websiteIssue: boolean;
    gbpIssue: boolean;
    integrationIssue: boolean;
    multiLocation: boolean;
  };
  priority: number;
}
const WEBSITE = ["SEARCH_CONSOLE_NOT_CONNECTED", "GA4_NOT_CONNECTED"];
const GBP = ["GOOGLE_NOT_CONNECTED", "GOOGLE_RECONNECT_REQUIRED"];
const has = (row: ClientRow, codes: string[]) =>
  row.health_reasons.some((reason) => codes.includes(reason));
export function clientRowView(row: ClientRow, now: Date): ClientRowView {
  const reviews = row.reviews;
  const sub = [
    row.location,
    row.location_count > 1
      ? `${row.location_count} locations`
      : (row.category ?? "No category set"),
  ]
    .filter(Boolean)
    .join(" · ");
  const reviewShown =
    reviews.availability === "available" && reviews.average_rating !== null;
  return {
    id: row.organization_id,
    slug: row.slug,
    name: row.name,
    mark: initials(row.name),
    href: clientRoute(row.slug),
    sub,
    search:
      `${row.name} ${row.category ?? ""} ${row.location ?? ""}`.toLowerCase(),
    visibility: show(row.local_visibility),
    rank: show(row.average_local_rank),
    organic: show(row.organic_sessions),
    organicDelta: signed(row.organic_sessions.percent_delta, 0),
    leads: show(row.leads),
    leadsDelta: signed(row.leads.percent_delta, 0),
    reviews: {
      state: reviews.availability,
      rating: reviewShown ? (reviews.average_rating as number).toFixed(1) : "",
      note: reviewShown
        ? `${reviews.total ?? 0} total · +${reviews.new_in_period ?? 0}`
        : show({
            current: null,
            previous: null,
            percent_delta: null,
            source: "reviews",
            availability: reviews.availability,
          }).text,
    },
    health: healthLabel[row.health],
    healthSub: healthSub(row),
    lastActivity: row.last_activity
      ? `${workflowDone(row.last_activity.workflow_key)} · ${when(row.last_activity.at, now)}`
      : "No completed work yet",
    nextTitle: row.next_work
      ? workflowNoun(row.next_work.workflow_key)
      : "Nothing scheduled",
    nextWhen: row.next_work ? when(row.next_work.at, now) : "",
    filters: {
      needsAttention: row.health !== "healthy",
      websiteIssue: has(row, WEBSITE),
      gbpIssue: has(row, GBP),
      integrationIssue: has(row, [...WEBSITE, ...GBP]),
      multiLocation: row.location_count > 1,
    },
    priority: row.health_reasons.length,
  };
}
export interface MetricCellView {
  label: string;
  value: string;
  description: string;
  missing: boolean;
}
function cell(
  label: string,
  shown: Shown,
  describe: (shown: Shown) => string,
): MetricCellView {
  return {
    label,
    value: shown.text,
    description: shown.state === "available" ? describe(shown) : shown.note,
    missing: shown.state !== "available",
  };
}
const vsPrevious = (shown: Shown) =>
  signed(shown.delta)
    ? `${signed(shown.delta)} vs previous period`
    : "No earlier period to compare";
export function portfolioMetrics(
  overview: PortfolioOverview,
): MetricCellView[] {
  const totals = overview.totals;
  const reviewsKnown = totals.new_reviews !== null;
  return [
    cell("Local visibility", show(totals.local_visibility), () => ""),
    cell("Website leads", show(totals.website_leads), vsPrevious),
    {
      label: "New reviews",
      value: reviewsKnown ? fmt(totals.new_reviews as number) : "No data",
      description:
        totals.average_rating !== null
          ? `${totals.average_rating.toFixed(1)} average Google rating`
          : "No reviews synced yet",
      missing: !reviewsKnown,
    },
    {
      label: "Reporting attention",
      value: String(totals.reporting_attention),
      description: "Clients with data gaps or issues to review",
      missing: false,
    },
  ];
}
export function snapshotMetrics(overview: ClientOverview): (MetricCellView & {
  href: string;
})[] {
  const row = overview.client;
  const slug = row.slug;
  const reviews = row.reviews;
  const reviewShown =
    reviews.availability === "available" && reviews.average_rating !== null;
  const unavailable = (label: string, note: string, href: string) => ({
    label,
    value: "Not tracked",
    description: note,
    missing: true,
    href,
  });
  return [
    {
      ...cell("Local visibility", show(row.local_visibility), () => ""),
      href: `${clientRoute(slug, "Local Search")}rankings/`,
    },
    {
      ...cell("Average local rank", show(row.average_local_rank), () => ""),
      href: `${clientRoute(slug, "Local Search")}rankings/`,
    },
    unavailable(
      "GBP actions",
      "Google profile performance is not collected yet",
      `${clientRoute(slug, "Local Search")}google-business-profile/`,
    ),
    {
      label: "Google rating",
      value: reviewShown
        ? `${(reviews.average_rating as number).toFixed(1)} ★`
        : "No data",
      description: reviewShown
        ? `+${reviews.new_in_period ?? 0} new reviews · ${reviews.total ?? 0} total`
        : "No reviews synced yet",
      missing: !reviewShown,
      href: clientRoute(slug, "Reviews"),
    },
    {
      ...cell("Organic sessions", show(row.organic_sessions), vsPrevious),
      href: clientRoute(slug, "Website & Content"),
    },
    {
      ...cell("Website leads", show(row.leads), vsPrevious),
      href: clientRoute(slug, "Leads"),
    },
  ];
}
export interface Insight {
  title: string;
  description: string;
  href: string;
  linkLabel: string;
}
/** A deterministic reading of the evidence, chosen by typed reason, never by text. */
export function clientInsight(overview: ClientOverview): Insight {
  const row = overview.client;
  const slug = row.slug;
  if (row.health_reasons.includes("GOOGLE_RECONNECT_REQUIRED"))
    return {
      title:
        "Google profile data is missing while authorization needs attention.",
      description:
        "Reconnect the Google Business Profile to separate data gaps from performance changes.",
      href: `${clientRoute(slug, "Integrations")}`,
      linkLabel: "Reconnect",
    };
  if (row.health_reasons.includes("GOOGLE_NOT_CONNECTED"))
    return {
      title: "Google Business Profile is not connected.",
      description:
        "Profile performance, reviews and posting stay unavailable until a Google account is connected.",
      href: `${clientRoute(slug, "Integrations")}`,
      linkLabel: "Connect",
    };
  const organic = row.organic_sessions;
  if (organic.availability === "available" && organic.percent_delta !== null)
    return {
      title: `Organic sessions ${organic.percent_delta >= 0 ? "increased" : "declined"} ${Math.abs(
        organic.percent_delta,
      )}% in this period.`,
      description:
        "Local visibility is not tracked until rank scans exist, so search movement is read from Search Console and Analytics.",
      href: clientRoute(slug, "Website & Content"),
      linkLabel: "Investigate",
    };
  if (row.health_reasons.includes("GA4_NOT_CONNECTED"))
    return {
      title: "Website traffic is not connected.",
      description:
        "Connect Analytics to read organic sessions and judge lead performance.",
      href: clientRoute(slug, "Integrations"),
      linkLabel: "Connect",
    };
  return {
    title: "No performance data is available for this period yet.",
    description:
      "Numbers appear here as soon as connected sources report. Missing sources are labeled, never shown as zero.",
    href: clientRoute(slug, "Integrations"),
    linkLabel: "Review connections",
  };
}
export interface HealthRow {
  label: string;
  status: string;
  note: string;
  href: string;
}
export function clientHealthRows(overview: ClientOverview): HealthRow[] {
  const slug = overview.client.slug;
  const runs = overview.insights.workflow_runs;
  const completed = runs.completed;
  const failed = (runs.failed ?? 0) + (runs.escalated ?? 0);
  return overview.systems.map((system) => ({
    label: systemLabel[system.key],
    status: systemStatusText[system.status],
    note:
      system.key === "automations" &&
      overview.insights.availability === "available" &&
      completed !== undefined
        ? `${fmt(completed)} completed${failed ? ` · ${fmt(failed)} need attention` : ""}`
        : "",
    href: clientRoute(
      slug,
      system.key === "automations" ? "Automations" : "Integrations",
    ),
  }));
}
export function portfolioHealthRows(overview: PortfolioOverview) {
  const label = {
    google: "Google Business Profile",
    analytics: "Analytics",
    automations: "Automations",
  } as const;
  const text = {
    google: ["All connected", "needs reconnection", "need reconnection"],
    analytics: ["All connected", "is not connected", "are not connected"],
    automations: ["Running normally", "has failing work", "have failing work"],
  } as const;
  return overview.systems.map((system) => {
    const [ok, one, many] = text[system.key];
    const count = system.affected_clients;
    return {
      label: label[system.key],
      status: systemStatusText[system.status],
      note:
        count === 0
          ? ok
          : `${count} ${count === 1 ? `client ${one}` : `clients ${many}`}`,
      href: system.key === "automations" ? "/automations/" : "/integrations/",
    };
  });
}
export function feedRows(items: PortfolioOverview["activity"], now: Date) {
  return items.map((item) => ({
    text: workflowDone(item.workflow_key),
    clientName: item.organization_name,
    clientHref: clientRoute(item.organization_slug),
    time: when(item.completed_at, now),
  }));
}
export function upcomingRows(items: PortfolioOverview["upcoming"], now: Date) {
  return items.map((item) => ({
    title: workflowNoun(item.workflow_key),
    clientName: item.organization_name,
    clientHref: clientRoute(item.organization_slug),
    when: when(item.next_run_at, now),
  }));
}
