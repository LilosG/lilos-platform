import {
  formatMetricValue,
  isNumericMetric,
  type MetricFormat,
  type MetricValue,
} from "./data-display";

export type TableColumn<T> = {
  key: string;
  header: string;
  render: (row: T) => HTMLElement | MetricValue;
  format?: MetricFormat;
  width?: "auto" | "content";
};

export function buildDataTable<T>(
  columns: TableColumn<T>[],
  rows: T[],
  options?: {
    emptyHeading?: string;
    emptyDescription?: string;
    emptyActionLabel?: string;
    emptyActionHref?: string;
    onRowClick?: (row: T) => void;
    rowKey?: (row: T) => string;
  },
): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = "ui-table-frame ui-table-frame--interactive";

  if (rows.length === 0) {
    const empty = document.createElement("div");
    empty.className = "ui-table__state";
    const heading = document.createElement("h3");
    heading.textContent = options?.emptyHeading ?? "No records yet";
    const body = document.createElement("p");
    body.textContent =
      options?.emptyDescription ?? "Records will appear here once available.";
    empty.append(heading, body);
    if (options?.emptyActionLabel && options?.emptyActionHref) {
      const link = document.createElement("a");
      link.className = "ui-button ui-button--secondary ui-button--sm";
      link.href = options.emptyActionHref;
      link.textContent = options.emptyActionLabel;
      empty.append(link);
    }
    wrap.append(empty);
    return wrap;
  }

  const scroll = document.createElement("div");
  scroll.className = "ui-table-frame__scroll";
  const table = document.createElement("table");
  table.className = "ui-table";
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col.header;
    const numeric = isNumericMetric(col.format);
    th.dataset.columnWidth = col.width ?? (numeric ? "content" : "auto");
    if (numeric) th.dataset.numeric = "true";
    headerRow.append(th);
  }
  thead.append(headerRow);
  table.append(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    if (options?.onRowClick) {
      tr.dataset.interactive = "true";
      tr.addEventListener("click", () => options.onRowClick!(row));
    }
    for (const col of columns) {
      const td = document.createElement("td");
      const rendered = col.render(row);
      if (rendered instanceof HTMLElement) {
        td.append(rendered);
      } else {
        td.textContent = formatMetricValue(rendered, col.format);
      }
      const numeric = isNumericMetric(col.format);
      td.dataset.columnWidth = col.width ?? (numeric ? "content" : "auto");
      if (numeric) td.classList.add("ui-table__numeric");
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  scroll.append(table);
  wrap.append(scroll);
  return wrap;
}

export function cellText(text: string | null | undefined): string {
  return text ?? "—";
}

export function cellBadge(status: string, label?: string): HTMLSpanElement {
  const badge = document.createElement("span");
  badge.className = `ui-badge ui-badge--${status}`;
  const dot = document.createElement("span");
  dot.setAttribute("aria-hidden", "true");
  dot.className = "ui-badge__dot";
  badge.append(dot, document.createTextNode(label ?? status));
  return badge;
}

export function cellMeta(primary: string, secondary?: string): HTMLDivElement {
  const div = document.createElement("div");
  div.className = "ui-table__cell-stack";
  const primaryEl = document.createElement("span");
  primaryEl.className = "ui-table__cell-primary";
  primaryEl.textContent = primary;
  div.append(primaryEl);
  if (secondary) {
    const secondaryEl = document.createElement("span");
    secondaryEl.className = "ui-table__cell-secondary";
    secondaryEl.textContent = secondary;
    div.append(secondaryEl);
  }
  return div;
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "Not available";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "Not available";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "Not available";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay} day${diffDay > 1 ? "s" : ""} ago`;
  return formatDate(iso);
}
