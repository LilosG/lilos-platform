import type { InsightsSummary } from "./workspace";
import { SEO_ACTIONABLE_OPPORTUNITY_STATUSES } from "./seo";

export type OperatingMetric = {
  key: string;
  label: string;
  value: number | null;
  meta: string;
  href: string;
};

export type WorkItem = {
  key: string;
  label: string;
  detail: string;
  count: number;
  severity: "urgent" | "work" | "result";
  href: string;
};

const REVIEW_NEEDS_RESPONSE = [
  "new",
  "classified",
  "triaged",
  "drafting",
  "awaiting_approval",
  "approved",
  "publication_failed",
  "escalated",
  "disputed",
] as const;

const LEAD_CLOSED = [
  "converted",
  "disqualified",
  "lost",
  "spam",
  "duplicate",
  "cancelled",
  "archived",
] as const;

export function totalStatuses(statuses: Record<string, number>): number {
  return Object.values(statuses).reduce((total, value) => total + value, 0);
}

export function hasRecordedActivity(summary: InsightsSummary | null): boolean {
  if (!summary) return false;
  return (
    totalStatuses(summary.workflow_runs) > 0 ||
    summary.gbp.profile_snapshots > 0 ||
    totalStatuses(summary.gbp.publications) > 0 ||
    totalStatuses(summary.reviews) > 0 ||
    totalStatuses(summary.content_publications) > 0 ||
    totalStatuses(summary.seo.crawl_runs) > 0 ||
    totalStatuses(summary.seo.opportunities) > 0 ||
    totalStatuses(summary.leads) > 0 ||
    Object.keys(summary.ga4?.metrics ?? {}).length > 0
  );
}

function count(
  statuses: Record<string, number>,
  keys: readonly string[],
): number {
  return keys.reduce((total, key) => total + (statuses[key] ?? 0), 0);
}

export function dashboardMetrics(
  summary: InsightsSummary | null,
): OperatingMetric[] {
  if (!summary) return [];

  const reviews = summary.reviews ?? {};
  const leads = summary.leads ?? {};
  const leadTotal = totalStatuses(leads);
  const activeLeads = Math.max(0, leadTotal - count(leads, LEAD_CLOSED));
  const publications = summary.content_publications ?? {};
  const publishedContent = count(publications, ["verified", "deployed"]);

  const metrics: OperatingMetric[] = [];
  if (
    summary.gbp &&
    (summary.gbp.profile_snapshots > 0 ||
      Object.keys(summary.gbp.publications).length > 0)
  ) {
    metrics.push({
      key: "gbp",
      label: "Managed locations",
      value: summary.gbp.locations,
      meta: "Google Business Profile",
      href: "/gbp",
    });
  }
  if (Object.keys(reviews).length > 0) {
    metrics.push({
      key: "reviews",
      label: "Reviews",
      value: totalStatuses(reviews),
      meta: "Recorded across locations",
      href: "/reviews",
    });
    metrics.push({
      key: "review-work",
      label: "Need a response",
      value: count(reviews, REVIEW_NEEDS_RESPONSE),
      meta: "Review inbox",
      href: "/reviews",
    });
  }
  if (Object.keys(leads).length > 0) {
    metrics.push({
      key: "leads",
      label: "Active leads",
      value: activeLeads,
      meta: "Not in a closed state",
      href: "/leads",
    });
  }
  if (Object.keys(publications).length > 0) {
    metrics.push({
      key: "content",
      label: "Published content",
      value: publishedContent,
      meta: "Provider-verified or deployed",
      href: "/content",
    });
  }
  const opportunities = summary.seo?.opportunities ?? {};
  if (Object.keys(opportunities).length > 0) {
    metrics.push({
      key: "seo",
      label: "Open SEO opportunities",
      value: count(opportunities, SEO_ACTIONABLE_OPPORTUNITY_STATUSES),
      meta: "Prioritized work queue",
      href: "/seo",
    });
  }
  return metrics;
}

export function requiresAttention(summary: InsightsSummary | null): WorkItem[] {
  if (!summary) return [];
  const items: WorkItem[] = [];
  const workflowFailures = count(summary.workflow_runs ?? {}, [
    "failed",
    "escalated",
    "expired",
  ]);
  const reviewFailures = count(summary.reviews ?? {}, [
    "publication_failed",
    "escalated",
    "disputed",
  ]);
  const gbpFailures = count(summary.gbp?.publications ?? {}, [
    "failed",
    "reconciliation_required",
  ]);
  const contentFailures = count(summary.content_publications ?? {}, [
    "failed",
    "checks_failed",
    "reconciliation_required",
  ]);

  if (workflowFailures > 0)
    items.push({
      key: "workflows",
      label: "Workflow failures",
      detail: "Failed or unresolved work needs operator review.",
      count: workflowFailures,
      severity: "urgent",
      href: "/administration",
    });
  if (reviewFailures > 0)
    items.push({
      key: "reviews",
      label: "Review responses",
      detail: "Escalated, disputed, or failed responses need attention.",
      count: reviewFailures,
      severity: "urgent",
      href: "/reviews",
    });
  if (gbpFailures > 0)
    items.push({
      key: "gbp",
      label: "Business Profile changes",
      detail: "Provider writes failed or need reconciliation.",
      count: gbpFailures,
      severity: "urgent",
      href: "/gbp",
    });
  if (contentFailures > 0)
    items.push({
      key: "content",
      label: "Content publishing",
      detail: "Publishing or verification did not complete.",
      count: contentFailures,
      severity: "urgent",
      href: "/content",
    });
  return items;
}

export function todaysWork(summary: InsightsSummary | null): WorkItem[] {
  if (!summary) return [];
  const items: WorkItem[] = [];
  const reviewCount = count(summary.reviews ?? {}, REVIEW_NEEDS_RESPONSE);
  const newLeads = count(summary.leads ?? {}, ["new", "unassigned"]);
  const seoWork = count(
    summary.seo?.opportunities ?? {},
    SEO_ACTIONABLE_OPPORTUNITY_STATUSES,
  );
  const contentWaiting = count(summary.content_publications ?? {}, [
    "reserved",
    "checks_running",
    "deployment_pending",
  ]);

  if (reviewCount > 0)
    items.push({
      key: "review-work",
      label: "Respond to reviews",
      detail: "Reviews are awaiting drafting, approval, or publication.",
      count: reviewCount,
      severity: "work",
      href: "/reviews",
    });
  if (newLeads > 0)
    items.push({
      key: "lead-work",
      label: "Follow up with new leads",
      detail: "New or unassigned leads are waiting in the queue.",
      count: newLeads,
      severity: "work",
      href: "/leads",
    });
  if (contentWaiting > 0)
    items.push({
      key: "content-work",
      label: "Monitor content publishing",
      detail:
        "Publications are reserved, running checks, or awaiting deployment.",
      count: contentWaiting,
      severity: "work",
      href: "/content",
    });
  if (seoWork > 0)
    items.push({
      key: "seo-work",
      label: "Review SEO opportunities",
      detail: "Open opportunities are ready to prioritize.",
      count: seoWork,
      severity: "work",
      href: "/seo",
    });
  return items;
}
