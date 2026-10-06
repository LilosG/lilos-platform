import type {
  OpportunityDetail,
  OpportunityKind,
  OpportunityView,
} from "../adapters/opportunities";
import { dateText, fmt, humanize, when } from "./present";
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
/** A band as a chip: "High priority", never the score behind it. */
export const bandChip = (band?: OpportunityView["priority_band"]): string =>
  band ? `${bandLabel[band]} priority` : "Priority unavailable";
export const SITE_CHANGES_NOT_CONFIGURED =
  "Site changes not configured for this client";
const nextActionText: Record<OpportunityView["next_action"], string> = {
  request_recommendation: "Ask Hermes for a recommendation",
  review_recommendation: "Review and approve the proposed change",
  monitor_publication: "Follow the approved change to the live site",
  measure_impact: "Measure impact",
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
export const fieldLabel: Record<string, string> = {
  seo_title: "SEO title",
  meta_description: "Meta description",
  h1: "H1 heading",
  body_section: "Body section",
  schema: "Structured data",
  internal_link: "Internal link",
};
export const labelField = (field: string) =>
  fieldLabel[field] ?? humanize(field);
/** Why an opportunity matters, by typed code. No code, no sentence. */
const importanceText: Record<
  NonNullable<OpportunityView["importance_reason"]>,
  string
> = {
  KEY_EVENTS_INFERRED:
    "Visitors from organic search complete key actions on this page, so it likely matters to the business. This is inferred from key events, not attributed revenue.",
};
export const whyItMatters = (o: OpportunityView): string | null =>
  o.importance_reason ? importanceText[o.importance_reason] : null;
export const statusLabel = (status: string) => humanize(status);
/** The opportunity's status for a badge: a verified change reads "Live · verified <date>". */
export const lifecycleLabel = (o: OpportunityView) =>
  o.lifecycle === "live" && o.verified_at
    ? `Live \u00b7 verified ${dateText(o.verified_at)}`
    : statusLabel(o.status);
/** What each detector or source type is called, once, for titles and the evidence line. */
const typeLabel: Record<string, string> = {
  gsc_low_ctr: "Low click-through",
  gsc_striking_distance: "Close to page one",
  gsc_query_demand: "Search demand",
  gsc_unmapped_demand: "Search demand without a page",
  missing_meta_description: "Missing meta description",
  missing_title: "Missing page title",
  missing_h1: "Missing H1 heading",
  non_200_status: "Page returns an error",
  seo: "Content opportunity",
  growth_plan: "Growth plan",
};
const pageSpeed =
  /^pagespeed_(?:performance|seo|accessibility|best_practices)_(mobile|desktop)$/;
export function sourceTypeLabel(type: string): string {
  const speed = pageSpeed.exec(type);
  if (speed) return `${humanize(speed[1])} page speed`;
  return typeLabel[type] ?? humanize(type);
}
// Titles are built from typed fields. A key, id or address never reaches a title.
const unsafe =
  /[0-9a-f]{8}-[0-9a-f]{4}-|seo-opportunity:|content-brief:|https?:/i;
const clean = (value: string | null) =>
  value && !unsafe.test(value) ? value : null;
/** The site root reads as "Homepage"; every other path stays as it is. */
export const pageLabel = (path: string) => (path === "/" ? "Homepage" : path);
const quoted = (query: string) => `\u201c${query}\u201d`;
const queryTitles: Record<string, string> = {
  gsc_low_ctr: "Low click-through",
  gsc_striking_distance: "Close to page one",
  gsc_query_demand: "Search demand",
  gsc_unmapped_demand: "No page for",
  seo: "Content for",
};
export interface FindingSubject {
  /** The detector or source type, such as "gsc_low_ctr". */
  source_type: string;
  kind: OpportunityKind;
  query: string | null;
  /** A path or a full address; an address is shown as its path. */
  path: string | null;
  headline?: string | null;
}
/** A landing page by its path; the site's own address adds nothing to a client's list. */
export function pagePath(address: string): string {
  try {
    const url = new URL(address);
    return pageLabel(url.pathname + url.search);
  } catch {
    return pageLabel(address);
  }
}
/** One title for a finding wherever it is listed: the Opportunities screen and a client's Overview. */
export function findingTitle(o: FindingSubject): string {
  if (o.headline && !unsafe.test(o.headline)) return o.headline;
  const query = clean(o.query);
  const path = o.path ? clean(pagePath(o.path)) : null;
  const lead = queryTitles[o.source_type];
  if (lead && query) return `${lead}: ${quoted(query)}`;
  const base =
    o.kind === "content"
      ? "Content opportunity"
      : sourceTypeLabel(o.source_type);
  if (path) return `${base} \u00b7 ${path}`;
  return query ? `${base}: ${quoted(query)}` : base;
}
export const title = (o: OpportunityView): string =>
  findingTitle({
    source_type: o.source_type,
    kind: o.kind,
    query: o.subject.query,
    path: o.subject.path,
    headline: o.headline,
  });
/** One finding is (organization, type, query or page); the first listed, the best ranked, stands for it. */
export function dedupeFindings<T>(
  items: T[],
  key: (item: T) => [string, string, string | null],
): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const [organization, type, target] = key(item);
    const id = `${organization}\u0000${type}\u0000${target ?? ""}`;
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
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
      : sourceTypeLabel(summary.signal);
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
  next: string;
  siteChangeNote: string | null;
}
export function rowView(
  o: OpportunityView,
  now: Date,
  from: "portfolio" | "client",
): OpportunityRowView {
  const slug = o.client?.slug ?? "";
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
    sub: lifecycleLabel(o),
    evidence: evidenceHeadline(o),
    evidenceSub: evidenceSub(o, now),
    next: nextAction(o),
    siteChangeNote:
      o.site_change_reason === "SITE_CHANGES_NOT_CONFIGURED"
        ? SITE_CHANGES_NOT_CONFIGURED
        : null,
  };
}
/** One row of a compact opportunity list, shared by the client Overview and Local Search. */
export interface CompactOpportunity {
  id: string;
  title: string;
  clientName: string;
  clientHref: string;
  href: string;
  classification: string;
  /** The priority band as a chip label. */
  priority: string;
}
/** A client's open findings for a compact list: one per finding, titled and banded as on the
 * Opportunities screen. */
