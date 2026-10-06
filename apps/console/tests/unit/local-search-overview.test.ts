import { describe, it, expect } from "vitest";
import fixtures from "../fixtures/phase2.json";
import { adaptLocalSearch } from "../../src/adapters/local-search";
import {
  insightRows,
  priorityPages,
  profileAndSearchRows,
  technicalRows,
} from "../../src/lib/local-search-overview";
import { compactRows, bandChip } from "../../src/lib/opportunity-view";

const org = fixtures.search.organization_id;
const site = fixtures.search.website_id!;
const page = "99999999-0000-4000-8000-000000000301";
// System text: ISO dates, UUIDs, SCREAMING_CODES, snake_case keys and web addresses.
const raw =
  /\d{4}-\d{2}-\d{2}T|[0-9a-f]{8}-[0-9a-f]{4}-|\b[A-Z]+(_[A-Z]+)+\b|\b[a-z]+_[a-z_]+\b|https?:\/\//;
function texts(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(texts);
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, v]) =>
      ["href", "tone"].includes(key) ? [] : texts(v),
    );
  return [];
}
const hrefs = {
  search_console: "/sc/",
  pages: "/pages/",
  google_business_profile: "/gbp/",
};
const insight = (over: Record<string, unknown>) => ({
  code: "SEARCH_CLICKS_UP",
  link: "search_console",
  subject: null,
  current: 300,
  previous: 200,
  percent_change: 50,
  count: null,
  ...over,
});
const view = (over: Record<string, unknown> = {}) =>
  adaptLocalSearch({ ...fixtures.search, ...over }, org, site);
