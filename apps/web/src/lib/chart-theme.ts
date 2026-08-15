import {
  CategoryScale,
  Chart,
  Filler,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
  type ChartDataset,
  type ChartOptions,
  type ScriptableContext,
  type TooltipItem,
} from "chart.js";

Chart.register(
  CategoryScale,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Filler,
  Tooltip,
);

export interface ChartTheme {
  series: string[];
  fillStart: string;
  fillEnd: string;
  grid: string;
  gridVertical: string;
  axis: string;
  tooltipBackground: string;
  tooltipForeground: string;
  fontFamily: string;
  captionSize: number;
  captionLineHeight: number;
  lineWidth: number;
}

export interface NiceAxis {
  minimum: number;
  stepSize: number;
  maximum: number;
}

let configured = false;

function cssNumber(styles: CSSStyleDeclaration, property: string): number {
  const value = styles.getPropertyValue(property).trim();
  if (value.endsWith("rem")) {
    return Number.parseFloat(value) * Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
  }
  return Number.parseFloat(value) || 12;
}

function themeFrom(element: HTMLElement): ChartTheme {
  const styles = getComputedStyle(element.isConnected ? element : document.documentElement);
  return {
    series: [1, 2, 3, 4, 5, 6].map(
      (index) => styles.getPropertyValue(`--chart-series-${index}`).trim() || "currentColor",
    ),
    fillStart: styles.getPropertyValue("--chart-series-1-fill-start").trim() || "currentColor",
    fillEnd: styles.getPropertyValue("--chart-series-1-fill-end").trim() || "transparent",
    grid: styles.getPropertyValue("--chart-grid").trim() || "transparent",
    gridVertical: styles.getPropertyValue("--chart-grid-vertical").trim() || "transparent",
    axis: styles.getPropertyValue("--chart-axis").trim() || "currentColor",
    tooltipBackground: styles.getPropertyValue("--chart-tooltip-background").trim() || "currentColor",
    tooltipForeground: styles.getPropertyValue("--chart-tooltip-foreground").trim() || "currentColor",
    fontFamily: styles.getPropertyValue("--font-family-sans").trim() || "sans-serif",
    captionSize: cssNumber(styles, "--type-caption-size"),
    captionLineHeight: cssNumber(styles, "--type-caption-line"),
    lineWidth: cssNumber(styles, "--chart-line-width"),
  };
}

export function configureChartTheme(element: HTMLElement): ChartTheme {
  const theme = themeFrom(element);
  if (!configured) {
    Chart.defaults.animation = false;
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.color = theme.axis;
    Chart.defaults.font.family = theme.fontFamily;
    Chart.defaults.font.size = theme.captionSize;
    Chart.defaults.font.lineHeight =
      theme.captionLineHeight / theme.captionSize;
    Chart.defaults.elements.line.tension = 0.25;
    Chart.defaults.elements.line.fill = "start";
    Chart.defaults.elements.point.radius = 0;
    Chart.defaults.elements.point.hoverRadius = 4;
    Chart.defaults.elements.point.hitRadius = 14;
    Chart.defaults.plugins.tooltip.displayColors = false;
    Chart.defaults.plugins.tooltip.backgroundColor = theme.tooltipBackground;
    Chart.defaults.plugins.tooltip.titleColor = theme.tooltipForeground;
    Chart.defaults.plugins.tooltip.bodyColor = theme.tooltipForeground;
    Chart.defaults.plugins.tooltip.borderColor = theme.grid;
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.titleFont = {
      family: theme.fontFamily,
      size: theme.captionSize,
      weight: 600,
    };
    Chart.defaults.plugins.tooltip.bodyFont = {
      family: theme.fontFamily,
      size: theme.captionSize,
    };
    configured = true;
  }
  return theme;
}

function roundStep(value: number): number {
  const exponent = Math.floor(Math.log10(value));
  const magnitude = 10 ** exponent;
  const fraction = value / magnitude;
  const factor = fraction <= 1.5 ? 1 : fraction <= 3 ? 2 : fraction <= 7 ? 5 : 10;
  return factor * magnitude;
}

