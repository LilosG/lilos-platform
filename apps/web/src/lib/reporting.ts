/* Shared reporting UI primitives for Insights and SEO pages.
 *
 * Components:
 *   reportingPeriodSelector — date range tabs (7 | 28 | 90 days)
 *   comparisonKPI — KPI card with current value, delta, percent change
 *   timeSeriesChart — accessible SVG trend chart from daily series
 *   sourceFreshness — compact data freshness display
 *   formatDelta — human-readable delta formatting
 *   formatPercentDelta — safe percent change formatting
 *   performanceSummary — deterministic digest text
 */

import { formatTimestamp } from "./ui";

// ---------- Formatting helpers ----------

export function formatDelta(delta: number | null): string {
  if (delta === null) return "—";
  const prefix = delta > 0 ? "+" : "";
  return `${prefix}${delta.toLocaleString()}`;
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
  container.className = "period-selector";
  container.setAttribute("role", "radiogroup");
  container.setAttribute("aria-label", "Reporting period");

  const options = [7, 28, 90] as const;
  for (const days of options) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "period-selector__option";
    btn.textContent = `${days} days`;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", days === currentDays ? "true" : "false");
    if (days === currentDays) {
      btn.classList.add("period-selector__option--active");
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
): HTMLDivElement {
  const card = document.createElement("div");
  card.className = "kpi-card";

  const labelEl = document.createElement("p");
  labelEl.className = "kpi-card__label";
  labelEl.textContent = label;
  card.append(labelEl);

  const valueEl = document.createElement("p");
  valueEl.className = "kpi-card__value";
  valueEl.textContent = current !== null ? current.toLocaleString() : "—";
  card.append(valueEl);

  if (delta !== null || percentDelta !== null) {
    const deltaRow = document.createElement("div");
    deltaRow.className = `kpi-card__delta ${deltaClass(delta)}`;

    if (delta !== null) {
      const deltaEl = document.createElement("span");
      deltaEl.className = "kpi-card__delta-value";
      deltaEl.textContent = formatDelta(delta);
      deltaRow.append(deltaEl);
    }

    if (percentDelta !== null) {
      const pctEl = document.createElement("span");
      pctEl.className = "kpi-card__delta-pct";
      pctEl.textContent = formatPercentDelta(percentDelta) || "";
      deltaRow.append(pctEl);
    }

    const diffLabel = document.createElement("span");
    diffLabel.className = "kpi-card__delta-label";
    diffLabel.textContent = `vs previous ${previous !== null ? periodLabel() : "period"}`;
    deltaRow.append(diffLabel);

    card.append(deltaRow);
  }

  if (meta) {
    const metaEl = document.createElement("p");
    metaEl.className = "kpi-card__meta";
    metaEl.textContent = meta;
    card.append(metaEl);
  }

  return card;
}

function periodLabel(): string {
  return "period";
}

// ---------- Time series chart (accessible SVG) ----------

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export function timeSeriesChart(
  data: TimeSeriesPoint[],
  metricLabel: string,
  height = 200,
): HTMLElement {
  const container = document.createElement("div");
  container.className = "timeseries-chart";
  container.setAttribute("role", "img");
  container.setAttribute("aria-label", `${metricLabel} trend chart`);

  if (data.length === 0) {
    container.classList.add("timeseries-chart--empty");
    const empty = document.createElement("p");
    empty.className = "timeseries-chart__empty";
    empty.textContent = "No data available for this period";
    container.append(empty);
    return container;
  }

  const values = data.map((d) => d.value);
  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;

  const chartHeight = height;
  const barWidth = Math.max(4, Math.min(12, 280 / data.length));
  const totalWidth = data.length * (barWidth + 1);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute(
    "viewBox",
    `0 0 ${Math.max(totalWidth, 280)} ${chartHeight + 30}`,
  );
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", `${chartHeight + 30}`);
  svg.setAttribute("aria-hidden", "true");

  // Y-axis line
  const yAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
  yAxis.setAttribute("x1", "0");
  yAxis.setAttribute("y1", `${chartHeight}`);
  yAxis.setAttribute("x2", `${Math.max(totalWidth, 280)}`);
  yAxis.setAttribute("y2", `${chartHeight}`);
  yAxis.setAttribute("stroke", "var(--line)");
  yAxis.setAttribute("stroke-width", "1");
  svg.append(yAxis);

  // Bars
  for (let i = 0; i < data.length; i++) {
    const point = data[i];
    const barH = Math.max(2, ((point.value - minVal) / range) * chartHeight);
    const x = i * (barWidth + 1);
    const y = chartHeight - barH;

    const bar = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    bar.setAttribute("x", `${x}`);
    bar.setAttribute("y", `${y}`);
    bar.setAttribute("width", `${barWidth}`);
    bar.setAttribute("height", `${barH}`);
    bar.setAttribute("rx", "2");
    bar.setAttribute("fill", "var(--green)");
    bar.setAttribute("opacity", "0.85");

    // Add title for tooltip/accessibility
    const title = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "title",
    );
    title.textContent = `${point.date}: ${point.value.toLocaleString()}`;
    bar.append(title);

    svg.append(bar);
  }

  // X-axis labels (every ~7th point or ~7 labels)
  const labelInterval = Math.max(1, Math.floor(data.length / 7));
  for (let i = 0; i < data.length; i += labelInterval) {
    const point = data[i];
    const x = i * (barWidth + 1);
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", `${x}`);
    text.setAttribute("y", `${chartHeight + 18}`);
    text.setAttribute("font-size", "10");
    text.setAttribute("fill", "var(--muted)");
    // Show shortened date label (MM-DD)
    const parts = point.date.split("-");
    if (parts.length >= 3) {
      text.textContent = `${parts[1]}-${parts[2]}`;
    } else {
      text.textContent = point.date;
    }
    svg.append(text);
  }

  container.append(svg);

  // Accessible data table (hidden visually but readable by screen readers)
  const srTable = document.createElement("table");
  srTable.className = "sr-only";
  srTable.setAttribute("aria-label", `${metricLabel} daily values`);
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr><th>Date</th><th>${metricLabel}</th></tr>`;
  srTable.append(thead);
  const tbody = document.createElement("tbody");
  for (const point of data) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${point.date}</td><td>${point.value.toLocaleString()}</td>`;
    tbody.append(tr);
  }
  srTable.append(tbody);
  container.append(srTable);

  return container;
}

