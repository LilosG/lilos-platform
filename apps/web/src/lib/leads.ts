import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

/** Lean, PII-free shape returned by list responses and lifecycle actions. */
export type LeadSummary = {
  id: string;
  status: string;
  urgency: string;
  location_id: string | null;
  service_id: string | null;
  assigned_to_user_id: string | null;
  received_at: string;
  acknowledged_at: string | null;
  first_human_contact_at: string | null;
  converted_at: string | null;
  converted_value_cents: number | null;
  loss_reason: string | null;
};

/** Full contact identity, only returned by the single-lead detail endpoint. */
export type LeadDetail = LeadSummary & {
  first_name: string | null;
  last_name: string | null;
  normalized_email: string | null;
  normalized_phone: string | null;
  message: string | null;
};

export type LeadNote = {
  id: string;
  author_user_id: string | null;
  body: string;
  created_at: string;
};

export type LeadTask = {
  id: string;
  title: string;
  description: string | null;
  due_at: string | null;
  assigned_to_user_id: string | null;
  status: string;
  completed_at: string | null;
};

export type LeadCommunication = {
  id: string;
  direction: string;
  channel: string;
  status: string;
  message_reference: string;
  sent_at: string | null;
  delivered_at: string | null;
  failed_at: string | null;
};

export type LeadConsentRecord = {
  id: string;
  channel: string;
  consent_type: string;
  status: string;
  captured_at: string;
  withdrawn_at: string | null;
};

export type LeadSummaryStats = {
  by_status: Record<string, number>;
  open_urgent_count: number;
  average_speed_to_lead_seconds: number | null;
};

export type LeadSourcePerformance = {
  source_id: string;
  name: string;
  lead_count: number;
  converted_count: number;
};

/**
 * Assignable teammate returned by the organization-scoped
 * `GET /api/v1/organizations/{id}/leads/assignees` picker endpoint. Mirrors the
 * backend `AssignableMemberData` contract: only the fields the picker needs,
 * and no email (the backend intentionally omits it because no public
 * membership contract exposes it).
 */
export type AssigneeCandidate = {
  user_profile_id: string;
  display_name: string | null;
  membership_status: string;
  membership_type: string;
  role_keys: string[];
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
  return `/api/v1/organizations/${organizationId}/leads`;
}

export function fetchLeads(
  organizationId: string,
  params: {
    statusFilter?: string;
    urgencyFilter?: string;
    assignedToUserId?: string;
    locationId?: string;
    search?: string;
  } = {},
): Promise<ApiOutcome<LeadSummary[]>> {
  const query = new URLSearchParams();
  if (params.statusFilter) query.set("status_filter", params.statusFilter);
  if (params.urgencyFilter) query.set("urgency_filter", params.urgencyFilter);
  if (params.assignedToUserId)
    query.set("assigned_to_user_id", params.assignedToUserId);
  if (params.locationId) query.set("location_id", params.locationId);
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<LeadSummary[]>(`${base(organizationId)}${suffix}`);
}

export function fetchLeadSummary(
  organizationId: string,
): Promise<ApiOutcome<LeadSummaryStats>> {
  return apiGet<LeadSummaryStats>(`${base(organizationId)}/summary`);
}

export function fetchSourcePerformance(
  organizationId: string,
): Promise<ApiOutcome<LeadSourcePerformance[]>> {
  return apiGet<LeadSourcePerformance[]>(
    `${base(organizationId)}/sources/performance`,
  );
}

/**
 * Fetch the teammates who may be assigned leads for the currently selected
 * organization. Organization-scoped and authorized through the existing
 * `leads.assign` policy; returns an empty list when the organization has no
 * assignable members, and a `forbidden` outcome when the caller cannot assign
 * leads — the caller must render each truthfully rather than guessing.
 */
export function fetchLeadAssignees(
  organizationId: string,
): Promise<ApiOutcome<AssigneeCandidate[]>> {
  return apiGet<AssigneeCandidate[]>(`${base(organizationId)}/assignees`);
}

export function fetchLead(
  organizationId: string,
  leadId: string,
): Promise<ApiOutcome<LeadDetail>> {
  return apiGet<LeadDetail>(`${base(organizationId)}/${leadId}`);
}

export function fetchLeadNotes(
  organizationId: string,
  leadId: string,
): Promise<ApiOutcome<LeadNote[]>> {
  return apiGet<LeadNote[]>(`${base(organizationId)}/${leadId}/notes`);
}

export function fetchLeadTasks(
  organizationId: string,
  leadId: string,
): Promise<ApiOutcome<LeadTask[]>> {
  return apiGet<LeadTask[]>(`${base(organizationId)}/${leadId}/tasks`);
}

export function fetchLeadCommunications(
  organizationId: string,
  leadId: string,
): Promise<ApiOutcome<LeadCommunication[]>> {
  return apiGet<LeadCommunication[]>(
    `${base(organizationId)}/${leadId}/communications`,
  );
}

export function fetchLeadConsents(
  organizationId: string,
  leadId: string,
): Promise<ApiOutcome<LeadConsentRecord[]>> {
  return apiGet<LeadConsentRecord[]>(
    `${base(organizationId)}/${leadId}/consents`,
  );
}

export function fetchLeadAudit(
  organizationId: string,
  leadId: string,
): Promise<ApiOutcome<AuditEntry[]>> {
  return apiGet<AuditEntry[]>(`${base(organizationId)}/${leadId}/audit`);
}

