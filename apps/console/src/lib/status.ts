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
