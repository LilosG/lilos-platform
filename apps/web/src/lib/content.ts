import { apiGet, apiRequest, type ApiOutcome } from "./api-client";
import { getWorkflowRun, type WorkflowRunDetail } from "./workflows";

export type ContentOpportunity = {
  id: string;
  location_id: string | null;
  product_key: string;
  target_reference: string;
  opportunity_type: string;
  priority_score: number;
  status: string;
};

/** Statuses accepted by the opportunity decision endpoint. */
export const CONTENT_ACTIONABLE_OPPORTUNITY_STATUSES = [
  "identified",
  "validated",
] as const;

/** Governed facts required by the current Content product catalog. */
export const CONTENT_REQUIRED_FACT_KEYS = [
  "business.name",
  "brand.approved_claims",
] as const;

export function isContentOpportunityActionable(status: string): boolean {
  return (
    CONTENT_ACTIONABLE_OPPORTUNITY_STATUSES as readonly string[]
  ).includes(status);
}

export type ContentItem = {
  id: string;
  opportunity_id: string | null;
  location_id: string | null;
  content_type: string;
  title: string;
  slug: string;
  status: string;
  published_at: string | null;
};

export type ContentBrief = {
  id: string;
  revision_number: number;
  audience: string;
  intent: string;
  target_reference: string;
  approved_fact_revision_ids: string[];
  status: string;
};

export type ContentRevision = {
  id: string;
  revision_number: number;
  body: string;
  frontmatter: Record<string, unknown>;
  created_by_type: string;
  status: string;
  validation_document: { valid: boolean; errors: string[] };
  approved_at: string | null;
};

export type ContentPublication = {
  id: string;
  status: string;
  target_path: string;
  branch_name: string | null;
  external_pull_request_id: string | null;
  build_status: string | null;
  deployment_status: string | null;
  published_url: string | null;
  verified_at: string | null;
};

export type PublishingTarget = {
  id: string;
  key: string;
  target_type: string;
  repository_id: string;
  base_branch: string;
  allowed_path_prefix: string;
  status: string;
};

export type GitHubConnection = {
  id: string;
  external_account_reference: string | null;
  status: string;
};

export function isGitHubAppConnection(connection: GitHubConnection): boolean {
  return (
    connection.external_account_reference?.startsWith("installation:") ?? false
  );
}

export type ContentSummaryStats = {
  by_status: Record<string, number>;
  open_opportunities: number;
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
  return `/api/v1/organizations/${organizationId}/content`;
}

export function fetchOpportunities(
  organizationId: string,
  statusFilter?: string,
): Promise<ApiOutcome<ContentOpportunity[]>> {
  const suffix = statusFilter
    ? `?status_filter=${encodeURIComponent(statusFilter)}`
    : "";
  return apiGet<ContentOpportunity[]>(
    `${base(organizationId)}/opportunities${suffix}`,
  );
}

export function decideOpportunity(
  organizationId: string,
  opportunityId: string,
  accept: boolean,
): Promise<ApiOutcome<ContentOpportunity>> {
  return apiRequest(
    `${base(organizationId)}/opportunities/${opportunityId}/decision`,
    {
      method: "POST",
      body: { accept },
    },
  );
}

export function fetchPublishingTargets(
  organizationId: string,
): Promise<ApiOutcome<PublishingTarget[]>> {
  return apiGet<PublishingTarget[]>(`${base(organizationId)}/targets`);
}

export function fetchGitHubConnections(
  organizationId: string,
): Promise<ApiOutcome<GitHubConnection[]>> {
  return apiGet<GitHubConnection[]>(`${base(organizationId)}/connections`);
}

export function registerGitHubConnection(
  organizationId: string,
  body: {
    accessToken: string;
    externalAccountReference?: string;
  },
): Promise<ApiOutcome<GitHubConnection>> {
  return apiRequest(`${base(organizationId)}/connections`, {
    method: "POST",
    body: {
      access_token: body.accessToken,
      external_account_reference: body.externalAccountReference ?? null,
    },
  });
}

