import type {
  Client,
  DisplayValue,
  MetricPresentation,
  ViewState,
} from "../types/domain";
import * as metrics from "../data/fixtures/metrics";
import {
  clients,
  reports,
  reviewRecords,
  pageRecords,
  opportunities,
  automationRuns,
  actions,
} from "../data/fixtures";
import { snapshotMetrics } from "../data/fixtures/snapshots";
import { clientInsight } from "../data/fixtures/insights";
import { createContext, fmt, periodMultiplier, required } from "./view";
import { route } from "../config/routes";
import type { createSampleSession } from "./sample-session";
type Session = ReturnType<typeof createSampleSession>;
type MetricView = (client: Client, state: ViewState) => MetricPresentation[];
const metricViews: Record<string, MetricView> = {
  leadsMetrics: metrics.leadsMetrics,
  outcomeMetrics: (_c, state) => metrics.outcomeMetrics(state),
  searchConsoleMetrics: metrics.searchConsoleMetrics,
  gbpMetrics: metrics.gbpMetrics,
  rankingMetrics: metrics.rankingMetrics,
  localSearchMetrics: metrics.localSearchMetrics,
  hospitalitySearchConsoleMetrics: (_c, state) =>
    metrics.hospitalitySearchConsoleMetrics(state),
  hospitalityGbpMetrics: metrics.hospitalityGbpMetrics,
  hospitalityRankingMetrics: metrics.hospitalityRankingMetrics,
  hospitalityLocalSearchMetrics: (_c, state) =>
    metrics.hospitalityLocalSearchMetrics(state),
  portfolioMetrics: metrics.portfolioMetrics,
  portfolioReportMetrics: metrics.portfolioReportMetrics,
  reviewMetrics: metrics.reviewMetrics,
  conversionPathMetrics: metrics.conversionPathMetrics,
  conversionMetrics: metrics.conversionMetrics,
  technicalMetrics: metrics.technicalMetrics,
  hospitalityTechnicalMetrics: metrics.hospitalityTechnicalMetrics,
  websiteMetrics: metrics.websiteMetrics,
};
function display(
  el: HTMLElement,
  value: DisplayValue,
  range: ViewState["range"],
) {
  delete el.dataset.periodBase;
  delete el.dataset.periodFormat;
  delete el.dataset.baselineText;
  if (typeof value === "object") {
    el.dataset.periodBase = String(value.base);
    if (value.format) el.dataset.periodFormat = value.format;
    const count = fmt(value.base * periodMultiplier(range));
    el.textContent = value.format
      ? value.format.replaceAll("{value}", count).replaceAll("{days}", range)
      : count;
  } else
    el.textContent = String(value).replace(
      /Last (7|30|90) days/g,
      `Last ${range} days`,
    );
}
/** Recompute only values affected by sample edits; Astro owns the document structure. */
import { pageSignals, legacyLinkFinding } from "../data/fixtures/pageSignals";
import { systemHealth } from "../data/fixtures/systems";
import { connectionInfo } from "./selectors";
import { updateBadge } from "./status";
export function refreshRecordViews(root: HTMLElement, session: Session) {
  const saved = sessionStorage.getItem("lilos-reporting-period");
  const range: ViewState["range"] =
    saved === "7" || saved === "90" ? saved : "30";
  const client = (id: string) =>
    required(
      createContext(
        "client",
        session.get(
          "client",
          id,
          required(
            clients.find((c) => c.id === id),
            "client",
          ),
        ),
      ).client,
      "client context",
    );
  root.querySelectorAll<HTMLElement>("[data-metric-kind]").forEach((grid) => {
    const c = client(
      grid.dataset.metricClient || root.dataset.clientId || clients[0].id,
    );
    const context = createContext(root.dataset.page || "dashboard", c);
    context.state.range = range;
    const view = metricViews[grid.dataset.metricKind || ""];
    if (!view) return;
    const items = view(c, context.state);
    if (grid.dataset.metricKind === "reviewMetrics")
      items[2] = [
        items[2][0],
        reviewRecords.filter(
          (r) =>
            r.client === c.id &&
            session.get("review", r.id, r).status !== "Published",
        ).length,
        items[2][2],
      ];
    if (grid.dataset.metricKind === "portfolioReportMetrics") {
      const current = reports.map((r) => session.get("report", r.id, r));
      const statuses = ["Ready", "Sent", "Upcoming", "attention"];
      items.forEach(
        (m, i) =>
          (items[i] = [
            m[0],
            current.filter((r) =>
              statuses[i] === "attention"
                ? ["Missing data", "Needs review"].includes(r.status)
                : r.status === statuses[i],
            ).length,
            m[2],
          ]),
      );
    }
    grid.querySelectorAll<HTMLElement>(".metric").forEach((metric, index) => {
      const item = items[index];
      if (!item) return;
      for (const [selector, value] of [
        [".metricLabel", item[0]],
        ["strong", item[1]],
        ["small", item[2]],
      ] as const) {
        const el = metric.querySelector<HTMLElement>(selector);
        if (el) display(el, value, range);
      }
    });
  });
  root.querySelectorAll<HTMLElement>("[data-snapshot-client]").forEach((el) => {
    const c = client(el.dataset.snapshotClient!);
    const metric = snapshotMetrics(c)[Number(el.dataset.snapshotIndex)];
    for (const [selector, value] of [
      ["strong", metric.value],
      ["small", metric.description],
    ] as const) {
      const target = el.querySelector<HTMLElement>(selector);
      if (target) display(target, value, range);
    }
  });
  if (root.dataset.clientId) {
    const c = client(root.dataset.clientId);
    const insight = clientInsight(c);
    root
      .querySelectorAll<HTMLElement>("[data-client-insight]")
      .forEach((el) => {
        if (
          el.dataset.clientInsight === "link" &&
          el instanceof HTMLAnchorElement
        )
          el.href = route("client", c.id, insight.area, insight.section);
        else
          el.textContent =
            el.dataset.clientInsight === "title"
              ? insight.title
              : insight.description;
      });
    root
      .querySelectorAll<HTMLElement>("[data-client-condition]")
      .forEach(
        (el) =>
          (el.hidden =
            el.dataset.clientCondition === "gbp-disconnected"
              ? c.gbp !== "Disconnected"
              : el.dataset.clientCondition === "gbp-connected"
                ? c.gbp === "Disconnected"
                : el.dataset.clientCondition === "tracking-issue"
                  ? c.website !== "Tracking issue"
                  : false),
      );
  }
  root
    .querySelectorAll<HTMLElement>("[data-open-opportunities]")
    .forEach(
      (el) =>
        (el.textContent = String(
          opportunities.filter(
            (o) => !session.get("opportunity", o.id, o).started,
          ).length,
        )),
    );
  root.querySelectorAll<HTMLElement>("[data-page-signals]").forEach((el) => {
    const fixture = pageRecords.find((p) => p.id === el.dataset.pageSignals);
    if (fixture) {
      const page = session.get("page", fixture.id, fixture);
      el.textContent = pageSignals(page, client(page.client));
    }
  });
  root
    .querySelectorAll<HTMLElement>("[data-monthly-report-delivery]")
    .forEach((el) => {
      const id = Number(el.dataset.monthlyReportDelivery);
      el.textContent =
        session.get("report", id, reports[id]).status === "Sent"
          ? "Sent"
          : "Mark as sent";
    });
  root
    .querySelectorAll<HTMLElement>(
      "[data-automation-heading],[data-automation-advice],[data-automation-recovery]",
    )
    .forEach((el) => {
      const id =
        el.dataset.automationHeading ||
        el.dataset.automationAdvice ||
        el.dataset.automationRecovery;
      const fixture = automationRuns.find((r) => r.id === id);
      if (!fixture) return;
      const run = session.get("automation", fixture.id, fixture);
      if (el.dataset.automationHeading)
        el.textContent =
          run.status === "Needs attention"
            ? "Human action required"
            : "Run outcome";
      else el.hidden = run.status !== "Needs attention";
    });
  root
    .querySelectorAll<HTMLButtonElement>('[data-command="runAutomation"]')
    .forEach((button) => {
      const parsed: unknown = JSON.parse(button.dataset.args || "[]");
      if (Array.isArray(parsed) && typeof parsed[0] === "string") {
        const fixture = automationRuns.find((r) => r.id === parsed[0]);
        if (fixture)
          button.textContent =
            session.get("automation", fixture.id, fixture).status ===
            "Needs attention"
              ? "Retry sample run"
              : "Run sample now";
      }
    });
  if (root.dataset.clientId) {
    const c = client(root.dataset.clientId);
    const finding = legacyLinkFinding(c);
    root.querySelectorAll<HTMLElement>("[data-legacy-link]").forEach((el) => {
      if (el.dataset.legacyLink === "status") {
        const b = el.querySelector<HTMLElement>(".badge");
        if (b) updateBadge(b, finding.status);
      } else
        el.textContent =
          el.dataset.legacyLink === "title"
            ? finding.title
            : finding.description;
    });
    root
      .querySelectorAll<HTMLElement>("[data-response-workflow]")
      .forEach(
        (el) =>
          (el.textContent =
            c.responsePreference === "review"
              ? "Human approval requested by this client"
              : c.responsePreference === "auto"
                ? "Automatic publishing configured"
                : "Publish when ready; approval is optional"),
      );
  }
  root
    .querySelectorAll<HTMLElement>("[data-priority-attention]")
    .forEach(
      (el) =>
        (el.textContent = String(
          actions.filter(
            (a) =>
              !session.get("action", a.id, a).done &&
              ["Critical", "High"].includes(a.severity),
          ).length,
        )),
    );
  const systems = systemHealth(
    clients.map((c) => session.get("client", c.id, c)),
  );
  root.querySelectorAll<HTMLElement>("[data-system]").forEach((card) => {
    const system = systems[Number(card.dataset.system)];
    if (!system) return;
    card.querySelectorAll<HTMLElement>("[data-system-field]").forEach((el) => {
      if (el.dataset.systemField === "status") {
        const b = el.querySelector<HTMLElement>(".badge");
        if (b) updateBadge(b, system[2]);
      } else if (el.dataset.systemField === "count")
        el.textContent = system[3] + " / 12";
      else if (el.dataset.systemField === "authorization")
        el.textContent =
          "Authorization: " +
          (system[2] === "Connected"
            ? "Authorized"
            : Number(card.dataset.system) === 0
              ? "1 account expired"
              : "Authorized · event setup needs attention");
      else if (el.dataset.systemField === "freshness")
        el.textContent =
          "Data freshness: " +
          (system[2] === "Connected"
            ? "Fresh"
            : "Connected sources fresh; flagged clients incomplete");
      else if (el.dataset.systemField === "note") el.textContent = system[4];
      else if (el.dataset.systemField === "progress")
        el.style.width = (system[3] / 12) * 100 + "%";
    });
  });
  root
    .querySelectorAll<HTMLButtonElement>("[data-connection-action]")
    .forEach((button) => {
      const info = connectionInfo(
        client(button.dataset.connectionAction!),
        Number(button.dataset.connectionSource),
      );
      button.textContent =
        info.status === "Disconnected"
          ? "Reconnect"
          : info.status === "Not configured"
            ? "Configure"
            : "View connection";
    });
  root.querySelectorAll<HTMLElement>("[data-report-state]").forEach((el) => {
    const id = Number(el.dataset.reportRecord);
    const report = session.get("report", id, reports[id]);
    el.hidden =
      el.dataset.reportState === "default"
        ? ["Sent", "Missing data", "Needs review"].includes(report.status)
        : el.dataset.reportState !== report.status;
  });
  root
    .querySelectorAll<HTMLElement>("[data-review-instructions]")
    .forEach((el) => {
      const fixture = reviewRecords.find(
        (r) => r.id === el.dataset.reviewInstructions,
      );
      if (fixture)
        el.textContent =
          session.get("review", fixture.id, fixture).status ===
          "Awaiting approval"
            ? "This client has requested review of this response. Approval is required only for this saved draft."
            : "Responses can be edited and published directly when ready.";
    });
}
