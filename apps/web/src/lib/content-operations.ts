import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type ContentOperatorStage =
  | "brief_needed"
  | "draft_needed"
  | "drafting"
  | "editorial_review"
  | "client_review"
  | "revision_needed"
  | "ready_to_publish"
  | "publishing"
  | "published"
  | "needs_attention";

export type ContentOperatorSummary = {
  id: string;
  location_id: string | null;
  content_type: string;
  title: string;
  slug: string;
  stage: ContentOperatorStage;
  next_action: { key: string; label: string };
  published_at: string | null;
  latest_revision_status: string | null;
  latest_revision_number: number | null;
  publication_status: string | null;
};

export type ContentOperatorBrief = {
  id: string;
  revision_number: number;
  audience: string;
  intent: string;
  target_reference: string;
  approved_fact_revision_ids: string[];
  status: string;
};

export type ContentOperatorRevision = {
  id: string;
  revision_number: number;
  body: string;
  frontmatter: Record<string, unknown>;
  created_by_type: string;
  status: string;
  validation_document: { valid: boolean; errors: string[] };
  approved_at: string | null;
};

export type ContentOperatorPublication = {
  id: string;
  status: string;
  target_path: string;
  external_pull_request_id: string | null;
  published_url: string | null;
  build_status: string | null;
  deployment_status: string | null;
  verified_at: string | null;
  safe_error_code: string | null;
};

export type ContentOperatorTarget = {
  id: string;
  key: string;
  repository_id: string;
  base_branch: string;
  allowed_path_prefix: string;
  file_extensions: string[];
  status: string;
};

export type ContentPublishingRequirements = {
  target_selected: boolean;
  target_id?: string;
  missing: string[];
  requires_image: boolean;
  requires_image_alt: boolean;
  file_extensions: string[];
};

export type ContentOperatorDetail = ContentOperatorSummary & {
  briefs: ContentOperatorBrief[];
  revisions: ContentOperatorRevision[];
  publications: ContentOperatorPublication[];
  publishing_targets: ContentOperatorTarget[];
  publishing_requirements: ContentPublishingRequirements;
};

export type ContentImageAsset = { path: string; name: string };

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/content-operations`;
}

export function fetchContentOperations(
  organizationId: string,
): Promise<ApiOutcome<ContentOperatorSummary[]>> {
  return apiGet<ContentOperatorSummary[]>(base(organizationId));
}

export function fetchContentOperation(
  organizationId: string,
  itemId: string,
): Promise<ApiOutcome<ContentOperatorDetail>> {
  return apiGet<ContentOperatorDetail>(`${base(organizationId)}/${itemId}`);
}

export function decideContentOperationRevision(
  organizationId: string,
  itemId: string,
  revisionId: string,
  stage: "editorial" | "client",
  approve: boolean,
): Promise<
  ApiOutcome<{ id: string; status: string; revision_number: number }>
> {
  return apiRequest(
    `${base(organizationId)}/${itemId}/revisions/${revisionId}/decision`,
    { method: "POST", body: { stage, approve } },
  );
}

export function publishContentOperation(
  organizationId: string,
  itemId: string,
  options: {
    idempotencyKey: string;
    publishingTargetId?: string;
    image?: string;
    imageAlt?: string;
  },
): Promise<ApiOutcome<{ id: string; status: string; target_path: string }>> {
  return apiRequest(`${base(organizationId)}/${itemId}/publish`, {
    method: "POST",
    body: {
      idempotency_key: options.idempotencyKey,
      publishing_target_id: options.publishingTargetId ?? null,
      image: options.image ?? null,
      image_alt: options.imageAlt ?? null,
    },
  });
}

export function fetchContentPublishingAssets(
  organizationId: string,
  itemId: string,
  targetId: string,
): Promise<ApiOutcome<ContentImageAsset[]>> {
  const query = new URLSearchParams({ target_id: targetId });
  return apiGet<ContentImageAsset[]>(
    `${base(organizationId)}/${itemId}/publishing-assets?${query.toString()}`,
  );
}

export function contentStageLabel(stage: ContentOperatorStage): string {
  switch (stage) {
    case "brief_needed":
      return "Brief needed";
    case "draft_needed":
      return "Ready for draft";
    case "drafting":
      return "Draft in progress";
    case "editorial_review":
      return "Editorial review";
    case "client_review":
      return "Final approval";
    case "revision_needed":
      return "Revision needed";
    case "ready_to_publish":
      return "Ready to publish";
    case "publishing":
      return "Publishing";
    case "published":
      return "Published";
    case "needs_attention":
      return "Needs attention";
  }
}

export function contentStageTone(stage: ContentOperatorStage): string {
  if (stage === "published" || stage === "ready_to_publish") return "ready";
  if (stage === "needs_attention" || stage === "revision_needed")
    return "blocked";
  return "setup";
}
