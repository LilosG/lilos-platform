/**
 * Geometry for the report's charts. Pure functions: the Astro components only draw what they get,
 * so the same numbers always give the same picture and the picture can be tested without a browser.
 * A month with no data is a gap in the chart, never a bar of zero.
 */
export interface BarInput {
  /** The month, as a short label ("Aug"). */
  label: string;
  /** The year, shown under the first bar of a year ("2026"). */
  year: string | null;
  /** Null when the month has no data: drawn as a gap and named in the alternative text. */
  value: number | null;
  /** Stored before the source settled it: drawn lighter, with an asterisk. */
  partial: boolean;
  group: "compared" | "period";
}
export interface Bar {
  x: number;
  y: number;
  width: number;
  height: number;
  group: "compared" | "period";
  partial: boolean;
  label: string;
  year: string | null;
  /** The value above the bar, when there is room for it. */
  valueLabel: string | null;
  /** x of the bar's centre, for labels. */
  centre: number;
  missing: boolean;
}
export interface BarChartModel {
  width: number;
  height: number;
  plot: { left: number; right: number; top: number; bottom: number };
  bars: Bar[];
  ticks: { y: number; label: string }[];
  baseline: { y: number; label: string } | null;
  divider: number | null;
  /** The chart in words, for the SVG's text alternative. */
  description: string;
}
/** 12,400 as "12.4k"; axis labels only, never the figures a person reads. */
export function compact(value: number): string {
  if (value >= 1_000_000) return `${trim(value / 1_000_000)}m`;
  if (value >= 10_000) return `${trim(value / 1_000)}k`;
  return Math.round(value).toLocaleString("en-US");
}
const trim = (n: number) => String(Math.round(n * 10) / 10);
/** A round upper bound for the axis, with four steps. */
export function niceMaximum(value: number): number {
  if (value <= 0) return 4;
  const power = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) {
    if (value <= step * power) return step * power;
  }
  return 10 * power;
}
export interface BarChartOptions {
  title: string;
  bars: BarInput[];
  /** The compared period's monthly average, drawn as a dashed line. */
  baseline: number | null;
  baselineText: string;
  format: (value: number) => string;
  width?: number;
  height?: number;
}
export function barChart(options: BarChartOptions): BarChartModel {
  const width = options.width ?? 600;
  const height = options.height ?? (options.bars.length <= 4 ? 190 : 240);
  const plot = { left: 54, right: width - 12, top: 20, bottom: height - 46 };
  const count = options.bars.length;
  const gap = options.bars.some((b) => b.group === "compared") ? 18 : 0;
  const usable = plot.right - plot.left - gap;
  const slot = count ? usable / count : usable;
  const barWidth = Math.max(6, Math.min(44, slot * 0.64));
  const values = options.bars.flatMap((b) =>
    b.value === null ? [] : [b.value],
  );
  const top = niceMaximum(Math.max(options.baseline ?? 0, ...values, 0));
  const scale = (value: number) =>
    plot.bottom - (value / top) * (plot.bottom - plot.top);
  const showValues = count <= 14;
  let x = plot.left;
  let divider: number | null = null;
  const bars: Bar[] = options.bars.map((input, index) => {
    if (gap && index > 0 && input.group !== options.bars[index - 1].group) {
      divider = x + gap / 2;
      x += gap;
    }
    const left = x + (slot - barWidth) / 2;
    x += slot;
    const value = input.value;
    const y = value === null ? plot.bottom : scale(value);
    return {
      x: left,
      y,
      width: barWidth,
      height: value === null ? 0 : Math.max(1, plot.bottom - y),
      group: input.group,
      partial: input.partial,
      label: input.label,
      year: input.year,
      valueLabel:
        value !== null && showValues
          ? `${options.format(value)}${input.partial ? "*" : ""}`
          : null,
      centre: left + barWidth / 2,
      missing: value === null,
    };
  });
  const ticks = [0, 1, 2, 3, 4].map((step) => ({
    y: scale((top / 4) * step),
    label: compact((top / 4) * step),
  }));
  const named = options.bars
    .map((b) =>
      b.value === null
        ? `${b.label} ${b.year ?? ""} not synced`.replace("  ", " ")
        : `${b.label} ${b.year ?? ""}: ${options.format(b.value)}`.replace(
            "  ",
            " ",
          ),
    )
    .join("; ");
  return {
    width,
    height,
    plot,
    bars,
    ticks,
    baseline:
      options.baseline === null
        ? null
        : { y: scale(options.baseline), label: options.baselineText },
    divider,
    description: `${options.title}. ${named}.${options.baseline === null ? "" : ` ${options.baselineText}.`}`,
  };
}
export interface HorizontalRow {
  label: string;
  value: number;
  valueLabel: string;
  share: number;
}
export interface HorizontalModel {
  width: number;
  height: number;
  rowHeight: number;
  labelWidth: number;
  valueWidth: number;
  rows: (HorizontalRow & { y: number; barWidth: number })[];
  description: string;
}
/** Rows of horizontal bars scaled to the largest value; used for splits and star counts. */
export function horizontalBars(
  title: string,
  rows: HorizontalRow[],
  width = 600,
): HorizontalModel {
  const rowHeight = 30;
  const labelWidth = 150;
  const valueWidth = 160;
  const maximum = Math.max(1, ...rows.map((row) => row.value));
  const room = width - labelWidth - valueWidth;
  return {
    width,
    height: rows.length * rowHeight + 6,
    rowHeight,
    labelWidth,
    valueWidth,
    rows: rows.map((row, index) => ({
      ...row,
      y: index * rowHeight + 3,
      barWidth: row.value ? Math.max(2, (row.value / maximum) * room) : 0,
    })),
    description: `${title}. ${rows.map((row) => `${row.label}: ${row.valueLabel}, ${row.share}%`).join("; ")}.`,
  };
}