export function assignLead(
  organizationId: string,
  leadId: string,
  assignedToUserId: string,
): Promise<ApiOutcome<LeadDetail>> {
  return apiRequest(`${base(organizationId)}/${leadId}/assign`, {
    method: "POST",
    body: { assigned_to_user_id: assignedToUserId },
  });
}

export function transitionLeadStatus(
  organizationId: string,
  leadId: string,
  toStatus: string,
  safeReason?: string,
): Promise<ApiOutcome<LeadDetail>> {
  return apiRequest(`${base(organizationId)}/${leadId}/status`, {
    method: "POST",
    body: { to_status: toStatus, safe_reason: safeReason ?? null },
  });
}

export function convertLead(
  organizationId: string,
  leadId: string,
  convertedValueCents: number | null,
): Promise<ApiOutcome<LeadDetail>> {
  return apiRequest(`${base(organizationId)}/${leadId}/convert`, {
    method: "POST",
    body: { converted_value_cents: convertedValueCents },
  });
}

export function recordLeadLoss(
  organizationId: string,
  leadId: string,
  toStatus: string,
  lossReason: string,
): Promise<ApiOutcome<LeadDetail>> {
  return apiRequest(`${base(organizationId)}/${leadId}/loss`, {
    method: "POST",
    body: { to_status: toStatus, loss_reason: lossReason },
  });
}

export function addLeadNote(
  organizationId: string,
  leadId: string,
  body: string,
): Promise<ApiOutcome<LeadNote>> {
  return apiRequest(`${base(organizationId)}/${leadId}/notes`, {
    method: "POST",
    body: { body },
  });
}

export function createLeadTask(
  organizationId: string,
  leadId: string,
  task: { title: string; description?: string; dueAt?: string },
): Promise<ApiOutcome<LeadTask>> {
  return apiRequest(`${base(organizationId)}/${leadId}/tasks`, {
    method: "POST",
    body: {
      title: task.title,
      description: task.description ?? null,
      due_at: task.dueAt ?? null,
      assigned_to_user_id: null,
    },
  });
}

export function completeLeadTask(
  organizationId: string,
  leadId: string,
  taskId: string,
): Promise<ApiOutcome<LeadTask>> {
  return apiRequest(
    `${base(organizationId)}/${leadId}/tasks/${taskId}/complete`,
    {
      method: "POST",
      body: {},
    },
  );
}

/**
 * Every lead status the API contract permits on `Lead.status` (the backend
 * check constraint). The Leads list filter offers exactly this set so a lead
 * can be found regardless of its lifecycle state — previously the filter only
 * listed six statuses, leaving leads in any other state unfilterable.
 */
export const LEAD_STATUS_VALUES = [
  "new",
  "validating",
  "unassigned",
  "assigned",
  "acknowledged",
  "contact_attempted",
  "contacted",
  "qualifying",
  "qualified",
  "appointment_requested",
  "appointment_scheduled",
  "converted",
  "nurture",
  "unresponsive",
  "disqualified",
  "lost",
  "spam",
  "duplicate",
  "archived",
] as const;

/**
 * Every urgency the API contract permits on `Lead.urgency`. `unknown` is the
 * server default assigned at intake, so it must be filterable or newly
 * intaken leads cannot be located through the filter.
 */
export const LEAD_URGENCY_VALUES = [
  "routine",
  "same_day",
  "urgent",
  "emergency",
  "unknown",
] as const;

/**
 * Statuses reachable through `POST .../status` (the `LeadStatusTransition`
 * `to_status` literal). Conversion, loss, spam, cancelled, and duplicate are
 * intentionally excluded: they are only reachable through the dedicated
 * `/convert` and `/loss` endpoints (or set at intake for `duplicate`), never
 * through the generic status transition.
 */
export const LEAD_TRANSITION_TARGET_STATUSES = [
  "new",
  "validating",
  "unassigned",
  "assigned",
  "acknowledged",
  "contact_attempted",
  "contacted",
  "qualifying",
  "qualified",
  "appointment_requested",
  "appointment_scheduled",
  "nurture",
  "unresponsive",
  "archived",
] as const;

/**
 * Statuses from which no further status transition is ever permitted. The
 * backend `can_transition` only allows a terminal status to move to
 * `archived`, and `archived` is itself terminal (and `from == to` is
 * rejected), so every status here is a true dead-end for the transition
 * control. Used to disable the transition/convert/loss controls for leads
 * that have already reached a terminal state, rather than leaving controls
 * that can only ever produce an `InvalidLeadTransition` error.
 */
export const TERMINAL_LEAD_STATUSES = [
  "converted",
  "disqualified",
  "lost",
  "spam",
  "duplicate",
  "cancelled",
  "archived",
] as const;

export function isTerminalLeadStatus(status: string): boolean {
  return (TERMINAL_LEAD_STATUSES as readonly string[]).includes(status);
}

/**
 * Truthful speed-to-lead display. Never rounds a sub-minute average down to
 * "0 min" (which previously displayed a real 30-second average as zero
 * minutes), and never invents a value when the backend returned `null`
 * (no leads have reached first human contact yet, so no average exists).
 */
export function formatSpeedToLead(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) return "Not available";
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  return `${Math.round(seconds / 60)} min`;
}
