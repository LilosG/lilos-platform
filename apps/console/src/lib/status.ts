export type Tone = "error" | "warn" | "neutral" | "";
export function statusTone(text: string): Tone {
  return /Error|Failed|Disconnected|Critical|High|Tracking/.test(text)
    ? "error"
    : /attention|review|issue|Missing|Medium|Declining/.test(text)
      ? "warn"
      : /Upcoming|configured|Stable|New|connected|access|tracked/.test(text)
        ? "neutral"
        : "";
}
/** A chip is a typed state's label and tone; its text never comes from an API string. */
export interface Chip {
  label: string;
  tone: Tone;
}
export type PostState =
  | "draft"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "publishing"
  | "published"
  | "not_published"
  | "discarded"
  | "needs_attention";
export const postChips: Record<PostState, Chip> = {
  draft: { label: "Draft", tone: "neutral" },
  awaiting_approval: { label: "Awaiting approval", tone: "warn" },
  approved: { label: "Approved", tone: "" },
  rejected: { label: "Rejected", tone: "error" },
  publishing: { label: "Publishing", tone: "neutral" },
  published: { label: "Published", tone: "" },
  not_published: { label: "Not published", tone: "warn" },
  discarded: { label: "Discarded", tone: "neutral" },
  needs_attention: { label: "Needs attention", tone: "error" },
};
const publicationState: Record<string, PostState> = {
  verified: "published",
  not_published: "not_published",
  discarded: "discarded",
  reserved: "publishing",
  scheduled: "publishing",
  dispatched: "publishing",
  failed: "needs_attention",
  reconciliation_required: "needs_attention",
  cancelled: "not_published",
  expired: "not_published",
};
const revisionState: Record<string, PostState> = {
  awaiting_approval: "awaiting_approval",
  approved: "approved",
  rejected: "rejected",
};
/** A post's state: what happened to its publication wins over its revision's approval. */
export function postState(
  revision: string,
  publication: string | null,
): PostState {
  if (publication) return publicationState[publication] ?? "needs_attention";
  return revisionState[revision] ?? "draft";
}
const approvalChips: Record<string, Chip> = {
  awaiting_approval: postChips.awaiting_approval,
  approved: postChips.approved,
  rejected: postChips.rejected,
  publishing: postChips.publishing,
  published: postChips.published,
  failed: postChips.needs_attention,
};
/** Photos, special hours and profile changes share one approval vocabulary. */
export const approvalChip = (status: string): Chip =>
  approvalChips[status] ?? postChips.draft;
export type HoursState =
  "awaiting_approval" | "rejected" | "publishing" | "live" | "needs_attention";
export const hoursChips: Record<HoursState, Chip> = {
  awaiting_approval: postChips.awaiting_approval,
  rejected: postChips.rejected,
  publishing: postChips.publishing,
  live: { label: "Live on Google", tone: "" },
  needs_attention: postChips.needs_attention,
};
const hoursStates: Record<string, HoursState> = {
  awaiting_approval: "awaiting_approval",
  rejected: "rejected",
  // Approved dates are queued to go to Google, so they read as publishing until confirmed.
  approved: "publishing",
  publishing: "publishing",
  published: "live",
  failed: "needs_attention",
  reconciliation_required: "needs_attention",
};
/** A special-hours date's state. A status this app does not know is shown as needing attention. */
export const hoursState = (status: string): HoursState =>
  hoursStates[status] ?? "needs_attention";
export const connectionChips = {
  connected: { label: "Google connected", tone: "" },
  degraded: { label: "Google needs attention", tone: "warn" },
  reconnect_required: { label: "Reconnect Google", tone: "error" },
  pending: { label: "Google connecting", tone: "neutral" },
  not_connected: { label: "Google not connected", tone: "neutral" },
} as const satisfies Record<string, Chip>;
export type ConnectionState = keyof typeof connectionChips;
export const connectionState = (status: string | null): ConnectionState =>
  status && status in connectionChips
    ? (status as ConnectionState)
    : "not_connected";
export const syncChips = {
  completed: { label: "Completed", tone: "" },
  succeeded: { label: "Completed", tone: "" },
  running: { label: "Running", tone: "neutral" },
  queued: { label: "Queued", tone: "neutral" },
  retry_scheduled: { label: "Retrying", tone: "warn" },
  partial: { label: "Partly synced", tone: "warn" },
  failed: { label: "Failed", tone: "error" },
  escalated: { label: "Needs attention", tone: "error" },
} as const satisfies Record<string, Chip>;
export const syncChip = (status: string): Chip =>
  (syncChips as Record<string, Chip>)[status] ?? {
    label: "Unknown",
    tone: "neutral",
  };

