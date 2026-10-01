import { apiGet, apiRequest, type ApiOutcome } from "./api-client";
import { statusLabel } from "./status-language";

// Fallback bounds used only until `fetchCrawlLimits` resolves, or if that
// call fails. The API (`apps.api.app.products.seo.crawl_limits`) is the
// single source of truth; these constants must never diverge from it in a
// way that under-bounds a crawl, since the API always re-validates.
export const FALLBACK_MAX_CRAWL_PAGES = 300;
export const FALLBACK_MAX_CRAWL_DEPTH = 5;
export const SEO_ACTIONABLE_OPPORTUNITY_STATUSES = [
  "identified",
  "recommended",
  "approved",
] as const;

export function isSEOOpportunityActionable(status: string): boolean {
  return (SEO_ACTIONABLE_OPPORTUNITY_STATUSES as readonly string[]).includes(
    status,
  );
}

export type SEOCrawlLimits = {
  default_max_pages: number;
  max_max_pages: number;
  min_max_pages: number;
  default_max_depth: number;
  max_max_depth: number;
  min_max_depth: number;
};

export function fetchCrawlLimits(
  organizationId: string,
): Promise<ApiOutcome<SEOCrawlLimits>> {
  return apiGet(`${base(organizationId)}/crawl-limits`);
}

export function normalizeCrawlPageLimit(
  value: number,
  maxPages: number = FALLBACK_MAX_CRAWL_PAGES,
): number {
  if (!Number.isFinite(value)) return maxPages;
  return Math.min(maxPages, Math.max(1, Math.trunc(value)));
}

export function normalizeCrawlDepthLimit(
  value: number,
  maxDepth: number = FALLBACK_MAX_CRAWL_DEPTH,
): number {
  if (!Number.isFinite(value)) return maxDepth;
  return Math.min(maxDepth, Math.max(1, Math.trunc(value)));
}

export type SEOWebsite = {
  id: string;
  location_id: string | null;
  key: string;
  name: string;
  canonical_origin: string;
  status: string;
  ownership_status: string;
  verified_at: string | null;
};

export type SEOSearchProperty = {
  id: string;
  provider: string;
  external_property_id: string;
  property_type: string;
  mapping_status: string;
  freshness_status: string;
  last_synced_at: string | null;
};

export type SEOOpportunity = {
  id: string;
  website_id: string;
  page_id: string | null;
  opportunity_type: string;
  recommendation_class?: "growth_change" | "technical_regression";
  priority_score: number;
  score_explanation: Record<string, string | number | null>;
  evidence: Record<string, unknown>;
  status: string;
};

/** One approved edit: the current value was read from the client repo, not guessed. */
export type SEOChangeSetItem = {
  page_id: string;
  field: string;
  current_value: string;
  proposed_value: string;
  rationale: string;
};

export type SEOLiveCheck = {
  field: string;
  expected: string;
  observed: string | null;
  state: string;
};

/** Where an approved site change is, and -- when it stopped -- the typed code why. */
export type SEOSiteChangeState = {
  mapping_state: "mapped" | "required" | null;
  blocked_code: string | null;
  publication_status: string | null;
  pull_request_url: string | null;
  build_gate: string | null;
  build_state: "passed" | "failed" | "pending" | "unavailable" | null;
  verification_state: string | null;
  live_checks: SEOLiveCheck[];
};

export type SEORecommendation = {
  id: string;
  revision_number: number;
  proposed_action: string;
  expected_result_hypothesis: string;
  risk: string;
  effort: string;
  status: string;
  approved_by_user_id: string | null;
  evidence_references: string[];
  decision_context: SEODecisionContext | null;
  change_set: SEOChangeSetItem[];
  change_set_limitation_code: string | null;
  site_change: SEOSiteChangeState | null;
};

/** Revisions a newer one replaced, or that were withdrawn, are history, never the live proposal. */
const ENDED_REVISION_STATUSES = new Set(["superseded", "withdrawn"]);

/** The newest revision that is still in play, or undefined when none is. */
export function latestLiveRecommendation(
  revisions: SEORecommendation[],
): SEORecommendation | undefined {
  return revisions
    .filter((revision) => !ENDED_REVISION_STATUSES.has(revision.status))
    .sort((a, b) => b.revision_number - a.revision_number)[0];
}

