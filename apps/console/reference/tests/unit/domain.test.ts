import { describe, it, expect } from "vitest";
import {
  clients,
  opportunities,
  pageRecords,
  hospitalityMetrics,
} from "../../src/data/fixtures";
import { route, routeInventory, clientBySlug } from "../../src/config/routes";
import {
  getOpportunity,
  periodMultiplier,
  websiteActions,
  createContext,
} from "../../src/lib/view";
import { filteredClients } from "../../src/lib/selectors";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
describe("Revision 10 data and routing", () => {
  it("preserves the immutable reference bytes", () => {
    const sums = {
      "SOURCE_MANIFEST.md":
        "c231204cb69dd6221d90aa053361e9f251468dac559a290a1cc37d7c9981eca0",
      "dist/app.js":
        "7cddcd496bd4fad89c7238897bcc49669b915510b0b06d040b8cd1a7633e426b",
      "dist/style.css":
        "a36c7e0958735cb6d963496b51549d08d6db133b494a7c88340338f267bfd6c5",
      "dist/index.html":
        "0848729be4030122759bc79d929138e5012765a81b98b3c08217908b4ba31c45",
      ".openai/hosting.json":
        "4d67a5253dcdd9cc7b8bd2ae26acec4bf98f685d170f274f708b9e3e96a3ad62",
    };
    for (const [path, sum] of Object.entries(sums))
      expect(
        createHash("sha256")
          .update(readFileSync("reference/revision-10/" + path))
          .digest("hex"),
      ).toBe(sum);
  });
  it("builds unique, reusable routes for every fixture client", () => {
    expect(new Set(routeInventory).size).toBe(routeInventory.length);
    expect(routeInventory).toHaveLength(240);
    for (const client of clients) {
      expect(clientBySlug(client.slug)).toBe(client);
      expect(route("client", client.id)).toBe(`/clients/${client.slug}/`);
      expect(
        route("client", client.id, "Local Search", "Google Business Profile"),
      ).toBe(`/clients/${client.slug}/local-search/google-business-profile/`);
    }
    expect(() => route("client", "unknown")).toThrow("Unknown client");
  });
  it("resolves each opportunity to one canonical record", () => {
    expect(opportunities).toHaveLength(19);
    expect(new Set(opportunities.map((o) => o.id)).size).toBe(19);
    for (const o of opportunities) {
      expect(getOpportunity(o.id)).toBe(o);
      expect(clients[o.client]).toBeDefined();
      expect(o.discovered).not.toBe("");
      expect(o.next).not.toBe("");
    }
    expect(getOpportunity(999)).toBeUndefined();
  });
  it("retains independent sessions, clicks, and outcome events", () => {
    expect(hospitalityMetrics).toEqual({
      ga4OrganicSessions: 4110,
      gscClicks: 1386,
      gscImpressions: 27720,
      reservationClicks: 132,
      formSubmissions: 48,
      phoneClicks: 106,
      gbpCalls: 515,
      gbpWebsiteClicks: 1201,
      gbpDirections: 772,
    });
    expect(websiteActions("30")).toBe(286);
    expect(websiteActions("7")).toBe(78);
    expect(websiteActions("90")).toBe(806);
    expect(periodMultiplier("7")).toBe(0.27);
    expect(periodMultiplier("90")).toBe(2.82);
    const pages = pageRecords.filter((p) => p.client === "1");
    expect(pages.reduce((n, p) => n + (p.sessions || 0), 0)).toBe(4110);
    expect(pages.reduce((n, p) => n + p.clicks, 0)).toBe(1386);
  });
  it("keeps attention filters and client search meaningful", () => {
    const context = createContext("clients");
    context.state.query = "Oceanside";
    expect(filteredClients(context.state).map((c) => c.name)).toEqual([
      "Pacific Restore",
      "Palm House Kitchen",
    ]);
    context.state.query = "";
    context.state.filter = "Declining";
    expect(
      filteredClients(context.state)
        .map((c) => c.name)
        .sort(),
    ).toEqual(["Coastline Home Co.", "Pacific Restore", "Summit Electrical"]);
  });
});

import vm from "node:vm";
import * as fixtures from "../../src/data/fixtures";
it("preserves every authored fixture field from the complete exported source", () => {
  const source = readFileSync(
    "reference/revision-10/dist/app.js",
    "utf8",
  ).split("window.addEventListener('hashchange'")[0];
  const sandbox = vm.createContext({
    document: { querySelector: () => ({ addEventListener() {} }) },
    Object,
    console,
  });
  vm.runInContext(source, sandbox);
  const names = [
    "clients",
    "actions",
    "opportunities",
    "reports",
    "activity",
    "pageRecords",
    "reviewRecords",
    "automationDefs",
    "automationRuns",
    "reportHistory",
  ] as const;
  for (const name of names) {
    const authored: Record<string, unknown>[] = JSON.parse(
      vm.runInContext(`JSON.stringify(${name})`, sandbox),
    );
    const converted = fixtures[name];
    expect(converted, name).toHaveLength(authored.length);
    authored.forEach((record, i) =>
      expect(converted[i], `${name}[${i}]`).toMatchObject(record),
    );
  }
  vm.runInContext("syncSystemHealth()", sandbox);
  expect(fixtures.systems).toEqual(
    JSON.parse(vm.runInContext("JSON.stringify(systems)", sandbox)),
  );
  expect(fixtures.hospitalitySearchQueries).toEqual(
    JSON.parse(vm.runInContext("JSON.stringify(cocoSearchQueries)", sandbox)),
  );
});
