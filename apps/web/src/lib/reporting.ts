/* Shared reporting UI primitives for Insights and SEO pages.
 *
 * Components:
 *   reportingPeriodSelector — date range tabs (7 | 28 | 90 days)
 *   comparisonKPI — KPI card with current value, delta, percent change
 *   toTimeSeriesPoints — preserves missing observations for shared charts
 *   sourceFreshness — compact data freshness display
 *   formatDelta — human-readable delta formatting
 *   formatPercentDelta — safe percent change formatting
 *   performanceSummary — deterministic digest text
 *   searchPerformanceTable — bounded, rank-coloured query/page table
 */

import {
  buildDataTable,
  formatTimestamp,
  rankBadge,
  type TableColumn,
} from "./ui";

// ---------- Formatting helpers ----------

export function formatDelta(delta: number | null): string {
  if (delta === null) return "—";
  const prefix = delta > 0 ? "+" : "";
  return `${prefix}${delta.toLocaleString()}`;
}

export function formatMetricDelta(
  metricKey: string,
  delta: number | null,
): string {
  if (metricKey !== "ctr" || delta === null) return formatDelta(delta);
  const percentagePoints = Number((delta * 100).toFixed(1));
  return `${percentagePoints > 0 ? "+" : ""}${percentagePoints.toFixed(1)}pp`;
}

export function formatPercentDelta(pct: number | null): string | null {
  if (pct === null) return null;
  if (!isFinite(pct)) return null;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

export function deltaClass(delta: number | null): string {
  if (delta === null) return "delta--neutral";
  if (delta > 0) return "delta--positive";
  if (delta < 0) return "delta--negative";
  return "delta--neutral";
}

const INVERTED_METRICS = new Set([
  "position",
  "avg_position",
  "average_position",
  "bounce_rate",
  "bounceRate",
]);

export function metricAwareDeltaClass(
  metricKey: string,
  delta: number | null,
): string {
  if (delta === null) return "delta--neutral";
  const inverted = INVERTED_METRICS.has(metricKey);
  if (inverted) {
    if (delta < 0) return "delta--positive";
    if (delta > 0) return "delta--negative";
    return "delta--neutral";
  }
  if (delta > 0) return "delta--positive";
  if (delta < 0) return "delta--negative";
  return "delta--neutral";
}

export function deltaLabel(delta: number | null): string {
  if (delta === null) return "No change";
  if (delta > 0) return "Increased";
  if (delta < 0) return "Decreased";
  return "Unchanged";
}

// ---------- Reporting period selector ----------

export function reportingPeriodSelector(
  currentDays: number,
  onChange: (days: number) => void,
): HTMLDivElement {
  const container = document.createElement("div");
  container.className = "ui-segmented";
  container.setAttribute("role", "radiogroup");
  container.setAttribute("aria-label", "Reporting period");

  const options = [7, 28, 90] as const;
  for (const days of options) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ui-segmented__option";
    btn.textContent = `${days} days`;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", days === currentDays ? "true" : "false");
    if (days === currentDays) {
      btn.classList.add("ui-segmented__option--active");
    }
    btn.addEventListener("click", () => {
      if (days !== currentDays) onChange(days);
    });
    container.append(btn);
  }
  return container;
}

// ---------- KPI comparison card ----------

export function comparisonKPI(
  label: string,
  current: number | null,
  previous: number | null,
  delta: number | null,
  percentDelta: number | null,
  meta?: string,
  metricKey?: string,
  comparisonPeriod?: string,
): HTMLDivElement {
  const card = document.createElement("div");
  card.className = "ui-card ui-metric-card";
  const body = document.createElement("div");
  body.className = "ui-card__body";

  const labelEl = document.createElement("p");
  labelEl.className = "ui-metric-card__label";
  labelEl.textContent = label;
  body.append(labelEl);

  const valueEl = document.createElement("p");
  valueEl.className = "ui-metric-card__value";
  valueEl.textContent = current !== null ? current.toLocaleString() : "No data";
  if (current === null) valueEl.classList.add("ui-metric-card__value--missing");
  body.append(valueEl);

  if (delta !== null || percentDelta !== null) {
    const deltaCls = metricKey
      ? metricAwareDeltaClass(metricKey, delta)
      : deltaClass(delta);
    const deltaRow = document.createElement("div");
    deltaRow.className = `ui-metric-card__delta ${deltaCls}`;

    if (delta !== null) {
      const deltaEl = document.createElement("span");
      deltaEl.className = "ui-metric-card__delta-value";
      deltaEl.textContent = metricKey
        ? formatMetricDelta(metricKey, delta)
        : formatDelta(delta);
      deltaRow.append(deltaEl);
    }

    if (percentDelta !== null) {
      const pctEl = document.createElement("span");
      pctEl.className = "ui-metric-card__delta-percent";
      pctEl.textContent = formatPercentDelta(percentDelta) || "";
      deltaRow.append(pctEl);
    }

    const diffLabel = document.createElement("span");
    diffLabel.className = "ui-metric-card__delta-label";
    diffLabel.textContent = `vs previous ${comparisonPeriod ?? "period"}`;
    deltaRow.append(diffLabel);

    body.append(deltaRow);
  }

  if (previous === null) {
    const prior = document.createElement("p");
    prior.className = "ui-metric-card__meta";
    prior.textContent = "No comparable prior-period data";
    body.append(prior);
  }

  if (meta) {
    const metaEl = document.createElement("p");
    metaEl.className = "ui-metric-card__meta";
    metaEl.textContent = meta;
    body.append(metaEl);
  }

  card.append(body);
  return card;
}

