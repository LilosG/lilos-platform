import type { AnalyticsPerformanceReport } from "../../../src/lib/analytics";
import type {
  ContentItem,
  ContentOpportunity,
  ContentSummaryStats,
  GitHubConnection,
  PublishingTarget,
} from "../../../src/lib/content";
import type {
  CompletenessReport,
  GBPMediaItem,
  GBPPostRevisionItem,
  GBPProviderPostItem,
  SpecialHours,
} from "../../../src/lib/gbp-operations";
import type { GBPConnectionStatus } from "../../../src/lib/gbp-connection";
import type { GBPLocationSummary } from "../../../src/lib/gbp";
import type {
  GoogleWorkspace,
  GitHubWorkspace,
  UnmappedResource,
} from "../../../src/lib/integrations";
import type {
  AssigneeCandidate,
  LeadSourcePerformance,
  LeadDetail,
  LeadSummary,
  LeadSummaryStats,
} from "../../../src/lib/leads";
import type {
  ReviewSummary,
  ReviewSummaryStats,
} from "../../../src/lib/reviews";
import type { SearchConsolePerformanceReport } from "../../../src/lib/search-console";
import type {
  SEOOpportunity,
  SEOSearchProperty,
  SEOSummaryStats,
  SEOWebsite,
} from "../../../src/lib/seo";
import type {
  EntitledProduct,
  InsightsSummary,
  LocationSummary,
  MyOrganization,
  PlatformAdministratorSelfStatus,
  PrincipalSummary,
  ProductReadiness,
} from "../../../src/lib/workspace";
import type {
  WorkflowRunSummary,
  WorkflowScheduleEntry,
  WorkflowTypeEntry,
} from "../../../src/lib/workflows";

export const organizationId = "org-packet-4";
export const locationId = "location-downtown";
export const websiteId = "website-main";
export const observedAt = "2026-08-14T20:00:00Z";

export const principal = {
  platform_user_id: "user-packet-4",
  auth_user_id: "auth-packet-4",
  user_status: "active",
  assurance_level: "aal2",
} satisfies PrincipalSummary;

export const organizations = [
  {
    organization_id: organizationId,
    organization_name: "Wheyland Electric",
    organization_slug: "wheyland-electric",
    organization_status: "active",
    membership_id: "membership-packet-4",
    membership_status: "active",
    membership_type: "internal",
  },
] satisfies MyOrganization[];

export const platformAdministratorStatus = {
  is_platform_administrator: true,
  meets_required_assurance: true,
  required_assurance_level: "aal2",
} satisfies PlatformAdministratorSelfStatus;

export const entitledProducts = [
  "gbp",
  "reviews",
  "leads",
  "content",
  "seo",
  "automations",
  "insights",
].map((product_key) => ({
  product_key,
  entitled: true,
  entitlement_status: "active",
})) satisfies EntitledProduct[];

export const locations = [
  {
    id: locationId,
    name: "Downtown",
    status: "active",
    is_primary: true,
  },
] satisfies LocationSummary[];

export function readyProduct(productKey: string): ProductReadiness {
  return {
    ready: true,
    readiness_state: "ready",
    product_key: productKey,
    blocking_requirements: [],
    warnings: [],
  };
}

export const insightsSummary = {
  workflow_runs: { completed: 46, failed: 2 },
  gbp: {
    locations: 1,
    profile_snapshots: 31,
    publications: { verified: 8 },
  },
  reviews: { new: 4, awaiting_approval: 2, responded: 84 },
  content_publications: { deployed: 11, awaiting_approval: 2 },
  seo: {
    crawl_runs: { completed: 12 },
    opportunities: { identified: 6, approved: 3 },
  },
  leads: { new: 7, assigned: 14, contacted: 9, converted: 6 },
} satisfies InsightsSummary;

