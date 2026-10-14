// A Coco Maya-shaped monthly report, as the API answers it. Synthetic numbers only.
export const ORG = "11111111-1111-4111-8111-111111111111";
const f = (value, extra = {}) => ({
  availability: "available",
  value,
  ...extra,
});
const gone = (reason) => ({ availability: "unavailable", reason });
const cmp = (cur, prev, year, change, pct, ychange, ypct) => ({
  current: cur === null ? gone("not_synced") : f(cur),
  previous: prev === null ? gone("no_data") : f(prev),
  year_ago: year === null ? gone("partial_period") : f(year),
  change: change ?? null,
  change_percent: pct ?? null,
  year_change: ychange ?? null,
  year_change_percent: ypct ?? null,
});
const rate = (v) =>
  v === null ? gone("no_views") : { availability: "available", value: v };
const metrics = [
  ["BUSINESS_IMPRESSIONS_DESKTOP_MAPS", 300, 250, 200],
  ["BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", 200, 180, 150],
  ["BUSINESS_IMPRESSIONS_MOBILE_MAPS", 600, 500, 400],
  ["BUSINESS_IMPRESSIONS_MOBILE_SEARCH", 700, 600, 500],
];
const row = (cur, prev, year) =>
  cmp(
    cur,
    prev,
    year,
    cur - prev,
    Math.round(((cur - prev) / prev) * 1000) / 10,
    cur - year,
    Math.round(((cur - year) / year) * 1000) / 10,
  );
const day = (n) => `2026-09-${String(n).padStart(2, "0")}`;
export const snapshot = (overrides = {}) => ({
  schema_version: 1,
  month: "2026-09-01",
  readiness: "ready_with_note",
  notes: [
    {
      code: "gbp_search_terms_unavailable",
      section: "search_terms",
      count: null,
      location_id: null,
    },
  ],
  gbp: {
    availability: "available",
    reason: null,
    current_range: { start: "2026-09-01", end: "2026-09-30", days: 30 },
    previous_range: { start: "2026-08-01", end: "2026-08-30", days: 30 },
    year_ago_range: { start: "2025-09-01", end: "2025-09-30", days: 30 },
    through_date: "2026-09-30",
    profile_views: {
      total: row(1800, 1530, 1250),
      sources: metrics.map(([metric, c, p, y]) => ({
        metric,
        comparison: row(c, p, y),
      })),
      maps_search: {
        parts: [
          { key: "maps", figure: f(900), share_percent: 50 },
          { key: "search", figure: f(900), share_percent: 50 },
        ],
      },
      desktop_mobile: {
        parts: [
          { key: "desktop", figure: f(500), share_percent: 27.8 },
          { key: "mobile", figure: f(1300), share_percent: 72.2 },
        ],
      },
    },
    actions: {
      total: row(515, 480, 400),
      action_rate: {
        current: rate(28.6),
        previous: rate(31.4),
        year_ago: rate(32),
        change: -2.8,
        year_change: -3.4,
      },
      actions: [
        {
          metric: "CALL_CLICKS",
          comparison: row(200, 180, 150),
          reported: true,
        },
        {
          metric: "WEBSITE_CLICKS",
          comparison: row(215, 200, 160),
          reported: true,
        },
        {
          metric: "BUSINESS_DIRECTION_REQUESTS",
          comparison: row(100, 100, 90),
          reported: true,
        },
      ],
      optional: [
        {
          metric: "BUSINESS_BOOKINGS",
          comparison: {
            current: f(0),
            previous: gone("not_reported"),
            year_ago: gone("not_reported"),
            change: null,
            change_percent: null,
            year_change: null,
            year_change_percent: null,
          },
          reported: true,
        },
      ],
    },
    daily: {
      availability: "available",
      days_expected: 30,
      days_synced: 30,
      missing_days: [],
      points: Array.from({ length: 30 }, (_, i) => ({
        day: day(i + 1),
        views: 50 + (i % 7) * 4,
        actions: 14 + (i % 5),
      })),
    },
    search_terms: {
      availability: "available",
      reason: null,
      terms: [
        {
          keyword: "brunch near me",
          value: 120,
          below_threshold: null,
          is_exact: true,
        },
        {
          keyword: "coco maya",
          value: 80,
          below_threshold: null,
          is_exact: true,
        },
        {
          keyword: "private event venue",
          value: null,
          below_threshold: 15,
          is_exact: false,
        },
      ],
    },
    locations: [],
  },
  reviews: {
    availability: "available",
    reason: null,
    new_in_month: f(18),
    average_rating_in_month: rate(4.8),
    average_rating_overall: rate(4.8),
    total_count: f(342),
    responses_published: f(16),
    responded_to_new: f(16),
    response_rate_percent: rate(88.9),
    distribution_overall: [1, 2, 3, 4, 5].map((stars, i) => ({
      stars,
      count: [4, 6, 12, 60, 260][i],
    })),
    distribution_month: [1, 2, 3, 4, 5].map((stars, i) => ({
      stars,
      count: [0, 0, 1, 4, 13][i],
    })),
  },
  search_console: {
    availability: "available",
    reason: null,
    clicks: row(1386, 1118, 1118),
    impressions: row(27720, 22720, 22720),
    ctr_percent: {
      current: rate(5),
      previous: rate(4.9),
      year_ago: null,
      change: 0.1,
      year_change: null,
    },
    average_position: {
      current: rate(8.4),
      previous: rate(9),
      year_ago: null,
      change: -0.6,
      year_change: null,
    },
    top_queries: [
      {
        query: "brunch",
        clicks: 300,
        impressions: 4000,
        ctr: 7.5,
        position: 3.2,
        previous_clicks: 250,
        clicks_change: 50,
      },
    ],
    top_pages: [
      {
        page: "https://cocomaya.example/menu/",
        clicks: 420,
        impressions: 6000,
        ctr: 7,
        position: 4,
        previous_clicks: null,
        clicks_change: null,
      },
    ],
    lag_days: null,
  },
  analytics: {
    availability: "available",
    reason: null,
    organic_sessions: row(4110, 3140, 3140),
  },
  local_rank: { state: "not_tracked", value: null },
  work: {
    groups: [
      { kind: "gbp_post", count: 4, titles: ["Weekend brunch is back"] },
      { kind: "website_content", count: 1, titles: ["Private events guide"] },
      { kind: "review_response", count: 16, titles: [] },
      { kind: "gbp_profile_change", count: 0, titles: [] },
      { kind: "website_change", count: 2, titles: ["/menu/"] },
    ],
  },
  ...overrides,
});
export const detail = (overrides = {}) => ({
  organization_id: ORG,
  client_name: "Coco Maya",
  client_slug: "coco-maya",
  month: "2026-09-01",
  revision: 1,
  revision_count: 1,
  status: "draft",
  readiness: "ready_with_note",
  is_current: true,
  created_at: "2026-10-01T15:00:00Z",
  approved_at: null,
  delivery: null,
  snapshot: snapshot(),
  narrative: { what_changed: "", next_work: "", origin: "none" },
  permissions: { can_generate: true, can_publish: true },
  ...overrides,
});
