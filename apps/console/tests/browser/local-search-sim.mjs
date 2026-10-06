// Synthetic Local Search and Business Profile feeds for browser tests and screenshots only.
// Never imported by the app. One organization (Synthetic Beta, two locations) gets rich data;
// every other organization keeps the edge-case fixture the earlier steps use.
const days = (count) =>
  Array.from({ length: count }, (_, i) => {
    const d = new Date(Date.UTC(2026, 9, 4) - (count - 1 - i) * 86400000);
    return d.toISOString().slice(0, 10);
  });
const wave = (i, base, swing) =>
  Math.round(base + Math.sin(i / 2.3) * swing + ((i * 7) % 5) * (swing / 6));
const uuid = (n) => `99999999-0000-4000-8000-${String(n).padStart(12, "0")}`;
const places = [
  { gbp: uuid(1), location: uuid(2), name: "Cococabana Beach Club", scale: 1 },
  { gbp: uuid(3), location: uuid(4), name: "Cococabana Kitchen", scale: 0.6 },
];
const queries = [
  ["cococabana san diego", 412, 3120, 0.132, 1.2, "/"],
  ["beach bar pacific beach", 238, 5410, 0.044, 4.8, "/"],
  ["brunch pacific beach", 196, 6820, 0.029, 6.1, "/menu/"],
  ["sunset happy hour san diego", 171, 4980, 0.034, 5.4, "/happy-hour/"],
  ["live music pacific beach", 142, 3890, 0.037, 7.2, "/events/"],
  ["private events san diego beach", 118, 2210, 0.053, 5.9, "/private-events/"],
  ["rooftop bar san diego", 96, 7440, 0.013, 11.3, "/"],
  ["best margaritas san diego", 88, 6010, 0.015, 9.8, "/menu/"],
  ["dog friendly restaurants pacific beach", 74, 1980, 0.037, 6.7, "/menu/"],
  ["fish tacos pacific beach", 69, 2640, 0.026, 8.1, "/menu/"],
  ["cococabana menu", 61, 540, 0.113, 2.1, "/menu/"],
  ["pacific beach bars with a view", 52, 3320, 0.016, 12.4, "/"],
  ["birthday dinner san diego", 44, 1560, 0.028, 10.2, "/private-events/"],
  ["bottomless mimosas pacific beach", 41, 2290, 0.018, 9.4, "/menu/"],
  ["cococabana reservations", 39, 410, 0.095, 1.9, "/reservations/"],
  ["waterfront dining san diego", 33, 4120, 0.008, 15.6, "/"],
  ["pb brunch spots", 31, 1730, 0.018, 11.7, "/menu/"],
  ["beach wedding venue san diego", 27, 980, 0.028, 13.2, "/private-events/"],
  ["happy hour deals pacific beach", 24, 1450, 0.017, 12.9, "/happy-hour/"],
  ["live band san diego", 19, 870, 0.022, 14.3, "/events/"],
].map(([query, clicks, impressions, ctr, position]) => ({
  query,
  clicks,
  impressions,
  ctr,
  position,
}));
const landing = [
  ["https://cococabana.example/", 702, 14200, 0.049, 5.6],
  ["https://cococabana.example/menu/", 421, 18900, 0.022, 7.8],
  ["https://cococabana.example/happy-hour/", 188, 5800, 0.032, 5.9],
  ["https://cococabana.example/events/", 161, 4900, 0.033, 7.5],
  ["https://cococabana.example/private-events/", 143, 3900, 0.037, 6.2],
  ["https://cococabana.example/reservations/", 61, 700, 0.087, 2.4],
].map(([page, clicks, impressions, ctr, position]) => ({
  page,
  page_id: page.endsWith("reservations/") ? null : uuid(300 + page.length),
  index_status: page.endsWith("private-events/")
    ? "not_indexable"
    : page.endsWith("reservations/")
      ? "not_crawled"
      : "indexable",
  clicks,
  impressions,
  ctr,
  position,
}));
export function search(org, count) {
  const series = days(count).map((date, i) => ({
    date,
    clicks: wave(i, 62, 18),
    impressions: wave(i, 1400, 300),
    ctr: 0.044,
    position: 8.4,
  }));
  return {
    organization_id: org,
    websites: [
      {
        id: uuid(10),
        name: "cococabana.example",
        canonical_origin: "https://cococabana.example",
        location_id: places[0].location,
        status: "active",
      },
    ],
    website_id: uuid(10),
    syncs: [
      {
        id: uuid(20),
        status: "completed",
        failure_code: null,
        started_at: "2026-10-04T06:00:00Z",
        completed_at: "2026-10-04T06:03:00Z",
        source_id: uuid(21),
        source: "search_console",
      },
      {
        id: uuid(22),
        status: "completed",
        failure_code: null,
        started_at: "2026-10-03T06:00:00Z",
        completed_at: "2026-10-03T06:02:00Z",
        source_id: uuid(23),
        source: "analytics",
      },
    ],
    google_status: "connected",
    search_console: {
      connected: true,
      properties: [
        {
          id: uuid(21),
          external_property_id: "sc-domain:cococabana.example",
          freshness_status: "fresh",
          last_synced_at: "2026-10-04T06:03:00Z",
        },
      ],
      range: {
        start: series[0].date,
        end: series[count - 1].date,
        days: count,
      },
      comparison_range: {
        start: "2026-08-08",
        end: "2026-09-05",
        days: count,
      },
      freshness: { last_synced_at: "2026-10-04T06:03:00Z", status: "fresh" },
      metrics: {
        clicks: {
          current: 1842,
          previous: 1617,
          delta: 225,
          percent_delta: 13.9,
          quality: "valid",
          label: null,
        },
        impressions: {
          current: 41260,
          previous: 38790,
          delta: 2470,
          percent_delta: 6.4,
          quality: "valid",
          label: null,
        },
        ctr: {
          current: 0.0446,
          previous: 0.0417,
          delta: 0.0029,
          percent_delta: 7.0,
          quality: "valid",
          label: null,
        },
        position: {
          current: 8.4,
          previous: 9.1,
          delta: -0.7,
          percent_delta: -7.7,
          quality: "valid",
          label: null,
        },
      },
      series,
      top_queries: queries,
      top_pages: landing,
    },
    analytics: null,
    analytics_scope: "organization_all_channels",
    analytics_availability: "permission_required",
    pages: [],
    next_offset: null,
    crawls: [],
    profiles: places.map((p, i) => ({
      id: p.gbp,
      location_id: p.location,
      business_name: p.name,
      mapping_status: "confirmed",
      write_enabled: i === 0,
      last_synced_at: "2026-10-04T06:00:00Z",
    })),
    insights: [
      {
        code: "PAGE_GAINING_CLICKS",
        link: "pages",
        subject: "https://cococabana.example/menu/",
        current: 421,
        previous: 305,
        percent_change: 38,
        count: null,
      },
      {
        code: "SEARCH_CLICKS_UP",
        link: "search_console",
        subject: null,
        current: 1842,
        previous: 1617,
        percent_change: 13.9,
        count: null,
      },
      {
        code: "PROFILE_ACTIONS_UP",
        link: "google_business_profile",
        subject: null,
        current: 898,
        previous: 784,
        percent_change: 14.5,
        count: null,
      },
    ],
    technical_health: {
      pages_crawled: { state: "tracked", value: 26 },
      indexable_pages: { state: "tracked", value: 24 },
      excluded_pages: { state: "tracked", value: 2 },
      pages_with_issues: { state: "tracked", value: 4 },
      structured_data_pages: { state: "tracked", value: 22 },
      google_indexed_pages: { state: "not_tracked", value: null },
      last_crawled_at: "2026-10-03T06:00:00Z",
    },
    can_crawl: true,
    unsupported: ["geographic_rank_grid", "rank_scan", "google_indexation"],
  };
}
const total = (value, count, expected) => ({
  availability: value === null ? "no_data" : "available",
  value,
  days_covered: value === null ? 0 : count,
  days_expected: expected,
});
const comparison = (current, previous, count) => ({
  current: total(current, count, count),
  previous: total(previous, count, count),
  change: current !== null && previous !== null ? current - previous : null,
  change_percent:
    current !== null && previous
      ? Math.round(((current - previous) / previous) * 1000) / 10
      : null,
});
const BASE = {
  BUSINESS_IMPRESSIONS_DESKTOP_MAPS: [3120, 2870],
  BUSINESS_IMPRESSIONS_DESKTOP_SEARCH: [2410, 2290],
  BUSINESS_IMPRESSIONS_MOBILE_MAPS: [9840, 8610],
  BUSINESS_IMPRESSIONS_MOBILE_SEARCH: [5120, 5040],
  CALL_CLICKS: [214, 188],
  WEBSITE_CLICKS: [388, 341],
  BUSINESS_DIRECTION_REQUESTS: [296, 255],
  BUSINESS_CONVERSATIONS: [null, null],
  BUSINESS_BOOKINGS: [null, null],
  BUSINESS_FOOD_ORDERS: [null, null],
  BUSINESS_FOOD_MENU_CLICKS: [120, 96],
};
export function performance(org, params) {
  const period = params.get("period") ?? "28d";
  const count = { "7d": 7, "28d": 28, "90d": 90 }[period] ?? 28;
  const place = places.find((p) => p.location === params.get("location_id"));
  const scale = (place?.scale ?? 1) * (count / 28);
  const scaled = ([c, p]) => [
    c === null ? null : Math.round(c * scale),
    p === null ? null : Math.round(p * scale),
  ];
  const metrics = Object.entries(BASE).map(([metric, pair]) => {
    const [c, p] = scaled(pair);
    return { metric, ...comparison(c, p, count) };
  });
  const views = Object.entries(BASE)
    .filter(([metric]) => metric.startsWith("BUSINESS_IMPRESSIONS"))
    .reduce(
      (sum, [, pair]) => {
        const [c, p] = scaled(pair);
        return [sum[0] + c, sum[1] + p];
      },
      [0, 0],
    );
  const range = days(count);
  return {
    organization_id: org,
    period,
    month: null,
    location_id: place?.location ?? null,
    locations: places.map((p) => ({
      id: p.location,
      name: p.name,
      mapped: true,
    })),
    availability: "available",
    current_range: { start: range[0], end: range[count - 1], days: count },
    previous_range: { start: "2026-08-08", end: "2026-09-05", days: count },
    profile_views: comparison(views[0], views[1], count),
    metrics,
    search_terms: {
      availability: "available",
      month: "2026-09-01",
      terms: [
        ["pacific beach bar", 1480, null],
        ["cococabana", 1210, null],
        ["brunch pacific beach", 860, null],
        ["happy hour near me", 640, null],
        ["live music san diego", 410, null],
        ["beach restaurants", 330, null],
        ["bars with outdoor seating", 190, null],
        ["birthday venue", null, 15],
        ["margarita bar", null, 15],
        ["wedding reception pacific beach", null, 15],
      ].map(([keyword, value, below]) => ({
        keyword,
        value,
        below_threshold: below,
        is_exact: below === null,
      })),
    },
    series: range.map((day, i) => ({
      day,
      impressions: Math.round(wave(i, 640, 150) * scale),
      actions: Math.round(wave(i, 32, 9) * scale),
    })),
    source: {
      last_synced_at: "2026-10-04T06:00:00Z",
      last_status: "succeeded",
      last_failure_code: null,
    },
  };
}
const state = { posts: [], media: [], hours: [], changes: [], seq: 100 };
/** Screenshots only: the photo list with nothing in it. */
export function clearMedia() {
  state.media = [];
}
export function reset() {
  state.posts = [
    {
      id: uuid(31),
      post_key: uuid(41),
      revision: 1,
      post_type: "standard",
      content:
        "Sunset happy hour is back! Two-for-one margaritas on the patio, Monday to Friday from 4 to 6.",
      call_to_action: {
        actionType: "LEARN_MORE",
        url: "https://cococabana.example/happy-hour/",
      },
      event_or_offer: null,
      status: "awaiting_approval",
      publication: null,
    },
    {
      id: uuid(32),
      post_key: uuid(42),
      revision: 1,
      post_type: "standard",
      content:
        "Live music every Saturday night. Come early, grab a table by the water and stay for the sunset.",
      call_to_action: null,
      event_or_offer: null,
      status: "approved",
      publication: null,
    },
    {
      id: uuid(33),
      post_key: uuid(43),
      revision: 2,
      post_type: "standard",
      content:
        "Our new weekend brunch menu has landed: fish tacos, bottomless mimosas and the best ocean view in Pacific Beach.",
      call_to_action: {
        actionType: "BOOK",
        url: "https://cococabana.example/reservations/",
      },
      event_or_offer: null,
      status: "approved",
      publication: {
        id: uuid(51),
        status: "verified",
        scheduled_for: null,
        dispatched_at: "2026-09-28T17:00:00Z",
        provider_post_id: "provider-post-1",
        verified_at: "2026-09-28T17:05:00Z",
        recovery_allowed: false,
      },
    },
    {
      id: uuid(34),
      post_key: uuid(44),
      revision: 1,
      post_type: "standard",
      content:
        "Book your private event with us: birthdays, rehearsal dinners and company parties on the beach.",
      call_to_action: null,
      event_or_offer: null,
      status: "approved",
      publication: {
        id: uuid(52),
        status: "not_published",
        scheduled_for: null,
        dispatched_at: "2026-09-20T17:00:00Z",
        provider_post_id: null,
        verified_at: null,
        recovery_allowed: false,
      },
    },
    {
      id: uuid(35),
      post_key: uuid(45),
      revision: 1,
      post_type: "standard",
      content: "A draft nobody will miss.",
      call_to_action: null,
      event_or_offer: null,
      status: "approved",
      publication: {
        id: uuid(53),
        status: "discarded",
        scheduled_for: null,
        dispatched_at: null,
        provider_post_id: null,
        verified_at: null,
        recovery_allowed: false,
      },
    },
  ];
  state.media = [
    ["photo", "Owned by the business", "awaiting_approval", null],
    ["photo", "Owned by the business", "approved", null],
    [
      "cover",
      "Supplied by the client with permission",
      "published",
      "2026-09-22T10:00:00Z",
    ],
    ["logo", "Owned by the business", "published", "2026-09-01T10:00:00Z"],
  ].map(([media_type, rights_authority, status, verified_at], i) => ({
    id: uuid(60 + i),
    media_type,
    origin: i === 3 ? "link" : "upload",
    preview_url: `https://photos.example.invalid/cococabana-${i}.jpg`,
    rights_authority,
    status,
    verified_at,
  }));
  state.hours = [
    ["2026-11-26", "11:00", "15:00", "awaiting_approval"],
    ["2026-12-25", null, null, "approved"],
    ["2027-01-01", "16:00", "23:00", "approved"],
  ].map(([service_date, opens, closes, status], i) => ({
    id: uuid(70 + i),
    service_date,
    revision: 1,
    closed: opens === null,
    periods: opens === null ? [] : [{ opens, closes }],
    source: "console",
    status,
  }));
  state.changes = [
    {
      id: uuid(80),
      revision: 1,
      field_changes: [
        {
          field: "description",
          value:
            "Beachfront bar and kitchen in Pacific Beach with live music, sunset happy hours and weekend brunch.",
        },
      ],
      evidence: {},
      risk: "low",
      status: "awaiting_approval",
    },
  ];
}
reset();
const profile = (place) => ({
  title: place.name,
  storefrontAddress: {
    addressLines: [place.scale === 1 ? "4521 Ocean Blvd" : "1210 Garnet Ave"],
    locality: "San Diego",
    administrativeArea: "CA",
    postalCode: "92109",
  },
  phoneNumbers: {
    primaryPhone: place.scale === 1 ? "(858) 555-0142" : "(858) 555-0177",
  },
  websiteUri: "https://cococabana.example/",
  categories: { primaryCategory: { displayName: "Bar & grill" } },
  regularHours: {
    periods: [
      "MONDAY",
      "TUESDAY",
      "WEDNESDAY",
      "THURSDAY",
      "FRIDAY",
      "SATURDAY",
      "SUNDAY",
    ].map((openDay, i) => ({
      openDay,
      openTime: { hours: i > 3 ? 10 : 15 },
      closeTime: { hours: i > 3 ? 23 : 22 },
    })),
  },
  profile: {
    description:
      "Cococabana is a beachfront bar and kitchen in Pacific Beach. Fish tacos, frozen margaritas, live music and the best sunset in San Diego.",
  },
});
const detail = (org, place) => ({
  organization_id: org,
  location_id: place.location,
  profile_id: place.gbp,
  snapshot_id: uuid(90),
  profile: profile(place),
  observed_at: "2026-10-04T06:00:00Z",
  health: { healthy: true, blockers: [], warnings: [], ranking_claim: null },
  completeness: null,
  completeness_code: null,
  posts: state.posts,
  provider_posts: [],
  can_propose: true,
  can_approve: true,
  can_publish: true,
});
const ok = (body, status = 200) => ({ body, status });
/** Returns { body, status } for a Synthetic Beta request, or null to fall through. */
export function handle(path, method, parsed, url, org) {
  if (path === "command-center/local-search" && method === "GET")
    return ok(search(org, Number(url.searchParams.get("days") ?? 28)));
  if (path === "command-center/gbp/performance")
    return ok(performance(org, url.searchParams));
  const profileMatch = path.match(
    /^command-center\/local-search\/locations\/([^/]+)\/profiles\/([^/]+)$/,
  );
  if (profileMatch) {
    const place = places.find((p) => p.gbp === profileMatch[2]);
    return place ? ok(detail(org, place)) : ok({ code: "NOT_FOUND" }, 404);
  }
  if (path === "workflows/gbp.upload_media/runs" && method === "POST")
    return ok(
      { data: { workflow_run_id: uuid(++state.seq), status: "queued" } },
      201,
    );
  const ops = path.match(/^locations\/([^/]+)\/gbp\/operations\/(.+)$/);
  if (!ops) return null;
  const rest = ops[2];
  const seq = () => uuid(++state.seq);
  if (rest.endsWith("/media") && method === "GET")
    return ok({ data: state.media });
  if (rest.endsWith("/special-hours") && method === "GET")
    return ok({ data: state.hours });
  if (rest.endsWith("/change-sets") && method === "GET")
    return ok({ data: state.changes });
  if (rest.endsWith("/completeness"))
    return ok({
      data: {
        complete: false,
        known: [
          "title",
          "storefrontAddress",
          "regularHours",
          "profile",
          "phoneNumbers",
          "websiteUri",
        ],
        unknown: ["categories", "serviceItems"],
      },
    });
  if (method !== "POST") return null;
  if (rest.endsWith("/posts") && !rest.includes("reconcile")) {
    const row = {
      id: seq(),
      post_key: parsed.post_key ?? seq(),
      revision: 1,
      post_type: parsed.post_type,
      content: parsed.content,
      call_to_action: null,
      event_or_offer: null,
      status: "awaiting_approval",
      publication: null,
    };
    state.posts = [
      row,
      ...state.posts.filter((p) => p.post_key !== row.post_key),
    ];
    return ok({ data: row }, 201);
  }
  const decide = (list, id, approve) => {
    const item = list.find((x) => x.id === id);
    if (item) item.status = approve ? "approved" : "rejected";
    return ok({ data: item ?? {} });
  };
  let m;
  if ((m = rest.match(/^posts\/([^/]+)\/decision$/)))
    return decide(state.posts, m[1], parsed.approve);
  if ((m = rest.match(/^posts\/([^/]+)\/dispatch$/))) {
    const post = state.posts.find((p) => p.id === m[1]);
    if (post)
      post.publication = {
        id: seq(),
        status: "scheduled",
        scheduled_for: null,
        dispatched_at: null,
        provider_post_id: null,
        verified_at: null,
        recovery_allowed: false,
      };
    return ok({ data: post?.publication ?? {} }, 202);
  }
  if ((m = rest.match(/^posts\/publications\/([^/]+)\/(repost|discard)$/))) {
    const post = state.posts.find((p) => p.publication?.id === m[1]);
    if (post && m[2] === "discard") post.publication.status = "discarded";
    if (post && m[2] === "repost") {
      post.publication.status = "discarded";
      state.posts.unshift({
        ...post,
        id: seq(),
        revision: post.revision + 1,
        status: "awaiting_approval",
        publication: null,
      });
    }
    return ok({ data: {} }, m[2] === "repost" ? 201 : 200);
  }
  if (rest.endsWith("/posts/reconcile")) return ok({ data: { reconciled: 0 } });
  if (rest.endsWith("/media")) {
    // The upload arrives as multipart; the stand-in reads its fields and the file's size.
    const { fields, fileBytes } = parsed;
    if (fileBytes < 10 * 1024)
      return ok({ error: { code: "MEDIA_TOO_SMALL" } }, 422);
    const row = {
      id: seq(),
      media_type: fields.media_type,
      origin: "upload",
      preview_url: `https://photos.example.invalid/uploaded-${state.seq}.jpg`,
      rights_authority: fields.rights_authority,
      status: "awaiting_approval",
      verified_at: null,
    };
    state.media.unshift(row);
    return ok({ data: row }, 201);
  }
  if ((m = rest.match(/^media\/([^/]+)\/decide$/)))
    return decide(state.media, m[1], parsed.approve);
  if ((m = rest.match(/^media\/([^/]+)\/publish$/))) {
    const item = state.media.find((x) => x.id === m[1]);
    if (item) item.status = "publishing";
    return ok({ data: item ?? {} });
  }
  if (rest.endsWith("/special-hours")) {
    const row = {
      id: seq(),
      service_date: parsed.service_date,
      revision: 1,
      closed: parsed.closed,
      periods: parsed.periods,
      source: parsed.source,
      status: "awaiting_approval",
    };
    state.hours.push(row);
    return ok({ data: row }, 201);
  }
  if ((m = rest.match(/^special-hours\/([^/]+)\/decision$/)))
    return decide(state.hours, m[1], parsed.approve);
  if (rest.endsWith("/change-sets")) {
    const row = {
      id: seq(),
      revision: 2,
      field_changes: parsed.field_changes,
      evidence: {},
      risk: "low",
      status: "awaiting_approval",
    };
    state.changes.unshift(row);
    return ok({ data: row }, 201);
  }
  if ((m = rest.match(/^change-sets\/([^/]+)\/decision$/)))
    return decide(state.changes, m[1], parsed.approve);
  return null;
}
export const rich = { places };
/** Every other organization has no mapped Business Profile location. */
export function notConnected(org, params) {
  const period = params.get("period") ?? "28d";
  const count = { "7d": 7, "28d": 28, "90d": 90 }[period] ?? 28;
  const none = {
    availability: "not_connected",
    value: null,
    days_covered: 0,
    days_expected: 0,
  };
  const empty = {
    current: none,
    previous: none,
    change: null,
    change_percent: null,
  };
  const range = days(count);
  return {
    organization_id: org,
    period,
    month: null,
    location_id: null,
    locations: [],
    availability: "not_connected",
    current_range: { start: range[0], end: range[count - 1], days: count },
    previous_range: { start: range[0], end: range[count - 1], days: count },
    profile_views: empty,
    metrics: Object.keys(BASE).map((metric) => ({ metric, ...empty })),
    search_terms: { availability: "not_connected", month: null, terms: [] },
    series: [],
    source: {
      last_synced_at: null,
      last_status: null,
      last_failure_code: null,
    },
  };
}