export function createPublishingTarget(
  organizationId: string,
  body: {
    key: string;
    connectionId: string;
    repositoryId: string;
    baseBranch: string;
    allowedPathPrefix: string;
    deploymentTargetReference?: string;
  },
): Promise<ApiOutcome<PublishingTarget>> {
  return apiRequest(`${base(organizationId)}/targets`, {
    method: "POST",
    body: {
      key: body.key,
      connection_id: body.connectionId,
      target_type: "github_astro",
      repository_id: body.repositoryId,
      base_branch: body.baseBranch,
      allowed_path_prefix: body.allowedPathPrefix,
      deployment_target_reference: body.deploymentTargetReference ?? null,
    },
  });
}

export function fetchContentSummary(
  organizationId: string,
): Promise<ApiOutcome<ContentSummaryStats>> {
  return apiGet<ContentSummaryStats>(`${base(organizationId)}/summary`);
}

export function fetchContentItems(
  organizationId: string,
  params: { statusFilter?: string; search?: string } = {},
): Promise<ApiOutcome<ContentItem[]>> {
  const query = new URLSearchParams();
  if (params.statusFilter) query.set("status_filter", params.statusFilter);
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<ContentItem[]>(`${base(organizationId)}${suffix}`);
}

export function createContentItem(
  organizationId: string,
  item: {
    opportunityId?: string;
    locationId?: string;
    contentType: string;
    title: string;
    slug: string;
  },
): Promise<ApiOutcome<ContentItem>> {
  return apiRequest(base(organizationId), {
    method: "POST",
    body: {
      opportunity_id: item.opportunityId ?? null,
      location_id: item.locationId ?? null,
      content_type: item.contentType,
      title: item.title,
      slug: item.slug,
    },
  });
}

export function fetchContentItem(
  organizationId: string,
  itemId: string,
): Promise<ApiOutcome<ContentItem>> {
  return apiGet<ContentItem>(`${base(organizationId)}/${itemId}`);
}

export function fetchItemAudit(
  organizationId: string,
  itemId: string,
): Promise<ApiOutcome<AuditEntry[]>> {
  return apiGet<AuditEntry[]>(`${base(organizationId)}/${itemId}/audit`);
}

export function fetchBriefs(
  organizationId: string,
  itemId: string,
): Promise<ApiOutcome<ContentBrief[]>> {
  return apiGet<ContentBrief[]>(`${base(organizationId)}/${itemId}/briefs`);
}

export function createBrief(
  organizationId: string,
  itemId: string,
  brief: {
    audience: string;
    intent: string;
    targetReference: string;
    approvedFactRevisionIds: string[];
  },
): Promise<ApiOutcome<ContentBrief>> {
  return apiRequest(`${base(organizationId)}/${itemId}/briefs`, {
    method: "POST",
    body: {
      audience: brief.audience,
      intent: brief.intent,
      target_reference: brief.targetReference,
      approved_fact_revision_ids: brief.approvedFactRevisionIds,
    },
  });
}

export function fetchRevisions(
  organizationId: string,
  itemId: string,
): Promise<ApiOutcome<ContentRevision[]>> {
  return apiGet<ContentRevision[]>(
    `${base(organizationId)}/${itemId}/revisions`,
  );
}

export function createRevision(
  organizationId: string,
  itemId: string,
  revision: {
    body: string;
    frontmatter: Record<string, unknown>;
    approvedFactRevisionIds: string[];
  },
): Promise<ApiOutcome<ContentRevision>> {
  return apiRequest(`${base(organizationId)}/${itemId}/revisions`, {
    method: "POST",
    body: {
      body: revision.body,
      frontmatter: revision.frontmatter,
      created_by_type: "user",
      approved_fact_revision_ids: revision.approvedFactRevisionIds,
    },
  });
}

/* ------------------------------------------------------------------ */
/*  Durable AI draft generation                                        */
/* ------------------------------------------------------------------ */

/** Response shape from the durable (202) AI draft start endpoint. */
export type DurableAIDraftStart = {
  workflow_run_id: string;
  status: string;
  workflow_key: string;
  item_id: string;
};

