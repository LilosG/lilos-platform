import {
  formatMetricDelta,
  formatMetricValue,
  type MetricFormat,
  type MetricValue,
} from "./data-display";

/**
 * Report-register display primitives.
 *
 * The platform renders one metric per card with uniform visual weight, so every
 * page reads as a console: nothing tells the eye which period is current or
 * which number is the answer. The client-facing dashboard this platform is
 * judged against does three things instead, and these are those three things:
 *
 *  1. Periods sit side by side, and the current one is inverted so it leads.
 *  2. A rank is coloured by how good the rank is, not by a uniform accent.
 *  3. Long lists show a useful head and disclose the rest on request.
 */

export interface ComparisonMetric {
  label: string;
  value: MetricValue;
  format?: MetricFormat;
  /**
   * Change against the comparison period, in the metric's own unit. Omit when
   * there is no prior period to compare against — a delta of zero and "no
   * comparison available" are different statements and must not render alike.
   */
  delta?: number | null;
}

export interface ComparisonPeriod {
  /** Human range, e.g. "Aug 1 – Aug 27". */
  label: string;
  /** Role of the period, e.g. "Current" or "Previous 27 days". */
  caption?: string;
  /** Inverts the card so the current period leads the row. */
  current?: boolean;
  metrics: ComparisonMetric[];
}

function metricRow(metric: ComparisonMetric): HTMLDivElement {
  const row = document.createElement("div");
  row.className = "ui-comparison-card__metric";

  const label = document.createElement("span");
  label.className = "ui-comparison-card__metric-label";
  label.textContent = metric.label;

  const value = document.createElement("span");
  value.className = "ui-comparison-card__metric-value";
  const format = metric.format ?? { unit: "text" as const };
  value.textContent = formatMetricValue(metric.value, format);

  row.append(label, value);

  if (metric.delta !== undefined && metric.delta !== null) {
    const delta = formatMetricDelta(metric.delta, format);
    const deltaEl = document.createElement("span");
    deltaEl.className = `ui-comparison-card__metric-delta delta--${delta.outcome}`;
    deltaEl.textContent = delta.text;
    row.append(deltaEl);
  }

  return row;
}

/**
 * One period as a card. The leading metric is rendered as a large serif figure;
 * the rest follow as hairline-separated label/value rows, which is what makes
 * the card read as a report rather than a stack of equal boxes.
 */
export function periodComparisonCard(period: ComparisonPeriod): HTMLElement {
  const card = document.createElement("article");
  card.className = "ui-card ui-comparison-card";
  if (period.current) {
    card.classList.add("ui-comparison-card--current");
    card.dataset.current = "true";
  }

  const body = document.createElement("div");
  body.className = "ui-card__body ui-comparison-card__body";

  const caption = document.createElement("p");
  caption.className = "ui-comparison-card__caption";
  caption.textContent =
    period.caption ?? (period.current ? "Current" : "Prior");

  const label = document.createElement("p");
  label.className = "ui-comparison-card__label";
  label.textContent = period.label;

  body.append(caption, label);

  const [lead, ...rest] = period.metrics;
  if (lead) {
    const leadWrap = document.createElement("div");
    leadWrap.className = "ui-comparison-card__lead";

    const leadValue = document.createElement("p");
    leadValue.className = "ui-comparison-card__lead-value";
    const leadFormat = lead.format ?? { unit: "text" as const };
    leadValue.textContent = formatMetricValue(lead.value, leadFormat);

    const leadLabel = document.createElement("p");
    leadLabel.className = "ui-comparison-card__lead-label";
    leadLabel.textContent = lead.label;

    leadWrap.append(leadValue, leadLabel);

    if (lead.delta !== undefined && lead.delta !== null) {
      const delta = formatMetricDelta(lead.delta, leadFormat);
      const deltaEl = document.createElement("p");
      deltaEl.className = `ui-comparison-card__lead-delta delta--${delta.outcome}`;
      deltaEl.textContent = `${delta.text} vs prior period`;
      leadWrap.append(deltaEl);
    }

    body.append(leadWrap);
  }

  if (rest.length > 0) {
    const rows = document.createElement("div");
    rows.className = "ui-comparison-card__metrics";
    for (const metric of rest) rows.append(metricRow(metric));
    body.append(rows);
  }

  card.append(body);
  return card;
}