export type SEOHermesRun = {
  workflow_run_id: string;
  agent_run_id: string | null;
  status: string;
  safe_error_code: string | null;
  proposal_references: string[];
};

export function fetchOpportunityHermesRun(
  organizationId: string,
  opportunityId: string,
): Promise<ApiOutcome<SEOHermesRun | null>> {
  return apiGet(
    `${base(organizationId)}/opportunities/${opportunityId}/hermes-run`,
  );
}

export function startOpportunityHermesRun(
  organizationId: string,
  opportunityId: string,
): Promise<ApiOutcome<SEOHermesRun>> {
  return apiRequest(
    `${base(organizationId)}/opportunities/${opportunityId}/hermes-run`,
    {
      method: "POST",
    },
  );
}

export type SEOReasoningPass = {
  availability: string;
  limitation?: string | null;
  [key: string]: unknown;
};

export type SEODecisionContext = {
  recommendation_class: "growth_change" | "technical_regression";
  page_mapping_state: string;
  evidence_references: string[];
  evidence_freshness: string | null;
  evidence_quality: string | null;
  evidence_limitation: string | null;
  business_importance_state: string;
  business_importance_value: number | null;
  business_importance_version: string | null;
  opportunity_score_policy_version: string | null;
  target_metric: string | null;
  passes: Record<
    "access" | "competition" | "answer_engines" | "conversion",
    SEOReasoningPass
  >;
};

export type SEOImplementationTask = {
  id: string;
  recommendation_revision_id: string;
  workflow_run_id: string;
  target_type: string;
  target_reference: string;
  status: string;
  verification_evidence: Record<string, unknown> | null;
  verified_at: string | null;
};

export type SEOOutcome = {
  id: string;
  implementation_task_id: string;
  classification: "improved" | "unchanged" | "regressed" | "inconclusive";
  baseline_start: string;
  baseline_end: string;
  measurement_start: string;
  measurement_end: string;
  metrics: Record<string, unknown>;
  limitations: string[];
};

export type SEOPageIntelligence = {
  version: string;
  identity: Record<string, string>;
  current_page: Record<string, unknown>;
  crawl: Record<string, unknown>;
  change: Record<string, unknown>;
  gsc: Record<string, unknown>;
  ga4_organic_landing: Record<string, unknown>;
  internal_links: Record<string, unknown>;
  content: Record<string, unknown>;
  workflow: Record<string, unknown>;
};

export type SearchIntelligenceItem = {
  opportunity: SEOOpportunity & {
    recommendation_class: "growth_change" | "technical_regression";
  };
  website: SEOWebsite;
  page: SEOPageRecord | null;
  recommendation: SEORecommendation | null;
  task: SEOImplementationTask | null;
  outcome: SEOOutcome | null;
  measurement: {
    metric: string | null;
    baseline_start?: string;
    baseline_end?: string;
    measurement_start?: string;
    measurement_end?: string;
    maturity: "unavailable" | "pending" | "mature";
    limitation: string | null;
  } | null;
  active_change: { revision_id: string; state: string } | null;
  governed_eligibility: {
    eligible: boolean;
    limitation: string | null;
    limitation_code: string | null;
  };
  latest_measured: {
    recommendation: SEORecommendation;
    task: SEOImplementationTask;
    outcome: SEOOutcome;
  } | null;
};

export type SearchIntelligenceReadiness = {
  website_id: string;
  website_name: string;
  location_id: string | null;
  gsc: "fresh" | "stale" | "unavailable";
  ga4: "fresh" | "stale" | "unavailable";
  page_inventory: "observed" | "unavailable";
};

export type SearchIntelligenceWorkspace = {
  items: SearchIntelligenceItem[];
  readiness: SearchIntelligenceReadiness[];
  readiness_has_more: boolean;
  history_truncated: boolean;
  pagination: {
    limit: number;
    offset: number;
    next_offset: number | null;
    has_more: boolean;
  };
};

export type SEOSummaryStats = {
  by_status: Record<string, number>;
  website_count: number;
  crawl_run_count: number;
};

export type SEOCrawlRun = {
  id: string;
  website_id: string;
  status: string;
  max_pages: number;
  max_depth: number | null;
  crawl_delay_seconds: number | null;
  stop_reason: string | null;
  safe_result: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
};

