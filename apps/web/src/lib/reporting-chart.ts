import {
  Chart,
  configureChartTheme,
  niceAxis,
  reportingChartOptions,
  themedLineDataset,
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
