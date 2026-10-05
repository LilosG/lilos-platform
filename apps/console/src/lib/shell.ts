const root = document.body;
const dialogOrigin = new WeakMap<HTMLDialogElement, HTMLElement>();
const openDialog = () => root.querySelector<HTMLDialogElement>("dialog[open]");
function showDialog(id: string, trigger: HTMLElement) {
  const dialog = root.querySelector<HTMLDialogElement>(`#${CSS.escape(id)}`);
  if (!dialog) return;
  const previous = openDialog();
  const origin = previous ? dialogOrigin.get(previous) : trigger;
  if (origin) dialogOrigin.set(dialog, origin);
  previous?.close();
  dialog.showModal();
}
root
  .querySelectorAll<HTMLDialogElement>("dialog[data-shell-dialog]")
  .forEach((dialog) => {
    dialog.addEventListener("close", () => {
      if (!openDialog()) dialogOrigin.get(dialog)?.focus();
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
const values = { query: "", filter: "All clients", sort: "priority" };
function applyClientTable() {
  const body = root.querySelector<HTMLElement>("#clientrows");
  if (!body) return;
  const rows = [
    ...body.querySelectorAll<HTMLTableRowElement>("[data-client-row]"),
  ];
  const q = values.query.trim().toLowerCase();
  const filters: Record<string, (row: HTMLElement) => boolean> = {
    "All clients": () => true,
    "Needs attention": (row) => row.dataset.needsAttention === "true",
    "Multi-location": (row) => Number(row.dataset.locations) > 1,
    "Website issues": (row) => row.dataset.websiteIssue === "true",
    "GBP issues": (row) => row.dataset.gbpIssue === "true",
    "Integration issues": (row) => row.dataset.integrationIssue === "true",
  };
  const matches = (row: HTMLElement) =>
    (row.dataset.search ?? "").includes(q) &&
    (filters[values.filter] ?? (() => true))(row);
  const number = (row: HTMLElement, key: string) =>
    Number(row.dataset[key] ?? "-1");
  const order: Record<string, (a: HTMLElement, b: HTMLElement) => number> = {
    priority: (a, b) => number(b, "priority") - number(a, "priority"),
    name: (a, b) => (a.dataset.name ?? "").localeCompare(b.dataset.name ?? ""),
    leads: (a, b) => number(b, "leads") - number(a, "leads"),
    change: (a, b) => number(b, "change") - number(a, "change"),
  };
  const compare = order[values.sort] ?? order.priority;
  const visible = rows.filter(matches).sort(compare);
  rows.forEach((row) => (row.hidden = !matches(row)));
  visible.forEach((row) => body.append(row));
  const empty = body.querySelector<HTMLElement>("[data-client-empty]");
  if (empty) empty.hidden = visible.length > 0;
  const count = root.querySelector<HTMLElement>("#rowcount");
  if (count) count.textContent = `${visible.length} of ${rows.length} clients`;
}
root.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const control = event.target.closest<HTMLElement>("button,a,[data-row-href]");
  if (!control) return;
  if (control.dataset.dialog) {
    showDialog(control.dataset.dialog, control);
    return;
  }
  if ("close" in control.dataset) {
    openDialog()?.close();
    return;
  }
  if ("menu" in control.dataset) {
    const open = root.classList.toggle("navopen");
    control.setAttribute("aria-expanded", String(open));
    return;
  }
  if (control.dataset.filter === "filter") {
    values.filter = control.dataset.value ?? "All clients";
    root
      .querySelectorAll<HTMLElement>("button[data-filter=filter]")
      .forEach((chip) =>
        chip.classList.toggle("active", chip.dataset.value === values.filter),
      );
    applyClientTable();
    return;
  }
  if (control.dataset.rowHref && control.tagName !== "A") {
    location.href = control.dataset.rowHref;
  }
});
root.addEventListener("input", (event) => {
  if (
    event.target instanceof HTMLInputElement &&
    "clientSearch" in event.target.dataset
  ) {
    values.query = event.target.value;
    applyClientTable();
  }
});
root.addEventListener("change", (event) => {
  if (!(event.target instanceof HTMLSelectElement)) return;
  if ("clientSelector" in event.target.dataset) {
    location.href = event.target.value;
    return;
  }
  if (event.target.dataset.querySelect) {
    const url = new URL(location.href);
    url.searchParams.set(event.target.dataset.querySelect, event.target.value);
    url.searchParams.delete("offset");
    location.href = url.toString();
    return;
  }
  if ("period" in event.target.dataset) {
    const url = new URL(location.href);
    url.searchParams.set("days", event.target.value);
    location.href = url.toString();
    return;
  }
  if (event.target.dataset.filter === "sort") {
    values.sort = event.target.value;
    applyClientTable();
  }
});
const initial = new URL(location.href).searchParams.get("query");
if (initial && root.dataset.page === "clients") {
  const input = root.querySelector<HTMLInputElement>("[data-client-search]");
  if (input) input.value = initial;
  values.query = initial;
}
applyClientTable();
root.dataset.appReady = "true";
