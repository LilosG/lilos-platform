import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type CapabilitySnapshot = {
  id: string;
  capabilities: Record<
    string,
    { readable: boolean; writable: boolean; reason?: string | null }
  >;
};

export type CompletenessReport = {
  complete: boolean;
  known: string[];
  unknown: string[];
  unsupported_excluded: boolean;
  ranking_score: number | null;
};

export type ChangeSet = {
  id: string;
  revision: number;
  field_changes: Array<{ field: string; value: unknown }>;
  evidence: Record<string, unknown>;
  risk: string;
  status: string;
};

export type SpecialHours = {
  id: string;
  service_date: string;
  revision: number;
  periods: Array<{ opens: string; closes: string }>;
  source: string;
  status: string;
};

export type GBPMediaItem = {
  id: string;
  media_type: string;
  source_reference: string;
  rights_authority: string;
  status: string;
  verified_at: string | null;
};

export type GBPPostRevisionItem = {
  id: string;
  post_key: string;
  revision: number;
  post_type: string;
  content: string;
  status: string;
  publication: GBPPostPublicationItem | null;
};

export type GBPPostPublicationItem = {
  id: string;
  status: string;
  scheduled_for: string | null;
  dispatched_at: string | null;
  provider_post_id: string | null;
  verified_at: string | null;
  recovery_allowed: boolean;
};

export type GBPProviderPostItem = {
  id: string;
  provider_post_name: string;
  post_type: string | null;
  state: string | null;
  summary: string | null;
  content_hash: string;
  status: "present" | "not_seen";
  first_seen_at: string;
  last_seen_at: string | null;
  observed_at: string;
};

export type GBPProviderPostReconciliation = {
  provider_count: number;
  persisted_count: number;
  present_count: number;
  live_count: number;
  processing_count: number;
  rejected_count: number;
  inserted_count: number;
  updated_count: number;
  missing_count: number;
  observed_at: string;
};

export type GBPProviderPostCounts = {
  live: number;
  processing: number;
  rejected: number;
  observed: number;
};

export type GBPPostPresentation = {
  label: string;
  tone: string;
  canPublish: boolean;
  canRecover: boolean;
};

export function providerPostCounts(
  posts: GBPProviderPostItem[],
): GBPProviderPostCounts {
  const present = posts.filter((post) => post.status === "present");
  return {
    live: present.filter((post) => post.state?.toUpperCase() === "LIVE").length,
    processing: present.filter(
      (post) => !["LIVE", "REJECTED"].includes(post.state?.toUpperCase() ?? ""),
    ).length,
    rejected: present.filter((post) => post.state?.toUpperCase() === "REJECTED")
      .length,
    observed: posts.length,
  };
}

export function postPresentation(
  post: GBPPostRevisionItem,
): GBPPostPresentation {
  const publication = post.publication;
  if (!publication) {
    if (post.status === "awaiting_approval") {
      return {
        label: "Awaiting approval",
        tone: "setup",
        canPublish: false,
        canRecover: false,
      };
    }
    if (post.status === "approved") {
      return {
        label: "Approved / never submitted",
        tone: "ready",
        canPublish: true,
        canRecover: false,
      };
    }
    return {
      label: post.status,
      tone: "neutral",
      canPublish: false,
      canRecover: false,
    };
  }

  const presentations: Record<string, { label: string; tone: string }> = {
    reserved: { label: "Reserved / queued", tone: "setup" },
    scheduled: { label: "Reserved / queued", tone: "setup" },
    dispatched: { label: "Dispatched / publishing", tone: "setup" },
    reconciliation_required: {
      label: publication.provider_post_id
        ? "Provider processing / reconciliation required"
        : "Provider result uncertain / operator attention",
      tone: "blocked",
    },
    verified: { label: "Published / verified", tone: "ready" },
    failed: { label: "Failed / rejected", tone: "blocked" },
    cancelled: { label: "Cancelled", tone: "neutral" },
    expired: { label: "Expired", tone: "neutral" },
  };
  const presentation = presentations[publication.status] ?? {
    label: publication.status,
    tone: "neutral",
  };
  return {
    ...presentation,
    canPublish: false,
    canRecover: publication.recovery_allowed,
  };
}

export function postPublicationIdempotencyKey(revisionId: string): string {
  return `web-post-publish-${revisionId}`;
}

export type SuspensionCase = {
  id: string;
  provider_status: string;
  status: string;
  evidence_references: string[];
  safe_timeline: Array<Record<string, unknown>>;
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

function base(organizationId: string, locationId: string): string {
  return `/api/v1/organizations/${organizationId}/locations/${locationId}/gbp/operations`;
}

export function recordCapabilitySnapshot(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
  capabilities: Record<
    string,
    { readable: boolean; writable: boolean; reason?: string }
  >,
): Promise<ApiOutcome<CapabilitySnapshot>> {
  return apiRequest(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/capability-snapshots`,
    {
      method: "POST",
      body: { capabilities, observed_at: new Date().toISOString() },
    },
  );
}

export function fetchCompleteness(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<CompletenessReport>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/completeness`,
  );
}

export function fetchChangeSets(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<ChangeSet[]>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/change-sets`,
  );
}

export function proposeChangeSet(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
  proposal: {
    capabilityKey: string;
    field: string;
    value: string;
    idempotencyKey: string;
  },
): Promise<ApiOutcome<ChangeSet>> {
  return apiRequest(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/change-sets`,
    {
      method: "POST",
      body: {
        capability_key: proposal.capabilityKey,
        field_changes: [{ field: proposal.field, value: proposal.value }],
        evidence: {},
        risk: "low",
        idempotency_key: proposal.idempotencyKey,
      },
    },
  );
}