export function compactRows(
  items: OpportunityView[],
  now: Date,
): CompactOpportunity[] {
  return dedupeFindings(items, (o) => [
    o.organization_id,
    o.source_type,
    o.subject.query ?? o.subject.path,
  ]).map((o) => {
    const row = rowView(o, now, "client");
    return {
      id: row.id,
      title: row.title,
      clientName: row.clientName,
      clientHref: row.clientHref,
      href: row.href,
      classification: o.classification,
      priority: bandChip(o.priority_band),
    };
  });
}
export const filterOptions = {
  type: [
    ["", "All types"],
    ["seo", kindLabel.seo],
    ["content", kindLabel.content],
    ["growth", kindLabel.growth],
  ],
  state: [
    ["", "Open"],
    ["done", "Done"],
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
  if (typeof o.evidence.issue === "string")
    return sourceTypeLabel(o.evidence.issue);
  if (typeof o.evidence.query === "string")
    return `Search query: ${o.evidence.query}`;
  return o.evidence_summary
    ? sourceTypeLabel(o.evidence_summary.signal)
    : "Discovery explanation unavailable.";
}
export const historyLabel = (event: {
  event_type: string;
  action: string;
  result: string;
}) => `${humanize(event.action)} · ${humanize(event.result)}`;
export const revisionLine = (r: {
  revision_number: number;
  status: string;
  created_at: string;
}) =>
  `Revision ${r.revision_number} \u00b7 ${statusLabel(r.status)} \u00b7 ${dateText(r.created_at)}`;
/** The implementation state, read from the publication's verified state, not the task row. */
export const implementationLabel = (
  taskStatus: string,
  liveState: string | null,
) => (liveState === "verified" ? "Verified live" : humanize(taskStatus));
