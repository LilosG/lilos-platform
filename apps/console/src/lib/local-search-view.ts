import type { LocalSearchView } from "../adapters/local-search";
import type { GbpMetric, GbpPerformanceView } from "../adapters/gbp";
import {
  connectionChips,
  connectionState,
  syncChip,
  type Chip,
  type ConnectionState,
  type Tone,
} from "./status";
import {
  countText,
  ctrText,
  dateText,
  fmt,
  positionText,
  rangeText,
  shortDate,
} from "./present";
import { pagePath } from "./opportunity-view";
type Report = NonNullable<LocalSearchView["search_console"]>;
type GbpTotal = GbpPerformanceView["profile_views"]["current"];
/** One metric tile: a number with its change, or a typed reason there is no number. */
export interface Tile {
  label: string;
  value: string;
  description: string;
  /** Whole-percent change against the previous period; null when there is none. */
  trend: number | null;
  missing: boolean;
}
const round = (percent: number | null | undefined): number | null =>
  percent === null || percent === undefined ? null : Math.round(percent);
const previousText = (days: number) => `vs previous ${days} days`;
const missingTile = (label: string, value: string, note: string): Tile => ({
  label,
  value,
  description: note,
  trend: null,
  missing: true,
});
/** Why a Search Console number is missing, from the report's typed state. */
function searchGap(report: Report | null): { value: string; note: string } {
  if (!report || !report.connected)
    return { value: "Not connected", note: "Connect Search Console" };
  return { value: "No data", note: "Connected, nothing reported yet" };
}
function searchTile(
  report: Report | null,
  key: "clicks" | "impressions",
  label: string,
  days: number,
): Tile {
  const metric = report?.metrics[key];
  if (!report || !metric || metric.current === null) {
    const gap = searchGap(report);
    return missingTile(label, gap.value, gap.note);
  }
  return {
    label,
    value: fmt(metric.current),
    description:
      metric.percent_delta === null ? "No earlier period" : previousText(days),
    trend: round(metric.percent_delta),
    missing: false,
  };
}
const GBP_GAP: Record<GbpTotal["availability"], { v: string; n: string }> = {
  available: { v: "", n: "" },
  partial: { v: "", n: "" },
  no_data: { v: "No data", n: "Connected, nothing reported yet" },
  not_synced: { v: "First sync pending", n: "Scheduled, not run yet" },
  not_connected: { v: "Not connected", n: "Connect Business Profile" },
};
export function gbpTile(
  perf: GbpPerformanceView | null,
  metric: GbpMetric,
  label: string,
  days: number,
): Tile {
  const found = perf?.metrics.find((m) => m.metric === metric);
  if (!perf || !found)
    return missingTile(
      label,
      "Unavailable",
      "Business Profile data failed to load",
    );
  const total = found.current;
  if (total.value === null) {
    const gap = GBP_GAP[total.availability];
    return missingTile(label, gap.v, gap.n);
  }
  const partial = total.availability === "partial";
  return {
    label,
    value: fmt(total.value),
    description: partial
      ? `Partial period · ${total.days_covered} of ${total.days_expected} days synced`
      : found.change_percent === null
        ? "No earlier period"
        : previousText(days),
    trend: partial ? null : round(found.change_percent),
    missing: false,
  };
}
/** The Overview's five tiles: Search Console clicks and impressions, then three profile actions. */
export function overviewTiles(
  search: LocalSearchView,
  gbp: GbpPerformanceView | null,
  days: number,
): Tile[] {
  const report = search.search_console;
  return [
    searchTile(report, "clicks", "Search clicks", days),
    searchTile(report, "impressions", "Search impressions", days),
    gbpTile(gbp, "CALL_CLICKS", "GBP calls", days),
    gbpTile(gbp, "WEBSITE_CLICKS", "Website clicks", days),
    gbpTile(gbp, "BUSINESS_DIRECTION_REQUESTS", "Direction requests", days),
  ];
}
/** The Search Console tab's four tiles. Position improves as it falls, so its trend is inverted. */
export function searchTiles(search: LocalSearchView, days: number): Tile[] {
  const report = search.search_console;
  const ctr = report?.metrics.ctr;
  const position = report?.metrics.position;
  const gap = searchGap(report);
  return [
    searchTile(report, "clicks", "Search clicks", days),
    searchTile(report, "impressions", "Impressions", days),
    !report || !ctr || ctr.current === null
      ? missingTile("Click-through rate", gap.value, gap.note)
      : {
          label: "Click-through rate",
          value: ctrText(ctr.current),
          description:
            ctr.delta === null ? "No earlier period" : previousText(days),
          trend: null,
          missing: false,
        },
    !report || !position || position.current === null
      ? missingTile("Average position", gap.value, gap.note)
      : {
          label: "Average position",
          value: positionText(position.current),
          description:
            position.percent_delta === null
              ? "No earlier period"
              : previousText(days),
          trend:
            position.percent_delta === null
              ? null
              : -Math.round(position.percent_delta),
          missing: false,
        },
  ];
}
/** Local rank grids are not collected yet, so each rank tile says so instead of showing a number. */
export const rankingTiles = (): Tile[] =>
  ["Local visibility", "Average local rank", "Top 3 share"].map((label) =>
    missingTile(label, "Not tracked", "Needs Local Visibility Grid scans"),
  );
