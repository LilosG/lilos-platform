import type {
  AutomationDetailView,
  AutomationItem,
  AutomationReason,
  AutomationSource,
  AutomationStatus,
  RecoveryAction,
  RunOutcome,
  WorkflowTypeCode,
} from "../adapters/automations";
import { STATUSES, WORKFLOW_TYPES } from "../adapters/automations";
import { durationText, frequencyText, runTime } from "./present";
import { automationChips, outcomeChips, type Chip } from "./status";

export const WORKFLOW_NAMES: Record<WorkflowTypeCode, string> = {
  "content.publish": "Content publishing",
  "content.draft_revision": "Content drafts",
  "content.compose": "Content writing",
  "seo.crawl_or_analysis": "Website health check",
  "seo.analyze": "Opportunity analysis",
  "seo.sync_search_console": "Search Console sync",
  "insights.sync_analytics": "Analytics sync",
  "seo.apply_site_change": "Website changes",
  "gbp.generate_post": "Business Profile posts",
  "gbp.publish_change": "Profile changes",
  "gbp.publish_post": "Post publishing",
  "gbp.upload_media": "Photo publishing",
  "gbp.publish_special_hours": "Special hours publishing",
  "reviews.publish_response": "Review reply publishing",
  "leads.send_communication": "Lead follow-up",
  "gbp.sync": "Business Profile sync",
  "gbp.sync_performance": "GBP performance refresh",
  "reviews.ingest": "Review monitoring",
  "agent.gbp": "Profile optimization",
  "agent.seo": "SEO analysis",
  "agent.content": "Content planning",
  "agent.reviews": "Review analysis",
  "agent.leads": "Lead analysis",
  "agent.insights": "Insights analysis",
  "agent.growth": "Growth planning",
};
export const SOURCE_NAMES: Record<AutomationSource, string> = {
  google_business_profile: "Google Business Profile",
  reviews: "Google reviews",
  website: "Website monitoring",
  analytics: "Google Analytics",
  search_console: "Search Console",
  leads: "Leads",
  platform: "LILOs",
};
/** What the last run did, said plainly, and what a person should do about it. */
interface ReasonCopy {
  what: string;
  next: string;
}
const GOOGLE: ReasonCopy = {
  what: "Google would not let LILOs read this profile.",
  next: "Reconnect Google Business Profile in Integrations, then run it again.",
};
const LOCATION: ReasonCopy = {
  what: "This location is not matched to a Business Profile.",
  next: "Check the location match in Integrations.",
};
const SEARCH: ReasonCopy = {
  what: "Search Console did not return its data.",
  next: "Check the Search Console connection in Integrations.",
};
const ANALYTICS: ReasonCopy = {
  what: "Google Analytics did not return all of its data. Earlier data is unchanged.",
  next: "Check the analytics connection in Integrations.",
};
const WEBSITE: ReasonCopy = {
  what: "There is no active website to check.",
  next: "Connect or choose this client's website.",
};
const WAITING: ReasonCopy = {
  what: "A temporary problem interrupted this run.",
  next: "Nothing to do. It will try again on its own.",
};
const INTERNAL: ReasonCopy = {
  what: "The run stopped before it could finish.",
  next: "It will run again on schedule. If it keeps stopping, contact LILOs support.",
};
const POST: ReasonCopy = {
  what: "A post could not be prepared.",
  next: "It will try again on schedule. If it keeps stopping, contact LILOs support.",
};
export const REASON_COPY: Record<AutomationReason, ReasonCopy> = {
  GBP_PERFORMANCE_ACCESS_DENIED: GOOGLE,
  INTEGRATION_RECONNECT_REQUIRED: {
    what: "Google needs to be connected again.",
    next: GOOGLE.next,
  },
  GBP_SCOPE_REQUIRED: {
    what: "Google access is missing a permission this needs.",
    next: GOOGLE.next,
  },
  GBP_INTEGRATION_NOT_FOUND: {
    what: "Google Business Profile is not connected.",
    next: GOOGLE.next,
  },
  NO_CONNECTED_INTEGRATION: {
    what: "Google Business Profile is not connected.",
    next: GOOGLE.next,
  },
  TOKEN_REFRESH_FAILED: {
    what: "Google sign-in expired and could not be renewed.",
    next: GOOGLE.next,
  },
  SECRET_RESOLUTION_FAILED: {
    what: "The saved Google sign-in could not be used.",
    next: GOOGLE.next,
  },
  TOKEN_RESOLUTION_FAILED: WAITING,
  GBP_LOCATION_NOT_FOUND: LOCATION,
  GBP_LOCATION_AMBIGUOUS: {
    what: "More than one Business Profile matches this location.",
    next: LOCATION.next,
  },
  GBP_LOCATION_NO_PLATFORM_LINK: LOCATION,
  LOCATION_ID_INVALID: LOCATION,
  LOCATION_ID_MISSING: LOCATION,
  GBP_PERFORMANCE_REQUEST_REJECTED: {
    what: "Google rejected the request for performance data.",
    next: "It will run again on schedule. If it keeps failing, contact LILOs support.",
  },
  GBP_PERFORMANCE_RATE_LIMITED: {
    what: "Google is limiting requests right now.",
    next: "Nothing to do. It will try again on its own.",
  },
  GBP_PERFORMANCE_PROVIDER_UNAVAILABLE: {
    what: "Google is not responding right now.",
    next: WAITING.next,
  },
  GBP_PERFORMANCE_RESPONSE_INVALID: {
    what: "Google sent data that could not be read.",
    next: WAITING.next,
  },
  GBP_PERFORMANCE_KEYWORDS_UNAVAILABLE: {
    what: "Performance numbers were saved, but search terms were not available yet.",
    next: WAITING.next,
  },
  GBP_PERFORMANCE_SYNC_FAILED: INTERNAL,
  GBP_SYNC_FAILED: INTERNAL,
  REVIEWS_INGEST_FAILED: INTERNAL,
  SEARCH_CONSOLE_SCOPE_REQUIRED: {
    what: "Google access is missing Search Console permission.",
    next: SEARCH.next,
  },
  SEARCH_PROPERTY_NOT_FOUND: {
    what: "The Search Console property is no longer matched to this client.",
    next: SEARCH.next,
  },
  SEARCH_PROPERTY_NOT_CONFIGURED: {
    what: "No Search Console property is set up for this client.",
    next: SEARCH.next,
  },
  SEARCH_PROPERTY_ID_INVALID: SEARCH,
  SEARCH_CONSOLE_SYNC_INCOMPLETE: {
    what: "Search Console did not return every report. Earlier data is unchanged.",
    next: SEARCH.next,
  },
  SEARCH_CONSOLE_SYNC_FAILED: SEARCH,
  ANALYTICS_SCOPE_REQUIRED: {
    what: "Google access is missing Analytics permission.",
    next: ANALYTICS.next,
  },
  ANALYTICS_PROPERTY_NOT_FOUND: {
    what: "The Analytics property is no longer matched to this client.",
    next: ANALYTICS.next,
  },
  ANALYTICS_NOT_CONFIGURED: {
    what: "No Analytics property is set up for this client.",
    next: ANALYTICS.next,
  },
  ANALYTICS_PROPERTY_ID_INVALID: ANALYTICS,
  ANALYTICS_SYNC_INCOMPLETE: ANALYTICS,
  ANALYTICS_SYNC_FAILED: ANALYTICS,
  SEO_ACTIVE_WEBSITE_MISSING: WEBSITE,
  SEO_WEBSITE_NOT_FOUND: WEBSITE,
  SEO_WEBSITE_NOT_ACTIVE: {
    what: "This client's website is not active.",
    next: WEBSITE.next,
  },
  SEO_WEBSITE_SCOPE_MISMATCH: WEBSITE,
  SEO_CRAWL_EMPTY: {
    what: "The website check found no pages to read.",
    next: "It will run again on schedule. If it keeps failing, contact LILOs support.",
  },
  SEO_ANALYSIS_FAILED: INTERNAL,
  SEO_CRAWL_FAILED: {
    what: "The website could not be read.",
    next: "It will run again on schedule. If it keeps failing, check that the website is online.",
  },
  SEO_CRAWL_NOT_TERMINAL: INTERNAL,
  SEO_CRAWL_RUN_NOT_FOUND: INTERNAL,
  MISSING_CRAWL_RUN_ID: INTERNAL,
  INVALID_CRAWL_RUN_ID: INTERNAL,
  GBP_POST_GROUNDING_REQUIRED: {
    what: "There was not enough approved information to write a post.",
    next: "Add approved business facts, then it will try again on schedule.",
  },
  GBP_POST_GENERATION_FAILED: POST,
  GBP_POST_DELIVERY_BINDING_MISSING: POST,
  GBP_REVIEW_SOURCE_INVALID: POST,
  GBP_ORGANIZATION_UNAVAILABLE: POST,
  GBP_POST_REVISION_UNAVAILABLE: POST,
  GBP_WEBSITE_TARGET_UNAVAILABLE: {
    what: "A post could not be linked to a page on the website.",
    next: "It will try again on schedule.",
  },
  GBP_WEBSITE_KNOWLEDGE_UNAVAILABLE: WAITING,
  GBP_DRIVE_MEDIA_NOT_CONFIGURED: {
    what: "No photo folder is set up for posts.",
    next: "Choose a photo folder for this client, then it will try again.",
  },
  GBP_DRIVE_NO_ELIGIBLE_IMAGE: {
    what: "There was no suitable photo for a post.",
    next: "Add photos to the client's folder, then it will try again.",
  },
  GBP_DRIVE_MEDIA_UNAVAILABLE: WAITING,
  GBP_DRIVE_MEDIA_PROXY_UNAVAILABLE: WAITING,
  GBP_DRIVE_UNREACHABLE: WAITING,
  GBP_DRIVE_TEMPORARILY_UNAVAILABLE: WAITING,
  HERMES_SCOPED_SESSION_BUSY: {
    what: "The assistant was busy with other work for this client.",
    next: WAITING.next,
  },
  VERIFICATION_CONTENT_PENDING: {
    what: "Google has not shown the reply yet.",
    next: "Nothing to do. LILOs checks again later.",
  },
  VERIFICATION_REREAD_FAILED: {
    what: "LILOs could not check the reply on Google yet.",
    next: "Nothing to do. LILOs checks again later.",
  },
  WORKFLOW_VERSION_NOT_EXECUTABLE: INTERNAL,
  WORKFLOW_HANDLER_NOT_REGISTERED: INTERNAL,
  WORKFLOW_RUN_MISSING: INTERNAL,
  WORKFLOW_CANCELLED: INTERNAL,
  HANDLER_EXCEPTION: INTERNAL,
  DATABASE_DETERMINISTIC_ERROR: INTERNAL,
  RUN_ESCALATED: {
    what: "The run stopped and needs a person to decide what happens next.",
    next: "Review it, then decide how the work should continue.",
  },
  RUN_WAITING_APPROVAL: {
    what: "The run is waiting for an approval.",
    next: "Approve or reject the proposed change.",
  },
  RUN_PARTIALLY_COMPLETED: {
    what: "Part of the run finished and part did not.",
    next: "Check the run details, then run it again.",
  },
  RUN_EXPIRED: {
    what: "The run took too long and was stopped.",
    next: "It will run again on schedule.",
  },
  UNMAPPED: {
    what: "The last run did not finish.",
    next: "It will run again on schedule. If it keeps failing, contact LILOs support.",
  },
};
export const ACTION_LABELS: Record<RecoveryAction, string> = {
  reconnect_google_business_profile: "Reconnect Google Business Profile",
  check_analytics_connection: "Check analytics connection",
  check_search_console_connection: "Check Search Console connection",
  connect_website: "Connect or choose website",
  check_location_mapping: "Check location match",
};
const actionPath: Record<RecoveryAction, string> = {
  reconnect_google_business_profile: "integrations/",
  check_analytics_connection: "integrations/",
  check_search_console_connection: "integrations/",
  connect_website: "website-content/",
  check_location_mapping: "integrations/",
};
export const actionHref = (action: RecoveryAction, slug: string) =>
  `/clients/${slug}/${actionPath[action]}`;