// ---------- Source freshness display ----------

export function sourceFreshness(
  lastSyncedAt: string | null,
  status: string,
): HTMLDivElement {
  const row = document.createElement("div");
  row.className = "source-freshness";

  const labelText =
    status === "never_synced"
      ? "Not yet synced"
      : status === "stale"
        ? "Data may be stale"
        : lastSyncedAt
          ? `Synced ${formatTimestamp(lastSyncedAt)}`
          : "Unknown";

  const label = document.createElement("span");
  label.className = "source-freshness__label";
  label.textContent = labelText;
  row.append(label);

  return row;
}

// ---------- Performance summary digest ----------

export function performanceSummary(
  statements: string[],
): HTMLDivElement | null {
  if (statements.length === 0) return null;

  const card = document.createElement("div");
  card.className = "card performance-summary";

  const header = document.createElement("div");
  header.className = "card__header";
  const title = document.createElement("h3");
  title.className = "card__title";
  title.textContent = "Performance summary";
  header.append(title);
  card.append(header);

  const body = document.createElement("div");
  body.className = "card__body";
  const list = document.createElement("ul");
  list.className = "performance-summary__list";
  for (const stmt of statements) {
    const li = document.createElement("li");
    li.textContent = stmt;
    list.append(li);
  }
  body.append(list);
  card.append(body);

  return card;
}

// ---------- Period label helper ----------

export function periodLabelFromDays(days: number): string {
  if (days === 7) return "7 days";
  if (days === 90) return "90 days";
  return "28 days";
}

export function formatDateRange(start: string, end: string): string {
  const fmt = (d: string) =>
    new Date(d + "T00:00:00Z").toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  return `${fmt(start)} – ${fmt(end)}`;
}

// ---------- Search Console data table ----------

export interface GscTableRow {
  primary: string;
  clicks: number;
  impressions: number;
  ctr: string;
  position: string;
}

export function buildGscDataTable(
  headers: string[],
  rows: GscTableRow[],
): HTMLDivElement {
  const table = document.createElement("div");
  table.className = "data-table";
  const t = document.createElement("table");
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr>`;
  t.append(thead);
  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="cell-meta"><span class="cell-meta__primary">${escHtml(row.primary)}</span></td>
      <td>${row.clicks.toLocaleString()}</td>
      <td>${row.impressions.toLocaleString()}</td>
      <td>${row.ctr}</td>
      <td>${row.position}</td>`;
    tbody.append(tr);
  }
  t.append(tbody);
  table.append(t);
  return table;
}

function escHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
