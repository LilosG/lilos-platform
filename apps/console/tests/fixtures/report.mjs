// A Coco Maya-shaped report, as the API answers it, for any period and comparison. Synthetic
// numbers only: a month's figure is a fixed base grown by a fixed step, so tests can predict it.
export const ORG = "11111111-1111-4111-8111-111111111111";
const f = (value, extra = {}) => ({
  availability: "available",
  value,
  ...extra,
});
const gone = (reason) => ({ availability: "unavailable", reason });
const rate = (v) =>
  v === null ? gone("no_views") : { availability: "available", value: v };
const index = (iso) =>
  Number(iso.slice(0, 4)) * 12 + Number(iso.slice(5, 7)) - 1;
const fromIndex = (n) =>
  `${Math.floor(n / 12)}-${String((n % 12) + 1).padStart(2, "0")}-01`;
export const add = (iso, n) => fromIndex(index(iso) + n);
export const monthsOf = (start, end) =>
  Array.from({ length: index(end) - index(start) + 1 }, (_, i) =>
    add(start, i),
  );
const lastDay = (iso) => {
  const year = Number(iso.slice(0, 4));
  const month = Number(iso.slice(5, 7));
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
};
export const periodSlug = (start, end) =>
  start === end ? start.slice(0, 7) : `${start.slice(0, 7)}_${end.slice(0, 7)}`;
export const comparisonSlug = (spec) =>
  spec.basis === "previous_period"
    ? "previous"
    : spec.basis === "same_period_last_year"
      ? "year-ago"
      : `vs-${periodSlug(spec.baseline_start, spec.baseline_end)}`;
/** What a month holds, by figure: grows 5% a month from a base, so earlier months are smaller. */
const BASE = {
  profile_views: 1500,
  calls: 150,
  website_clicks: 170,
  direction_requests: 80,
  search_clicks: 900,
  search_impressions: 19000,
  organic_sessions: 3100,
  new_reviews: 14,
};
const GROWTH = 1.05;
const anchor = "2025-09-01";
const valueOf = (key, month) =>
  Math.round(BASE[key] * GROWTH ** (index(month) - index(anchor)));
const sum = (key, months) =>
  months.reduce((total, month) => total + valueOf(key, month), 0);
const pct = (change, base) =>
  base ? Math.round((change / base) * 1000) / 10 : null;
const resolve = (period, spec) => {
  const span = index(period.end_month) - index(period.start_month) + 1;
  let compared;
  if (spec.basis === "previous_period")
    compared = {
      start_month: add(period.start_month, -span),
      end_month: add(period.start_month, -1),
    };
  else if (spec.basis === "same_period_last_year")
    compared = {
      start_month: add(period.start_month, -12),
      end_month: add(period.end_month, -12),
    };
  else
    compared = {
      start_month: spec.baseline_start,
      end_month: spec.baseline_end,
    };
  const comparedSpan =
    index(compared.end_month) - index(compared.start_month) + 1;
  return {
    basis: spec.basis,
    compared,
    year_ago:
      spec.basis === "same_period_last_year"
        ? null
        : {
            start_month: add(period.start_month, -12),
            end_month: add(period.end_month, -12),
          },
    compared_as: comparedSpan === span ? "total" : "monthly_average",
    span,
    comparedSpan,
  };
};
/** One count against its comparison, the way the API states it. */
const count = (key, period, resolved, options = {}) => {
  const months = monthsOf(period.start_month, period.end_month);
  const comparedMonths = monthsOf(
    resolved.compared.start_month,
    resolved.compared.end_month,
  );
  const current = sum(key, months);
  const total = sum(key, comparedMonths);
  const averaged = resolved.compared_as === "monthly_average";
  const shown = averaged ? Math.round(total / resolved.comparedSpan) : total;
  const against = averaged ? current / resolved.span : current;
  const base = averaged ? total / resolved.comparedSpan : total;
  const change = Math.round(against) - Math.round(base);
  const year = resolved.year_ago
    ? sum(
        key,
        monthsOf(resolved.year_ago.start_month, resolved.year_ago.end_month),
      )
    : null;
  const partial = options.partial;
  return {
    current: partial
      ? {
          availability: "partial",
          value: current,
          months_covered: months.length - 1,
          months_expected: months.length,
        }
      : f(current),
    compared: f(shown),
    compared_as: resolved.compared_as,
    current_monthly_average: averaged
      ? Math.round(current / resolved.span)
      : null,
    year_ago: year === null ? null : f(year),
    change: partial ? null : change,
    change_percent: partial ? null : pct(change, Math.round(base)),
    year_change: year === null || partial ? null : current - year,
    year_change_percent:
      year === null || partial ? null : pct(current - year, year),
  };
};
const points = (key, months, options = {}) =>
  months.map((month) =>
    options.missing?.includes(month)
      ? { month, availability: "unavailable", value: null }
      : {
          month,
          availability: options.partial?.includes(month)
            ? "partial"
            : "available",
          value: valueOf(key, month),
        },
  );
