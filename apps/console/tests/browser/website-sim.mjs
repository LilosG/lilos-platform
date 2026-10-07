// Website & Content scenarios for the simulator. Each mode answers the same two reads the
// real API does, so the production loaders, adapters and screens are the code under test.
const uuid = (n) =>
  `${n.toString(16).padStart(8, "0")}-0000-4000-8000-000000000000`;
const SITE_A = "11111111-1111-4111-8111-111111111111";
const SITE_B = uuid(0xb0b);
const ago = (days) => new Date(Date.now() - days * 86_400_000).toISOString();
const unsupported = [
  "named_cta_events",
  "conversion_funnels",
  "page_health_score",
  "google_indexation",
];
const site = (id, name, origin) => ({
  id,
  name,
  canonical_origin: origin,
  location_id: SITE_A,
  status: "active",
});
const page = (n, site_id, path, over = {}) => ({
  id: uuid(n),
  website_id: site_id,
  normalized_url: `https://synthetic.example.invalid${path}`,
  title: `Synthetic ${path.replaceAll("/", " ").trim() || "home"}`,
  http_status: 200,
  indexability: "indexable",
  quality_status: "clean",
  observed_at: ago(2),
  technical_issues: [],
  ...over,
});
const crawl = (n, site_id, status, days) => ({
  id: uuid(0xc00 + n),
  website_id: site_id,
  status,
  stop_reason: null,
  started_at: ago(days),
  completed_at: status === "running" ? null : ago(days),
  safe_result: { page_evidence_version: "crawl_page.v1" },
});
const opportunity = (org, n, site_id, page_id, type) => ({
  id: `seo_opportunity:${uuid(0x900 + n)}`,
  source_kind: "seo_opportunity",
  kind: "seo",
  source_id: uuid(0x900 + n),
  organization_id: org,
  client: {
    organization_id: org,
    name: "Synthetic Alpha",
    slug: "synthetic-alpha",
  },
  location_id: null,
  website_id: site_id,
  page_id,
  classification: "Issue",
  source_type: type,
  status: "identified",
  priority: 80,
  evidence: {},
  score_explanation: {},
  observed_at: ago(1),
  evidence_context: {
    source: "crawl",
    quality: null,
    freshness_at: null,
    period_start: null,
    period_end: null,
    limitation_code: null,
  },
  priority_band: "high",
  headline: null,
  confidence: null,
  summary: null,
  subject: { query: null, path: "/menu/" },
  lifecycle: "open",
  verified_at: null,
  importance_reason: null,
  earlier_observations: [],
  evidence_summary: {
    source: "crawl",
    signal: type,
    metrics: [],
    source_count: null,
  },
  next_action: "request_recommendation",
  latest_revision_status: null,
  site_change: "configured",
  site_change_reason: null,
});
const base = (org) => ({
  organization_id: org,
  websites: [],
  website_id: null,
  pages: [],
  crawls: [],
  next_page_offset: null,
  opportunities: [],
  next_opportunity_offset: null,
  content: [],
  next_content_offset: null,
  page_availability: "available",
  content_availability: "available",
  content_scope: "organization",
  can_create: true,
  can_crawl: true,
  conversions: "unavailable_no_canonical_path_source",
  unsupported,
});
export const modes = [
  "default",
  "rich",
  "empty",
  "no_website",
  "no_access",
  "unavailable",
  "failed",
  "clean",
  "error",
];
/** The workspace for one scenario; null when the scenario answers with a server error. */
export function workspace(mode, org, requested) {
  const a = site(
    SITE_A,
    "Synthetic hospitality site",
    "https://synthetic.example.invalid",
  );
  const b = site(
    SITE_B,
    "Synthetic second site",
    "https://second.example.invalid",
  );
  const data = base(org);
  if (mode === "error") return null;
  if (mode === "no_website") return data;
  data.websites = mode === "rich" ? [a, b] : [a];
  data.website_id = requested ?? SITE_A;
  if (mode === "no_access") {
    data.page_availability = "permission_required";
    data.can_crawl = false;
    return data;
  }
  if (mode === "unavailable") {
    data.page_availability = "unavailable";
    return data;
  }
  if (mode === "empty") return data;
  if (data.website_id === SITE_B) {
    data.pages = [
      page(0xb1, SITE_B, "/", { title: "Second site home" }),
      page(0xb2, SITE_B, "/contact/", {
        title: "Second site contact",
        quality_status: "issues_detected",
        technical_issues: ["missing_title"],
      }),
    ];
    data.crawls = [crawl(2, SITE_B, "completed", 1)];
    return data;
  }
  if (mode === "clean") {
    data.pages = [
      page(1, SITE_A, "/"),
      page(2, SITE_A, "/menu/"),
      page(3, SITE_A, "/events/"),
    ];
    data.crawls = [crawl(1, SITE_A, "completed", 1)];
    return data;
  }
  if (mode === "failed") {
    data.pages = [page(1, SITE_A, "/", { observed_at: ago(9) })];
    data.crawls = [
      crawl(1, SITE_A, "failed", 1),
      crawl(2, SITE_A, "completed", 9),
    ];
    return data;
  }
  // rich: a spread of states, one that is closed to search engines, a long title, two proposals.
  data.pages = [
    page(1, SITE_A, "/"),
    page(2, SITE_A, "/menu/", {
      title: "Synthetic menu",
      quality_status: "issues_detected",
      technical_issues: ["missing_meta_description", "multiple_h1"],
    }),
    page(3, SITE_A, "/events/", {
      title:
        "Private events and group dining at the synthetic restaurant, including holiday parties",
      quality_status: "issues_detected",
      technical_issues: ["missing_title"],
    }),
    page(4, SITE_A, "/gift-cards/", {
      title: null,
      indexability: "not_indexable",
      quality_status: "issues_detected",
      technical_issues: ["missing_meta_description"],
    }),
    page(5, SITE_A, "/old-menu/", {
      http_status: 404,
      quality_status: "issues_detected",
      technical_issues: ["non_200_status", "some_future_code"],
    }),
    page(6, SITE_A, "/about/", {
      quality_status: "partial",
      http_status: null,
    }),
    page(7, SITE_A, "/jobs/", {
      indexability: null,
      quality_status: "unknown",
      observed_at: null,
    }),
    page(8, SITE_A, "/reservations/"),
  ];
  data.crawls = [
    crawl(1, SITE_A, "completed", 2),
    crawl(3, SITE_A, "partial", 12),
  ];
  data.opportunities = [
    opportunity(org, 1, SITE_A, uuid(2), "missing_meta_description"),
    opportunity(org, 2, SITE_A, uuid(3), "missing_title"),
  ];
  return data;
}
/** One page's evidence, the repository link and its proposals; null when no such page exists. */
export function pageDetail(mode, org, websiteId, pageId) {
  const space = workspace(mode, org, websiteId);
  const row = space?.pages.find((p) => p.id === pageId);
  if (!row || row.website_id !== websiteId) return null;
  const rich = mode === "rich";
  return {
    evidence: {
      version: "page_intelligence.v1",
      identity: {
        organization_id: org,
        website_id: websiteId,
        page_id: pageId,
        normalized_url: row.normalized_url,
        observed_url: row.normalized_url,
        canonical_url: null,
      },
      current_page: {
        title: row.title,
        meta_description: null,
        quality_status: row.quality_status,
        indexability: row.indexability,
      },
      crawl: {
        availability: row.observed_at ? "observed" : "unavailable",
        run_status: "completed",
        observed_at: row.observed_at,
        observation: row.observed_at
          ? {
              http_status: row.http_status,
              indexability: row.indexability,
              quality_status: row.quality_status,
            }
          : null,
        quality: row.quality_status,
        limitation:
          "Crawl and sitemap evidence do not establish Google indexation.",
      },
      change: { state: rich ? "changed" : "first_observation" },
      gsc: rich
        ? {
            availability: "observed",
            period_start: "2026-09-01",
            period_end: "2026-09-28",
            page: {
              items: [
                { clicks: 120, impressions: 3400 },
                { clicks: 30, impressions: 900 },
              ],
            },
          }
        : { availability: "unavailable" },
      ga4_organic_landing: rich
        ? {
            availability: "observed",
            page: { items: [{ metric_key: "keyEvents", value: 18 }] },
          }
        : { availability: "unavailable" },
      internal_links: rich
        ? {
            availability: "observed",
            mapped_inbound_count: 6,
            mapped_outbound_count: 14,
          }
        : { availability: "unavailable" },
      content: {
        availability: row.observed_at ? "observed" : "unavailable",
        observed_at: row.observed_at,
        word_count: rich ? 640 : null,
        structured_data_present: rich ? true : null,
      },
      workflow: { opportunities: { items: [] } },
    },
    mapping: rich
      ? {
          state: "mapped",
          code: null,
          repository: "synthetic/restaurant-site",
          base_branch: "main",
          fields: {
            seo_title: "src/pages/menu.astro",
            meta_description: "src/pages/menu.astro",
          },
          verification: "executor_rechecks_before_write",
        }
      : {
          state: "unavailable",
          code: "SITE_MAPPING_REQUIRED",
          repository: null,
          base_branch: null,
          fields: {},
          verification: "executor_rechecks_before_write",
        },
    opportunities: rich
      ? (space.opportunities ?? []).filter((o) => o.page_id === pageId)
      : [],
  };
}
