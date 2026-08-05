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
