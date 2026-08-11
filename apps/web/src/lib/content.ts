import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

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

export function generateAIDraft(
  organizationId: string,
  itemId: string,
  briefId: string,
  idempotencyKey: string,
): Promise<
  ApiOutcome<
    ContentRevision & {
      requires_human_review: boolean;
      provider: string | null;
    }
  >
> {
  return apiRequest(`${base(organizationId)}/${itemId}/revisions/ai-draft`, {
    method: "POST",
    body: { brief_id: briefId, idempotency_key: idempotencyKey },
  });
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