export interface ChartPoint {
  /** Calendar day, "YYYY-MM-DD". */
  day: string;
  value: number;
}
export interface ChartModel {
  line: string;
  area: string;
  dots: { x: number; y: number }[];
  grid: { y: number; label: string }[];
  labels: { x: number; text: string; anchor: "start" | "middle" | "end" }[];
}
const compact = (value: number) =>
  value >= 10000
    ? `${Math.round(value / 1000)}k`
    : value >= 1000
      ? `${(value / 1000).toFixed(1)}k`
      : String(Math.round(value));
const X0 = 38;
const X1 = 560;
const Y_TOP = 18;
const Y_BASE = 140;
/** A line chart over days that have a value. A day with none is a gap in the data, not zero. */
export function chartModel(points: ChartPoint[]): ChartModel | null {
  const sorted = [...points].sort((a, b) => a.day.localeCompare(b.day));
  if (sorted.length < 2) return null;
  const max = Math.max(...sorted.map((p) => p.value), 1);
  const xs = sorted.map((_, i) => X0 + ((X1 - X0) * i) / (sorted.length - 1));
  const ys = sorted.map((p) => Y_BASE - ((Y_BASE - Y_TOP) * p.value) / max);
  const line = xs
    .map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)} ${ys[i].toFixed(1)}`)
    .join(" ");
  const middle = Math.floor((sorted.length - 1) / 2);
  return {
    line,
    area: `${line} L${X1} ${Y_BASE} L${X0} ${Y_BASE} Z`,
    dots: sorted.length <= 12 ? xs.map((x, i) => ({ x, y: ys[i] })) : [],
    grid: [0, 1, 2, 3].map((i) => ({
      y: Y_BASE - ((Y_BASE - Y_TOP) * i) / 3,
      label: compact((max * i) / 3),
    })),
    labels: [
      { x: X0, text: shortDate(sorted[0].day), anchor: "start" },
      { x: xs[middle], text: shortDate(sorted[middle].day), anchor: "middle" },
      {
        x: X1,
        text: shortDate(sorted[sorted.length - 1].day),
        anchor: "end",
      },
    ],
  };
}
/** Search Console's daily clicks, from the series the source returned. */
export function clickSeries(report: Report | null): ChartPoint[] {
  return (report?.series ?? []).flatMap((row) =>
    typeof row.date === "string" && typeof row.clicks === "number"
      ? [{ day: row.date, value: row.clicks }]
      : [],
  );
}
export interface MomentumView {
  chip: Chip;
  stats: { label: string; value: string; trend: number | null }[];
  chart: ChartModel | null;
  period: string;
}
// Lower is better: a falling average position is an improvement, so its trend is inverted.
const positionTrend = (report: Report): number | null => {
  const change = report.metrics.position?.percent_delta;
  return change === null || change === undefined ? null : -Math.round(change);
};
/** Search momentum: clicks against the previous period, with the average position beside it. */
export function momentum(search: LocalSearchView): MomentumView | null {
  const report = search.search_console;
  if (!report || !report.connected) return null;
  const clicks = report.metrics.clicks;
  const change = round(clicks?.percent_delta);
  const chip: Chip =
    change === null
      ? { label: "No comparison yet", tone: "neutral" }
      : change > 0
        ? { label: "Growing", tone: "" }
        : change < 0
          ? { label: "Declining", tone: "warn" }
          : { label: "Steady", tone: "neutral" };
  const position = report.metrics.position;
  return {
    chip,
    stats: [
      {
        label: "Search clicks",
        value: countText(clicks?.current),
        trend: change,
      },
      {
        label: "Impressions",
        value: countText(report.metrics.impressions?.current),
        trend: round(report.metrics.impressions?.percent_delta),
      },
      {
        label: "Average position",
        value: positionText(position?.current),
        trend: positionTrend(report),
      },
    ],
    chart: chartModel(clickSeries(report)),
    period: report.range ? rangeText(report.range.start, report.range.end) : "",
  };
}
export interface QueryRow {
  query: string;
  clicks: number | null;
  impressions: number | null;
  clicksText: string;
  impressionsText: string;
  ctrText: string;
  position: number | null;
  positionText: string;
}
export function queryRows(search: LocalSearchView, limit?: number): QueryRow[] {
  const rows = (search.search_console?.top_queries ?? []).map((q) => ({
    query: q.query,
    clicks: q.clicks,
    impressions: q.impressions,
    clicksText: countText(q.clicks),
    impressionsText: countText(q.impressions),
    ctrText: ctrText(q.ctr),
    position: q.position,
    positionText: positionText(q.position),
  }));
  return limit ? rows.slice(0, limit) : rows;
}
export interface PageRow {
  label: string;
  clicksText: string;
  impressionsText: string;
  positionText: string;
}
export function pageRows(search: LocalSearchView): PageRow[] {
  return (search.search_console?.top_pages ?? []).map((p) => ({
    label: pagePath(p.page),
    clicksText: countText(p.clicks),
    impressionsText: countText(p.impressions),
    positionText: positionText(p.position),
  }));
}
const freshnessLabel: Record<string, string> = {
  fresh: "Up to date",
  current: "Up to date",
  stale: "Out of date",
  never_synced: "Never synced",
};
const syncFailure: Record<string, string> = {
  PROVIDER_RATE_LIMITED: "Google limited the request; it will be retried.",
  INTEGRATION_RECONNECT_REQUIRED: "Google needs to be reconnected.",
  PROVIDER_ACCESS_DENIED: "Google denied access to this property.",
  PROVIDER_UNAVAILABLE: "Google was unavailable; it will be retried.",
};
const sourceName = { search_console: "Search Console", analytics: "Analytics" };
export interface SourceDetails {
  chip: Chip;
  connection: { label: string; chip: Chip };
  sources: { name: string; chip: Chip; detail: string }[];
  syncs: { name: string; chip: Chip; when: string; note: string }[];
}
const worse = (a: Tone, b: Tone): Tone =>
  a === "error" || b === "error"
    ? "error"
    : a === "warn" || b === "warn"
      ? "warn"
      : a || b;
/** Everything the header chip stands for: Google's state, each source's freshness and recent syncs. */
export function sourceDetails(search: LocalSearchView): SourceDetails {
  const state: ConnectionState = connectionState(search.google_status);
  const connection = connectionChips[state];
  const report = search.search_console;
  const sources: SourceDetails["sources"] = [];
  if (report?.connected) {
    const stale = report.freshness.status !== "fresh";
    sources.push({
      name: "Search Console",
      chip: stale
        ? { label: "Out of date", tone: "warn" }
        : { label: "Up to date", tone: "" },
      detail: report.freshness.last_synced_at
        ? `Last synced ${dateText(report.freshness.last_synced_at)}`
        : (freshnessLabel[report.freshness.status] ?? "Not synced yet"),
    });
  } else
    sources.push({
      name: "Search Console",
      chip: { label: "Not connected", tone: "neutral" },
      detail: "Connect it in Integrations to see search data.",
    });
  if (search.analytics_availability === "available")
    sources.push({
      name: "Analytics",
      chip: search.analytics?.connected
        ? { label: "Connected", tone: "" }
        : { label: "Not connected", tone: "neutral" },
      detail: search.analytics?.freshness.last_synced_at
        ? `Last synced ${dateText(search.analytics.freshness.last_synced_at)}`
        : "Not synced yet",
    });
  const syncs = search.syncs.slice(0, 6).map((sync) => ({
    name: `${sourceName[sync.source]} sync`,
    chip: syncChip(sync.status),
    when: dateText(sync.completed_at ?? sync.started_at),
    note: sync.failure_code
      ? (syncFailure[sync.failure_code] ?? "The sync did not finish.")
      : "",
  }));
  const tone = [
    connection.tone,
    ...sources.map((s) => s.chip.tone),
    ...syncs.slice(0, 1).map((s) => s.chip.tone),
  ].reduce<Tone>(worse, "");
  const label =
    state !== "connected"
      ? connection.label
      : tone === "error" || tone === "warn"
        ? "Data needs attention"
        : "Data up to date";
  return {
    chip: { label, tone: state === "connected" ? tone : connection.tone },
    connection: { label: connection.label, chip: connection },
    sources,
    syncs,
  };
}
export const TABS = [
  ["Overview", ""],
  ["Rankings", "rankings"],
  ["Google Business Profile", "google-business-profile"],
  ["Search Console", "search-console"],
  ["Pages", "pages"],
  ["Technical", "technical"],
] as const;
