import { apiGet, apiRequest, type ApiOutcome } from "./api-client";
import {
  getWorkflowRun,
  listWorkflowRuns,
  startWorkflowRun,
  type WorkflowRunStart,
} from "./workflows";

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

export type ReviewIngestionRun = {
  workflow_run_id: string;
  status: string;
  product_key: string | null;
};

const REVIEW_SYNC_ACTIVE_STATUSES = new Set([
  "created",
  "queued",
  "running",
  "retry_scheduled",
]);
const REVIEW_SYNC_TERMINAL_FAILURE_STATUSES = new Set([
  "failed",
  "cancelled",
  "escalated",
]);
const REVIEW_SYNC_POLL_INTERVAL_MS = 1_500;
const REVIEW_SYNC_MAX_WAIT_MS = 10 * 60 * 1_000;

export function isReviewSyncActiveStatus(status: string): boolean {
  return REVIEW_SYNC_ACTIVE_STATUSES.has(status);
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function workflowFailure(run: {
  status: string;
  failure_code: string | null;
}): ApiOutcome<ReviewIngestionRun> {
  return {
    kind: "error",
    status: 409,
    code: run.failure_code ?? "REVIEWS_INGEST_FAILED",
    message:
      run.status === "escalated"
        ? "Google review sync requires reconciliation before it can continue."
        : "Google review sync failed. Check the workflow run for the provider error.",
    details: [],
  };
}

async function waitForReviewIngestion(
  organizationId: string,
  initial: WorkflowRunStart,
): Promise<ApiOutcome<ReviewIngestionRun>> {
  let current: ReviewIngestionRun = initial;
  const deadline = Date.now() + REVIEW_SYNC_MAX_WAIT_MS;

  while (Date.now() < deadline) {
    if (current.status === "completed") {
      return { kind: "ok", data: current };
    }
    if (REVIEW_SYNC_TERMINAL_FAILURE_STATUSES.has(current.status)) {
      const detail = await getWorkflowRun(organizationId, current.workflow_run_id);
      if (detail.kind !== "ok") return detail;
      return workflowFailure(detail.data);
    }

    await sleep(REVIEW_SYNC_POLL_INTERVAL_MS);
    const detail = await getWorkflowRun(organizationId, current.workflow_run_id);
    if (detail.kind !== "ok") return detail;
    current = {
      workflow_run_id: detail.data.id,
      status: detail.data.status,
      product_key: detail.data.product_key,
    };
  }

  return {
    kind: "error",
    status: 0,
    code: "REVIEWS_INGEST_STILL_RUNNING",
    message:
      "Google review sync is still running in the background. Refresh this page to see the latest completed data.",
    details: [],
  };
}

/**
 * Start review ingestion on the platform's durable workflow queue, then poll
 * the persisted run instead of holding one browser request open while Google
 * paginates. If the page is refreshed while a sync is already active, reuse
 * that run rather than enqueueing duplicate provider work.
 */
export async function ingestReviews(
  organizationId: string,
  locationId: string,
): Promise<ApiOutcome<ReviewIngestionRun>> {
  const existing = await listWorkflowRuns(organizationId, {
    workflowKey: "reviews.ingest",
    locationId,
    limit: 20,
  });
  if (existing.kind !== "ok") return existing;

  const active = existing.data.find((run) =>
    isReviewSyncActiveStatus(run.status),
  );
  let run: WorkflowRunStart;
  if (active) {
    run = {
      workflow_run_id: active.id,
      status: active.status,
      product_key: active.product_key,
    };
  } else {
    const started = await startWorkflowRun(organizationId, "reviews.ingest", {
      locationId,
      idempotencyKey: `web-reviews-ingest-${locationId}-${Date.now()}`,
      execute: true,
    });
    if (started.kind !== "ok") return started;
    run = started.data;
  }

  return waitForReviewIngestion(organizationId, run);
}