// ---------- Time series data ----------

export interface TimeSeriesPoint {
  date: string;
  value: number | null;
}

export function toTimeSeriesPoints(
  data: { date: string; metrics: Record<string, number> }[],
  metricKey: string,
): TimeSeriesPoint[] {
  return data.map((d) => ({
    date: d.date,
    value: d.metrics[metricKey] ?? null,
  }));
}

// ---------- Source freshness display ----------

export function sourceFreshness(
  lastSyncedAt: string | null,
  status: string,
): HTMLDivElement {
  const row = document.createElement("div");
  row.className = "source-freshness";

  const labelText = formatFreshness(lastSyncedAt, status);

  const label = document.createElement("span");
  label.className = "source-freshness__label";
  label.textContent = labelText;
  row.append(label);

  return row;
}

export function formatFreshness(
  lastSyncedAt: string | null,
  status: string,
): string {
  return status === "never_synced"
    ? "Not yet synced"
    : status === "stale"
      ? "Data may be stale"
      : lastSyncedAt
        ? `Synced ${formatTimestamp(lastSyncedAt)}`
        : "Freshness unavailable";
}

// ---------- Performance summary digest ----------

export function performanceSummary(
  statements: string[],
): HTMLDivElement | null {
  if (statements.length === 0) return null;

  const summary = document.createElement("div");
  summary.className = "performance-summary";
  const prose = document.createElement("p");
  const label = document.createElement("strong");
  label.textContent = "Performance summary. ";
  prose.append(
    label,
    document.createTextNode(statements.slice(0, 3).join(" ")),
  );
  summary.append(prose);
  return summary;
}

// ---------- Period label helper ----------

export function periodLabelFromDays(days: number): string {
  return `${days} days`;
}

export function formatDateRange(start: string, end: string): string {
  const fmt = (d: string) =>
    new Date(d + "T00:00:00Z").toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
  return `${fmt(start)} – ${fmt(end)}`;
}

// ---------- Search Console data table ----------

export interface SearchPerformanceRow {
  primary: string;
  clicks: number | null;
  impressions: number | null;
  ctr: number | null;
  position: number | null;
}

/**
 * Search Console rows as a bounded, rank-coloured table.
 *
 * Both Insights and SEO rendered this themselves, and both got it wrong in the
 * same way: the table was hard-truncated to five rows, and the remainder was
 * either on another page or behind a one-way "View all" that destroyed its own
 * control when clicked. Data the browser already holds should not require a
 * navigation to read. The head leads, the rest discloses in place and collapses
 * again, and position is coloured by rank band so a long table can be scanned
 * for wins and gaps rather than read number by number.
 */
export function searchPerformanceTable(
  primaryHeader: string,
  rows: SearchPerformanceRow[],
  noun: string,
  initialRows = 5,
): HTMLElement {
  const columns: TableColumn<SearchPerformanceRow>[] = [
    { key: "primary", header: primaryHeader, render: (row) => row.primary },
    {
      key: "clicks",
      header: "Clicks",
      format: { unit: "count" },
      render: (row) => row.clicks,
    },
    {
      key: "impressions",
      header: "Impressions",
      format: { unit: "count" },
      render: (row) => row.impressions,
    },
    {
      key: "ctr",
      header: "CTR",
      format: { unit: "percentage", sourceScale: "ratio" },
      render: (row) => row.ctr,
    },
    {
      key: "position",
      header: "Position",
      width: "content",
      render: (row) => rankBadge(row.position),
    },
  ];

  return buildDataTable(columns, rows, {
    disclosure: { initialRows, noun },
    emptyHeading: `No ${noun} reported`,
    emptyDescription: "Search Console returned no rows for this period yet.",
  });
}