/** Periods side by side, current first, on one row at desktop width. */
export function periodComparisonGrid(
  periods: ComparisonPeriod[],
): HTMLDivElement {
  const grid = document.createElement("div");
  grid.className = "ui-comparison-grid";
  grid.dataset.periods = String(periods.length);
  for (const period of periods) grid.append(periodComparisonCard(period));
  return grid;
}

export type RankTier =
  "top" | "page-one" | "reachable" | "distant" | "unranked";

/**
 * Search rank quality bands. These are the bands that change what an operator
 * does: 1-3 is won, 4-10 is on page one and worth defending, 11-20 is the
 * reachable band where work pays off, beyond that is a long game.
 */
export function rankTier(position: number | null | undefined): RankTier {
  if (position === null || position === undefined || !Number.isFinite(position))
    return "unranked";
  if (position <= 0) return "unranked";
  if (position <= 3) return "top";
  if (position <= 10) return "page-one";
  if (position <= 20) return "reachable";
  return "distant";
}

const TIER_TITLES: Record<RankTier, string> = {
  top: "Top three",
  "page-one": "Page one",
  reachable: "Within reach",
  distant: "Beyond page two",
  unranked: "Not ranking",
};

/**
 * A position rendered as a rank-coloured badge. Colour carries the band so a
 * long keyword table can be scanned for where the wins and the gaps are without
 * reading every number.
 */
export function rankBadge(
  position: number | null | undefined,
  options?: { precision?: number },
): HTMLSpanElement {
  const tier = rankTier(position);
  const badge = document.createElement("span");
  badge.className = `ui-rank-badge ui-rank-badge--${tier}`;
  badge.dataset.tier = tier;
  badge.title = TIER_TITLES[tier];

  if (tier === "unranked") {
    badge.textContent = "—";
    badge.setAttribute("aria-label", TIER_TITLES.unranked);
    return badge;
  }

  badge.textContent = formatMetricValue(position, {
    unit: "position",
    precision: options?.precision ?? 1,
  });
  badge.setAttribute(
    "aria-label",
    `Position ${badge.textContent} · ${TIER_TITLES[tier]}`,
  );
  return badge;
}

export interface SummaryItem {
  label: string;
  value: MetricValue;
  format?: MetricFormat;
  /** Escalates the item visually — used for counts that mean something is wrong. */
  tone?: "neutral" | "attention" | "critical";
  meta?: string;
}

/**
 * The answer to "is this working?" as a single strip, meant to sit at the top of
 * a page above any history. A page whose health summary is below a table of
 * every run ever executed cannot answer that question at a glance.
 */
export function healthSummary(items: SummaryItem[]): HTMLDivElement {
  const strip = document.createElement("div");
  strip.className = "ui-summary-strip";
  strip.dataset.items = String(items.length);

  for (const item of items) {
    const cell = document.createElement("div");
    cell.className = "ui-summary-strip__item";
    cell.dataset.tone = item.tone ?? "neutral";

    const label = document.createElement("p");
    label.className = "ui-summary-strip__label";
    label.textContent = item.label;

    const value = document.createElement("p");
    value.className = "ui-summary-strip__value";
    value.textContent = formatMetricValue(
      item.value,
      item.format ?? { unit: "text" },
    );

    cell.append(label, value);

    if (item.meta) {
      const meta = document.createElement("p");
      meta.className = "ui-summary-strip__meta";
      meta.textContent = item.meta;
      cell.append(meta);
    }

    strip.append(cell);
  }

  return strip;
}