export const emptyInsightsSummary = {
  workflow_runs: {},
  gbp: { locations: 1, profile_snapshots: 0, publications: {} },
  reviews: {},
  content_publications: {},
  seo: { crawl_runs: {}, opportunities: {} },
  leads: {},
} satisfies InsightsSummary;

const analyticsSeries = Array.from({ length: 28 }, (_, index) => {
  const date = new Date(Date.UTC(2026, 6, 18 + index))
    .toISOString()
    .slice(0, 10);
  const metrics: Record<string, number> = {
    sessions: 88 + index * 3 + (index % 4) * 7,
    totalUsers: 64 + index * 2 + (index % 3) * 5,
    screenPageViews: 132 + index * 5 + (index % 5) * 8,
  };
  if (index !== 12) metrics.conversions = 5 + (index % 6);
  return { date, metrics };
});

export const analyticsPerformance = {
  connected: true,
  properties: [
    {
      id: "analytics-main",
      display_name: "Main website",
      external_property_id: "properties/1001",
      freshness_status: "fresh",
      last_synced_at: observedAt,
    },
  ],
  range: { start: "2026-07-18", end: "2026-08-14", days: 28 },
  comparison_range: { start: "2026-06-20", end: "2026-07-17", days: 28 },
  freshness: { last_synced_at: observedAt, status: "fresh" },
  metrics: {
    "ga4.sessions": {
      label: "Sessions",
      current: 3248,
      previous: 2860,
      delta: 388,
      percent_delta: 13.6,
      quality: "observed",
    },
    "ga4.totalUsers": {
      label: "Users",
      current: 2376,
      previous: 2241,
      delta: 135,
      percent_delta: 6,
      quality: "observed",
    },
    "ga4.screenPageViews": {
      label: "Page views",
      current: 4912,
      previous: 4388,
      delta: 524,
      percent_delta: 11.9,
      quality: "observed",
    },
    "ga4.conversions": {
      label: "Conversions",
      current: 184,
      previous: 161,
      delta: 23,
      percent_delta: 14.3,
      quality: "observed",
    },
  },
  series: analyticsSeries,
} satisfies AnalyticsPerformanceReport;

export const searchConsolePerformance = {
  connected: true,
  properties: [
    {
      id: "search-main",
      external_property_id: "sc-domain:example.test",
      property_type: "domain",
      freshness_status: "fresh",
      last_synced_at: observedAt,
    },
  ],
  range: { start: "2026-07-18", end: "2026-08-14", days: 28 },
  comparison_range: { start: "2026-06-20", end: "2026-07-17", days: 28 },
  freshness: { last_synced_at: observedAt, status: "fresh" },
  metrics: {
    clicks: {
      current: 924,
      previous: 801,
      delta: 123,
      percent_delta: 15.4,
      quality: "observed",
    },
    impressions: {
      current: 28140,
      previous: 26520,
      delta: 1620,
      percent_delta: 6.1,
      quality: "observed",
    },
    ctr: {
      current: 0.0328,
      previous: 0.0302,
      delta: 0.0026,
      percent_delta: 8.6,
      quality: "observed",
    },
    position: {
      current: 11.4,
      previous: 12.1,
      delta: -0.7,
      percent_delta: -5.8,
      quality: "observed",
    },
  },
  series: analyticsSeries.map((item, index) => ({
    date: item.date,
    clicks: 18 + index + (index % 4) * 3,
    impressions: 720 + index * 28,
    ctr: 0.034 + (index % 5) * 0.002,
    position: 13.8 - index * 0.09,
  })),
  top_queries: [
    ["emergency electrician near me", 142, 3100, 0.0458, 4.2],
    ["licensed electrician", 118, 2820, 0.0418, 5.1],
    ["panel upgrade cost", 96, 2510, 0.0382, 6.4],
    ["commercial electrical service", 74, 2250, 0.0329, 8.1],
    ["ev charger installation", 69, 1980, 0.0348, 7.3],
    ["electrical inspection", 55, 1770, 0.0311, 9.2],
  ].map(([query, clicks, impressions, ctr, position]) => ({
    query: String(query),
    clicks: Number(clicks),
    impressions: Number(impressions),
    ctr: Number(ctr),
    position: Number(position),
  })),
  top_pages: [
    ["/services/emergency-electrician", 188, 4420, 0.0425, 4.7],
    ["/services/panel-upgrades", 142, 3680, 0.0386, 5.9],
    ["/services/ev-chargers", 121, 3220, 0.0376, 6.4],
    ["/commercial", 93, 2810, 0.0331, 7.8],
    ["/", 82, 2600, 0.0315, 8.3],
    ["/contact", 48, 1220, 0.0393, 6.8],
  ].map(([page, clicks, impressions, ctr, position]) => ({
    page: String(page),
    clicks: Number(clicks),
    impressions: Number(impressions),
    ctr: Number(ctr),
    position: Number(position),
  })),
} satisfies SearchConsolePerformanceReport;