const DONE: Partial<Record<WorkflowTypeCode, string>> = {
  "gbp.sync_performance": "Profile performance refreshed",
  "gbp.sync": "Business Profile details refreshed",
  "reviews.ingest": "New reviews checked for responses",
  "seo.crawl_or_analysis": "Technical findings refreshed",
  "seo.sync_search_console": "Search performance refreshed",
  "insights.sync_analytics": "Website traffic refreshed",
};
export const doneText = (type: WorkflowTypeCode) =>
  DONE[type] ?? `${WORKFLOW_NAMES[type]} completed`;

export interface Filters {
  view: "overview" | "all";
  status: AutomationStatus | "all";
  client: string;
  type: WorkflowTypeCode | "all";
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** The screen's filters from its query string; anything unknown is refused, not ignored. */
export function parseFilters(params: URLSearchParams): Filters | null {
  const view = params.get("view") ?? "overview";
  const status = params.get("status") ?? "all";
  const client = params.get("organization_id") ?? "all";
  const type = params.get("type") ?? "all";
  if (view !== "overview" && view !== "all") return null;
  if (status !== "all" && !(STATUSES as readonly string[]).includes(status))
    return null;
  if (client !== "all" && !uuid.test(client)) return null;
  if (type !== "all" && !(WORKFLOW_TYPES as readonly string[]).includes(type))
    return null;
  return {
    view,
    status: status as Filters["status"],
    client,
    type: type as Filters["type"],
  };
}
export const filtersActive = (f: Filters) =>
  f.status !== "all" || f.client !== "all" || f.type !== "all";
/** Query string for a list URL; defaults are left out. */
export function filterQuery(f: Partial<Filters>): string {
  const params = new URLSearchParams();
  if (f.view === "all") params.set("view", "all");
  if (f.status && f.status !== "all") params.set("status", f.status);
  if (f.client && f.client !== "all") params.set("organization_id", f.client);
  if (f.type && f.type !== "all") params.set("type", f.type);
  const text = params.toString();
  return text ? `?${text}` : "";
}
export function applyFilters(
  items: AutomationItem[],
  f: Filters,
): AutomationItem[] {
  return items.filter(
    (i) =>
      (f.status === "all" || i.status === f.status) &&
      (f.client === "all" || i.client.id === f.client) &&
      (f.type === "all" || i.workflow_type === f.type),
  );
}
/** Only types that exist for these automations, never a fixed catalog. */
export function typeOptions(items: AutomationItem[]) {
  const present = new Set(items.map((i) => i.workflow_type));
  return WORKFLOW_TYPES.filter((t) => present.has(t))
    .map((value) => ({ value, label: WORKFLOW_NAMES[value] }))
    .sort((a, b) => a.label.localeCompare(b.label));
}
export function clientOptions(items: AutomationItem[]) {
  const seen = new Map(items.map((i) => [i.client.id, i.client.name]));
  return [...seen]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
}
export const STATUS_FILTER_LABELS: Record<AutomationStatus | "all", string> = {
  all: "All statuses",
  needs_attention: automationChips.needs_attention.label,
  running: automationChips.running.label,
  healthy: automationChips.healthy.label,
  paused: automationChips.paused.label,
  not_run_yet: automationChips.not_run_yet.label,
};

/** What the last run did, in words. A run that never happened is said so, not zeroed. */
function outcomeText(item: AutomationItem): string {
  const run = item.latest_run;
  if (!run) return "Not run yet";
  if (item.attention) return REASON_COPY[item.attention.reason].what;
  if (run.reason && run.outcome === "will_retry")
    return REASON_COPY[run.reason].what;
  if (run.outcome === "succeeded") return "Completed successfully";
  if (run.outcome === "in_progress") return "Running now";
  return outcomeChips[run.outcome].label;
}
/**
 * Clients whose schedules cover more than one location. Only those need the location named
 * to tell two otherwise identical rows apart; a single-location client shows nothing extra.
 */
export function multiLocationClients(items: AutomationItem[]): Set<string> {
  const places = new Map<string, Set<string>>();
  for (const i of items)
    if (i.location) {
      const seen = places.get(i.client.id) ?? new Set<string>();
      seen.add(i.location.id);
      places.set(i.client.id, seen);
    }
  return new Set(
    [...places].filter(([, seen]) => seen.size > 1).map(([client]) => client),
  );
}
export interface AutomationRow {
  id: string;
  name: string;
  clientName: string;
  clientSlug: string;
  /** The location's name, only where the client has more than one location with schedules. */
  locationName: string | null;
  source: string;
  status: AutomationStatus;
  statusChip: Chip;
  outcomeChip: Chip | null;
  outcome: string;
  frequency: string;
  last: string;
  next: string;
  action: string;
}
export function rowView(
  item: AutomationItem,
  now: Date,
  multi: ReadonlySet<string> = new Set(),
): AutomationRow {
  const run = item.latest_run;
  return {
    id: item.id,
    name: WORKFLOW_NAMES[item.workflow_type],
    clientName: item.client.name,
    clientSlug: item.client.slug,
    locationName: multi.has(item.client.id)
      ? (item.location?.name ?? null)
      : null,
    source: SOURCE_NAMES[item.source],
    status: item.status,
    statusChip: automationChips[item.status],
    outcomeChip: run ? outcomeChips[run.outcome] : null,
    outcome: outcomeText(item),
    frequency: frequencyText(item.frequency, now),
    last: run
      ? run.finished_at
        ? runTime(run.finished_at, now)
        : "Running now"
      : "Not run yet",
    next:
      item.status === "paused"
        ? "Paused"
        : item.next_run_at
          ? runTime(item.next_run_at, now)
          : "Not scheduled",
    action: item.status === "needs_attention" ? "Investigate" : "View run",
  };
}
export interface OverviewView {
  attention: AutomationRow[];
  upcoming: (AutomationRow & { note: string })[];
  recent: (AutomationRow & { done: string })[];
  health: { label: string; count: number }[];
}
const at = (iso: string | null) => (iso ? Date.parse(iso) : 0);
/** Overview sections for the (already filtered) automations, by the one attention rule. */
export function overviewView(
  items: AutomationItem[],
  now: Date,
  limit: number,
  multi: ReadonlySet<string> = new Set(),
): OverviewView {
  const count = (s: AutomationStatus) =>
    items.filter((i) => i.status === s).length;
  return {
    attention: items
      .filter((i) => i.status === "needs_attention")
      .sort(
        (a, b) =>
          at(b.attention?.occurred_at ?? null) -
          at(a.attention?.occurred_at ?? null),
      )
      .map((i) => rowView(i, now, multi)),
    upcoming: items
      .filter((i) => i.next_run_at !== null && i.status !== "paused")
      .sort((a, b) => at(a.next_run_at) - at(b.next_run_at))
      .slice(0, limit)
      .map((i) => ({
        ...rowView(i, now, multi),
        note:
          i.status === "needs_attention"
            ? "Resolve the cause before this run"
            : SOURCE_NAMES[i.source],
      })),
    recent: items
      .filter((i) => i.latest_run?.outcome === "succeeded")
      .sort(
        (a, b) =>
          at(b.latest_run?.finished_at ?? null) -
          at(a.latest_run?.finished_at ?? null),
      )
      .slice(0, limit)
      .map((i) => ({
        ...rowView(i, now, multi),
        done: doneText(i.workflow_type),
      })),
    health: [
      { label: "Active automations", count: items.length - count("paused") },
      { label: "Require attention", count: count("needs_attention") },
      { label: "Healthy", count: count("healthy") },
      { label: "Paused", count: count("paused") },
    ],
  };
}

export interface RunRow {
  key: string;
  started: string;
  duration: string;
  chip: Chip;
  note: string;
}
export interface DialogView {
  name: string;
  clientName: string;
  clientSlug: string;
  locationName: string | null;
  status: Chip;
  latest: string;
  next: string;
  source: string;
  frequency: string;
  heading: "Human action required" | "Run outcome";
  body: string;
  advice: string | null;
  actions: { label: string; href: string }[];
  canRun: boolean;
  running: boolean;
  history: RunRow[];
}
export function dialogView(
  d: AutomationDetailView,
  now: Date,
  multi: ReadonlySet<string> = new Set(),
): DialogView {
  const row = rowView(d, now, multi);
  const needs = d.status === "needs_attention" && d.attention !== null;
  const latest = d.latest_run;
  const copy = d.attention
    ? REASON_COPY[d.attention.reason]
    : latest?.reason && latest.outcome === "will_retry"
      ? REASON_COPY[latest.reason]
      : null;
  return {
    name: row.name,
    clientName: row.clientName,
    clientSlug: row.clientSlug,
    locationName: row.locationName,
    status: row.statusChip,
    latest: row.last,
    next: row.next,
    source: row.source,
    frequency: row.frequency,
    heading: needs ? "Human action required" : "Run outcome",
    body: copy?.what ?? row.outcome,
    advice: copy?.next ?? null,
    actions: (d.attention?.recovery_actions ?? []).map((a) => ({
      label: ACTION_LABELS[a],
      href: actionHref(a, d.client.slug),
    })),
    canRun: d.run_now_allowed && d.status !== "running",
    running: d.status === "running",
    history: d.runs.map((r, index) => ({
      key: String(index),
      started: r.started_at ? runTime(r.started_at, now) : "Queued",
      duration: durationText(r.duration_seconds),
      chip: outcomeChips[r.outcome as RunOutcome],
      note: r.reason ? REASON_COPY[r.reason].what : "",
    })),
  };
}
/** What a person reads when Run now does not go through; the code itself is never shown. */
export const RUN_FAILURE_TEXT: Record<string, string> = {
  AUTOMATION_RUN_IN_PROGRESS:
    "This automation is already running. Wait for it to finish, then check the result.",
  AUTOMATION_PAUSED: "This automation is paused, so it cannot be run now.",
  AUTOMATION_RUN_NOT_ALLOWED: "This automation can only run on its schedule.",
  PERMISSION_DENIED: "You do not have permission to run this automation.",
  AAL2_REQUIRED: "Verify your authenticator, then try again.",
  CSRF_INVALID: "Your session expired. Refresh the page and try again.",
};
export const runFailureText = (code: string): string =>
  RUN_FAILURE_TEXT[code] ??
  "That did not start. Refresh to see the current state, then try again.";

/** The typed code of a failed call, from the API's `error.code` or the BFF's `code`. */
export function failureCode(raw: unknown, status: number): string {
  if (raw && typeof raw === "object") {
    const body = raw as { code?: unknown; error?: { code?: unknown } };
    const code = body.error?.code ?? body.code;
    if (typeof code === "string" && /^[A-Z][A-Z0-9_]{0,127}$/.test(code))
      return code;
  }
  return `HTTP_${status}`;
}