const ALL = [
  insight({ code: "QUERY_GAINING_CLICKS", subject: "brunch near me" }),
  insight({ code: "QUERY_LOSING_CLICKS", subject: "brunch near me" }),
  insight({
    code: "PAGE_GAINING_CLICKS",
    link: "pages",
    subject: "https://example.test/menu/",
  }),
  insight({
    code: "PAGE_LOSING_CLICKS",
    link: "pages",
    subject: "https://example.test/menu/",
  }),
  insight({ code: "SEARCH_CLICKS_UP" }),
  insight({ code: "SEARCH_CLICKS_DOWN" }),
  insight({ code: "IMPRESSIONS_OUTRUNNING_CLICKS" }),
  insight({
    code: "PROFILE_ACTIONS_UP",
    link: "google_business_profile",
    percent_change: 22,
  }),
  insight({
    code: "PROFILE_ACTIONS_DOWN",
    link: "google_business_profile",
    percent_change: -22,
  }),
  insight({
    code: "QUERIES_NEAR_PAGE_ONE",
    subject: "rooftop bar",
    current: 11.3,
    count: 4,
  }),
];
describe("insight presenter", () => {
  it("words every code as a sentence with no system text", () => {
    const rows = insightRows(view({ insights: ALL }), hrefs);
    expect(rows).toHaveLength(ALL.length);
    for (const text of texts(rows)) expect(text, text).not.toMatch(raw);
    for (const row of rows) {
      expect(row.title.length).toBeGreaterThan(10);
      expect(row.detail.length).toBeGreaterThan(10);
    }
  });
  it("reads the numbers and subjects, and links to the evidence", () => {
    const [mover, page_, clicks, , , near] = [
      ALL[0],
      ALL[2],
      ALL[4],
      ALL[5],
      ALL[6],
      ALL[9],
    ];
    const rows = insightRows(
      view({ insights: [mover, page_, clicks, near] }),
      hrefs,
    );
    expect(rows[0].title).toBe("“brunch near me” is bringing in more clicks.");
    expect(rows[0].detail).toContain("rose 50%");
    expect(rows[1].title).toBe("/menu/ is attracting more search clicks.");
    expect(rows[1].href).toBe("/pages/");
    expect(rows[2]).toMatchObject({
      title: "Search clicks are up 50%.",
      detail: "300 clicks against 200 in the previous period.",
      href: "/sc/",
      linkLabel: "Search queries",
    });
    expect(rows[3].title).toBe("4 searches sit just off the first page.");
    expect(rows[3].detail).toContain("position of 11.3");
  });
  it("returns no rows when the read has no insights", () => {
    expect(insightRows(view(), hrefs)).toEqual([]);
  });
});
const health = {
  pages_crawled: { state: "tracked", value: 26 },
  indexable_pages: { state: "tracked", value: 24 },
  excluded_pages: { state: "tracked", value: 2 },
  pages_with_issues: { state: "tracked", value: 4 },
  structured_data_pages: { state: "tracked", value: 22 },
  google_indexed_pages: { state: "not_tracked", value: null },
  last_crawled_at: "2026-10-03T06:00:00Z",
};
describe("indexing and technical health", () => {
  it("shows what the crawl found and says so for what is not collected", () => {
    const rows = technicalRows(
      view({ technical_health: health }).technical_health!,
    );
    expect(rows.map((r) => [r.label, r.value])).toEqual([
      ["Indexed by Google", "Not tracked"],
      ["Indexable pages", "24 of 26"],
      ["Excluded pages", "2"],
      ["Pages with technical issues", "4"],
      ["Structured data", "22 of 26"],
    ]);
    expect(rows[0].missing).toBe(true);
    expect(rows[1].sub).toBe(
      "Open to search engines · Site crawl · Oct 2, 2026",
    );
    for (const text of texts(rows)) expect(text, text).not.toMatch(raw);
  });
  it("never turns an uncrawled site into zeros", () => {
    const none = {
      state: "not_tracked",
      value: null,
    };
    const rows = technicalRows(
      view({
        technical_health: {
          pages_crawled: none,
          indexable_pages: none,
          excluded_pages: none,
          pages_with_issues: none,
          structured_data_pages: none,
          google_indexed_pages: none,
          last_crawled_at: null,
        },
      }).technical_health!,
    );
    expect(rows.every((r) => r.value === "Not tracked" && r.missing)).toBe(
      true,
    );
    expect(rows.map((r) => r.value)).not.toContain("0");
  });
});
describe("profile and organic search", () => {
  it("names each number's source and period, or why it is absent", () => {
    const base = fixtures.search.search_console!;
    const rows = profileAndSearchRows(
      view({
        search_console: {
          ...base,
          metrics: {
            ...base.metrics,
            impressions: {
              current: 41260,
              previous: 38790,
              delta: 2470,
              percent_delta: 6.4,
              quality: "valid",
              label: null,
            },
          },
        },
      }),
      null,
      28,
    );
    expect(rows.map((r) => r.label)).toEqual([
      "Calls",
      "Website clicks",
      "Direction requests",
      "Search impressions",
    ]);
    expect(rows[0]).toMatchObject({
      value: "Unavailable",
      missing: true,
    });
    expect(rows[3].sub).toBe("Search Console · Last 28 days");
    for (const text of texts(rows)) expect(text, text).not.toMatch(raw);
  });
});
describe("priority landing pages", () => {
  it("shows each page by its path with the crawl's index status", () => {
    const base = fixtures.search.search_console!;
    const rows = priorityPages(
      view({
        search_console: {
          ...base,
          top_pages: [
            {
              page: "https://example.test/menu/",
              page_id: page,
              index_status: "indexable",
              clicks: 120,
              impressions: 2000,
              ctr: 0.06,
              position: 5,
            },
            {
              page: "https://example.test/private/",
              page_id: null,
              index_status: "not_crawled",
              clicks: 15,
              impressions: 200,
              ctr: 0.07,
              position: 9,
            },
            {
              page: "https://example.test/thanks/",
              page_id: page,
              index_status: "not_indexable",
              clicks: 9,
              impressions: 100,
              ctr: 0.09,
              position: 3,
            },
          ],
        },
      }),
      (w, p) => `/p/${w}/${p}/`,
    );
    expect(rows.map((r) => [r.label, r.chip.label])).toEqual([
      ["/menu/", "Indexable"],
      ["/private/", "Not crawled yet"],
      ["/thanks/", "Not indexable"],
    ]);
    expect(rows[0].href).toBe(`/p/${site}/${page}/`);
    expect(rows[1].href).toBeNull();
    expect(rows[2].chip.tone).toBe("warn");
    for (const text of texts(rows)) expect(text, text).not.toMatch(raw);
  });
});
describe("relevant opportunities", () => {
  const opp = (id: string, over: Record<string, unknown> = {}) =>
    ({
      id: `seo_opportunity:${id}`,
      source_kind: "seo_opportunity",
      kind: "seo",
      source_id: id,
      organization_id: org,
      client: { organization_id: org, name: "Park 101", slug: "park101" },
      classification: "Issue",
      source_type: "gsc_low_ctr",
      priority: 82,
      priority_band: "high",
      headline: null,
      status: "new",
      lifecycle: "open",
      observed_at: "2026-10-04T06:00:00Z",
      verified_at: null,
      next_action: "review_opportunity",
      evidence_summary: null,
      site_change_reason: null,
      importance_reason: null,
      subject: { query: "brunch spots", path: null },
      ...over,
    }) as never;
  it("titles, dedupes and bands exactly as the Opportunities screen", () => {
    const rows = compactRows(
      [
        opp("11111111-1111-4111-8111-111111111111"),
        opp("22222222-2222-4222-8222-222222222222"),
        opp("33333333-3333-4333-8333-333333333333", {
          source_type: "missing_title",
          priority_band: "low",
          subject: { query: null, path: "/" },
        }),
      ],
      new Date("2026-10-05T12:00:00Z"),
    );
    expect(rows.map((r) => r.title)).toEqual([
      "Low click-through: “brunch spots”",
      "Missing page title · Homepage",
    ]);
    expect(rows.map((r) => r.priority)).toEqual([
      "High priority",
      "Low priority",
    ]);
    expect(rows[0].href).toBe(
      "/clients/park101/opportunities/11111111-1111-4111-8111-111111111111/",
    );
  });
  it("never prints a raw score", () => {
    expect(bandChip("medium")).toBe("Medium priority");
    expect(bandChip(null)).toBe("Priority unavailable");
    expect(bandChip(undefined)).toBe("Priority unavailable");
  });
});