export const websites = [
  {
    id: websiteId,
    location_id: locationId,
    key: "main",
    name: "Wheyland Electric",
    canonical_origin: "https://example.test",
    status: "active",
    ownership_status: "verified",
    verified_at: observedAt,
  },
] satisfies SEOWebsite[];

export const searchProperties = [
  {
    id: "search-property-main",
    provider: "google_search_console",
    external_property_id: "sc-domain:example.test",
    property_type: "domain",
    mapping_status: "confirmed",
    freshness_status: "fresh",
    last_synced_at: observedAt,
  },
] satisfies SEOSearchProperty[];

export const seoSummary = {
  by_status: { identified: 6, approved: 3 },
  website_count: 1,
  crawl_run_count: 12,
} satisfies SEOSummaryStats;

export const seoOpportunities = [
  {
    id: "seo-opp-1",
    website_id: websiteId,
    page_id: "page-1",
    opportunity_type: "missing_service_page",
    priority_score: 92,
    score_explanation: { search_demand: 88, business_relevance: 96 },
    evidence: { query: "commercial electrical service", impressions: 2250 },
    status: "identified",
  },
  {
    id: "seo-opp-2",
    website_id: websiteId,
    page_id: "page-2",
    opportunity_type: "title_improvement",
    priority_score: 78,
    score_explanation: { low_ctr: 72 },
    evidence: { page: "/services/panel-upgrades", ctr: "2.1%" },
    status: "recommended",
  },
  {
    id: "seo-opp-3",
    website_id: websiteId,
    page_id: "page-3",
    opportunity_type: "internal_linking",
    priority_score: 64,
    score_explanation: { orphan_depth: 3 },
    evidence: { page: "/commercial" },
    status: "approved",
  },
] satisfies SEOOpportunity[];

export const googleConnection = {
  status: "connected",
  token_expires_at: "2026-09-01T00:00:00Z",
  last_verified_at: observedAt,
  services: { gbp: true, search_console: true, analytics: true },
} satisfies Exclude<GBPConnectionStatus, null>;

export const disconnectedGoogleConnection = {
  status: "disconnected",
  token_expires_at: null,
  last_verified_at: null,
  services: { gbp: false, search_console: false, analytics: false },
} satisfies Exclude<GBPConnectionStatus, null>;

export const googleWorkspace = {
  connection_status: "connected",
  connection_id: "google-connection-1",
  token_expires_at: "2026-09-01T00:00:00Z",
  last_verified_at: observedAt,
  capabilities: [
    { key: "gbp", label: "Business Profile", enabled: true },
    { key: "search_console", label: "Search Console", enabled: true },
    { key: "analytics", label: "Google Analytics", enabled: true },
  ],
  mapped_resources: [
    {
      id: "mapping-1",
      external_resource_id: "locations/1001",
      platform_resource_id: locationId,
      resource_type: "gbp_location",
      status: "confirmed",
      display_name: "Downtown",
      last_synced_at: observedAt,
      sync_freshness: "fresh",
    },
    {
      id: "mapping-2",
      external_resource_id: "sc-domain:example.test",
      platform_resource_id: websiteId,
      resource_type: "search_console_property",
      status: "confirmed",
      display_name: "example.test",
      last_synced_at: "2026-08-14T19:30:00Z",
      sync_freshness: "fresh",
    },
  ],
  unmapped_count: 2,
} satisfies GoogleWorkspace;