/**
 * Start a durable AI-assisted content draft generation.
 *
 * The backend returns 202 Accepted with a ``workflow_run_id`` immediately.
 * The AI generation executes asynchronously via the platform worker.
 * Poll ``GET /workflows/runs/{run_id}`` for status.
 *
 * The same ``idempotencyKey`` + same brief/item produces the same
 * workflow run — repeated clicks do not create duplicates.
 */
export function generateAIDraft(
  organizationId: string,
  itemId: string,
  briefId: string,
  idempotencyKey: string,
): Promise<ApiOutcome<DurableAIDraftStart>> {
  return apiRequest(`${base(organizationId)}/${itemId}/revisions/ai-draft`, {
    method: "POST",
    body: { brief_id: briefId, idempotency_key: idempotencyKey },
    /** The durable start returns promptly — no need for a 60-second
     *  timeout.  The default 15-second client timeout is sufficient. */
  });
}

/* ------------------------------------------------------------------ */
/*  Durable AI draft polling and status mapping                        */
/* ------------------------------------------------------------------ */

/** Client-appropriate Content status derived from a workflow run. */
export type ContentAIDraftStatus =
  "queued" | "running" | "retrying" | "completed" | "failed" | "cancelled";

/**
 * Map raw workflow-run state into a client/operator-appropriate Content
 * status.  Internal worker IDs, safe-error codes, and job-level detail
 * are never exposed to the UX.
 */
export function mapWorkflowRunToContentStatus(
  run: WorkflowRunDetail,
): ContentAIDraftStatus {
  const runStatus = run.status;
  const jobStatus = run.jobs?.[0]?.status;

  if (runStatus === "completed") return "completed";
  if (runStatus === "cancelled" || runStatus === "expired") return "cancelled";

  // The runtime sets run.status="failed" for both permanent and retryable
  // failures.  When the job is still retry_scheduled, the operation is
  // still in progress — surface it truthfully as "retrying".
  if (runStatus === "failed" && jobStatus === "retry_scheduled") {
    return "retrying";
  }
  if (runStatus === "failed") return "failed";

  if (runStatus === "running") return "running";
  if (runStatus === "queued" || runStatus === "created") return "queued";

  // Unknown / unexpected states — treat as queued (still in progress).
  return "queued";
}

/** Human-readable label for a Content AI draft generation status. */
export function describeAIDraftStatus(status: ContentAIDraftStatus): string {
  switch (status) {
    case "queued":
      return "Queued — waiting for a worker…";
    case "running":
      return "Generating draft…";
    case "retrying":
      return "Retrying — a previous attempt did not complete.  The platform will try again automatically.";
    case "completed":
      return "Draft complete.";
    case "failed":
      return "Draft generation did not complete.  You can try again.";
    case "cancelled":
      return "Draft generation was cancelled.";
  }
}

/** Whether the status is terminal (no further polling needed). */
export function isAIDraftTerminal(status: ContentAIDraftStatus): boolean {
  return (
    status === "completed" || status === "failed" || status === "cancelled"
  );
}

/* ------------------------------------------------------------------ */
/*  In-flight operation persistence (sessionStorage)                   */
/* ------------------------------------------------------------------ */

export type InFlightAIDraft = {
  itemId: string;
  briefId: string;
  idempotencyKey: string;
  runId: string;
};

function storageKey(
  organizationId: string,
  itemId: string,
  briefId: string,
): string {
  return `lilos.content.ai-draft.${organizationId}.${itemId}.${briefId}`;
}

/** Persist an in-flight AI draft operation so a browser refresh can recover it. */
export function storeInFlightAIDraft(
  organizationId: string,
  state: InFlightAIDraft,
): void {
  try {
    sessionStorage.setItem(
      storageKey(organizationId, state.itemId, state.briefId),
      JSON.stringify(state),
    );
  } catch {
    // sessionStorage unavailable — graceful degradation.
  }
}