/** A review's state for the person reading it: what happened to the reply wins over the review. */
export type ReviewState =
  | "needs_response"
  | "draft"
  | "awaiting_approval"
  | "approved"
  | "publishing"
  | "published"
  | "needs_attention"
  | "escalated"
  | "closed";
export const reviewChips: Record<ReviewState, Chip> = {
  needs_response: { label: "Needs response", tone: "warn" },
  draft: { label: "Draft", tone: "neutral" },
  awaiting_approval: { label: "Awaiting approval", tone: "warn" },
  approved: { label: "Approved", tone: "" },
  publishing: { label: "Publishing", tone: "neutral" },
  published: { label: "Published", tone: "" },
  needs_attention: { label: "Needs attention", tone: "error" },
  escalated: { label: "Escalated", tone: "error" },
  closed: { label: "Closed", tone: "neutral" },
};
const responseState: Record<string, ReviewState> = {
  draft: "draft",
  generated: "draft",
  awaiting_approval: "awaiting_approval",
  approved: "approved",
  publishing: "publishing",
  published: "published",
  failed: "needs_attention",
  reconciliation_required: "needs_attention",
};
const reviewState: Record<string, ReviewState> = {
  escalated: "escalated",
  publication_failed: "needs_attention",
  responded: "published",
  closed: "closed",
  archived: "closed",
  removed: "closed",
  disputed: "closed",
};
export function reviewStateOf(
  status: string,
  response: string | null,
): ReviewState {
  const reply = response ? responseState[response] : undefined;
  if (status === "escalated") return "escalated";
  if (reply && reply !== "needs_attention") return reply;
  return reviewState[status] ?? reply ?? "needs_response";
}
export const reviewChip = (status: string, response: string | null): Chip =>
  reviewChips[reviewStateOf(status, response)];

/** An automation's state (and its latest run's outcome) as a chip; the label is ours, never the API's. */
export const automationChips = {
  needs_attention: { label: "Needs attention", tone: "error" },
  running: { label: "Running", tone: "neutral" },
  healthy: { label: "Healthy", tone: "" },
  paused: { label: "Paused", tone: "neutral" },
  not_run_yet: { label: "Not run yet", tone: "neutral" },
} as const satisfies Record<string, Chip>;
export const outcomeChips = {
  succeeded: { label: "Completed", tone: "" },
  partial: { label: "Partly completed", tone: "warn" },
  failed: { label: "Failed", tone: "error" },
  will_retry: { label: "Will retry", tone: "neutral" },
  needs_decision: { label: "Needs a decision", tone: "error" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  expired: { label: "Expired", tone: "warn" },
  in_progress: { label: "Running", tone: "neutral" },
} as const satisfies Record<string, Chip>;

/** Where a client's website publishing stands; the label is ours, never the API's. */
export const publishingChips = {
  linked: { label: "Ready to publish", tone: "" },
  not_linked: { label: "Choose a repository", tone: "warn" },
  github_not_connected: { label: "GitHub not connected", tone: "neutral" },
  format_unverified: { label: "Blog format not checked yet", tone: "warn" },
} as const satisfies Record<string, Chip>;
export type PublishingState = keyof typeof publishingChips;
export const unverifiedFormatChip: Chip = publishingChips.format_unverified;
export const githubConnectionChips = {
  connected: { label: "GitHub connected", tone: "" },
  not_connected: { label: "GitHub not connected", tone: "neutral" },
  reconnect: { label: "Reconnect GitHub", tone: "error" },
} as const satisfies Record<string, Chip>;
/** Data from a source, by how recently it was refreshed. */
export const freshnessChips = {
  fresh: { label: "Up to date", tone: "" },
  current: { label: "Up to date", tone: "" },
  stale: { label: "Out of date", tone: "warn" },
  never: { label: "Never synced", tone: "neutral" },
  never_synced: { label: "Never synced", tone: "neutral" },
} as const satisfies Record<string, Chip>;
export const freshnessChip = (status: string): Chip =>
  (freshnessChips as Record<string, Chip>)[status] ?? {
    label: "Not synced yet",
    tone: "neutral",
  };
/** A Google resource or property by whether it is matched to this client. */
export const matchChip = (status: string | null): Chip =>
  status === "mapped" || status === "confirmed"
    ? { label: "Matched", tone: "" }
    : status === "stale" || status === "disconnected"
      ? { label: "Needs attention", tone: "warn" }
      : { label: "Not matched yet", tone: "neutral" };