export type SEOPageRecord = {
  id: string;
  website_id: string;
  normalized_url: string;
  observed_url: string;
  http_status: number | null;
  content_type: string | null;
  title: string | null;
  meta_description: string | null;
  h1: string | null;
  canonical_url: string | null;
  robots_directives: string[];
  internal_links_count: number;
  external_links_count: number;
  word_count: number | null;
  structured_data_present: boolean;
  content_hash: string | null;
  indexability: string;
  crawl_depth: number | null;
  redirect_destination: string | null;
};

export type SEOCrawlResult = {
  id: string;
  status: string;
  max_pages: number;
  stop_reason: string | null;
  safe_result: Record<string, unknown>;
};

export function crawlTerminalState(status: string): boolean {
  return ["success", "partial", "error"].includes(status);
}

export function describeCrawlResult(result: SEOCrawlResult): string {
  const pages = result.safe_result.pages_crawled;
  const details: string[] = [`Status: ${statusLabel(result.status)}`];
  if (typeof pages === "number") {
    details.push(`${pages} page${pages === 1 ? "" : "s"} crawled`);
  }
  if (result.stop_reason) {
    details.push(result.stop_reason);
  }
  return details.join(" · ");
}

export type LandingPageGap = {
  location_id: string;
  location_name: string;
};