export const unmappedResources = [
  {
    id: "provider-location-2",
    external_location_id: "locations/1002",
    display_name: "Northside",
    primary_category: "Electrician",
  },
  {
    id: "provider-location-3",
    external_location_id: "locations/1003",
    display_name: "Westside",
    primary_category: "Electrical installation service",
  },
] satisfies UnmappedResource[];

export const githubWorkspace = {
  connection_status: "active",
  connection_id: "github-connection-1",
  external_account_reference: "wheyland-electric",
  repositories: [
    {
      repository_id: "repo-1",
      name: "wheyland-electric-site",
      default_branch: "main",
      private: true,
    },
  ],
} satisfies GitHubWorkspace;

export const githubConnections = [
  {
    id: "github-connection-1",
    external_account_reference: "installation:1001",
    status: "active",
  },
] satisfies GitHubConnection[];

export const gbpLocations = [
  {
    id: "gbp-location-1",
    business_name: "Wheyland Electric — Downtown",
    mapping_status: "confirmed",
    location_id: locationId,
    write_enabled: true,
    last_discovered_at: observedAt,
    last_synced_at: observedAt,
  },
] satisfies GBPLocationSummary[];

export const completeness = {
  complete: true,
  known: ["title", "phone", "hours"],
  unknown: [],
  unsupported_excluded: true,
  ranking_score: 96,
} satisfies CompletenessReport;

export const specialHours = [
  {
    id: "hours-1",
    service_date: "2026-09-07",
    revision: 1,
    periods: [{ opens: "08:00", closes: "14:00" }],
    source: "manual",
    status: "approved",
  },
] satisfies SpecialHours[];

export const gbpPosts = [
  {
    id: "post-1",
    post_key: "fall-inspections",
    revision: 2,
    post_type: "standard",
    content: "Now booking fall electrical inspections.",
    status: "approved",
  },
] satisfies GBPPostRevisionItem[];

export const providerPosts = [
  {
    id: "provider-post-1",
    provider_post_name: "locations/1001/localPosts/2001",
    post_type: "STANDARD",
    state: "LIVE",
    summary: "Now booking fall electrical inspections.",
    content_hash: "fixture",
    status: "present",
    first_seen_at: observedAt,
    last_seen_at: observedAt,
    observed_at: observedAt,
  },
] satisfies GBPProviderPostItem[];

export const gbpMedia = [
  {
    id: "media-1",
    media_type: "cover",
    source_reference: "approved-library/crew.jpg",
    rights_authority: "organization",
    status: "verified",
    verified_at: observedAt,
  },
] satisfies GBPMediaItem[];

export const reviewSummary = {
  by_status: { new: 4, awaiting_approval: 2, responded: 84 },
  average_rating: 4.8,
  open_restricted_cases: 0,
} satisfies ReviewSummaryStats;

export const reviews = [
  {
    id: "review-1",
    rating: 5,
    status: "new",
    sentiment: "unknown",
    risk_level: "low",
    provider: "google",
    review_created_at: "2026-08-13T17:20:00Z",
    last_synced_at: observedAt,
    current_revision_number: 1,
  },
  {
    id: "review-2",
    rating: 4,
    status: "awaiting_approval",
    sentiment: "positive",
    risk_level: "low",
    provider: "google",
    review_created_at: "2026-08-12T15:10:00Z",
    last_synced_at: observedAt,
    current_revision_number: 1,
  },
  {
    id: "review-3",
    rating: 2,
    status: "drafting",
    sentiment: "negative",
    risk_level: "medium",
    provider: "google",
    review_created_at: "2026-08-11T19:45:00Z",
    last_synced_at: observedAt,
    current_revision_number: 2,
  },
] satisfies ReviewSummary[];

