import type { Client, ViewState } from "../types/domain";
import { clients, actions, automationRuns } from "../data/fixtures";
export function filteredClients(state: ViewState) {
  const matching = clients
    .filter((c) =>
      (c.name + " " + c.category + " " + c.location)
        .toLowerCase()
        .includes(state.query.toLowerCase()),
    )
    .filter(
      (c) =>
        state.filter === "All clients" ||
        (state.filter === "Needs attention" &&
          actions.some((x) => x.client === Number(c.id) - 1 && !x.done)) ||
        (state.filter === "Improving" && c.change > 0) ||
        (state.filter === "Declining" && c.change < 0) ||
        (state.filter === "New clients" && c.status === "New client") ||
        (state.filter === "Multi-location" && c.locations > 1) ||
        (state.filter === "Website issues" && c.website !== "Healthy") ||
        (state.filter === "GBP issues" && c.gbp !== "Healthy") ||
        (state.filter === "Review issues" &&
          actions.some(
            (x) =>
              x.client === Number(c.id) - 1 && x.type === "Reviews" && !x.done,
          )) ||
        (state.filter === "Integration issues" &&
          c.integration !== "Connected"),
    );
  return matching.sort((a, b) =>
    state.sort === "name"
      ? a.name.localeCompare(b.name)
      : state.sort === "visibility"
        ? b.visibility - a.visibility
        : state.sort === "leads"
          ? b.leads - a.leads
          : state.sort === "change"
            ? b.change - a.change
            : actions.filter((x) => x.client === Number(b.id) - 1 && !x.done)
                .length -
              actions.filter((x) => x.client === Number(a.id) - 1 && !x.done)
                .length,
  );
}
export const filteredAutomations = (state: ViewState, c?: Client) =>
  automationRuns.filter(
    (r) =>
      (!c || r.client === c.id) &&
      (c ||
        state.automationClient === "All clients" ||
        r.client === state.automationClient) &&
      (state.automationStatus === "All statuses" ||
        (state.automationStatus === "Needs attention" &&
          r.status === "Needs attention") ||
        (state.automationStatus === "Healthy" && r.status === "Healthy") ||
        state.automationStatus === r.lastStatus) &&
      (state.automationType === "All types" ||
        r.def === Number(state.automationType)),
  );
export function connectionInfo(c: Client, i: number) {
  const status =
    i === 0
      ? c.gbp === "Healthy"
        ? "Connected"
        : "Disconnected"
      : i === 2
        ? c.integration
        : "Connected";
  return {
    status,
    authorization:
      status === "Disconnected"
        ? "Expired"
        : status === "Not configured"
          ? "Not configured"
          : "Authorized",
    sync:
      c.sourceSync?.[i] ||
      (status === "Disconnected"
        ? "Sep 28 · 11:40 PM"
        : status === "Not configured"
          ? "No sync yet"
          : "18 minutes ago"),
    freshness:
      status === "Disconnected"
        ? "Stale · sync paused"
        : status === "Not configured"
          ? "No data available"
          : status === "Needs attention"
            ? "Traffic fresh · conversion events incomplete"
            : "Fresh · latest source data available",
    capabilities:
      i === 0
        ? "Profile performance · Posts · Google reviews and responses"
        : i === 1
          ? "Queries · Clicks · Impressions · Indexing"
          : "Traffic · Channels · Conversion events",
  };
}
