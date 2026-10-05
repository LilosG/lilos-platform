import type {
  OpportunityDetail,
  OpportunityKind,
  OpportunityView,
} from "../adapters/opportunities";
import { fmt, humanize, when } from "./present";
/** Every label for an opportunity comes from a typed code here, never from API prose. */
export const kindLabel: Record<OpportunityKind, string> = {
  seo: "Website & search",
  content: "Content",
  growth: "Growth plan",
};
export const bandLabel = {
  high: "High",
  medium: "Medium",
  low: "Low",
} as const;
export const SITE_CHANGES_NOT_CONFIGURED =
  "Site changes not configured for this client";
const nextActionText: Record<OpportunityView["next_action"], string> = {
  request_recommendation: "Ask Hermes for a recommendation",
  review_recommendation: "Review and approve the proposed change",
  monitor_publication: "Follow the approved change to the live site",
  review_opportunity: "Decide whether to act on this opportunity",
  review_growth_plan: "Review and approve the growth plan",
  monitor_execution: "Follow the plan's actions to completion",
  none: "No action needed",
};
const metricLabel: Record<string, string> = {
  clicks: "Clicks",
  impressions: "Impressions",
  ctr: "CTR",
  position: "Average position",
  http_status: "HTTP status",
};
const sourceLabel: Record<string, string> = {
  crawl: "Site crawl",
  gsc: "Search Console",
  search_console: "Search Console",
};
export const nextAction = (o: OpportunityView) => nextActionText[o.next_action];
export const statusLabel = (status: string) => humanize(status);
export function title(o: OpportunityView): string {
  if (o.headline) return o.headline;
  const query = o.evidence.query;
  const type = humanize(o.source_type);
  return typeof query === "string" ? `${type}: ${query}` : type;
}
export function metricText(key: string, value: number): [string, string] {
  const label = metricLabel[key] ?? humanize(key);
  if (key === "ctr")
    return [`${(value <= 1 ? value * 100 : value).toFixed(1)}%`, label];
  if (key === "position") return [value.toFixed(1), label];
  return [key === "http_status" ? String(value) : fmt(value), label];
}
export const sourceText = (source: string | null) =>
  source ? (sourceLabel[source] ?? humanize(source)) : "Source unavailable";
/** One line for the list: what was found, with its leading number when there is one. */
export function evidenceHeadline(o: OpportunityView): string {
  const summary = o.evidence_summary;
  if (!summary) return "Evidence unavailable";
  const lead = summary.metrics[0];
  const found =
    o.kind === "growth"
      ? `${summary.source_count ?? 0} supporting sources`
      : humanize(summary.signal);
  if (!lead || o.kind === "growth") return found;
  const [value, label] = metricText(lead.key, lead.value);
  return `${found} · ${value} ${label.toLowerCase()}`;
}
export function evidenceSub(o: OpportunityView, now: Date): string {
  const summary = o.evidence_summary;
  return `${sourceText(summary?.source ?? null)} · Observed ${when(o.observed_at, now)}`;
}
export interface OpportunityRowView {
  id: string;
  title: string;
  href: string;
  clientName: string;
  clientHref: string;
  type: string;
  kind: OpportunityKind;
  classification: string;
  band: string;
  bandKey: string;
  sub: string;
  evidence: string;
  evidenceSub: string;
  why: string | null;
  next: string;
  siteChangeNote: string | null;
}
export function rowView(
  o: OpportunityView,
  now: Date,
  from: "portfolio" | "client",
): OpportunityRowView {
  const slug = o.client?.slug ?? "";
  const reason = o.score_explanation.reason;
  return {
    id: o.source_id,
    title: title(o),
    href: `/clients/${slug}/opportunities/${o.source_id}/${from === "portfolio" ? "?from=portfolio" : ""}`,
    clientName: o.client?.name ?? "",
    clientHref: `/clients/${slug}/`,
    type: kindLabel[o.kind],
    kind: o.kind,
    classification: o.classification,
    band: o.priority_band ? bandLabel[o.priority_band] : "Priority unavailable",
    bandKey: o.priority_band ?? "unavailable",
    sub: statusLabel(o.status),
    evidence: evidenceHeadline(o),
    evidenceSub: evidenceSub(o, now),
    why: typeof reason === "string" ? reason : null,
    next: nextAction(o),
    siteChangeNote:
      o.site_change_reason === "SITE_CHANGES_NOT_CONFIGURED"
        ? SITE_CHANGES_NOT_CONFIGURED
        : null,
  };
}
export const filterOptions = {
  type: [
    ["", "All types"],
    ["seo", kindLabel.seo],
    ["content", kindLabel.content],
    ["growth", kindLabel.growth],
  ],
  priority: [
    ["", "All priorities"],
    ["high", "High"],
    ["medium", "Medium"],
    ["low", "Low"],
  ],
} as const;
/** The discovery sentence for the detail, from the signal code and numbers. */
export function discovered(d: OpportunityDetail): string {
  const o = d.data;
  if (d.growth) return d.growth.rationale;
  if (typeof o.evidence.issue === "string") return humanize(o.evidence.issue);
  if (typeof o.evidence.query === "string")
    return `Search query: ${o.evidence.query}`;
  return o.evidence_summary
    ? humanize(o.evidence_summary.signal)
    : "Discovery explanation unavailable.";
}
export function whyItMatters(o: OpportunityView): string {
  const s = o.score_explanation;
  return typeof s.reason === "string"
    ? s.reason
    : typeof s.business_evidence_limitation === "string"
      ? s.business_evidence_limitation
      : "Business importance evidence is unavailable.";
}
export const historyLabel = (event: {
  event_type: string;
  action: string;
  result: string;
}) => `${humanize(event.action)} · ${humanize(event.result)}`;