export const contentSummary = {
  by_status: { drafting: 3, awaiting_approval: 2, published: 11 },
  open_opportunities: 2,
} satisfies ContentSummaryStats;

export const contentOpportunities = [
  {
    id: "content-opp-1",
    location_id: locationId,
    product_key: "content",
    target_reference: "/services/ev-chargers",
    opportunity_type: "service_page",
    priority_score: 88,
    status: "identified",
  },
] satisfies ContentOpportunity[];

export const publishingTargets = [
  {
    id: "target-1",
    key: "main-site",
    target_type: "github",
    repository_id: "repo-1",
    base_branch: "main",
    allowed_path_prefix: "src/content/services",
    status: "active",
  },
] satisfies PublishingTarget[];

export const contentItems = [
  {
    id: "content-1",
    opportunity_id: "content-opp-1",
    location_id: locationId,
    content_type: "service_page",
    title: "EV Charger Installation",
    slug: "ev-charger-installation",
    status: "awaiting_approval",
    published_at: null,
  },
  {
    id: "content-2",
    opportunity_id: null,
    location_id: locationId,
    content_type: "local_update",
    title: "Fall Electrical Safety Checklist",
    slug: "fall-electrical-safety",
    status: "drafting",
    published_at: null,
  },
  {
    id: "content-3",
    opportunity_id: null,
    location_id: locationId,
    content_type: "service_page",
    title: "Commercial Panel Upgrades",
    slug: "commercial-panel-upgrades",
    status: "published",
    published_at: "2026-08-10T18:00:00Z",
  },
] satisfies ContentItem[];

export const leadSummary = {
  by_status: { new: 4, assigned: 7, contacted: 5, qualified: 3, converted: 6 },
  open_urgent_count: 2,
  average_speed_to_lead_seconds: 194,
} satisfies LeadSummaryStats;

export const leadSources = [
  {
    source_id: "source-form",
    name: "Website contact form",
    lead_count: 18,
    converted_count: 6,
  },
  {
    source_id: "source-gbp",
    name: "Google Business Profile",
    lead_count: 7,
    converted_count: 2,
  },
] satisfies LeadSourcePerformance[];

export const leadAssignees = [
  {
    user_profile_id: "user-packet-4",
    display_name: "Jordan Lee",
    membership_status: "active",
    membership_type: "internal",
    role_keys: ["lead_manager"],
  },
] satisfies AssigneeCandidate[];

export const leads = [
  {
    id: "lead-1",
    status: "new",
    urgency: "urgent",
    location_id: locationId,
    service_id: "service-emergency",
    assigned_to_user_id: null,
    received_at: "2026-08-14T18:40:00Z",
    acknowledged_at: null,
    first_human_contact_at: null,
    converted_at: null,
    converted_value_cents: null,
    loss_reason: null,
  },
  {
    id: "lead-2",
    status: "assigned",
    urgency: "same_day",
    location_id: locationId,
    service_id: "service-panel",
    assigned_to_user_id: "user-packet-4",
    received_at: "2026-08-14T16:15:00Z",
    acknowledged_at: "2026-08-14T16:21:00Z",
    first_human_contact_at: null,
    converted_at: null,
    converted_value_cents: null,
    loss_reason: null,
  },
  {
    id: "lead-3",
    status: "contacted",
    urgency: "routine",
    location_id: locationId,
    service_id: "service-ev",
    assigned_to_user_id: "user-packet-4",
    received_at: "2026-08-13T20:10:00Z",
    acknowledged_at: "2026-08-13T20:18:00Z",
    first_human_contact_at: "2026-08-13T20:26:00Z",
    converted_at: null,
    converted_value_cents: null,
    loss_reason: null,
  },
] satisfies LeadSummary[];