/** Recover a previously-stored in-flight operation, if any. */
export function recoverInFlightAIDraft(
  organizationId: string,
  itemId: string,
  briefId: string,
): InFlightAIDraft | null {
  try {
    const raw = sessionStorage.getItem(
      storageKey(organizationId, itemId, briefId),
    );
    if (!raw) return null;
    const parsed = JSON.parse(raw) as InFlightAIDraft;
    if (
      parsed.itemId === itemId &&
      parsed.briefId === briefId &&
      parsed.idempotencyKey &&
      parsed.runId
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** Clear the stored in-flight operation (terminal state or navigation away). */
export function clearInFlightAIDraft(
  organizationId: string,
  itemId: string,
  briefId: string,
): void {
  try {
    sessionStorage.removeItem(storageKey(organizationId, itemId, briefId));
  } catch {
    // sessionStorage unavailable — graceful degradation.
  }
}

/**
 * Poll a workflow run for the current Content AI draft status.
 *
 * Returns the mapped status and the full run detail (for output_reference
 * resolution on completion).  Returns ``null`` when the run cannot be
 * fetched (e.g. 404 — the run may have been cleaned up).
 */
export async function pollAIDraftRun(
  organizationId: string,
  runId: string,
): Promise<{ status: ContentAIDraftStatus; run: WorkflowRunDetail } | null> {
  const result = await getWorkflowRun(organizationId, runId);
  if (result.kind !== "ok") return null;
  return {
    status: mapWorkflowRunToContentStatus(result.data),
    run: result.data,
  };
}

export function decideRevision(
  organizationId: string,
  itemId: string,
  revisionId: string,
  stage: "editorial" | "client",
  approve: boolean,
): Promise<ApiOutcome<ContentRevision>> {
  return apiRequest(
    `${base(organizationId)}/${itemId}/revisions/${revisionId}/decision`,
    {
      method: "POST",
      body: { stage, approve },
    },
  );
}

export function fetchPublications(
  organizationId: string,
  itemId: string,
): Promise<ApiOutcome<ContentPublication[]>> {
  return apiGet<ContentPublication[]>(
    `${base(organizationId)}/${itemId}/publications`,
  );
}

export function reservePublication(
  organizationId: string,
  itemId: string,
  revisionId: string,
  publish: {
    publishingTargetId: string;
    workflowRunId: string;
    targetPath: string;
    idempotencyKey: string;
  },
): Promise<ApiOutcome<ContentPublication>> {
  return apiRequest(
    `${base(organizationId)}/${itemId}/revisions/${revisionId}/publish`,
    {
      method: "POST",
      body: {
        publishing_target_id: publish.publishingTargetId,
        workflow_run_id: publish.workflowRunId,
        target_path: publish.targetPath,
        idempotency_key: publish.idempotencyKey,
      },
    },
  );
}

/**
 * Derive a URL-friendly slug from a title.
 * Matches the backend slug contract: lowercase alphanumeric with hyphens,
 * no leading/trailing hyphens, no consecutive hyphens.
 */
export function deriveSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/['']/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 200);
}

/* ------------------------------------------------------------------ */
/*  Content brief character limits                                     */
/* ------------------------------------------------------------------ */

/** Maximum characters the backend accepts for a content goal / intent. */
export const CONTENT_GOAL_MAXLENGTH = 500;

/** Maximum characters the backend accepts for audience. */
export const AUDIENCE_MAXLENGTH = 500;

/* ------------------------------------------------------------------ */
/*  Document rendering                                                 */
/* ------------------------------------------------------------------ */

/**
 * Render long-form document body text into a safe, readable DOM fragment.
 *
 * The text is interpreted as a lightweight Markdown subset (paragraphs
 * separated by blank lines, ATX headings, unordered lists, and plain
 * inline text).  Everything is built with DOM text nodes — there is no
 * innerHTML injection and therefore no XSS vector from user/AI content.
 *
 * The returned `<article>` element carries the `.content-document` class
 * so CSS can apply readable line-length, heading/paragraph/list spacing,
 * and review-appropriate typography.
 */
export function renderDocumentBody(body: string): HTMLElement {
  const article = document.createElement("article");
  article.className = "content-document";

  if (!body || !body.trim()) {
    const empty = document.createTextNode(
      "No document body available for this revision.",
    );
    article.append(empty);
    return article;
  }

  // Normalise line endings.
  const normalised = body.replace(/\r\n?/g, "\n");

  // Split into logical blocks separated by blank lines.
  const blocks = normalised.split(/\n{2,}/);

  for (const rawBlock of blocks) {
    const trimmed = rawBlock.trim();
    if (!trimmed) continue;

    // --- ATX heading (# … through ###### …) ---
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = Math.min(headingMatch[1].length, 6);
      const heading = document.createElement(
        `h${level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6",
      );
      heading.textContent = headingMatch[2];
      article.append(heading);
      continue;
    }

    // --- Unordered list block (every line starts with `- `, `* `, or `+ `) ---
    const lines = trimmed.split("\n");
    const allListLines = lines.every(
      (line) => /^[-*+]\s/.test(line) || line.trim() === "",
    );
    if (allListLines && lines.some((line) => /^[-*+]\s/.test(line))) {
      const list = document.createElement("ul");
      for (const line of lines) {
        const itemMatch = line.match(/^[-*+]\s+(.+)$/);
        if (!itemMatch) continue;
        const li = document.createElement("li");
        li.textContent = itemMatch[1];
        list.append(li);
      }
      article.append(list);
      continue;
    }

    // --- Plain paragraph ---
    const paragraph = document.createElement("p");
    // Collapse single newlines inside a paragraph block into spaces.
    paragraph.textContent = trimmed.replace(/\n/g, " ");
    article.append(paragraph);
  }

  return article;
}

/* ------------------------------------------------------------------ */
/*  Validation helpers                                                 */
/* ------------------------------------------------------------------ */

/**
 * Format a "N / M characters" label for a character-count constraint.
 * Returns `"0 / 500 characters"`, `"500 / 500 characters"`, etc.
 */
export function formatCharacterCount(current: number, max: number): string {
  return `${Math.max(0, current)} / ${max} characters`;
}

/**
 * Whether the given count exceeds the limit (useful for submit guards).
 */
export function isOverCharacterLimit(count: number, limit: number): boolean {
  return count > limit;
}

/* ------------------------------------------------------------------ */
/*  Field-specific API error helpers                                   */
/* ------------------------------------------------------------------ */

export type FieldValidationError = {
  field: string;
  message: string;
};

/**
 * Extract validation errors scoped to a specific field from an API error
 * outcome's `details` array.
 *
 * Returns `null` when the outcome is not an error or has no relevant
 * detail — the caller should fall back to the generic outcome message.
 */
export function fieldErrorFromDetails(
  outcome: ApiOutcome<unknown>,
  fieldName: string,
): string | null {
  if (outcome.kind !== "error") return null;
  if (!outcome.details || outcome.details.length === 0) return null;
  const match = outcome.details.find(
    (detail) => detail.field?.toLowerCase() === fieldName.toLowerCase(),
  );
  return match?.message ?? null;
}

/**
 * Build a user-facing error summary from the outcome and optional context.
 * When field-level details are present they take priority over the generic
 * error envelope.
 */
export function describeContentFailure(
  outcome: ApiOutcome<unknown>,
  context?: string,
): string {
  if (outcome.kind === "error" && outcome.details?.length) {
    const messages = outcome.details
      .map((detail) => (detail.field ? `${detail.message}` : detail.message))
      .filter(Boolean);
    if (messages.length > 0) {
      return messages.join(" ");
    }
  }
  // Fall through to the generic outcome description.
  const prefix = context ? `${context}: ` : "";
  switch (outcome.kind) {
    case "forbidden":
      return `${prefix}You do not have permission to perform this action.`;
    case "not-found":
      return `${prefix}The requested resource could not be found.`;
    case "disconnected":
      return `${prefix}Could not confirm the platform received your request.  Try again — your request will not be duplicated.`;
    case "unauthenticated":
      return `${prefix}Your session has expired. Sign in again.`;
    case "not-configured":
      return `${prefix}This deployment is not configured.`;
    case "error":
      return outcome.message || `${prefix}The request failed.`;
    case "ok":
      return "";
  }
}
