import {
  Chart,
  configureChartTheme,
  niceAxis,
  overlayChartOptions,
  reportingChartOptions,
  themedLineDataset,
  themedOverlayDataset,
  type NiceAxis,
} from "./chart-theme";

export type TrendPoint = {
  date: string;
  value: number | null;
};

export type TrendMetric = {
  key: string;
  label: string;
  points: TrendPoint[];
  formatValue?: (value: number) => string;
};

export type TrendChartModel = {
  labels: string[];
  values: Array<number | null>;
  minimum: number;
  stepSize: number;
  maximum: number;
};

export function trendChartModel(metric: TrendMetric): TrendChartModel {
  const values = metric.points.map((point) => point.value);
  const observedValues = values.filter(
    (value): value is number => value !== null,
  );
  const observedMinimum =
    observedValues.length > 0 ? Math.min(...observedValues) : 0;
  const observedMaximum =
    observedValues.length > 0 ? Math.max(...observedValues) : 1;
  const axis = niceAxis(observedMinimum, observedMaximum);

  return {
    labels: metric.points.map((point) => point.date),
    values,
    minimum: axis.minimum,
    stepSize: axis.stepSize,
    maximum: axis.maximum,
  };
}

export function trendSummary(metric: TrendMetric): string {
  const observed = metric.points.filter(
    (point): point is TrendPoint & { value: number } => point.value !== null,
  );
  if (observed.length === 0) {
    return `${metric.label} has no observations for this period.`;
  }
  const values = observed.map((point) => point.value);
  const missing = metric.points.length - observed.length;
  const format =
    metric.formatValue ?? ((value: number) => value.toLocaleString());
  return `${metric.label} ranged from ${format(Math.min(...values))} to ${format(Math.max(...values))} across ${observed.length} reported days${missing > 0 ? `, with ${missing} ${missing === 1 ? "day" : "days"} missing` : ""}.`;
}