export type AuditEntry = {
  id: string;
  event_type: string;
  action: string;
  result: string;
  occurred_at: string;
  summary: string;
  actor_type: string;
};

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/seo`;
}

export function fetchWebsites(
  organizationId: string,
): Promise<ApiOutcome<SEOWebsite[]>> {
  return apiGet<SEOWebsite[]>(`${base(organizationId)}/websites`);
}

export function createWebsite(
  organizationId: string,
  website: {
    locationId?: string;
    key: string;
    name: string;
    canonicalOrigin: string;
  },
): Promise<ApiOutcome<SEOWebsite>> {
  return apiRequest(`${base(organizationId)}/websites`, {
    method: "POST",
    body: {
      location_id: website.locationId ?? null,
      key: website.key,
      name: website.name,
      canonical_origin: website.canonicalOrigin,
    },
  });
}

export function fetchWebsiteAudit(
  organizationId: string,
  websiteId: string,
): Promise<ApiOutcome<AuditEntry[]>> {
  return apiGet<AuditEntry[]>(
    `${base(organizationId)}/websites/${websiteId}/audit`,
  );
}

export function fetchSearchProperties(
  organizationId: string,
  websiteId: string,
): Promise<ApiOutcome<SEOSearchProperty[]>> {
  return apiGet<SEOSearchProperty[]>(
    `${base(organizationId)}/websites/${websiteId}/search-properties`,
  );
}

export function fetchLandingPageGaps(
  organizationId: string,
  websiteId: string,
): Promise<ApiOutcome<LandingPageGap[]>> {
  return apiGet<LandingPageGap[]>(
    `${base(organizationId)}/websites/${websiteId}/landing-page-gaps`,
  );
}

export function runCrawl(
  organizationId: string,
  websiteId: string,
  crawl: {
    workflowRunId: string;
    seedPaths: string[];
    maxPages: number;
    maxDepth: number;
    crawlDelaySeconds: number;
    idempotencyKey: string;
  },
): Promise<ApiOutcome<SEOCrawlResult>> {
  return apiRequest(`${base(organizationId)}/websites/${websiteId}/crawl`, {
    method: "POST",
    body: {
      workflow_run_id: crawl.workflowRunId,
      seed_paths: crawl.seedPaths,
      max_pages: normalizeCrawlPageLimit(crawl.maxPages),
      max_depth: normalizeCrawlDepthLimit(crawl.maxDepth),
      crawl_delay_seconds: crawl.crawlDelaySeconds,
      idempotency_key: crawl.idempotencyKey,
    },
  });
}

export function fetchCrawlRun(
  organizationId: string,
  crawlRunId: string,
): Promise<ApiOutcome<SEOCrawlRun>> {
  return apiGet<SEOCrawlRun>(
    `${base(organizationId)}/crawl-runs/${crawlRunId}`,
  );
}

export function fetchCrawlRuns(
  organizationId: string,
  websiteId?: string,
): Promise<ApiOutcome<SEOCrawlRun[]>> {
  const query = websiteId ? `?website_id=${websiteId}` : "";
  return apiGet<SEOCrawlRun[]>(`${base(organizationId)}/crawl-runs${query}`);
}

export function fetchCrawlPages(
  organizationId: string,
  crawlRunId: string,
): Promise<ApiOutcome<SEOPageRecord[]>> {
  return apiGet<SEOPageRecord[]>(
    `${base(organizationId)}/crawl-runs/${crawlRunId}/pages`,
  );
}

export function fetchSEOSummary(
  organizationId: string,
): Promise<ApiOutcome<SEOSummaryStats>> {
  return apiGet<SEOSummaryStats>(`${base(organizationId)}/summary`);
}

export function fetchOpportunities(
  organizationId: string,
  params: { websiteId?: string; statusFilter?: string } = {},
): Promise<ApiOutcome<SEOOpportunity[]>> {
  const query = new URLSearchParams();
  if (params.websiteId) query.set("website_id", params.websiteId);
  if (params.statusFilter) query.set("status_filter", params.statusFilter);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<SEOOpportunity[]>(
    `${base(organizationId)}/opportunities${suffix}`,
  );
}

export function fetchSearchIntelligenceWorkspace(
  organizationId: string,
  offset = 0,
): Promise<ApiOutcome<SearchIntelligenceWorkspace>> {
  return apiGet<SearchIntelligenceWorkspace>(
    `${base(organizationId)}/workspace?limit=50&offset=${offset}`,
  );
}

export function fetchPageIntelligence(
  organizationId: string,
  websiteId: string,
  pageId: string,
): Promise<ApiOutcome<SEOPageIntelligence>> {
  return apiGet<SEOPageIntelligence>(
    `${base(organizationId)}/websites/${websiteId}/pages/${pageId}/intelligence`,
  );
}

export function fetchOpportunityAudit(
  organizationId: string,
  opportunityId: string,
): Promise<ApiOutcome<AuditEntry[]>> {
  return apiGet<AuditEntry[]>(
    `${base(organizationId)}/opportunities/${opportunityId}/audit`,
  );
}

export function fetchRecommendations(
  organizationId: string,
  opportunityId: string,
): Promise<ApiOutcome<SEORecommendation[]>> {
  return apiGet<SEORecommendation[]>(
    `${base(organizationId)}/opportunities/${opportunityId}/recommendations`,
  );
}

export function createRecommendation(
  organizationId: string,
  opportunityId: string,
  recommendation: {
    proposedAction: string;
    expectedResultHypothesis: string;
    risk: "low" | "medium" | "high";
    effort: "low" | "medium" | "high";
  },
): Promise<ApiOutcome<SEORecommendation>> {
  return apiRequest(
    `${base(organizationId)}/opportunities/${opportunityId}/recommendations`,
    {
      method: "POST",
      body: {
        proposed_action: recommendation.proposedAction,
        evidence_references: [`seo-opportunity:${opportunityId}`],
        expected_result_hypothesis: recommendation.expectedResultHypothesis,
        risk: recommendation.risk,
        effort: recommendation.effort,
      },
    },
  );
}

export function decideRecommendation(
  organizationId: string,
  revisionId: string,
  approve: boolean,
): Promise<ApiOutcome<SEORecommendation>> {
  return apiRequest(
    `${base(organizationId)}/recommendations/${revisionId}/decision`,
    {
      method: "POST",
      body: { approve },
    },
  );
}

export function fetchImplementationTasks(
  organizationId: string,
  revisionId: string,
): Promise<ApiOutcome<SEOImplementationTask[]>> {
  return apiGet<SEOImplementationTask[]>(
    `${base(organizationId)}/recommendations/${revisionId}/tasks`,
  );
}

export function createImplementationTask(
  organizationId: string,
  revisionId: string,
  task: { workflowRunId: string; targetType: string; targetReference: string },
): Promise<ApiOutcome<SEOImplementationTask>> {
  return apiRequest(
    `${base(organizationId)}/recommendations/${revisionId}/tasks`,
    {
      method: "POST",
      body: {
        workflow_run_id: task.workflowRunId,
        target_type: task.targetType,
        target_reference: task.targetReference,
      },
    },
  );
}

export function verifyImplementationTask(
  organizationId: string,
  taskId: string,
): Promise<ApiOutcome<SEOImplementationTask>> {
  return apiRequest(`${base(organizationId)}/tasks/${taskId}/verify`, {
    method: "POST",
    body: { verification_evidence: {} },
  });
}
