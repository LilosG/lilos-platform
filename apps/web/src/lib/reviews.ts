import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type ReviewSummary = {
  id: string;
  rating: number | null;
  status: string;
  sentiment: string;
  risk_level: string;
  provider: string;
  review_created_at: string;
  last_synced_at: string;
  current_revision_number: number;
};

export type ReviewRevisionDetail = {
  id: string;
  revision_number: number;
  rating: number | null;
  title: string | null;
  body: string | null;
  captured_at: string;
  change_summary: string | null;
};

export type ReviewDetail = ReviewSummary & {
  revisions: ReviewRevisionDetail[];
};

export type ReviewResponse = {
  id: string;
  revision_number: number;
  response_text: string;
  status: string;
  generated_by_type: string;
  approved_at: string | null;
  published_at: string | null;
};

export type ReviewSummaryStats = {
  by_status: Record<string, number>;
  average_rating: number | null;
  open_restricted_cases: number;
};

const NEEDS_RESPONSE_STATUSES = [
  "new",
  "classified",
  "triaged",
  "drafting",
  "awaiting_approval",
  "approved",
  "publication_failed",
  "escalated",
  "disputed",
] as const;

export function summarizeReviewStatuses(stats: ReviewSummaryStats): {
  total: number;
  newCount: number;
  responded: number;
  needsResponse: number;
} {
  const byStatus = stats.by_status ?? {};
  return {
    total: Object.values(byStatus).reduce((sum, count) => sum + count, 0),
    newCount: byStatus.new ?? 0,
    responded: byStatus.responded ?? 0,
    needsResponse: NEEDS_RESPONSE_STATUSES.reduce(
      (sum, status) => sum + (byStatus[status] ?? 0),
      0,
    ),
  };
}

export function canDraftReviewResponse(reviewStatus: string): boolean {
  return !["responded", "publishing", "removed", "closed", "archived"].includes(
    reviewStatus,
  );
}

export function reviewResponseSourceLabel(generatedByType: string): string {
  if (generatedByType === "imported") return "Google response";
  if (generatedByType === "ai") return "LILOs AI response";
  if (generatedByType === "template") return "LILOs template response";
  if (generatedByType === "user") return "LILOs manual response";
  return "Response";
}

export type AuditEntry = {
  id: string;
  event_type: string;
  action: string;
  result: string;
  occurred_at: string;
  summary: string;
  actor_type: string;
};

function base(organizationId: string, locationId: string): string {
  return `/api/v1/organizations/${organizationId}/locations/${locationId}/reviews`;
}

export function fetchReviews(
  organizationId: string,
  locationId: string,
  params: { statusFilter?: string; search?: string } = {},
): Promise<ApiOutcome<ReviewSummary[]>> {
  const query = new URLSearchParams();
  if (params.statusFilter) query.set("status_filter", params.statusFilter);
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<ReviewSummary[]>(
    `${base(organizationId, locationId)}${suffix}`,
  );
}

export function fetchReviewSummary(
  organizationId: string,
  locationId: string,
): Promise<ApiOutcome<ReviewSummaryStats>> {
  return apiGet<ReviewSummaryStats>(
    `${base(organizationId, locationId)}/summary`,
  );
}

export function fetchReviewDetail(
  organizationId: string,
  locationId: string,
  reviewId: string,
): Promise<ApiOutcome<ReviewDetail>> {
  return apiGet<ReviewDetail>(
    `${base(organizationId, locationId)}/${reviewId}`,
  );
}

export function fetchReviewResponses(
  organizationId: string,
  locationId: string,
  reviewId: string,
): Promise<ApiOutcome<ReviewResponse[]>> {
  return apiGet<ReviewResponse[]>(
    `${base(organizationId, locationId)}/${reviewId}/responses`,
  );
}

export function fetchReviewAudit(
  organizationId: string,
  locationId: string,
  reviewId: string,
): Promise<ApiOutcome<AuditEntry[]>> {
  return apiGet<AuditEntry[]>(
    `${base(organizationId, locationId)}/${reviewId}/audit`,
  );
}

export function draftResponse(
  organizationId: string,
  locationId: string,
  reviewId: string,
  body: {
    review_revision_id: string;
    response_text: string;
    generated_by_type: "user" | "ai" | "template";
    approved_fact_revision_ids: string[];
  },
): Promise<ApiOutcome<{ id: string; revision: number; status: string }>> {
  return apiRequest(
    `${base(organizationId, locationId)}/${reviewId}/responses`,
    {
      method: "POST",
      body,
    },
  );
}

export function generateAIDraft(
  organizationId: string,
  locationId: string,
  reviewId: string,
  body: {
    review_revision_id: string;
    approved_fact_revision_ids: string[];
    idempotency_key: string;
  },
): Promise<
  ApiOutcome<{
    id: string;
    revision: number;
    status: string;
    response_text: string;
    requires_human_review: boolean;
    provider: string | null;
  }>
> {
  return apiRequest(
    `${base(organizationId, locationId)}/${reviewId}/responses/ai-draft`,
    {
      method: "POST",
      body,
    },
  );
}

export function approveResponse(
  organizationId: string,
  locationId: string,
  reviewId: string,
  responseId: string,
): Promise<ApiOutcome<{ id: string; status: string }>> {
  return apiRequest(
    `${base(organizationId, locationId)}/${reviewId}/responses/${responseId}/approve`,
    { method: "POST", body: {} },
  );
}

export function publishResponse(
  organizationId: string,
  locationId: string,
  reviewId: string,
  responseId: string,
  idempotencyKey: string,
): Promise<ApiOutcome<{ id: string; status: string }>> {
  return apiRequest(
    `${base(organizationId, locationId)}/${reviewId}/responses/${responseId}/publish`,
    { method: "POST", body: { idempotency_key: idempotencyKey } },
  );
}

export type ReviewIngestionSummary = {
  total: number;
  ingested: number;
  updated: number;
};

export function ingestReviews(
  organizationId: string,
  locationId: string,
): Promise<ApiOutcome<ReviewIngestionSummary>> {
  return apiRequest<ReviewIngestionSummary>(
    `${base(organizationId, locationId)}/ingest`,
    { method: "POST", body: {} },
  );
}
