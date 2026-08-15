import { statusLabel } from "../status-language";

export type BadgeKind =
  | "ready"
  | "blocked"
  | "setup"
  | "degraded"
  | "missing"
  | "partial"
  | "connected"
  | "neutral";

const STATUS_TO_BADGE: Record<string, BadgeKind> = {
  ready: "ready",
  connected: "connected",
  active: "ready",
  confirmed: "ready",
  approved: "ready",
  published: "ready",
  responded: "ready",
  verified: "ready",
  completed: "ready",
  converted: "ready",
  accepted: "ready",
  effective: "ready",
  ok: "ready",
  blocked: "blocked",
  forbidden: "blocked",
  suspended: "blocked",
  conflicted: "blocked",
  disconnected: "blocked",
  failed: "blocked",
  publication_failed: "blocked",
  checks_failed: "blocked",
  reconciliation_required: "blocked",
  reconnect_required: "blocked",
  dead_letter: "blocked",
  revoked: "blocked",
  rate_limited: "blocked",
  escalated: "blocked",
  restricted: "blocked",
  rejected: "blocked",
  lost: "blocked",
  expired: "blocked",
  setup: "setup",
  not_entitled: "setup",
  pending: "setup",
  identified: "setup",
  validated: "setup",
  recommended: "setup",
  awaiting_approval: "setup",
  approved_for_publish: "setup",
  publishing: "setup",
  checks_running: "setup",
  deployment_pending: "setup",
  branch_created: "setup",
  pull_request_created: "setup",
  editorial_approved: "setup",
  client_approved: "setup",
  scheduled: "setup",
  unassigned: "setup",
  unverified: "setup",
  unmapped: "setup",
  suggested: "setup",
  degraded: "degraded",
  partial: "partial",
  missing: "missing",
  not_found: "missing",
  archived: "neutral",
  cancelled: "neutral",
  draft: "neutral",
  new: "neutral",
  routine: "neutral",
};

export function badgeKindFor(status: string): BadgeKind {
  const normalized = status.toLowerCase().replace(/[-\s]/g, "_");
  return STATUS_TO_BADGE[normalized] ?? "neutral";
}

export function badgeLabel(status: string): string {
  return statusLabel(status);
}

export function statusBadge(
  status: string,
  label?: string,
  kindOverride?: BadgeKind,
): HTMLSpanElement {
  const kind = kindOverride ?? badgeKindFor(status);
  const badge = document.createElement("span");
  const tone =
    kind === "ready" || kind === "connected"
      ? "success"
      : kind === "blocked"
        ? "danger"
        : kind === "setup" || kind === "degraded" || kind === "partial"
          ? "warning"
          : kind === "missing"
            ? "info"
            : "neutral";
  badge.className = `ui-badge ui-badge--${tone}`;
  const dot = document.createElement("span");
  dot.setAttribute("aria-hidden", "true");
  dot.className = "ui-badge__dot";
  badge.append(dot, document.createTextNode(label ?? badgeLabel(status)));
  return badge;
}
