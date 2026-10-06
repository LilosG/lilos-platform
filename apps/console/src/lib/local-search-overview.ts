import type { GbpPerformanceView } from "../adapters/gbp";
import type { LocalSearchView } from "../adapters/local-search";
import { gbpTile, searchTile, type Tile } from "./local-search-view";
import { pagePath } from "./opportunity-view";
import { countText, dateText, fmt, periodText, positionText } from "./present";
import type { Chip } from "./status";

type Insight = LocalSearchView["insights"][number];
type InsightLink = Insight["link"];
/** Where each insight's evidence lives, as hrefs the screen already knows. */
export type InsightHrefs = Record<InsightLink, string>;
export interface InsightRow {
  title: string;
  detail: string;
  href: string;
  linkLabel: string;
}
const linkLabel: Record<InsightLink, string> = {
  search_console: "Search queries",
  pages: "Landing pages",
  google_business_profile: "Profile details",
};
const percent = (change: number | null) =>
  change === null ? "" : `${Math.abs(Math.round(change))}%`;
const quoted = (value: string | null) => `“${value ?? ""}”`;
const was = (item: Insight, unit: string) =>
  `${fmt(item.current ?? 0)} ${unit} against ${fmt(item.previous ?? 0)} in the previous period.`;
/** A sentence for each typed insight. No code, number or address reaches the screen as is. */
const sentences: Record<
  Insight["code"],
  (item: Insight) => { title: string; detail: string }
