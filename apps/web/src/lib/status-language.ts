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

export interface WebsiteStatusPresentation {
  tone: string;
  label: string;
  note: string;
}

/**
 * How an SEO website's lifecycle status should read to an operator.
 *
 * `pending_verification` is the state every newly provisioned website starts
 * in, and it blocks nothing: the crawler never consults it. Rendered as a lone
 * amber "Pending verification" chip it read as a fault and sent operators
 * looking for a verification step that does not exist — the status is flipped
 * automatically once a Search Console property matching the canonical origin
 * is mapped. So the label states the capability that is actually true, and the
 * note says what the outstanding evidence costs and how it resolves itself.
 */
export function websiteStatusPresentation(
  status: string | null | undefined,
): WebsiteStatusPresentation {
  if (status === "archived") {
    return { tone: "neutral", label: "Unavailable", note: "Archived." };
  }
  if (status === "paused") {
    return {
      tone: "setup",
      label: "Needs attention",
      note: "Paused — crawls and opportunity work will not run until it resumes.",
    };
  }
  if (status === "pending_verification") {
    return {
      tone: "ready",
      label: "Ready to crawl",
      note:
        "Crawling works now. Search performance needs Search Console " +
        "connected, which also confirms ownership automatically — there is no " +
        "verification step to complete by hand.",
    };
  }
  if (status === "active") {
    return {
      tone: "ready",
      label: "Ready",
      note: "Crawlable, and ownership is confirmed.",
    };
  }
  return {
    tone: statusTone(status),
    label: statusLabel(status),
    note: "Website configured.",
  };
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