const series = (key, period, resolved, options = {}) => ({
  key,
  period: points(key, monthsOf(period.start_month, period.end_month), options),
  compared: points(
    key,
    monthsOf(resolved.compared.start_month, resolved.compared.end_month),
  ),
});
const metrics = [
  ["BUSINESS_IMPRESSIONS_DESKTOP_MAPS", 0.17],
  ["BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", 0.11],
  ["BUSINESS_IMPRESSIONS_MOBILE_MAPS", 0.33],
  ["BUSINESS_IMPRESSIONS_MOBILE_SEARCH", 0.39],
];
const termNames = [
  "brunch near me",
  "mexican restaurant",
  "coco maya",
  "happy hour",
  "private event venue",
  "best tacos",
  "margarita bar",
  "restaurants open now",
  "patio dining",
  "birthday dinner",
  "date night",
  "cocktail bar",
];
const queries = [
  ["brunch near me", false, 300],
  ["coco maya menu", true, 280],
  ["best tacos downtown", false, 210],
  ["coco maya", true, 190],
  ["margarita happy hour", false, 160],
  ["mexican restaurant open now", false, 150],
  ["private event venue", false, 120],
  ["patio dining", false, 100],
  ["birthday dinner ideas", false, 90],
  ["date night restaurant", false, 85],
  ["cocktail bar", false, 70],
  ["taco tuesday", false, 60],
  ["brunch specials", false, 55],
];
/**
 * The snapshot of one period against one comparison.
 * Options: `missing`/`partial` name months of the search figures that are not synced or not final;
 * `gone` removes whole sources ("search_console", "analytics", "reviews").
 */
