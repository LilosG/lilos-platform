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
  "content",
  "content_empty",
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

// --- Content: the list, the draft review, and the actions on them -------------------------
const CONTENT = {
  ready: uuid(0xc1),
  writing: uuid(0xc2),
  failed: uuid(0xc3),
  page: uuid(0xc4),
  published: uuid(0xc5),
};
const REV = uuid(0xd1);
const REV_NEW = uuid(0xd2);
const BRIEF = uuid(0xe1);
const FACT = uuid(0xf1);
const TARGET = uuid(0xa1);
export const contentSim = {
  requests: [],
  composed: [],
  advanced: false,
  confirmed: false,
  regenerated: false,
  revisionStatus: "awaiting_editorial",
};
export function resetContent() {
  contentSim.requests = [];
  contentSim.composed = [];
  contentSim.advanced = false;
  contentSim.confirmed = false;
  contentSim.regenerated = false;
  contentSim.revisionStatus = "awaiting_editorial";
}
const composeState = (status, code, prompt, n) => ({
  status,
  failure_code: code,
  prompt,
  workflow_run_id: uuid(0x500 + n),
});
const row = (id, over) => ({
  id,
  title: "Untitled",
  slug: "untitled",
  content_type: "blog_post",
  stage: "drafting",
  next_action: { key: "review", label: "Review draft" },
  published_at: null,
  latest_revision_status: null,
  latest_revision_number: null,
  publication_status: null,
  publication_job_status: null,
  technical_site_change: false,
  word_count: null,
  compose: null,
  ...over,
});
const stageForRevision = {
  awaiting_editorial: "editorial_review",
  awaiting_client: "client_review",
  approved: "ready_to_publish",
};
export function contentItems() {
  const items = [
    row(CONTENT.ready, {
      title: "Miss B's: The Green Bay Packers Bar in San Diego",
      slug: "green-bay-packers-bar-san-diego",
      stage: stageForRevision[contentSim.revisionStatus],
      latest_revision_status: contentSim.revisionStatus,
      latest_revision_number: contentSim.regenerated ? 2 : 1,
      word_count: contentSim.regenerated ? 1810 : 1520,
    }),
    row(CONTENT.writing, {
      title: "Best places to watch Packers games in San Diego",
      slug: "draft-2",
      content_type: "listicle",
      stage: contentSim.advanced ? "editorial_review" : "writing",
      latest_revision_status: contentSim.advanced ? "awaiting_editorial" : null,
      latest_revision_number: contentSim.advanced ? 1 : null,
      word_count: contentSim.advanced ? 1640 : null,
      compose: contentSim.advanced
        ? null
        : composeState(
            "writing",
            null,
            "listicle: best places to watch Packers games in San Diego",
            2,
          ),
    }),
    row(CONTENT.failed, {
      title: "A guide to game day parking",
      slug: "draft-3",
      content_type: "guide",
      stage: "compose_failed",
      compose: composeState(
        "failed",
        "CONTENT_BELOW_QUALITY_FLOOR",
        "write a guide to game day parking near Miss B's",
        3,
      ),
    }),
    row(CONTENT.page, {
      title: "Packers watch party space",
      slug: "packers-watch-party",
      content_type: "landing_page",
      stage: "editorial_review",
      latest_revision_status: "awaiting_editorial",
      latest_revision_number: 1,
      word_count: 1490,
    }),
    row(CONTENT.published, {
      title: "Wing night at Miss B's",
      slug: "wing-night",
      stage: "published",
      latest_revision_status: "approved",
      latest_revision_number: 2,
      publication_status: "verified",
      publication_job_status: "succeeded",
      word_count: 1710,
      published_at: ago(6),
    }),
  ];
  for (const [index, c] of contentSim.composed.entries())
    items.unshift(
      row(uuid(0x700 + index), {
        title: c.prompt.slice(0, 60),
        slug: `draft-${index}`,
        content_type: c.content_type ?? "blog_post",
        stage: "writing",
        compose: composeState("writing", null, c.prompt, 10 + index),
      }),
    );
  return items;
}
export function contentWorkspace(mode, org, requested) {
  const data = workspace("rich", org, requested);
  if (!data) return data;
  data.content = mode === "content_empty" ? [] : contentItems();
  return data;
}
const BODY = [
  "## Why Packers fans pick Miss B's in San Diego",
  "",
  "Every Sunday the bar fills with green and gold. Start with [our full food and drink menu](/menu/) before kickoff, then [reserve a table for game day](/reservations/) so your group sits together.",
  "",
  "## Where the bar is and how to get there",
  "",
  "Find us at [the San Diego location](/locations/san-diego/), a short walk from the trolley.",
  "",
  "## What to order during the game",
  "",
  "- Wings by the dozen",
  "- Cheese curds",
  "",
  "### Group orders",
  "",
  "Large groups can order ahead and see [upcoming game day events](/events/).",
].join("\n");
const FILLER = (words) =>
  Array.from({ length: words }, (_, n) => `detail${n}`).join(" ");
