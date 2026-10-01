import { clients, actions, opportunities } from "../data/fixtures";
import { periodMultiplier, fmt } from "./view";
import { visibilitySeries } from "./visibility";
import { createSampleSession } from "./sample-session";
export function createFilters(root: HTMLElement) {
  const values: Record<string, string> = {};
  function apply(name: string, value: string, control?: HTMLElement) {
    values[name] = value;
    const session = createSampleSession();
    if (name === "tab")
      root
        .querySelectorAll<HTMLElement>("main [data-attention-id]")
        .forEach(
          (row) =>
            (row.hidden =
              value !== "All items" && row.dataset.attentionType !== value),
        );
    root
      .querySelectorAll<HTMLButtonElement>("button[data-filter]")
      .forEach((button) => {
        if (button.dataset.filter === name)
          button.classList.toggle("active", button.dataset.value === value);
      });
    if (control?.tagName === "BUTTON")
      control.parentElement
        ?.querySelectorAll("button")
        .forEach((button) =>
          button.classList.toggle("active", button === control),
        );
    if (name === "range") {
      sessionStorage.setItem("lilos-reporting-period", value);
      const m = periodMultiplier(value);
      if (value === "7" || value === "30" || value === "90")
        root
          .querySelectorAll<SVGElement>("[data-visibility-chart]")
          .forEach((chart) => {
            const series = visibilitySeries(
              Number(chart.dataset.current),
              chart.dataset.declining === "true",
              value,
            );
            chart
              .querySelector("[data-chart-area]")
              ?.setAttribute("d", series.path + " L535 140 L35 140 Z");
            chart
              .querySelector("[data-chart-previous]")
              ?.setAttribute("d", series.previous);
            chart
              .querySelector("[data-chart-current]")
              ?.setAttribute("d", series.path);
            chart
              .querySelectorAll("[data-chart-point]")
              .forEach((point, i) =>
                point.setAttribute(
                  "cy",
                  String(150 - (series.values[i] - 20) * 1.8),
                ),
              );
            chart
              .querySelectorAll("[data-chart-label]")
              .forEach((label, i) => (label.textContent = series.labels[i]));
          });
      root
        .querySelectorAll<HTMLElement>("[data-period-days]")
        .forEach((el) => (el.textContent = value));
      root
        .querySelectorAll<HTMLElement>("[data-period-components]")
        .forEach((el) => {
          const parts: unknown = JSON.parse(
            el.dataset.periodComponents || "[]",
          );
          if (Array.isArray(parts) && parts.every((n) => typeof n === "number"))
            el.textContent = fmt(
              parts.reduce((sum, n) => sum + Math.round(n * m), 0),
            );
        });
      root
        .querySelectorAll<HTMLElement>("[data-period-base]")
        .forEach(
          (el) =>
            (el.textContent = el.dataset.periodFormat
              ? el.dataset.periodFormat
                  .replaceAll("{days}", value)
                  .replaceAll("{value}", fmt(Number(el.dataset.periodBase) * m))
              : fmt(Number(el.dataset.periodBase) * m)),
        );
      root
        .querySelectorAll<HTMLElement>("[data-period-label]")
        .forEach((el) => {
          if (el.dataset.periodBase || el.querySelector("[data-period-base]"))
            return;
          el.dataset.baselineText ??= el.textContent || "";
          el.textContent = el.dataset.baselineText.replace(
            /Last (7|30|90) days/g,
            `Last ${value} days`,
          );
        });
      return;
    }
    const clientRows = [
      ...root.querySelectorAll<HTMLTableRowElement>("[data-client-row]"),
    ];
    if (["query", "filter", "sort"].includes(name)) {
      const filtered = clientRows.filter((row) => {
        const fixture = clients.find((x) => x.id === row.dataset.clientRow);
        const c = fixture
          ? session.get("client", fixture.id, fixture)
          : undefined;
        if (!c) return false;
        const f = values.filter || "All clients";
        const allowed =
          f === "All clients" ||
          (f === "Needs attention" &&
            actions.some(
              (a) =>
                a.client === Number(c.id) - 1 &&
                !session.get("action", a.id, a).done,
            )) ||
          (f === "Improving" && c.change > 0) ||
          (f === "Declining" && c.change < 0) ||
          (f === "New clients" && c.status === "New client") ||
          (f === "Multi-location" && c.locations > 1) ||
          (f === "Website issues" && c.website !== "Healthy") ||
          (f === "GBP issues" && c.gbp !== "Healthy") ||
          (f === "Review issues" &&
            actions.some(
              (a) =>
                a.client === Number(c.id) - 1 &&
                a.type === "Reviews" &&
                !session.get("action", a.id, a).done,
            )) ||
          (f === "Integration issues" && c.integration !== "Connected");
        row.hidden =
          !allowed ||
          !(c.name + " " + c.location + " " + c.category)
            .toLowerCase()
            .includes((values.query || "").toLowerCase());
        return !row.hidden;
      });
      if (name === "sort") {
        const mode = values.sort;
        clientRows
          .sort((a, b) => {
            const ca = clients.find((c) => c.id === a.dataset.clientRow)!;
            const cb = clients.find((c) => c.id === b.dataset.clientRow)!;
            return mode === "name"
              ? ca.name.localeCompare(cb.name)
              : mode === "visibility"
                ? cb.visibility - ca.visibility
                : mode === "leads"
                  ? cb.leads - ca.leads
                  : mode === "change"
                    ? cb.change - ca.change
                    : actions.filter((a) => a.client === Number(cb.id) - 1)
                        .length -
                      actions.filter((a) => a.client === Number(ca.id) - 1)
                        .length;
          })
          .forEach((row) => row.parentElement?.append(row));
      }
      const count = root.querySelector("#rowcount");
      if (count) count.textContent = `${filtered.length} of 12 clients`;
      const empty = root.querySelector<HTMLElement>("[data-client-empty]");
      if (empty) empty.hidden = filtered.length > 0;
      if (name === "filter" && value === "Declining")
        root
          .querySelector("#clientrows")
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    root
      .querySelectorAll<HTMLElement>("main [data-opportunity-id]")
      .forEach(
        (row) =>
          (row.hidden = Boolean(
            (values.oppType &&
              values.oppType !== "All types" &&
              row.dataset.type !== values.oppType) ||
            (values.oppPriority &&
              values.oppPriority !== "All priorities" &&
              row.dataset.priority !== values.oppPriority) ||
            (values.oppKind &&
              values.oppKind !== "All classifications" &&
              row.dataset.kind !== values.oppKind) ||
            (values.oppClient &&
              values.oppClient !== "All clients" &&
              row.dataset.clientId !== values.oppClient),
          )),
      );
    root
      .querySelectorAll<HTMLElement>("main [data-report-id]")
      .forEach(
        (row) =>
          (row.hidden = Boolean(
            values.reportFilter &&
            values.reportFilter !== "All reports" &&
            (values.reportFilter === "Needs attention"
              ? !["Missing data", "Needs review"].includes(
                  row.dataset.status || "",
                )
              : row.dataset.status !== values.reportFilter),
          )),
      );
    root
      .querySelectorAll<HTMLElement>("main [data-review-id]")
      .forEach(
        (row) =>
          (row.hidden = Boolean(
            values.reviewFilter &&
            values.reviewFilter !== "All reviews" &&
            row.dataset.status !== values.reviewFilter,
          )),
      );
    const requestPanel = root.querySelector<HTMLElement>(
      "[data-review-requests]",
    );
    if (requestPanel)
      requestPanel.hidden = values.reviewFilter !== "Review requests";
    const inbox = root.querySelector<HTMLElement>("[data-review-inbox]");
    if (inbox) inbox.hidden = values.reviewFilter === "Review requests";
    root
      .querySelectorAll<HTMLElement>("main [data-automation-id]")
      .forEach((row) => {
        row.hidden = Boolean(
          (values.automationClient &&
            values.automationClient !== "All clients" &&
            row.dataset.clientId !== values.automationClient) ||
          (values.automationType &&
            values.automationType !== "All types" &&
            row.dataset.type !== values.automationType) ||
          (values.automationStatus &&
            values.automationStatus !== "All statuses" &&
            row.dataset.status !== values.automationStatus &&
            row.dataset.outcome !== values.automationStatus),
        );
      });
    for (const group of ["attention", "upcoming", "recent"]) {
      const rows = [
        ...root.querySelectorAll<HTMLElement>(
          `[data-automation-group="${group}"]`,
        ),
      ];
      const matching = rows.filter(
        (row) =>
          !row.hidden &&
          (group !== "attention" || row.dataset.status === "Needs attention") &&
          (group !== "recent" || row.dataset.outcome === "Completed"),
      );
      const limit = group === "attention" ? 100 : root.dataset.clientId ? 3 : 5;
      rows.forEach(
        (row) => (row.hidden = !matching.slice(0, limit).includes(row)),
      );
      root
        .querySelectorAll<HTMLElement>(`[data-automation-empty="${group}"]`)
        .forEach((el) => (el.hidden = matching.length > 0));
      if (group === "attention") {
        const count = root.querySelector("[data-automation-attention-count]");
        if (count) count.textContent = String(matching.length);
      }
    }
    const inventory = root.querySelector<HTMLElement>(
      "[data-automation-inventory]",
    );
    if (inventory)
      inventory.hidden = values.automationView !== "All automations";
    root
      .querySelectorAll<HTMLElement>("[data-automation-overview]")
      .forEach(
        (el) => (el.hidden = values.automationView === "All automations"),
      );
    const compactGroups = new Map<Element, HTMLElement[]>();
    root
      .querySelectorAll<HTMLElement>('main [data-opportunity-mode="compact"]')
      .forEach((row) => {
        const parent = row.parentElement;
        if (parent)
          compactGroups.set(parent, [
            ...(compactGroups.get(parent) || []),
            row,
          ]);
      });
    compactGroups.forEach((rows, parent) => {
      const available = rows.filter((row) => {
        const fixture = opportunities.find(
          (o) => String(o.id) === row.dataset.opportunityId,
        );
        return (
          fixture && !session.get("opportunity", fixture.id, fixture).started
        );
      });
      const limit = Number(rows[0]?.dataset.opportunityLimit || 3);
      rows.forEach(
        (row) => (row.hidden = !available.slice(0, limit).includes(row)),
      );
      const empty = parent.querySelector<HTMLElement>(
        "[data-opportunity-empty]",
      );
      if (empty) empty.hidden = available.length > 0;
    });
    const opportunityCount = root.querySelector<HTMLElement>(
      "[data-opportunity-count]",
    );
    if (opportunityCount) {
      const n = [
        ...root.querySelectorAll<HTMLElement>("main [data-opportunity-id]"),
      ].filter((x) => !x.hidden).length;
      opportunityCount.textContent = `${n} ${root.dataset.clientId ? "findings" : "opportunities"}${root.dataset.clientId ? " · " + (clients.find((c) => c.id === root.dataset.clientId)?.name || "") : ""}`;
    }
  }
  function resetAutomations() {
    for (const name of [
      "automationClient",
      "automationType",
      "automationStatus",
    ]) {
      const select = root.querySelector<HTMLSelectElement>(
        `[data-filter="${name}"]`,
      );
      if (select) {
        select.selectedIndex = 0;
        apply(name, select.value);
      }
    }
  }
  return { apply, resetAutomations, refresh: () => apply("refresh", "") };
}
