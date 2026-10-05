import { describe, it, expect, vi } from "vitest";
import {
  attentionRows,
  clientHealthRows,
  clientInsight,
  clientRowView,
  opportunityRows,
  portfolioMetrics,
  snapshotMetrics,
} from "../../src/lib/portfolio-view";
import { show, when } from "../../src/lib/present";
import {
  loadOverview,
  loadPortfolio,
  reportingDays,
  type ClientOverview,
  type ClientRow,
  type MetricValue,
} from "../../src/server/command-center";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
const org = "22222222-2222-4222-8222-222222222222";
const other = "33333333-3333-4333-8333-333333333333";
const now = new Date("2026-10-02T18:00:00Z");
const missing = (
  availability: MetricValue["availability"],
  source: MetricValue["source"] = "ga4",
): MetricValue => ({
  current: null,
  previous: null,
  percent_delta: null,
  source,
  availability,
});
const have = (current: number, previous: number | null): MetricValue => ({
  current,
  previous,
  percent_delta:
    previous === null ? null : Number(((current - previous) / previous) * 100),
  source: "ga4",
  availability: "available",
});
function row(overrides: Partial<ClientRow> = {}): ClientRow {
  return {
    organization_id: org,
    slug: "park101-carlsbad",
    name: "Park 101",
    location: "Carlsbad, CA",
    category: "Restaurant",
    location_count: 1,
    organic_sessions: have(120, 100),
    search_clicks: missing("not_connected", "search_console"),
    average_position: missing("not_connected", "search_console"),
    average_local_rank: missing("not_tracked", "rank_scan"),
    gbp_actions: missing("not_connected", "gbp"),
    leads: have(0, 0),
    local_visibility: missing("not_tracked", "rank_scan"),
    reviews: {
      availability: "available",
      total: 40,
      new_in_period: 3,
      average_rating: 4.6,
    },
    open_opportunities: 2,
    health: "healthy",
    health_reasons: [],
    last_activity: null,
    next_work: null,
    ...overrides,
  };
}
function overview(client: ClientRow): ClientOverview {
  return {
    generated_at: now.toISOString(),
    days: 28,
    period_start: now.toISOString(),
    period_end: now.toISOString(),
    access: "member",
    client,
    attention: [],
    opportunities: [],
    activity: [],
    upcoming: [],
    systems: [
      { key: "google", status: "healthy" },
      { key: "automations", status: "error" },
    ],
    insights: {
      availability: "available",
      workflow_runs: { completed: 12, failed: 1 },
      growth_outcomes: {},
      seo_opportunities: {},
      seo_opportunities_blocked: null,
      content_publications: {},
      reviews: {},
    },
  };
}
describe("missing data is never shown as a number", () => {
  it.each([
    ["not_tracked", "Not tracked"],
    ["no_data", "No data"],
    ["not_connected", "Not connected"],
    ["not_permitted", "No access"],
  ] as const)("%s is labeled %s", (state, label) => {
    const shown = show(missing(state));
    expect(shown.text).toBe(label);
    expect(shown.state).toBe(state);
    expect(shown.delta).toBeNull();
  });
  it("keeps a real zero as zero", () => {
    expect(show(have(0, 0)).text).toBe("0");
  });
  it("treats available-without-a-value as no data, not zero", () => {
    const shown = show({ ...missing("available"), availability: "available" });
    expect(shown.text).toBe("No data");
  });
  it("leads without an active source read Not connected, never 0", () => {
    const view = clientRowView(
      row({ leads: missing("not_connected", "leads") }),
      now,
    );
    expect(view.leads.text).toBe("Not connected");
    expect(view.leads.state).toBe("not_connected");
    expect(view.leadsDelta).toBeNull();
    const totals = portfolioMetrics({
      totals: {
        website_leads: missing("not_connected", "leads"),
        organic_sessions: missing("not_connected"),
        new_reviews: null,
        average_rating: null,
        reporting_attention: 0,
        local_visibility: missing("not_tracked", "rank_scan"),
      },
    } as never);
    expect(totals[1].value).toBe("Not connected");
    expect(totals[1].missing).toBe(true);
  });
  it("local visibility and rank are not tracked on every client row", () => {
    const view = clientRowView(row(), now);
    expect(view.visibility.text).toBe("Not tracked");
    expect(view.rank.text).toBe("Not tracked");
    expect(view.organic.text).toBe("120");
    expect(view.organicDelta).toBe("+20%");
  });
  it("portfolio totals label unavailable sources", () => {
    const totals = portfolioMetrics({
      totals: {
        website_leads: missing("no_data", "leads"),
        organic_sessions: missing("not_connected"),
        new_reviews: null,
        average_rating: null,
        reporting_attention: 2,
        local_visibility: missing("not_tracked", "rank_scan"),
      },
    } as never);
    expect(totals.map((t) => t.value)).toEqual([
      "Not tracked",
      "No data",
      "No data",
      "2",
    ]);
    expect(totals.slice(0, 3).every((t) => t.missing)).toBe(true);
  });
  it("snapshot never invents local rank and shows GBP actions only from the sync", () => {
    const metrics = snapshotMetrics(overview(row()));
    const byLabel = Object.fromEntries(metrics.map((m) => [m.label, m]));
    expect(byLabel["GBP actions"].value).toBe("Not connected");
    expect(byLabel["GBP actions"].missing).toBe(true);
    expect(byLabel["Average local rank"].value).toBe("Not tracked");
    expect(byLabel["Google rating"].value).toBe("4.6 ★");
    const synced = (gbp: MetricValue) =>
      Object.fromEntries(
        snapshotMetrics(overview(row({ gbp_actions: gbp }))).map((m) => [
          m.label,
          m,
        ]),
      )["GBP actions"];
    expect(synced(missing("no_data", "gbp")).value).toBe("No data");
    const available = synced({ ...have(140, 100), source: "gbp" });
    expect(available.value).toBe("140");
    expect(available.description).toContain("+40% vs previous period");
    // A zero from a real sync is a result; it is not the same as no data.
    expect(synced({ ...have(0, 12), source: "gbp" }).value).toBe("0");
  });
  it("lists a finding once, with the title the Opportunities screen uses", () => {
    const item = (id: string, over: Record<string, unknown> = {}) => ({
      id,
      organization_id: org,
      organization_name: "Park 101",
      organization_slug: "park101-carlsbad",
      opportunity_type: "gsc_low_ctr",
      classification: "Issue" as const,
      status: "approved",
      priority: 90,
      query: "brunch spots san diego",
      page: null,
      impressions: 100,
      ...over,
    });
    const rows = opportunityRows([
      item("a"),
      item("b"),
      item("c", { query: null, page: "https://park101.example/menu/" }),
      item("d", { query: null, page: "https://park101.example/menu/" }),
      item("e", {
        opportunity_type: "missing_meta_description",
        query: null,
        page: "/",
      }),
    ]);
    expect(rows.map((r) => r.id)).toEqual(["a", "c", "e"]);
    expect(rows.map((r) => r.title)).toEqual([
      "Low click-through: \u201cbrunch spots san diego\u201d",
      "Low click-through \u00b7 /menu/",
      "Missing meta description \u00b7 Homepage",
    ]);
    for (const r of rows) expect(r.title).not.toMatch(/gsc_|_|https?:/);
  });
});
describe("typed codes, not sentences", () => {
  it("maps attention codes to copy and falls back safely", () => {
    const rows = attentionRows(
      [
        {
          organization_id: org,
          organization_name: "Park 101",
          organization_slug: "park101-carlsbad",
          code: "WORKFLOW_FAILED",
          severity: "high",
          occurred_at: now.toISOString(),
          reference: "gbp.publish_post:PROVIDER_REJECTED",
          workflow_key: "gbp.publish_post",
          failure_code: "PROVIDER_REJECTED",
        },
        {
          organization_id: org,
          organization_name: "Park 101",
          organization_slug: "park101-carlsbad",
          code: "SOMETHING_NEW",
          severity: "medium",
          occurred_at: null,
          reference: null,
        },
      ],
      now,
    );
    expect(rows[0].title).toBe("Google post publishing failed");
    expect(rows[0].workflow).toBe("Google post publishing");
    expect(rows[0].failureCode).toBe("PROVIDER_REJECTED");
    expect(rows[0].actionHref).toBe("/clients/park101-carlsbad/automations/");
    expect(rows[1].title).toBe("Attention needed");
    expect(rows[1].time).toBe("Open");
  });
  it("chooses the insight from health reasons", () => {
    const reconnect = clientInsight(
      overview(row({ health_reasons: ["GOOGLE_RECONNECT_REQUIRED"] })),
    );
    expect(reconnect.title).toContain("authorization needs attention");
    const none = clientInsight(
      overview(
        row({
          organic_sessions: missing("no_data"),
          health_reasons: [],
        }),
      ),
    );
    expect(none.title).toContain("No performance data");
  });
  it("folds the insights summary into operational health", () => {
    const rows = clientHealthRows(overview(row()));
    expect(rows.find((r) => r.label === "Automations")?.note).toBe(
      "12 completed · 1 need attention",
    );
  });
  it("formats days in the display zone", () => {
    expect(when("2026-10-02T20:00:00Z", now)).toBe("Today");
    expect(when("2026-10-03T20:00:00Z", now)).toBe("Tomorrow");
    expect(when("2026-10-09T20:00:00Z", now)).toBe("Oct 9");
  });
});
describe("period and source scope", () => {
  it("accepts only 7, 28 and 90", () => {
    expect(reportingDays(null)).toBe(28);
    expect(reportingDays("90")).toBe(90);
    expect(reportingDays("30")).toBeNull();
    expect(reportingDays("abc")).toBeNull();
  });
  const settings = {
    origin: "https://console.test",
    apiOrigin: "https://api.test",
    supabaseUrl: "https://auth.test",
    supabaseKey: "key",
    csrfSecret: "x".repeat(32),
    local: false,
  };
  const locals = {
    settings,
    userId: "u",
    token: "t",
    binding: "b",
    csrf: csrfToken("b", "u", settings.csrfSecret),
    correlationId: "c",
    auth: {} as App.Locals["auth"],
  } as App.Locals;
  const fetcher = (payload: unknown) =>
    vi.fn(
      async () =>
        new Response(JSON.stringify(payload), {
          headers: { "Content-Type": "application/json" },
        }),
    );
  it("the BFF registry serves exactly the three read feeds", async () => {
    const ok = fetcher({ data: [] });
    for (const path of [
      "command-center/portfolio/",
      "command-center/clients/",
      `command-center/clients/${org}/overview/`,
    ]) {
      const result = await forward(
        new Request(`https://console.test/api/${path}?days=28`),
        path,
        locals,
        ok,
      );
      expect(result.status).toBe(200);
    }
    for (const path of [
      "command-center/clients/not-a-uuid/overview/",
      `command-center/clients/${org}/overview/extra/`,
    ])
      expect(
        (
          await forward(
            new Request(`https://console.test/api/${path}`),
            path,
            locals,
            ok,
          )
        ).status,
      ).toBe(404);
    expect(
      (
        await forward(
          new Request(
            `https://console.test/api/command-center/portfolio/?days=30`,
          ),
          "command-center/portfolio/",
          locals,
          ok,
        )
      ).status,
    ).toBe(400);
  });
  it("rejects an overview for a different client than requested", async () => {
    const payload = overview(row({ organization_id: other }));
    const original = globalThis.fetch;
    globalThis.fetch = fetcher(payload) as never;
    try {
      await expect(loadOverview(locals, org, 28)).rejects.toThrow(
        "SOURCE_SCOPE_INVALID",
      );
    } finally {
      globalThis.fetch = original;
    }
  });
  it("rejects a portfolio that breaks the contract", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = fetcher({ clients: [{ name: "x" }] }) as never;
    try {
      await expect(loadPortfolio(locals, 28)).rejects.toThrow();
    } finally {
      globalThis.fetch = original;
    }
  });
});
