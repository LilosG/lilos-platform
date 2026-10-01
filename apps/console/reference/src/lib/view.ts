import type { Client, ViewContext, ViewState } from "../types/domain";
import {
  actions,
  opportunities,
  reports,
  activity,
  automationRuns,
  hospitalityMetrics,
} from "../data/fixtures";
export const fmt = (n: number) => Math.round(n).toLocaleString("en-US");
export const pct = (n: number) => `${n > 0 ? "+" : ""}${n}%`;
export const periodMultiplier = (range: string) =>
  range === "7" ? 0.27 : range === "90" ? 2.82 : 1;
export const scopedActions = (c?: Client | null) =>
  actions.filter((a) => !a.done && (!c || a.client === Number(c.id) - 1));
export const scopedOpps = (c?: Client | null) =>
  opportunities.filter((o) => !c || o.client === Number(c.id) - 1);
export const clientReports = (c?: Client | null) =>
  reports.filter((r) => !c || r.client === Number(c.id) - 1);
export const clientActivity = (c?: Client | null) =>
  activity.filter((a) => !c || a.client === Number(c.id) - 1);
export const evidenceText = (text: string) =>
  text
    .replaceAll("Organic visits", "Organic sessions")
    .replaceAll("website leads fell 8%", "reservation clicks fell 8%")
    .replaceAll("Organic traffic", "Organic sessions")
    .replaceAll("organic traffic", "organic sessions")
    .replaceAll("Menu visits", "Menu organic sessions")
    .replaceAll("menu visits", "menu organic sessions")
    .replaceAll("lead events declined", "reservation click events declined")
    .replaceAll(
      "completed bookings.",
      "completed bookings only when provider data becomes available.",
    );
export const websiteActions = (range: string) =>
  [132, 48, 106].reduce(
    (sum, n) => sum + Math.round(n * periodMultiplier(range)),
    0,
  );
export const getOpportunity = (id: number) =>
  opportunities.find((o) => o.id === id);
export const automationNextAction = (
  r: (typeof automationRuns)[number],
  c: Client,
) =>
  c.gbp === "Disconnected" && [0, 4].includes(r.def)
    ? "Reconnect the Google account, then retry."
    : r.def === 3
      ? "Inspect the affected pages and repair the identified technical issue."
      : r.def === 4
        ? "Check reporting inputs, then regenerate the summary."
        : "Review the latest run and retry when ready.";
export function createContext(
  page: string,
  client?: Client,
  tab: ViewState["tab"] = "Overview",
  subtab = "Overview",
): ViewContext {
  const state: ViewState = {
    page,
    client: client?.id || null,
    tab,
    subtab,
    filter: "All clients",
    query: "",
    sort: "priority",
    range: "30",
    oppType: "All types",
    reportFilter: "All reports",
    systemFilter: "All statuses",
    role: "owner",
    adminTab: "Clients / organizations",
    automationFilter: "All",
    reviewFilter: "All reviews",
    oppPriority: "All priorities",
    oppClient: "All clients",
    automationView: "Overview",
    automationStatus: "All statuses",
    automationClient: "All clients",
    automationType: "All types",
    oppKind: "All classifications",
  };
  return {
    state,
    client:
      client?.workspaceProfile === "hospitality"
        ? { ...client, organic: hospitalityMetrics.ga4OrganicSessions }
        : client,
  };
}
export function required<T>(value: T | undefined | null, name: string): T {
  if (value == null) throw new Error(`Missing ${name}`);
  return value;
}
export const scaled = (
  base: number,
  format?: string,
): { base: number; format?: string } => ({ base, format });
export function requireClient(
  context: ViewContext,
  override?: Client | null,
): Client {
  return required(override ?? context.client, "active client context");
}