export function snapshot(period, spec, options = {}) {
  const resolved = resolve(period, spec);
  const months = monthsOf(period.start_month, period.end_month);
  const lastMonth = months.at(-1);
  const cur = (key, o) => count(key, period, resolved, o);
  const views = cur("profile_views");
  const calls = cur("calls");
  const website = cur("website_clicks");
  const directions = cur("direction_requests");
  const actionTotal = (field) =>
    [calls, website, directions].reduce(
      (total, item) => total + (item[field]?.value ?? 0),
      0,
    );
  const actions = {
    current: f(actionTotal("current")),
    compared: f(actionTotal("compared")),
    compared_as: resolved.compared_as,
    current_monthly_average:
      calls.current_monthly_average === null
        ? null
        : Math.round(actionTotal("current") / resolved.span),
    year_ago: resolved.year_ago ? f(actionTotal("year_ago")) : null,
    change: calls.change + website.change + directions.change,
    change_percent: pct(
      calls.change + website.change + directions.change,
      actionTotal("compared"),
    ),
    year_change: resolved.year_ago
      ? actionTotal("current") - actionTotal("year_ago")
      : null,
    year_change_percent: resolved.year_ago
      ? pct(
          actionTotal("current") - actionTotal("year_ago"),
          actionTotal("year_ago"),
        )
      : null,
  };
  const searchOptions = options.partialSearch ? { partial: true } : {};
  const clicks = cur("search_clicks", searchOptions);
  const gbpMonthly = [
    "profile_views",
    "calls",
    "website_clicks",
    "direction_requests",
  ].map((key) => series(key, period, resolved));
  const actionSeries = {
    key: "profile_actions",
    period: months.map((month) => ({
      month,
      availability: "available",
      value:
        valueOf("calls", month) +
        valueOf("website_clicks", month) +
        valueOf("direction_requests", month),
    })),
    compared: monthsOf(
      resolved.compared.start_month,
      resolved.compared.end_month,
    ).map((month) => ({
      month,
      availability: "available",
      value:
        valueOf("calls", month) +
        valueOf("website_clicks", month) +
        valueOf("direction_requests", month),
    })),
  };
  const searchSeriesOptions = {
    missing: options.missing,
    partial: options.partial,
  };
  const total = views.current.value;
  const actionRateNow = Math.round((actions.current.value / total) * 1000) / 10;
  const actionRateBefore =
    Math.round((actions.compared.value / views.compared.value) * 1000) / 10;
  const share = (n) => Math.round((n / total) * 1000) / 10;
  const maps = Math.round(total * 0.5);
  const desktop = Math.round(total * 0.28);
  const headlineKeys = [
    ["profile_views", views],
    ["profile_actions", actions],
    ["website_search_clicks", clicks],
    ["organic_sessions", cur("organic_sessions")],
  ];
  const reviewsNew = cur("new_reviews");
  const snap = {
    schema_version: 2,
    period,
    comparison: {
      basis: resolved.basis,
      compared: resolved.compared,
      year_ago: resolved.year_ago,
      compared_as: resolved.compared_as,
    },
    location_names: options.internalNames ?? [
      "Coco Maya Downtown",
      "Coco Maya Beach",
    ],
    sync: {
      gbp: "2026-10-12",
      search_console: "2026-10-12",
      analytics: "2026-10-12",
    },
    readiness: "ready_with_note",
    notes: [
      ...(options.partialSearch || options.missing?.length
        ? [
            {
              code: "search_console_months_missing",
              section: "search_console",
              count: options.missing?.length ?? 1,
              location_id: null,
              metric: null,
            },
          ]
        : []),
      ...(options.bookings
        ? [
            {
              code: "optional_figure_not_reported",
              section: "profile_actions",
              count: options.bookingsCompared ?? 45,
              location_id: null,
              metric: "BUSINESS_BOOKINGS",
            },
          ]
        : []),
    ],
    headlines: headlineKeys
      .filter(
        ([key, item]) =>
          !(
            options.gone?.includes("search_console") &&
            key === "website_search_clicks"
          ) &&
          !(
            options.gone?.includes("analytics") && key === "organic_sessions"
          ) &&
          item.change !== null,
      )
      .slice(0, 4)
      .map(([key, item]) => ({ key, count: item, rate: null })),
    monthly: [
      ...gbpMonthly.slice(0, 1),
      actionSeries,
      ...gbpMonthly.slice(1),
      series("search_clicks", period, resolved, searchSeriesOptions),
      series("search_impressions", period, resolved, searchSeriesOptions),
      series("organic_sessions", period, resolved),
      series("new_reviews", period, resolved),
    ],
    gbp: {
      availability: "available",
      reason: null,
      current_range: {
        start: months[0],
        end: `${lastMonth.slice(0, 8)}${lastDay(lastMonth)}`,
        days: months.reduce((n, m) => n + lastDay(m), 0),
      },
      compared_range: {
        start: resolved.compared.start_month,
        end: `${resolved.compared.end_month.slice(0, 8)}${lastDay(resolved.compared.end_month)}`,
        days: monthsOf(
          resolved.compared.start_month,
          resolved.compared.end_month,
        ).reduce((n, m) => n + lastDay(m), 0),
      },
      year_ago_range: resolved.year_ago
        ? {
            start: resolved.year_ago.start_month,
            end: `${resolved.year_ago.end_month.slice(0, 8)}${lastDay(resolved.year_ago.end_month)}`,
            days: 1,
          }
        : null,
      through_date: `${lastMonth.slice(0, 8)}${lastDay(lastMonth)}`,
      profile_views: {
        total: views,
        sources: metrics.map(([metric, portion]) => ({
          metric,
          comparison: {
            ...views,
            current: f(Math.round(views.current.value * portion)),
            compared: f(Math.round(views.compared.value * portion)),
          },
        })),
        maps_search: {
          parts: [
            { key: "maps", figure: f(maps), share_percent: share(maps) },
            {
              key: "search",
              figure: f(total - maps),
              share_percent: share(total - maps),
            },
          ],
        },
        desktop_mobile: {
          parts: [
            {
              key: "desktop",
              figure: f(desktop),
              share_percent: share(desktop),
            },
            {
              key: "mobile",
              figure: f(total - desktop),
              share_percent: share(total - desktop),
            },
          ],
        },
      },
      actions: {
        total: actions,
        action_rate: {
          current: rate(actionRateNow),
          compared: rate(actionRateBefore),
          year_ago: null,
          change: Math.round((actionRateNow - actionRateBefore) * 10) / 10,
          year_change: null,
        },
        actions: [
          {
            metric: "CALL_CLICKS",
            comparison: calls,
            reported: true,
            comparable: true,
            note: null,
          },
          {
            metric: "WEBSITE_CLICKS",
            comparison: website,
            reported: true,
            comparable: true,
            note: null,
          },
          {
            metric: "BUSINESS_DIRECTION_REQUESTS",
            comparison: directions,
            reported: true,
            comparable: true,
            note: null,
          },
        ],
        optional: options.bookings
          ? [
              {
                metric: "BUSINESS_BOOKINGS",
                comparison: {
                  current: gone("not_reported"),
                  compared: f(options.bookingsCompared ?? 45),
                  compared_as: "total",
                  current_monthly_average: null,
                  year_ago: options.bookingsYear
                    ? f(options.bookingsYear)
                    : null,
                  change: null,
                  change_percent: null,
                  year_change: null,
                  year_change_percent: null,
                },
                reported: true,
                comparable: false,
                note: "optional_figure_not_reported",
              },
            ]
          : [],
      },
      daily: {
        availability: "available",
        days_expected: 1,
        days_synced: 1,
        missing_days: [],
        points: [{ day: months[0], views: 50, actions: 14 }],
      },
      search_terms: {
        availability: "available",
        reason: null,
        terms: termNames.map((keyword, i) =>
          i === 4
            ? { keyword, value: null, below_threshold: 15, is_exact: false }
            : {
                keyword,
                value: Math.round((900 - i * 60) * resolved.span),
                below_threshold: null,
                is_exact: true,
              },
        ),
        total_terms: 97,
        months_covered: resolved.span,
        months_expected: resolved.span,
      },
      locations: [],
    },
    reviews: options.gone?.includes("reviews")
      ? undefined
      : {
          availability: "available",
          reason: null,
          new_reviews: reviewsNew,
          average_rating_in_period: {
            current: rate(4.8),
            compared: rate(4.7),
            year_ago: null,
            change: 0.1,
            year_change: null,
          },
          average_rating_overall: {
            current: rate(4.8),
            compared: rate(4.7),
            year_ago: null,
            change: 0.1,
            year_change: null,
          },
          total_count: f(342),
          responses_published: f(16 * resolved.span),
          responded_to_new: f(14 * resolved.span),
          response_rate_percent: {
            current: rate(88.9),
            compared: rate(85.2),
            year_ago: null,
            change: 3.7,
            year_change: null,
          },
          distribution_overall: [1, 2, 3, 4, 5].map((stars, i) => ({
            stars,
            count: [4, 6, 12, 60, 260][i],
          })),
          distribution_period: [1, 2, 3, 4, 5].map((stars, i) => ({
            stars,
            count: [0, 0, 1, 4, 13][i],
          })),
        },
    search_console: options.gone?.includes("search_console")
      ? undefined
      : {
          availability: options.partialSearch ? "partial" : "available",
          reason: null,
          clicks,
          impressions: cur("search_impressions", searchOptions),
          ctr_percent: {
            current: rate(4.8),
            compared: rate(4.6),
            year_ago: null,
            change: 0.2,
            year_change: null,
          },
          average_position: {
            current: rate(8.4),
            compared: rate(9),
            year_ago: null,
            change: -0.6,
            year_change: null,
          },
          top_queries: queries.map(([query, branded, base]) => ({
            query,
            is_branded: branded,
            clicks: base * resolved.span,
            impressions: base * 12 * resolved.span,
            ctr: 7.5,
            position: 3.2,
            compared_clicks: Math.round(base * 0.9 * resolved.span),
            clicks_change: Math.round(base * 0.1 * resolved.span),
          })),
          top_pages: (options.urlVariants
            ? [
                ["https://cocomaya.example/", 210],
                ["http://cocomaya.example/", 90],
                ["https://www.cocomaya.example/", 60],
                ["https://cocomaya.example/index.html", 20],
                ["https://cocomaya.example/menu/", 420],
                ["https://cocomaya.example/private-events/", 160],
              ]
            : [
                ["https://cocomaya.example/menu/", 420],
                ["https://cocomaya.example/", 380],
                ["https://cocomaya.example/private-events/", 160],
              ]
          ).map(([page, base]) => ({
            page,
            clicks: base * resolved.span,
            impressions: base * 14 * resolved.span,
            ctr: 7,
            position: 4,
            compared_clicks: null,
            clicks_change: null,
          })),
          branded_share_percent: 31.4,
          lag_days: null,
        },
    analytics: options.gone?.includes("analytics")
      ? undefined
      : {
          availability: "available",
          reason: null,
          organic_sessions: cur("organic_sessions"),
        },
    local_rank: { state: "not_tracked", value: null },
    work: {
      groups: [
        {
          kind: "gbp_post",
          count: 4 * resolved.span,
          titles: ["Weekend brunch is back", "New cocktail menu"],
        },
        {
          kind: "website_content",
          count: resolved.span,
          titles: ["Private events guide"],
        },
        { kind: "review_response", count: 16 * resolved.span, titles: [] },
        { kind: "gbp_profile_change", count: 0, titles: [] },
        { kind: "website_change", count: 2, titles: ["/menu/"] },
      ],
    },
  };
  const unavailable = (reason) => ({
    current: gone(reason),
    compared: gone(reason),
    compared_as: "total",
    current_monthly_average: null,
    year_ago: null,
    change: null,
    change_percent: null,
    year_change: null,
    year_change_percent: null,
  });
  const rates = (reason) => ({
    current: gone(reason),
    compared: gone(reason),
    year_ago: null,
    change: null,
    year_change: null,
  });
  if (options.gone?.includes("reviews"))
    snap.reviews = {
      availability: "unavailable",
      reason: "not_synced",
      new_reviews: unavailable("not_synced"),
      average_rating_in_period: rates("not_synced"),
      average_rating_overall: rates("not_synced"),
      total_count: gone("not_synced"),
      responses_published: gone("not_synced"),
      responded_to_new: gone("not_synced"),
      response_rate_percent: rates("not_synced"),
      distribution_overall: [1, 2, 3, 4, 5].map((stars) => ({
        stars,
        count: 0,
      })),
      distribution_period: [1, 2, 3, 4, 5].map((stars) => ({
        stars,
        count: 0,
      })),
    };
  if (options.gone?.includes("search_console"))
    snap.search_console = {
      availability: "unavailable",
      reason: "not_connected",
      clicks: unavailable("not_connected"),
      impressions: unavailable("not_connected"),
      ctr_percent: rates("not_connected"),
      average_position: rates("not_connected"),
      top_queries: [],
      top_pages: [],
      branded_share_percent: null,
      lag_days: null,
    };
  if (options.gone?.includes("analytics"))
    snap.analytics = {
      availability: "unavailable",
      reason: "not_connected",
      organic_sessions: unavailable("not_connected"),
    };
  if (options.partialSearch || options.missing?.length) {
    // The figure covers fewer months than the period: partial, with how many.
    const covered = months.length - (options.missing?.length ?? 1);
    for (const key of ["clicks", "impressions"]) {
      const item = snap.search_console[key];
      item.current = {
        availability: "partial",
        value: item.current.value,
        months_covered: covered,
        months_expected: months.length,
      };
      item.change = null;
      item.change_percent = null;
      item.year_change = null;
      item.year_change_percent = null;
    }
    snap.search_console.availability = "partial";
    snap.headlines = snap.headlines.filter(
      (item) => item.key !== "website_search_clicks",
    );
  }
  if (options.searchAlone) {
    // No search data before the report period: nothing to set the period against.
    const sc = snap.search_console;
    for (const key of ["clicks", "impressions"]) {
      sc[key].compared = gone("not_synced");
      sc[key].change = null;
      sc[key].change_percent = null;
      sc[key].year_ago = null;
      sc[key].year_change = null;
      sc[key].year_change_percent = null;
    }
    sc.ctr_percent.compared = gone("not_synced");
    sc.ctr_percent.change = null;
    sc.average_position.compared = gone("not_synced");
    sc.average_position.change = null;
    snap.headlines = snap.headlines.filter(
      (item) => item.key !== "website_search_clicks",
    );
    snap.notes.push({
      code: "search_console_compared_period_unavailable",
      section: "search_console",
      count: null,
      location_id: null,
      metric: null,
    });
  }
  if (options.search === "results")
    snap.search_movement = movementOf(months.length, true);
  if (options.search === "alone")
    snap.search_movement = movementOf(months.length, false);
  return JSON.parse(
    JSON.stringify(snap, (key, value) => (value === undefined ? null : value)),
  );
}
/** The stored searches behind the topics and gains. Positions and counts are synthetic. */
const MOVEMENT = [
  ["san diego rooftop venues", [7.5, 13, 1], [3.2, 182, 1]],
  ["rooftop party venues in san diego", [9, 10, 0], [4.4, 136, 0]],
  ["rooftop event space san diego", [11.2, 13, 0], [6.4, 159, 0]],
  ["rooftop venues san diego", [6.1, 38, 0], [5.1, 189, 4]],
  ["rehearsal dinner san diego", [7.2, 10, 0], [6.5, 128, 3]],
  ["san diego bachelorette party", [18.4, 49, 0], [15, 546, 2]],
  ["happy hour little italy san diego", [10.7, 82, 3], [8.5, 392, 14]],
  ["best happy hour little italy san diego", [15.3, 13, 1], [7.6, 101, 6]],
  ["happy hour in little italy", [12, 7, 1], [5.9, 70, 4]],
  ["little italy happy hour", [10.7, 75, 5], [8.9, 372, 10]],
  ["best brunch spots near me", [26, 2, 0], [7.1, 177, 0]],
  ["brunch in san diego with a view", [21.6, 9, 0], [9.3, 173, 0]],
  ["rooftop brunch san diego", [6.1, 178, 5], [4.1, 240, 13]],
  ["brunch san diego", [30.6, 565, 7], [22.9, 898, 5]],
  ["little italy san diego", [9.3, 32, 1], [9.5, 525, 4]],
  ["little italy bars", [10.1, 224, 0], [8.8, 429, 1]],
  ["restaurants in little italy", [18, 266, 2], [16.7, 374, 8]],
  ["little italy restaurants", [18.1, 1308, 11], [18.3, 1343, 21]],
  ["best restaurants for date night", [null, null, null], [9.5, 129, 0]],
  ["cocomaia san diego", [2.1, 300, 30], [1.9, 320, 41]],
];
function movementOf(span, comparable) {
  return {
    comparable,
    months_covered: span,
    months_expected: span,
    compared_months_covered: comparable ? span : 0,
    compared_months_expected: span,
    queries: MOVEMENT.map(([query, before, after]) => ({
      query,
      before_position: comparable ? before[0] : null,
      after_position: after[0],
      before_impressions: comparable ? before[1] : null,
      after_impressions: after[1],
      before_clicks: comparable ? before[2] : null,
      after_clicks: after[2],
    })),
  };
}
const TOPICS = {
  topics: [
    {
      key: "private-events",
      label: "Private events & groups",
      queries: MOVEMENT.slice(0, 6).map((row) => row[0]),
    },
    {
      key: "happy-hour",
      label: "Happy hour",
      queries: MOVEMENT.slice(6, 10).map((row) => row[0]),
    },
    {
      key: "brunch",
      label: "Brunch",
      queries: MOVEMENT.slice(10, 14).map((row) => row[0]),
    },
    {
      key: "little-italy",
      label: "Little Italy & dining",
      queries: MOVEMENT.slice(14, 19).map((row) => row[0]),
    },
  ],
  brand_variants: ["cocomaia san diego"],
};
const GAIN_GROUPS = [
  ["private-events", "Private events & groups", [0, 1, 2, 3, 4, 5]],
  ["happy-hour", "Happy hour", [6, 7, 8, 9]],
  ["brunch", "Brunch", [10, 11, 12, 13]],
  ["little-italy", "Little Italy & dining", [14, 15, 16, 18]],
];
/** What the API works out from the movement and the topics, for one report. */
function resultsOf(span, comparable) {
  const line = (index) => {
    const [query, before, after] = MOVEMENT[index];
    return {
      query,
      position_before: comparable ? before[0] : null,
      position_after: after[0],
      impressions_before: comparable ? before[1] : null,
      impressions_after: after[1],
      clicks_before: comparable ? before[2] : null,
      clicks_after: after[2],
    };
  };
  const topic = (key, label, examples, top, position, clicks) => ({
    key,
    label,
    examples,
    top_ten_before: comparable ? top[0] : null,
    top_ten_after: top[1],
    position_before: comparable ? position[0] : null,
    position_after: position[1],
    clicks_before: comparable ? clicks[0] : null,
    clicks_after: clicks[1],
  });
  return {
    comparable,
    months_covered: span,
    months_expected: span,
    top_ten_before: comparable ? 95 : null,
    top_ten_after: 171,
    new_to_page_one: comparable ? 64 : null,
    clicks_before: comparable ? 412 : null,
    clicks_after: 542,
    impressions_before: comparable ? 29986 : null,
    impressions_after: 37290,
    position_before: comparable ? 15.8 : null,
    position_after: 14.6,
    topics: [
      topic(
        "private-events",
        "Private events & groups",
        ["rooftop venues", "bachelorette party", "rehearsal dinner"],
        [2, 32],
        [14.1, 11.4],
        [6, 26],
      ),
      topic(
        "happy-hour",
        "Happy hour",
        ["little italy happy hour"],
        [2, 10],
        [16.1, 10.9],
        [32, 64],
      ),
      topic(
        "brunch",
        "Brunch",
        ["brunch san diego", "rooftop brunch"],
        [26, 33],
        [14.3, 13.1],
        [146, 173],
      ),
      topic(
        "little-italy",
        "Little Italy & dining",
        ["little italy bars", "little italy restaurants"],
        [51, 77],
        [12.4, 11.4],
        [191, 311],
      ),
    ],
    gains: comparable
      ? GAIN_GROUPS.map(([key, label, rows]) => ({
          key,
          label,
          rows: rows.map(line),
        }))
      : [],
  };
}
export const PREVIOUS = {
  basis: "previous_period",
  baseline_start: null,
  baseline_end: null,
};
const figure = (key, c) => ({
  key,
  unit: "count",
  current:
    c.compared_as === "monthly_average"
      ? c.current_monthly_average
      : c.current.value,
  monthly_average: c.compared_as === "monthly_average",
  compared: c.compared.value,
  change: c.change,
  change_percent: c.change_percent,
});
const words = (c) => `${Math.round(c.current.value).toLocaleString("en-US")}`;
/** Result cards as Hermes would draft them for this report: figures from the snapshot. */
function cardsOf(snap, options) {
  const views = snap.gbp.profile_views.total;
  const clicks = snap.search_console.clicks;
  const reviewsNew = snap.reviews.new_reviews;
  const cards = [];
  if (options.search === "results")
    cards.push({
      figure_keys: ["searches_in_top_ten"],
      figures: [
        {
          key: "searches_in_top_ten",
          unit: "count",
          current: 171,
          monthly_average: false,
          compared: 95,
          change: 76,
          change_percent: 80,
        },
      ],
      tone: "good",
      headline: true,
      title: "More first-page Google rankings",
      text: "The website now ranks in Google’s top 10 for 171 searches that don’t include the restaurant’s name, up from 95. The biggest gains are in event venue, happy hour and rooftop searches.",
    });
  cards.push({
    figure_keys: ["profile_views"],
    figures: [figure("profile_views", views)],
    tone: "good",
    headline: !options.search,
    title: "More people found the profile",
    text: `The Google profile was seen ${words(views)} times, up from ${views.compared.value.toLocaleString("en-US")}. More views mean more people deciding where to eat.`,
  });
  if (
    snap.search_console.availability !== "unavailable" &&
    snap.search_console.clicks.change !== null
  )
    cards.push({
      figure_keys: ["search_clicks"],
      figures: [figure("search_clicks", clicks)],
      tone: options.partialSearch ? "neutral" : "good",
      headline: false,
      title: "More visits from Google Search",
      text: `Google Search sent ${words(clicks)} clicks to the website, against ${clicks.compared.value.toLocaleString("en-US")} before.`,
    });
  cards.push({
    figure_keys: ["new_reviews"],
    figures: [figure("new_reviews", reviewsNew)],
    tone: "good",
    headline: false,
    title: "More new reviews",
    text: `${words(reviewsNew)} new reviews arrived, up from ${reviewsNew.compared.value.toLocaleString("en-US")}, and every one was answered.`,
  });
  return cards.slice(0, 4);
}
/** The report view the API answers for one stored revision. */
export const detail = (overrides = {}) => {
  const period = overrides.period ?? {
    start_month: "2026-09-01",
    end_month: "2026-09-01",
  };
  const spec = overrides.comparison ?? PREVIOUS;
  const options = overrides.options ?? {};
  const snap = snapshot(period, spec, options);
  const span = monthsOf(period.start_month, period.end_month).length;
  const narrative = {
    what_changed: "",
    next_work: "",
    origin: "none",
    ...overrides.narrative,
  };
  if (!narrative.result_cards)
    narrative.result_cards = options.cards ? cardsOf(snap, options) : [];
  return {
    organization_id: ORG,
    client_name: "Coco Maya",
    client_slug: "coco-maya",
    period,
    comparison: spec,
    revision: 1,
    revision_count: 1,
    status: "draft",
    readiness: "ready_with_note",
    is_current: true,
    created_at: "2026-10-01T15:00:00Z",
    approved_at: null,
    delivery: null,
    snapshot: snap,
    narrative,
    topics: options.search ? TOPICS : null,
    search_results: options.search
      ? resultsOf(span, options.search === "results")
      : null,
    profile_names: options.names ?? [],
    milestones: options.milestones ?? [],
    permissions: { can_generate: true, can_publish: true },
    ...Object.fromEntries(
      Object.entries(overrides).filter(
        ([key]) => !["options", "narrative"].includes(key),
      ),
    ),
  };
};

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const monthName = (iso) => MONTH_NAMES[Number(iso.slice(5, 7)) - 1];
const group = (start, end) =>
  start === end
    ? `in ${monthName(start)}`
    : `from ${monthName(start)} to ${monthName(end)}`;
