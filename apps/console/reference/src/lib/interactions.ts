import { registerPortfolioTools } from "./model-context";
import { createDialogs } from "./dialogs";
import { createFilters } from "./filters";
import { createWorkflows } from "./workflows";
const root = document.body;
const dialogs = createDialogs(root);
const filters = createFilters(root);
let toastTimer: ReturnType<typeof setTimeout>;
function notify(message: string) {
  const toast = root.querySelector<HTMLElement>("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.style.display = "block";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.style.display = "none";
  }, 4000);
}
const workflows = createWorkflows(root, dialogs, notify, filters.refresh);
function args(value?: string): (string | number)[] {
  const parsed: unknown = JSON.parse(value || "[]");
  if (
    !Array.isArray(parsed) ||
    !parsed.every((v) => typeof v === "string" || typeof v === "number")
  )
    throw new Error("Invalid control arguments");
  return parsed;
}
function openOpportunityRow(row: HTMLElement) {
  workflows.execute("openOpp", args(row.dataset.args), row);
}
root.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const control = event.target.closest<HTMLElement>("button,a,[data-row-href]");
  if (!control) {
    const row = event.target.closest<HTMLElement>("[data-opportunity-row]");
    if (row) openOpportunityRow(row);
    return;
  }
  if (control.dataset.dialog) {
    dialogs.open(control.dataset.dialog, control);
    return;
  }
  if ("close" in control.dataset) {
    dialogs.close();
    return;
  }
  if ("menu" in control.dataset) {
    const open = root.classList.toggle("navopen");
    control.setAttribute("aria-expanded", String(open));
    return;
  }
  if ("disclosure" in control.dataset) {
    const panel = control.nextElementSibling;
    if (panel instanceof HTMLElement) {
      panel.hidden = !panel.hidden;
      control.setAttribute("aria-expanded", String(!panel.hidden));
    }
    return;
  }
  if (control.dataset.filter) {
    filters.apply(control.dataset.filter, control.dataset.value || "", control);
    return;
  }
  if (control.dataset.command === "resetAutomationFilters") {
    filters.resetAutomations();
    return;
  }
  if (control.dataset.command) {
    workflows.execute(
      control.dataset.command,
      args(control.dataset.args),
      control,
    );
    return;
  }
  if (control.dataset.commandSpec) {
    const value: unknown = JSON.parse(control.dataset.commandSpec);
    if (
      typeof value === "object" &&
      value &&
      "name" in value &&
      typeof value.name === "string" &&
      "args" in value
    )
      workflows.execute(value.name, args(JSON.stringify(value.args)), control);
    return;
  }
  if (control.dataset.rowHref) {
    location.href = control.dataset.rowHref;
    return;
  }
});
root.addEventListener("keydown", (event) => {
  if (!(event.target instanceof HTMLElement)) return;
  const row = event.target.closest<HTMLElement>("[data-opportunity-row]");
  if (!row || event.target !== row) return;
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  openOpportunityRow(row);
});
root.addEventListener("input", (event) => {
  if (
    event.target instanceof HTMLInputElement &&
    "clientSearch" in event.target.dataset
  )
    filters.apply("query", event.target.value);
});
root.addEventListener("change", (event) => {
  if (!(event.target instanceof HTMLSelectElement)) return;
  if ("clientSelector" in event.target.dataset) {
    location.href = event.target.value;
    return;
  }
  if (event.target.dataset.filter)
    filters.apply(
      event.target.dataset.filter,
      event.target.value,
      event.target,
    );
});
root.addEventListener("submit", (event) => {
  if (
    event.target instanceof HTMLFormElement &&
    event.target.dataset.form === "settings"
  ) {
    event.preventDefault();
    workflows.settings(event.target);
  }
});

const savedPeriod = sessionStorage.getItem("lilos-reporting-period");
if (savedPeriod && ["7", "30", "90"].includes(savedPeriod)) {
  filters.apply("range", savedPeriod);
  const select = root.querySelector<HTMLSelectElement>("[data-filter=range]");
  if (select) select.value = savedPeriod;
}
root.dataset.appReady = "true";
const portfolioQuery = new URL(location.href).searchParams.get("query");
if (portfolioQuery && root.dataset.page === "clients") {
  const input = root.querySelector<HTMLInputElement>("[data-client-search]");
  if (input) input.value = portfolioQuery;
  filters.apply("query", portfolioQuery);
}
registerPortfolioTools();

const review = new URL(location.href).searchParams.get("review");
if (
  review &&
  root.querySelector<HTMLDialogElement>("#" + CSS.escape("review-" + review))
)
  dialogs.open("review-" + review);