> = {
  QUERY_GAINING_CLICKS: (i) => ({
    title: `${quoted(i.subject)} is bringing in more clicks.`,
    detail: `Clicks from this search rose ${percent(i.percent_change)}: ${was(i, "clicks")}`,
  }),
  QUERY_LOSING_CLICKS: (i) => ({
    title: `${quoted(i.subject)} is losing clicks.`,
    detail: `Clicks from this search fell ${percent(i.percent_change)}: ${was(i, "clicks")}`,
  }),
  PAGE_GAINING_CLICKS: (i) => ({
    title: `${pagePath(i.subject ?? "")} is attracting more search clicks.`,
    detail: `Clicks to this page rose ${percent(i.percent_change)}: ${was(i, "clicks")}`,
  }),
  PAGE_LOSING_CLICKS: (i) => ({
    title: `${pagePath(i.subject ?? "")} is losing search clicks.`,
    detail: `Clicks to this page fell ${percent(i.percent_change)}: ${was(i, "clicks")}`,
  }),
  SEARCH_CLICKS_UP: (i) => ({
    title: `Search clicks are up ${percent(i.percent_change)}.`,
    detail: was(i, "clicks"),
  }),
  SEARCH_CLICKS_DOWN: (i) => ({
    title: `Search clicks are down ${percent(i.percent_change)}.`,
    detail: was(i, "clicks"),
  }),
  IMPRESSIONS_OUTRUNNING_CLICKS: (i) => ({
    title:
      "More people see the business in search, but clicks are not keeping pace.",
    detail: `Impressions rose ${percent(i.percent_change)} to ${fmt(i.current ?? 0)}, and clicks grew by far less.`,
  }),
  PROFILE_ACTIONS_UP: (i) => ({
    title: "Business Profile activity is growing.",
    detail: `Calls, website clicks and directions rose ${percent(i.percent_change)}: ${was(i, "actions")}`,
  }),
  PROFILE_ACTIONS_DOWN: (i) => ({
    title: "Business Profile activity is falling.",
    detail: `Calls, website clicks and directions fell ${percent(i.percent_change)}: ${was(i, "actions")}`,
  }),
  QUERIES_NEAR_PAGE_ONE: (i) => ({
    title:
      (i.count ?? 0) > 1
        ? `${i.count} searches sit just off the first page.`
        : "One search sits just off the first page.",
    detail: `${quoted(i.subject)} has the most impressions of them, at an average position of ${positionText(i.current)}.`,
  }),
};
export function insightRows(
  view: LocalSearchView,
  hrefs: InsightHrefs,
): InsightRow[] {
  return view.insights.map((item) => ({
    ...sentences[item.code](item),
    href: hrefs[item.link],
    linkLabel: linkLabel[item.link],
  }));
}
export interface FactRow {
  label: string;
  /** What the row's source and period are, or why there is no number. */
  sub: string;
  value: string;
  trend: number | null;
  missing: boolean;
}
const fromTile = (tile: Tile, source: string, days: number): FactRow => ({
  label: tile.label,
  sub: tile.missing ? tile.description : `${source} · ${periodText(days)}`,
  value: tile.value,
  trend: tile.trend,
  missing: tile.missing,
});
/** Profile actions beside organic search: each with its source and period, or why it is absent. */
export function profileAndSearchRows(
  view: LocalSearchView,
  gbp: GbpPerformanceView | null,
  days: number,
): FactRow[] {
  return [
    fromTile(
      gbpTile(gbp, "CALL_CLICKS", "Calls", days),
      "Business Profile",
      days,
    ),
    fromTile(
      gbpTile(gbp, "WEBSITE_CLICKS", "Website clicks", days),
      "Business Profile",
      days,
    ),
    fromTile(
      gbpTile(gbp, "BUSINESS_DIRECTION_REQUESTS", "Direction requests", days),
      "Business Profile",
      days,
    ),
    fromTile(
      searchTile(
        view.search_console,
        "impressions",
        "Search impressions",
        days,
      ),
      "Search Console",
      days,
    ),
  ];
}
type Health = NonNullable<LocalSearchView["technical_health"]>;
type Count = Health["pages_crawled"];
const NOT_TRACKED = "Not tracked";
/** The latest site crawl's counts. A count the platform does not collect says so, never 0. */
export function technicalRows(health: Health): FactRow[] {
  const crawl = health.last_crawled_at
    ? `Site crawl · ${dateText(health.last_crawled_at)}`
    : "Site crawl";
  const row = (
    label: string,
    count: Count,
    note: string,
    text = (n: number) => fmt(n),
  ): FactRow =>
    count.state === "tracked" && count.value != null
      ? {
          label,
          sub: `${note} · ${crawl}`,
          value: text(count.value),
          trend: null,
          missing: false,
        }
      : {
          label,
          sub: "Run a website check to collect this",
          value: NOT_TRACKED,
          trend: null,
          missing: true,
        };
  const crawled = health.pages_crawled.value ?? null;
  const of = (n: number) =>
    crawled === null ? fmt(n) : `${fmt(n)} of ${fmt(crawled)}`;
  return [
    {
      label: "Indexed by Google",
      sub: "Google's own index count is not collected yet",
      value: NOT_TRACKED,
      trend: null,
      missing: true,
    },
    row(
      "Indexable pages",
      health.indexable_pages,
      "Open to search engines",
      of,
    ),
    row(
      "Excluded pages",
      health.excluded_pages,
      "Marked noindex or not loading",
    ),
    row(
      "Pages with technical issues",
      health.pages_with_issues,
      "At least one finding",
    ),
    row(
      "Structured data",
      health.structured_data_pages,
      "Pages with schema markup",
      of,
    ),
  ];
}
export interface PriorityPage {
  label: string;
  sub: string;
  chip: Chip;
  /** The page's own screen, when the crawl has seen it. */
  href: string | null;
}
type IndexStatus = "indexable" | "not_indexable" | "not_crawled";
const indexChip: Record<IndexStatus, Chip> = {
  indexable: { label: "Indexable", tone: "" },
  not_indexable: { label: "Not indexable", tone: "warn" },
  not_crawled: { label: "Not crawled yet", tone: "neutral" },
};
/** The pages Search Console sends the most clicks to, each with what the crawl says about it. */
export function priorityPages(
  view: LocalSearchView,
  pageHref: (websiteId: string, pageId: string) => string,
  limit = 5,
): PriorityPage[] {
  return (view.search_console?.top_pages ?? []).slice(0, limit).map((page) => ({
    label: pagePath(page.page),
    sub: `${countText(page.clicks)} clicks · ${countText(page.impressions)} impressions`,
    chip: indexChip[page.index_status ?? "not_crawled"],
    href:
      page.page_id && view.website_id
        ? pageHref(view.website_id, page.page_id)
        : null,
  }));
}
