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

/**
 * Bounds a table to a useful head and discloses the remainder on request.
 *
 * Unbounded history is the platform's most persistent UX defect: a run list or
 * keyword table renders every record it holds, so the page grows without limit
 * and the summary that answers the operator's question gets pushed off screen.
 * The overflow rows stay in the DOM — this is disclosure, not truncation, so an
 * expanded table still holds every record it was given.
 */
export interface TableDisclosure {
  /** Rows visible before expanding. */
  initialRows: number;
  /** Noun for the remainder, e.g. "keywords" → "+ 29 more keywords". */
  noun?: string;
  collapseLabel?: string;
}

export interface TableGroup<T> {
  key: string;
  label: string;
  /** Secondary line on the group header, e.g. last run or current health. */
  caption?: string;
  rows: T[];
}

export interface TableOptions<T> {
  emptyHeading?: string;
  emptyDescription?: string;
  emptyActionLabel?: string;
  emptyActionHref?: string;
  onRowClick?: (row: T) => void;
  rowKey?: (row: T) => string;
  disclosure?: TableDisclosure;
}

function disclosureLabel(remaining: number, noun?: string): string {
  const subject = noun ? ` ${noun}` : remaining === 1 ? " row" : " rows";
  return `+ ${remaining} more${subject}`;
}

function disclosureToggle(
  hiddenRows: HTMLTableRowElement[],
  disclosure: TableDisclosure,
): HTMLDivElement {
  for (const row of hiddenRows) row.hidden = true;

  const footer = document.createElement("div");
  footer.className = "ui-table-frame__footer ui-table__disclosure";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "ui-button ui-button--ghost ui-button--sm";
  toggle.setAttribute("aria-expanded", "false");
  toggle.textContent = disclosureLabel(hiddenRows.length, disclosure.noun);

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    for (const row of hiddenRows) row.hidden = expanded;
    toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
    toggle.textContent = expanded
      ? disclosureLabel(hiddenRows.length, disclosure.noun)
      : (disclosure.collapseLabel ?? "Show less");
  });

  footer.append(toggle);
  return footer;
}

function renderHead<T>(columns: TableColumn<T>[]): HTMLTableSectionElement {
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
  return thead;
}

function renderBodyRow<T>(
  columns: TableColumn<T>[],
  row: T,
  options?: TableOptions<T>,
): HTMLTableRowElement {
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
  return tr;
}

function emptyFrame<T>(options?: TableOptions<T>): HTMLDivElement {
  const wrap = document.createElement("div");
  wrap.className = "ui-table-frame ui-table-frame--interactive";
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

export function buildDataTable<T>(
  columns: TableColumn<T>[],
  rows: T[],
  options?: TableOptions<T>,
): HTMLDivElement {
  if (rows.length === 0) return emptyFrame(options);

  const wrap = document.createElement("div");
  wrap.className = "ui-table-frame ui-table-frame--interactive";

  const scroll = document.createElement("div");
  scroll.className = "ui-table-frame__scroll";
  const table = document.createElement("table");
  table.className = "ui-table";
  table.append(renderHead(columns));

  const tbody = document.createElement("tbody");
  const limit = options?.disclosure?.initialRows ?? rows.length;
  const hidden: HTMLTableRowElement[] = [];
  rows.forEach((row, index) => {
    const tr = renderBodyRow(columns, row, options);
    if (index >= limit) hidden.push(tr);
    tbody.append(tr);
  });
  table.append(tbody);
  scroll.append(table);
  wrap.append(scroll);

  if (options?.disclosure && hidden.length > 0) {
    wrap.append(disclosureToggle(hidden, options.disclosure));
  }

  return wrap;
}

/**
 * Rows grouped under labelled headers, each group bounded independently.
 *
 * A flat list of every run across every automation cannot answer "is this
 * automation healthy" — grouping by the thing that owns the runs can, and
 * bounding each group keeps the page a fixed height as history accumulates.
 */
export function buildGroupedDataTable<T>(
  columns: TableColumn<T>[],
  groups: TableGroup<T>[],
  options?: TableOptions<T>,
): HTMLDivElement {
  const populated = groups.filter((group) => group.rows.length > 0);
  if (populated.length === 0) return emptyFrame(options);

  const wrap = document.createElement("div");
  wrap.className = "ui-table-frame ui-table-frame--interactive";
  const scroll = document.createElement("div");
  scroll.className = "ui-table-frame__scroll";
  const table = document.createElement("table");
  table.className = "ui-table ui-table--grouped";
  table.append(renderHead(columns));

  for (const group of populated) {
    const tbody = document.createElement("tbody");
    tbody.dataset.group = group.key;

    const headerRow = document.createElement("tr");
    headerRow.className = "ui-table__group-row";
    const headerCell = document.createElement("th");
    headerCell.colSpan = columns.length;
    headerCell.scope = "colgroup";

    const label = document.createElement("span");
    label.className = "ui-table__group-label";
    label.textContent = group.label;

    const count = document.createElement("span");
    count.className = "ui-table__group-count";
    count.textContent = String(group.rows.length);

    headerCell.append(label, count);

    if (group.caption) {
      const caption = document.createElement("span");
      caption.className = "ui-table__group-caption";
      caption.textContent = group.caption;
      headerCell.append(caption);
    }

    headerRow.append(headerCell);
    tbody.append(headerRow);

    const limit = options?.disclosure?.initialRows ?? group.rows.length;
    const hidden: HTMLTableRowElement[] = [];
    group.rows.forEach((row, index) => {
      const tr = renderBodyRow(columns, row, options);
      if (index >= limit) hidden.push(tr);
      tbody.append(tr);
    });

    if (options?.disclosure && hidden.length > 0) {
      const footerRow = document.createElement("tr");
      footerRow.className = "ui-table__group-footer";
      const footerCell = document.createElement("td");
      footerCell.colSpan = columns.length;
      footerCell.append(disclosureToggle(hidden, options.disclosure));
      footerRow.append(footerCell);
      tbody.append(footerRow);
    }

    table.append(tbody);
  }

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