export function niceAxis(
  observedMinimum: number,
  observedMaximum: number,
  beginAtZero = false,
): NiceAxis {
  const safeMinimum = Number.isFinite(observedMinimum) ? observedMinimum : 0;
  const safeMaximum = Number.isFinite(observedMaximum)
    ? observedMaximum
    : safeMinimum + 1;
  const maximum = Math.max(safeMinimum, safeMaximum);
  const rawSpan = Math.max(0, maximum - safeMinimum);
  const span = rawSpan || Math.max(Math.abs(maximum) * 0.2, 1);
  const stepSize = roundStep(span / 5);
  const nonNegative = safeMinimum >= 0;
  let minimum = Math.floor(safeMinimum / stepSize) * stepSize;
  if (minimum === safeMinimum && (!nonNegative || minimum > 0)) {
    minimum -= stepSize;
  }
  if (beginAtZero) minimum = 0;
  if (nonNegative) minimum = Math.max(0, minimum);
  let ceiling = Math.ceil(maximum / stepSize) * stepSize;
  if (ceiling === maximum) ceiling += stepSize;

  return {
    minimum: Object.is(minimum, -0) ? 0 : minimum,
    stepSize,
    maximum: ceiling > minimum ? ceiling : minimum + stepSize,
  };
}

export function themedLineDataset(
  theme: ChartTheme,
  label: string,
  values: Array<number | null>,
  seriesIndex = 0,
): ChartDataset<"line", Array<number | null>> {
  let gradient: CanvasGradient | null = null;
  let gradientTop = 0;
  let gradientBottom = 0;
  return {
    label,
    data: values,
    borderColor: theme.series[seriesIndex % theme.series.length],
    borderWidth: theme.lineWidth,
    fill: "start",
    backgroundColor: (context: ScriptableContext<"line">) => {
      const area = context.chart.chartArea;
      if (!area || area.bottom <= area.top) return theme.fillEnd;
      if (!gradient || gradientTop !== area.top || gradientBottom !== area.bottom) {
        gradientTop = area.top;
        gradientBottom = area.bottom;
        gradient = context.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
        gradient?.addColorStop(0, theme.fillStart);
        gradient?.addColorStop(1, theme.fillEnd);
      }
      return gradient ?? theme.fillStart;
    },
    spanGaps: false,
  };
}

export function reportingChartOptions(args: {
  theme: ChartTheme;
  axis: NiceAxis;
  formatDate: (date: string, includeYear?: boolean) => string;
  formatValue: (value: number) => string;
  metricLabel: string;
}): ChartOptions<"line"> {
  return {
    interaction: { intersect: false, mode: "index" },
    layout: { padding: 0 },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items: TooltipItem<"line">[]) =>
            args.formatDate(items[0]?.label ?? "", true),
          label: (item: TooltipItem<"line">) =>
            `${args.metricLabel}: ${args.formatValue(item.parsed.y ?? 0)}`,
        },
      },
    },
    scales: {
      x: {
        offset: false,
        border: { display: false },
        grid: {
          color: args.theme.gridVertical,
          display: true,
          drawTicks: false,
          lineWidth: 1,
          offset: false,
        },
        ticks: {
          autoSkip: true,
          maxRotation: 0,
          maxTicksLimit: 7,
          minRotation: 0,
          padding: 8,
          callback(value) {
            return args.formatDate(this.getLabelForValue(Number(value)));
          },
        },
      },
      y: {
        beginAtZero: false,
        bounds: "ticks",
        border: { display: false },
        grid: {
          color: (context) =>
            Number(context.tick.value) === args.axis.minimum
              ? "transparent"
              : args.theme.grid,
        },
        min: args.axis.minimum,
        max: args.axis.maximum,
        ticks: {
          maxTicksLimit: 7,
          padding: 8,
          stepSize: args.axis.stepSize,
          callback: (value) => args.formatValue(Number(value)),
        },
      },
    },
  };
}

export { Chart };