export function decideChangeSet(
  organizationId: string,
  locationId: string,
  changeSetId: string,
  approve: boolean,
): Promise<ApiOutcome<ChangeSet>> {
  return apiRequest(
    `${base(organizationId, locationId)}/change-sets/${changeSetId}/decision`,
    {
      method: "POST",
      body: { approve },
    },
  );
}

export function fetchSpecialHours(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<SpecialHours[]>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/special-hours`,
  );
}

export function proposeSpecialHours(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
  proposal: { serviceDate: string; opens: string; closes: string },
): Promise<ApiOutcome<SpecialHours>> {
  return apiRequest(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/special-hours`,
    {
      method: "POST",
      body: {
        service_date: proposal.serviceDate,
        periods: [{ opens: proposal.opens, closes: proposal.closes }],
        source: "manual",
      },
    },
  );
}

export function decideSpecialHours(
  organizationId: string,
  locationId: string,
  specialHoursId: string,
  approve: boolean,
): Promise<ApiOutcome<SpecialHours>> {
  return apiRequest(
    `${base(organizationId, locationId)}/special-hours/${specialHoursId}/decision`,
    {
      method: "POST",
      body: { approve },
    },
  );
}

export function fetchMedia(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<GBPMediaItem[]>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/media`,
  );
}

export function proposeMedia(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
  media: {
    mediaType: "photo" | "video" | "logo" | "cover";
    sourceReference: string;
    rightsAuthority: string;
  },
): Promise<ApiOutcome<GBPMediaItem>> {
  return apiRequest(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/media`,
    {
      method: "POST",
      body: {
        media_type: media.mediaType,
        source_reference: media.sourceReference,
        rights_authority: media.rightsAuthority,
        idempotency_key: `web-media-${gbpLocationId}-${Date.now()}`,
      },
    },
  );
}

export function fetchPostRevisions(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<GBPPostRevisionItem[]>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/posts`,
  );
}

export function fetchProviderPosts(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<GBPProviderPostItem[]>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/posts/provider`,
  );
}

export function reconcileProviderPosts(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<GBPProviderPostReconciliation>> {
  return apiRequest(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/posts/reconcile`,
    { method: "POST" },
  );
}

export function createPostRevision(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
  post: { postType: "standard" | "event" | "offer" | "alert"; content: string },
): Promise<ApiOutcome<GBPPostRevisionItem>> {
  return apiRequest(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/posts`,
    {
      method: "POST",
      body: { post_type: post.postType, content: post.content },
    },
  );
}

export function decidePostRevision(
  organizationId: string,
  locationId: string,
  revisionId: string,
  approve: boolean,
): Promise<ApiOutcome<GBPPostRevisionItem>> {
  return apiRequest(
    `${base(organizationId, locationId)}/posts/${revisionId}/decision`,
    {
      method: "POST",
      body: { approve },
    },
  );
}

export function publishPost(
  organizationId: string,
  locationId: string,
  revisionId: string,
  workflowRunId: string,
  idempotencyKey: string,
): Promise<ApiOutcome<GBPPostPublicationItem>> {
  return apiRequest(
    `${base(organizationId, locationId)}/posts/${revisionId}/publish`,
    {
      method: "POST",
      body: {
        workflow_run_id: workflowRunId,
        idempotency_key: idempotencyKey,
      },
    },
  );
}

export function recoverPostPublication(
  organizationId: string,
  locationId: string,
  publicationId: string,
): Promise<ApiOutcome<GBPPostPublicationItem>> {
  return apiRequest(
    `${base(organizationId, locationId)}/posts/publications/${publicationId}/recover`,
    { method: "POST" },
  );
}

export function fetchSuspensionCases(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<SuspensionCase[]>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/suspension-cases`,
  );
}

export function reportSuspensionCase(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
  report: { providerStatus: string },
): Promise<ApiOutcome<SuspensionCase>> {
  return apiRequest(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/suspension-cases`,
    {
      method: "POST",
      body: { provider_status: report.providerStatus, evidence_references: [] },
    },
  );
}

export function fetchOperationsAudit(
  organizationId: string,
  locationId: string,
  gbpLocationId: string,
): Promise<ApiOutcome<AuditEntry[]>> {
  return apiGet(
    `${base(organizationId, locationId)}/locations/${gbpLocationId}/audit`,
  );
}
