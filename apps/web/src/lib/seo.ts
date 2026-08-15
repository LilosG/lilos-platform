import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export const MAX_CRAWL_PAGES = 20;
export const MAX_CRAWL_DEPTH = 10;
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

export function normalizeCrawlPageLimit(value: number): number {
  if (!Number.isFinite(value)) return MAX_CRAWL_PAGES;
  return Math.min(MAX_CRAWL_PAGES, Math.max(1, Math.trunc(value)));
}

export function normalizeCrawlDepthLimit(value: number): number {
  if (!Number.isFinite(value)) return MAX_CRAWL_DEPTH;
  return Math.min(MAX_CRAWL_DEPTH, Math.max(1, Math.trunc(value)));
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
  priority_score: number;
  score_explanation: Record<string, number>;
  evidence: Record<string, unknown>;
  status: string;
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
};

export type SEOImplementationTask = {
  id: string;
  target_type: string;
  target_reference: string;
  status: string;
  verification_evidence: Record<string, unknown> | null;
  verified_at: string | null;
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
  const details: string[] = [`Status: ${result.status}`];
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
        evidence_references: [],
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