const bodyOf = (words) => {
  const count = (text) => (text.match(/[\w'-]+/g) ?? []).length;
  const head = `${BODY}\n\n## More about game day\n\n`;
  return head + FILLER(Math.max(0, words - count(head)));
};
const QUALITY = {
  floor: {
    minimum_words: 1400,
    target_minimum_words: 1700,
    target_maximum_words: 2300,
    minimum_h2s: 7,
    minimum_internal_links: 4,
    minimum_faqs: 4,
  },
  word_count: 1520,
  links: [
    {
      anchor: "our full food and drink menu",
      url: "/menu",
      verified: true,
      kind: "menu",
    },
    {
      anchor: "reserve a table for game day",
      url: "/reservations",
      verified: true,
      kind: "reservation",
    },
    {
      anchor: "the San Diego location",
      url: "/locations/san-diego",
      verified: true,
      kind: "location",
    },
    {
      anchor: "upcoming game day events",
      url: "/events",
      verified: true,
      kind: "other",
    },
  ],
  checks: [
    "article_too_thin",
    "article_heading_depth_missing",
    "article_internal_links_missing",
    "article_internal_link_unverified",
    "article_anchor_generic",
    "article_anchor_stuffing",
    "article_commercial_link_missing",
    "article_faq_depth_missing",
  ].map((code) => ({ code, passed: true })),
};
const FAQS = [
  {
    question: "Do you show every Packers game?",
    answer: "Yes, every game is on the big screens.",
  },
  {
    question: "Can I reserve a table?",
    answer: "Yes, reserve ahead for game days.",
  },
];
export function contentDetail(org, id) {
  const items = contentItems();
  const item = items.find((c) => c.id === id);
  if (!item) return null;
  const hasDraft = item.latest_revision_status !== null;
  const claims = [
    {
      claim_id: "a1b2c3d4e5f6",
      text: "Miss B's opened in 1987 and has hosted every Packers game since.",
      basis: "needs_confirmation",
      status: contentSim.confirmed ? "confirmed" : "needs_confirmation",
      detected: true,
    },
    {
      claim_id: "b2c3d4e5f6a1",
      text: "Miss B's is a Green Bay Packers bar in San Diego.",
      basis: "operator_prompt",
      status: "backed",
      detected: false,
    },
  ];
  const revision = (revId, number, by, status) => ({
    id: revId,
    revision_number: number,
    body: bodyOf(item.word_count ?? 1520),
    frontmatter: {
      title: item.title,
      seo_title: "Packers Bar in San Diego | Miss B's",
      description: "Where to watch Green Bay Packers games in San Diego.",
      faqs: FAQS,
    },
    created_by_type: by,
    status,
    validation_document:
      id === CONTENT.ready
        ? {
            valid: true,
            errors: [],
            quality: { ...QUALITY, word_count: item.word_count ?? 1520 },
            topic_overlap: {
              url: "https://synthetic.example.invalid/blog/packers-games-san-diego/",
              title: "Where to Watch Packers Games in San Diego",
            },
            claims,
            inbound_links: [
              {
                status: "proposed",
                page_url: "https://synthetic.example.invalid/events/",
                field: "internal_link",
                anchor: "Green Bay Packers bar",
                target_url: "/blog/green-bay-packers-bar-san-diego",
                before: "Visit the Green Bay Packers bar for game day.",
                after:
                  "Visit the [Green Bay Packers bar](/blog/green-bay-packers-bar-san-diego) for game day.",
                recommendation_id: uuid(0x910),
              },
              {
                status: "unavailable",
                code: "LINK_FIELD_NOT_MAPPED",
                page_url: "https://synthetic.example.invalid/about/",
                field: "internal_link",
              },
            ],
          }
        : { valid: true, errors: [] },
    approved_at: null,
  });
  const revisions = !hasDraft
    ? []
    : contentSim.regenerated && id === CONTENT.ready
      ? [
          revision(REV_NEW, 2, "ai", contentSim.revisionStatus),
          revision(REV, 1, "ai", "superseded"),
        ]
      : [revision(REV, 1, "ai", item.latest_revision_status)];
  const requirements = {
    target_selected: true,
    target_id: TARGET,
    missing: [],
    requires_image: false,
    requires_image_alt: false,
    file_extensions: [".mdx"],
  };
  return {
    ...item,
    organization_id: org,
    briefs: [
      {
        id: BRIEF,
        revision_number: 1,
        audience: "Packers fans in San Diego",
        intent: "Find the best place to watch Packers games",
        target_reference: `/blog/${item.slug}/`,
        approved_fact_revision_ids: [FACT],
        status: "ready",
        target_kind: "new_page",
        source_prompt:
          "write a blog about Miss B's being the Green Bay Packers bar in San Diego",
      },
    ],
    revisions,
    publications: [],
    publishing_targets: [
      {
        id: TARGET,
        key: "miss-bs",
        repository_id: "synthetic/missbs-site",
        base_branch: "main",
        allowed_path_prefix: "src/content/blog",
        file_extensions: [".mdx"],
        status: "active",
      },
    ],
    publishing_requirements: requirements,
    publishing_requirements_by_target: { [TARGET]: requirements },
    publish_preview: [
      {
        target_id: TARGET,
        repository_id: "synthetic/missbs-site",
        base_branch: "main",
        file_path: `src/content/blog/${item.slug}.mdx`,
        change_kind: "new_file",
      },
    ],
    facts: [{ id: FACT, key: "business.name", value: "Miss B's" }],
    draft_runs: [],
    can_edit: true,
    can_approve: true,
    can_publish: true,
  };
}
export const contentIds = CONTENT;
