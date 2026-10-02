import type { ClientRow, MetricValue } from "../server/command-center";
export type Availability = MetricValue["availability"];
export const DISPLAY_TIME_ZONE = "America/Los_Angeles";
/** Missing data is never a number. Each state has one label and one explanation. */
export const availabilityText: Record<
  Availability,
  { label: string; note: string }
> = {
  available: { label: "", note: "" },
  no_data: { label: "No data", note: "Connected, nothing reported yet" },
  not_connected: { label: "Not connected", note: "Connect the source" },
  not_tracked: { label: "Not tracked", note: "Not collected yet" },
  not_permitted: { label: "No access", note: "Not available to your role" },
};
export const fmt = (n: number) => Math.round(n).toLocaleString("en-US");
export function signed(delta: number | null, digits = 1): string | null {
  if (delta === null) return null;
  const value = Number(delta.toFixed(digits));
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value)}%`;
}
export interface Shown {
  state: Availability;
  /** The number when there is one; otherwise the state's label. */
  text: string;
  note: string;
  delta: number | null;
}
export function show(metric: MetricValue): Shown {
  if (metric.availability === "available" && metric.current !== null)
    return {
      state: "available",
      text: fmt(metric.current),
      note: "",
      delta: metric.percent_delta,
    };
  const state =
    metric.availability === "available" ? "no_data" : metric.availability;
  return {
    state,
    text: availabilityText[state].label,
    note: availabilityText[state].note,
    delta: null,
  };
}
const workflowText: Record<string, { noun: string; done: string }> = {
  "gbp.publish_post": {
    noun: "Google post publishing",
    done: "Published a Google post",
  },
  "gbp.generate_post": {
    noun: "Google post drafting",
    done: "Drafted a Google post",
  },
  "gbp.sync": {
    noun: "Google profile sync",
    done: "Synced the Google profile",
  },
  "reviews.publish_response": {
    noun: "Review response publishing",
    done: "Published a review response",
  },
  "reviews.ingest": {
    noun: "Review sync",
    done: "Synced Google reviews",
  },
  "content.publish": {
    noun: "Content publishing",
    done: "Published website content",
  },
  "content.draft_revision": {
    noun: "Content drafting",
    done: "Drafted a content revision",
  },
  "seo.apply_site_change": {
    noun: "Website change",
    done: "Applied an approved website change",
  },
  "seo.crawl_or_analysis": {
    noun: "Site analysis",
    done: "Completed a site analysis",
  },
  "seo.analyze": { noun: "Site analysis", done: "Completed a site analysis" },
  "seo.sync_search_console": {
    noun: "Search Console sync",
    done: "Synced Search Console",
  },
  "insights.sync_analytics": {
    noun: "Analytics sync",
    done: "Synced Analytics",
  },
  "leads.send_communication": {
    noun: "Lead communication",
    done: "Sent a lead communication",
  },
};
function humanize(key: string): string {
  const text = key.replaceAll(/[._]+/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
export const workflowNoun = (key: string) =>
  workflowText[key]?.noun ?? humanize(key);
export const workflowDone = (key: string) =>
  workflowText[key]?.done ?? humanize(key) + " completed";
export type AttentionArea = "integrations" | "automations";
interface AttentionCopy {
  title: (workflow: string) => string;
  impact: string;
  next: string;
  area: AttentionArea;
}
export const attentionCopy: Record<string, AttentionCopy> = {
  GOOGLE_RECONNECT_REQUIRED: {
    title: () => "Google Business Profile needs to be reconnected",
    impact:
      "Profile data, review sync and posting are paused until the Google account is authorized again.",
    next: "Reconnect the Google account, then confirm the next sync completes.",
    area: "integrations",
  },
  WORKFLOW_FAILED: {
    title: (workflow) => `${workflow} failed`,
    impact: "A workflow stopped before completing its work.",
    next: "Inspect the latest run and retry once the cause is resolved.",
    area: "automations",
  },
  WORKFLOW_ESCALATED: {
    title: (workflow) => `${workflow} needs a person`,
    impact: "A workflow escalated and is waiting for a decision.",
    next: "Review the escalation and decide how the work should continue.",
    area: "automations",
  },
  WORKFLOW_RETRY_SCHEDULED: {
    title: (workflow) => `${workflow} is retrying`,
    impact: "A workflow hit a problem and is scheduled to try again.",
    next: "No action needed unless the retry fails.",
    area: "automations",
  },
};
const fallbackAttention: AttentionCopy = {
  title: () => "Attention needed",
  impact: "This client has an item that needs a person to look at it.",
  next: "Open the client workspace and review the source.",
  area: "automations",
};
export interface AttentionLike {
  code: string;
  severity: "critical" | "high" | "medium";
  reference: string | null;
  occurred_at: string | null;
}
export function attentionView(item: AttentionLike) {
  const copy = attentionCopy[item.code] ?? fallbackAttention;
  const workflow = item.reference?.split(":", 1)[0] ?? "";
  return {
    title: copy.title(workflow ? workflowNoun(workflow) : "Workflow"),
    impact: copy.impact,
    next: copy.next,
    area: copy.area,
    severity: item.severity,
    severityLabel: { critical: "Critical", high: "High", medium: "Medium" }[
      item.severity
    ],
  };
}
export const healthLabel: Record<ClientRow["health"], string> = {
  healthy: "Healthy",
  needs_attention: "Needs attention",
  not_configured: "Not configured",
};
const reasonText: Record<string, string> = {
  GOOGLE_RECONNECT_REQUIRED: "GBP disconnected",
  GOOGLE_NOT_CONNECTED: "Google not connected",
  SEARCH_CONSOLE_NOT_CONNECTED: "Search Console not connected",
  GA4_NOT_CONNECTED: "Analytics not connected",
  WORKFLOW_ATTENTION: "Automation needs attention",
};
export function healthSub(row: ClientRow): string {
  if (!row.health_reasons.length) return "GBP · Web · Data healthy";
  return reasonText[row.health_reasons[0]] ?? "Needs attention";
}
export const systemLabel = {
  google: "Google Business Profile",
  analytics: "Analytics",
  search_console: "Search Console",
  automations: "Automations",
} as const;
export const systemStatusText = {
  healthy: "Healthy",
  needs_attention: "Needs attention",
  error: "Error",
  not_connected: "Not connected",
  not_permitted: "No access",
} as const;
function zoned(date: Date) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
const dayNumber = (date: Date) => Date.parse(zoned(date)) / 86400000;
/** "Today", "Tomorrow", "Yesterday", or "Oct 4" in the display time zone. */
export function when(iso: string | null, now: Date): string {
  if (!iso) return "";
  const at = new Date(iso);
  const diff = dayNumber(at) - dayNumber(now);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  if (diff === -1) return "Yesterday";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: DISPLAY_TIME_ZONE,
    month: "short",
    day: "numeric",
  }).format(at);
}
export const longDate = (now: Date) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone: DISPLAY_TIME_ZONE,
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(now);
export const initials = (name: string) =>
  name
    .split(/\s+/)
    .map((word) => word[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
export function opportunityTitle(item: {
  opportunity_type: string;
  query: string | null;
  page: string | null;
}): string {
  const type = humanize(item.opportunity_type);
  const target = item.query ?? item.page;
  return target ? `${type}: ${target}` : type;
}
export const priorityText = (score: number | null) =>
  score === null ? "Priority unavailable" : `Priority ${Math.round(score)}`;
export const AREAS = {
  opportunities: "Opportunities",
  reports: "Reports",
  automations: "Automations",
  integrations: "Integrations",
  administration: "Administration",
  attention: "Requires attention",
  activity: "Activity",
  settings: "Settings",
} as const;
export type PortfolioArea = keyof typeof AREAS;
