export type MetricValue = number | string | null | undefined;
export type MetricOutcome = "positive" | "negative" | "neutral";
export type MetricUnit =
  | "text"
  | "count"
  | "decimal"
  | "percentage"
  | "percentagePoint"
  | "position"
  | "currency"
  | "duration";

export interface MetricFormat {
  unit: MetricUnit;
  precision?: number;
  sourceScale?: "unit" | "ratio";
  currency?: string;
  durationUnit?: "milliseconds" | "seconds" | "minutes" | "hours";
  outcome?: "higher-is-better" | "lower-is-better" | "neutral";
}

export interface FormattedMetricDelta {
  text: string;
  outcome: MetricOutcome;
}

const wholeNumber = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

function numericValue(value: MetricValue): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function scaledPercentage(value: number, format: MetricFormat): number {
  return format.sourceScale === "ratio" ? value * 100 : value;
}

function fixed(value: number, precision: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
}

function durationInSeconds(value: number, unit: MetricFormat["durationUnit"]): number {
  if (unit === "milliseconds") return value / 1000;
  if (unit === "minutes") return value * 60;
  if (unit === "hours") return value * 3600;
  return value;
}

function formatDuration(value: number, format: MetricFormat): string {
  const seconds = Math.max(0, Math.round(durationInSeconds(value, format.durationUnit)));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${remainder}s`;
  return `${remainder}s`;
}

export function isNumericMetric(format?: MetricFormat): boolean {
  return Boolean(format && format.unit !== "text");
}

export function formatMetricValue(
  value: MetricValue,
  format: MetricFormat = { unit: "text" },
): string {
  if (format.unit === "text") return value === null || value === undefined || value === "" ? "—" : String(value);
  const numeric = numericValue(value);
  if (numeric === null) return "—";

  if (format.unit === "count") return wholeNumber.format(Math.round(numeric));
  if (format.unit === "percentage") return `${fixed(scaledPercentage(numeric, format), format.precision ?? 1)}%`;
  if (format.unit === "percentagePoint") return `${fixed(scaledPercentage(numeric, format), format.precision ?? 1)}pp`;
  if (format.unit === "position") return fixed(numeric, format.precision ?? 1);
  if (format.unit === "currency") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: format.currency ?? "USD",
      minimumFractionDigits: format.precision ?? 2,
      maximumFractionDigits: format.precision ?? 2,
    }).format(numeric);
  }
  if (format.unit === "duration") return formatDuration(numeric, format);
  return fixed(numeric, format.precision ?? 1);
}

export function metricOutcome(value: number, format: MetricFormat): MetricOutcome {
  if (value === 0 || format.outcome === "neutral" || !format.outcome) return "neutral";
  const improved = format.outcome === "higher-is-better" ? value > 0 : value < 0;
  return improved ? "positive" : "negative";
}

export function formatMetricDelta(
  value: number | null | undefined,
  format: MetricFormat,
): FormattedMetricDelta {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return { text: "—", outcome: "neutral" };
  }
  const rendered = formatMetricValue(Math.abs(value), format);
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return { text: `${sign}${rendered}`, outcome: metricOutcome(value, format) };
}