function formatDateLabel(date: string, includeYear = false): string {
  // GA4 returns its date dimension in basic format (YYYYMMDD), which `new Date`
  // cannot parse -- every axis label read "Invalid Date". The API now normalises
  // this, but an axis must never render "Invalid Date" whatever it receives, so
  // basic format is accepted here too and an unparseable value falls back to
  // itself rather than to a lie.
  const normalized = /^\d{8}$/.test(date)
    ? `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
    : date;
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: includeYear ? "numeric" : undefined,
    timeZone: "UTC",
  });
}

export function reportingTrendChart(
  metrics: TrendMetric[],
  initialMetricKey: string,
): HTMLElement {
  const container = document.createElement("div");
  container.className = "reporting-trend";

  if (metrics.length === 0) {
    const empty = document.createElement("p");
    empty.className = "reporting-trend__empty";
    empty.textContent = "No trend data is available for this period.";
    container.append(empty);
    return container;
  }

  const switcher = document.createElement("div");
  switcher.className = "reporting-trend__switcher";
  switcher.setAttribute("role", "group");
  switcher.setAttribute("aria-label", "Chart metric");

  const visual = document.createElement("div");
  visual.className = "reporting-trend__visual";

  const summary = document.createElement("p");
  summary.className = "sr-only";
  const summaryId = `trend-summary-${Math.random().toString(36).slice(2)}`;
  summary.id = summaryId;

  let activeKey = metrics.some((metric) => metric.key === initialMetricKey)
    ? initialMetricKey
    : metrics[0].key;
  let chart: Chart<"line", Array<number | null>, string> | null = null;

  function render(metric: TrendMetric): void {
    chart?.destroy();
    chart = null;
    visual.replaceChildren();
    summary.textContent = trendSummary(metric);

    const observed = metric.points.filter(
      (point): point is TrendPoint & { value: number } => point.value !== null,
    );
    if (observed.length === 0) {
      const empty = document.createElement("p");
      empty.className = "reporting-trend__empty";
      empty.textContent = "No observations returned for this period.";
      visual.append(empty);
      return;
    }

    const model = trendChartModel(metric);
    const format =
      metric.formatValue ?? ((value: number) => value.toLocaleString());
    const canvas = document.createElement("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `${metric.label} daily trend`);
    canvas.setAttribute("aria-describedby", summaryId);
    canvas.tabIndex = 0;
    visual.append(canvas);
    const theme = configureChartTheme(container);

    chart = new Chart(canvas, {
      type: "line",
      data: {
        labels: model.labels,
        datasets: [themedLineDataset(theme, metric.label, model.values)],
      },
      options: reportingChartOptions({
        theme,
        axis: {
          minimum: model.minimum,
          stepSize: model.stepSize,
          maximum: model.maximum,
        },
        formatDate: formatDateLabel,
        formatValue: format,
        metricLabel: metric.label,
      }),
    });
  }

  for (const metric of metrics) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "reporting-trend__metric";
    button.textContent = metric.label;
    button.setAttribute("aria-pressed", String(metric.key === activeKey));
    button.addEventListener("click", () => {
      activeKey = metric.key;
      for (const option of switcher.querySelectorAll<HTMLButtonElement>(
        ".reporting-trend__metric",
      )) {
        option.setAttribute("aria-pressed", String(option === button));
      }
      render(metric);
    });
    switcher.append(button);
  }

  container.append(switcher, visual, summary);
  render(metrics.find((metric) => metric.key === activeKey) ?? metrics[0]);
  return container;
}

export type OverlayChartModel = {
  labels: string[];
  primary: { values: Array<number | null>; axis: NiceAxis };
  secondary: { values: Array<number | null>; axis: NiceAxis };
};

/**
 * Aligns two metrics onto one set of labels, each keeping its own scale.
 *
 * Two series only compare honestly if they share an x axis, so the union of
 * both date sets is used and a metric with no observation on a given day
 * contributes a gap rather than a zero — a missing day and a zero day mean
 * different things and must not render alike.
 */
export function overlayChartModel(
  primary: TrendMetric,
  secondary: TrendMetric,
): OverlayChartModel {
  const labels = [
    ...new Set([
      ...primary.points.map((point) => point.date),
      ...secondary.points.map((point) => point.date),
    ]),
  ].sort();

  const align = (metric: TrendMetric): Array<number | null> => {
    const byDate = new Map(
      metric.points.map((point) => [point.date, point.value]),
    );
    return labels.map((label) => byDate.get(label) ?? null);
  };

  const axisFor = (values: Array<number | null>): NiceAxis => {
    const observed = values.filter((value): value is number => value !== null);
    return niceAxis(
      observed.length > 0 ? Math.min(...observed) : 0,
      observed.length > 0 ? Math.max(...observed) : 1,
    );
  };

  const primaryValues = align(primary);
  const secondaryValues = align(secondary);

  return {
    labels,
    primary: { values: primaryValues, axis: axisFor(primaryValues) },
    secondary: { values: secondaryValues, axis: axisFor(secondaryValues) },
  };
}

/**
 * Two metrics on one plot with a shared legend.
 *
 * The switcher chart answers "how did impressions move?" one metric at a time;
 * it cannot answer "did clicks follow impressions?", which is the question an
 * operator actually asks of search data. This renders both at once, each on its
 * own axis, in the sage/gold pairing the client dashboard uses.
 */
export function reportingOverlayChart(
  primary: TrendMetric,
  secondary: TrendMetric,
): HTMLElement {
  const container = document.createElement("div");
  container.className = "reporting-trend reporting-trend--overlay";

  const model = overlayChartModel(primary, secondary);
  const observedCount = [
    ...model.primary.values,
    ...model.secondary.values,
  ].filter((value) => value !== null).length;

  if (model.labels.length === 0 || observedCount === 0) {
    const empty = document.createElement("p");
    empty.className = "reporting-trend__empty";
    empty.textContent = "No observations returned for this period.";
    container.append(empty);
    return container;
  }

  const theme = configureChartTheme(container);

  const legend = document.createElement("div");
  legend.className = "reporting-trend__legend";
  [primary, secondary].forEach((metric, index) => {
    const item = document.createElement("span");
    item.className = "reporting-trend__legend-item";
    const swatch = document.createElement("span");
    swatch.className = "reporting-trend__legend-swatch";
    swatch.setAttribute("aria-hidden", "true");
    swatch.style.background = theme.series[index % theme.series.length];
    item.append(swatch, document.createTextNode(metric.label));
    legend.append(item);
  });

  const visual = document.createElement("div");
  visual.className = "reporting-trend__visual";

  const summary = document.createElement("p");
  summary.className = "sr-only";
  const summaryId = `overlay-summary-${Math.random().toString(36).slice(2)}`;
  summary.id = summaryId;
  summary.textContent = `${trendSummary(primary)} ${trendSummary(secondary)}`;

  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    `${primary.label} and ${secondary.label} daily trend`,
  );
  canvas.setAttribute("aria-describedby", summaryId);
  canvas.tabIndex = 0;
  visual.append(canvas);

  const primaryFormat =
    primary.formatValue ?? ((value: number) => value.toLocaleString());
  const secondaryFormat =
    secondary.formatValue ?? ((value: number) => value.toLocaleString());

  container.append(legend, visual, summary);

  new Chart(canvas, {
    type: "line",
    data: {
      labels: model.labels,
      datasets: [
        themedOverlayDataset(
          theme,
          primary.label,
          model.primary.values,
          0,
          "yPrimary",
        ),
        themedOverlayDataset(
          theme,
          secondary.label,
          model.secondary.values,
          1,
          "ySecondary",
        ),
      ],
    },
    options: overlayChartOptions({
      theme,
      primary: {
        axis: model.primary.axis,
        label: primary.label,
        formatValue: primaryFormat,
      },
      secondary: {
        axis: model.secondary.axis,
        label: secondary.label,
        formatValue: secondaryFormat,
      },
      formatDate: formatDateLabel,
    }),
  });

  return container;
}