const before = (start, end) =>
  start === end
    ? `in ${monthName(start)}`
    : `over ${monthName(start)} to ${monthName(end)}`;
const n = (value) => Math.round(value).toLocaleString("en-US");
/**
 * The "what changed" paragraph a drafted summary would hold for this report, built from the
 * fixture's own figures and worded for its period, so it cannot drift from the numbers.
 */
export function narrativeFor(period, spec, options = {}) {
  const snap = snapshot(period, spec, options);
  const views = snap.gbp.profile_views.total;
  const actions = snap.gbp.actions.total;
  const averaged = views.compared_as === "monthly_average";
  const compared = snap.comparison.compared;
  const against = averaged
    ? `a monthly average of ${n(views.compared.value)} ${before(compared.start_month, compared.end_month)}`
    : `${n(views.compared.value)} ${before(compared.start_month, compared.end_month)}`;
  const current = averaged
    ? `${n(views.current_monthly_average)} times a month on average`
    : `${n(views.current.value)} times`;
  const percent = Math.abs(views.change_percent);
  const direction = views.change >= 0 ? "up" : "down";
  return {
    what_changed: `Your profile was viewed ${current} ${group(period.start_month, period.end_month)}, ${direction} from ${against}, a ${direction === "up" ? "rise" : "fall"} of ${percent}%. Calls, website clicks and direction requests together came to ${n(actions.current.value)}.`,
    next_work:
      "We will keep publishing weekly posts, answer every review, and watch the private events search terms.",
  };
}