export const leadDetails = [
  {
    ...leads[0],
    first_name: "Maya",
    last_name: "Chen",
    normalized_email: "maya.chen@example.test",
    normalized_phone: "+12065550141",
    message: "Power is out in half of the house after a breaker trip.",
  },
  {
    ...leads[1],
    first_name: "Noah",
    last_name: "Williams",
    normalized_email: "noah.williams@example.test",
    normalized_phone: "+12065550172",
    message: "Requesting an estimate for a residential panel upgrade.",
  },
  {
    ...leads[2],
    first_name: "Avery",
    last_name: "Patel",
    normalized_email: "avery.patel@example.test",
    normalized_phone: null,
    message: "Planning an EV charger installation this month.",
  },
] satisfies LeadDetail[];

export const workflowCatalog = [
  {
    key: "reviews.sync",
    display_name: "Sync Google reviews",
    product_key: "reviews",
    definition_status: "active",
    latest_version: 3,
  },
  {
    key: "content.publish",
    display_name: "Publish approved content",
    product_key: "content",
    definition_status: "active",
    latest_version: 2,
  },
  {
    key: "seo.search_console_sync",
    display_name: "Sync Search Console",
    product_key: "seo",
    definition_status: "active",
    latest_version: 4,
  },
] satisfies WorkflowTypeEntry[];

export const workflowSchedules = [
  {
    id: "schedule-1",
    key: "review-sync",
    workflow_key: "reviews.sync",
    workflow_name: "Sync Google reviews",
    cron_expression: "0 * * * *",
    timezone: "America/Los_Angeles",
    status: "active",
    next_run_at: "2026-08-14T21:00:00Z",
    last_run_at: "2026-08-14T20:00:00Z",
    location_id: locationId,
    created_at: "2026-07-01T00:00:00Z",
  },
  {
    id: "schedule-2",
    key: "search-sync",
    workflow_key: "seo.search_console_sync",
    workflow_name: "Sync Search Console",
    cron_expression: "0 0 * * *",
    timezone: "America/Los_Angeles",
    status: "active",
    next_run_at: "2026-08-15T07:00:00Z",
    last_run_at: "2026-08-14T07:00:00Z",
    location_id: locationId,
    created_at: "2026-07-01T00:00:00Z",
  },
] satisfies WorkflowScheduleEntry[];

export const workflowRuns = [
  {
    id: "run-1",
    workflow_key: "reviews.sync",
    workflow_name: "Sync Google reviews",
    product_key: "reviews",
    status: "completed",
    trigger_type: "schedule",
    location_id: locationId,
    input_document: {},
    output_reference: null,
    failure_code: null,
    correlation_id: "corr-1",
    started_at: "2026-08-14T20:00:00Z",
    completed_at: "2026-08-14T20:01:00Z",
    created_at: "2026-08-14T20:00:00Z",
    job_status: "completed",
    job_attempt_count: 1,
    job_max_attempts: 3,
    job_last_error_category: null,
  },
  {
    id: "run-2",
    workflow_key: "content.publish",
    workflow_name: "Publish approved content",
    product_key: "content",
    status: "failed",
    trigger_type: "operator",
    location_id: locationId,
    input_document: {},
    output_reference: null,
    failure_code: "PROVIDER_UNAVAILABLE",
    correlation_id: "corr-2",
    started_at: "2026-08-14T18:00:00Z",
    completed_at: "2026-08-14T18:01:00Z",
    created_at: "2026-08-14T18:00:00Z",
    job_status: "retry_scheduled",
    job_attempt_count: 1,
    job_max_attempts: 3,
    job_last_error_category: "provider",
  },
] satisfies WorkflowRunSummary[];
