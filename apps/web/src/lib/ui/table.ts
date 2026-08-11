export type TableColumn<T> = {
  key: string;
  header: string;
  render: (row: T) => HTMLElement | string | null;
  width?: string;
  align?: "left" | "right" | "center";
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
  wrap.className = "data-table";

  if (rows.length === 0) {
    const empty = document.createElement("div");
    empty.className = "data-table__empty";
    const icon = document.createElement("span");
    icon.className = "empty-state__icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "○";
    const heading = document.createElement("h3");
    heading.textContent = options?.emptyHeading ?? "No records yet";
    const body = document.createElement("p");
    body.textContent =
      options?.emptyDescription ?? "Records will appear here once available.";
    empty.append(icon, heading, body);
    if (options?.emptyActionLabel && options?.emptyActionHref) {
      const link = document.createElement("a");
      link.className = "button button--secondary button--sm";
      link.href = options.emptyActionHref;
      link.textContent = options.emptyActionLabel;
      empty.append(link);
    }
    wrap.append(empty);
    return wrap;
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col.header;
    if (col.width) th.style.width = col.width;
    if (col.align) th.style.textAlign = col.align;
    headerRow.append(th);
  }
  thead.append(headerRow);
  table.append(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    if (options?.onRowClick) {
      tr.classList.add("data-table__row--clickable");
      tr.addEventListener("click", () => options.onRowClick!(row));
    }
    for (const col of columns) {
      const td = document.createElement("td");
      const rendered = col.render(row);
      if (rendered instanceof HTMLElement) {
        td.append(rendered);
      } else if (rendered !== null) {
        td.textContent = rendered;
      }
      if (col.align) td.style.textAlign = col.align;
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  wrap.append(table);
  return wrap;
}

export function cellText(text: string | null | undefined): string {
  return text ?? "—";
}

export function cellBadge(status: string, label?: string): HTMLSpanElement {
  const badge = document.createElement("span");
  badge.className = `status status--${status}`;
  const dot = document.createElement("span");
  dot.setAttribute("aria-hidden", "true");
  dot.className = "status__dot";
  badge.append(dot, document.createTextNode(label ?? status));
  return badge;
}

export function cellMeta(primary: string, secondary?: string): HTMLDivElement {
  const div = document.createElement("div");
  div.className = "cell-meta";
  const primaryEl = document.createElement("span");
  primaryEl.className = "cell-meta__primary";
  primaryEl.textContent = primary;
  div.append(primaryEl);
  if (secondary) {
    const secondaryEl = document.createElement("span");
    secondaryEl.className = "cell-meta__secondary";
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
