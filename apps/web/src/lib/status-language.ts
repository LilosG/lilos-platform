const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  approved: "Approved",
  archived: "Archived",
  assigned: "Assigned",
  awaiting_approval: "Awaiting approval",
  cancelled: "Cancelled",
  cancelled_workflow: "Cancelled",
  checks_failed: "Checks failed",
  checks_running: "Checks running",
  classified: "Classified",
  completed: "Completed",
  configured: "Configured",
  connected: "Connected",
  connection_required: "Needs attention",
  contacted: "Contacted",
  contact_attempted: "Contact attempted",
  converted: "Converted",
  dead_lettered: "Needs attention",
  degraded: "Needs attention",
  deployed: "Published",
  disconnected: "Needs attention",
  draft: "Draft",
  drafting: "Drafting",
  escalated: "Needs attention",
  failed: "Needs attention",
  fresh: "Synced",
  identified: "Identified",
  implementation_blocked: "Needs attention",
  mapped: "Mapped",
  new: "New",
  never: "Not yet synced",
  never_synced: "Not yet synced",
  not_configured: "Unavailable",
  not_connected: "Needs attention",
  not_entitled: "Unavailable",
  not_mapped: "Needs attention",
  not_persisted: "Not activated",
  paused: "Paused",
  pending: "Pending",
  pending_verification: "Pending verification",
  publication_failed: "Response failed",
  published: "Published",
  publishing: "Publishing",
  queued: "Queued",
  ready: "Ready",
  reconnect_required: "Needs attention",
  reconciliation_required: "Needs attention",
  responded: "Responded",
  restricted: "Restricted",
  retry_scheduled: "Retry scheduled",
  running: "Running",
  scheduled: "Scheduled",
  setup_required: "Needs attention",
  stale: "Stale",
  synced: "Synced",
  unavailable: "Unavailable",
  unassigned: "Unassigned",
  unknown: "Unknown",
  validated: "Validated",
  verified: "Verified",
  waiting_approval: "Awaiting approval",
};

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "Unavailable";
  return (
    STATUS_LABELS[status] ??
    status
      .replace(/_/g, " ")
      .replace(/\b\w/g, (character) => character.toUpperCase())
  );
}

export function sentimentLabel(sentiment: string | null | undefined): string {
  if (!sentiment || sentiment === "unknown" || sentiment === "unclassified") {
    return "Not classified";
  }
  return statusLabel(sentiment);
}

export function statusTone(status: string | null | undefined): string {
  if (!status) return "neutral";
  if (
    [
      "active",
      "approved",
      "completed",
      "connected",
      "converted",
      "deployed",
      "fresh",
      "published",
      "ready",
      "responded",
      "synced",
      "verified",
    ].includes(status)
  ) {
    return "ready";
  }
  if (
    [
      "checks_failed",
      "dead_lettered",
      "degraded",
      "failed",
      "publication_failed",
      "reconnect_required",
      "reconciliation_required",
      "stale",
    ].includes(status)
  ) {
    return "blocked";
  }
  if (
    [
      "connection_required",
      "disconnected",
      "never",
      "never_synced",
      "not_connected",
      "not_mapped",
      "setup_required",
    ].includes(status)
  ) {
    return "missing";
  }
  return "setup";
}
