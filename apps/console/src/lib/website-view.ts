import type { WebsitePageView, WebsiteView } from "../adapters/website-content";
import type { OpportunityView } from "../adapters/opportunities";
import type { Tile } from "./local-search-view";
import {
  bandChip,
  evidenceHeadline,
  evidenceSub,
  labelField,
  lifecycleLabel,
  nextAction,
  pagePath,
  title as opportunityTitle,
} from "./opportunity-view";
import { countText, fmt, humanize, rangeText, reviewDate } from "./present";
import type { Chip, Tone } from "./status";

type PageSummary = WebsiteView["pages"][number];
type Crawl = WebsiteView["crawls"][number];

/** The five tabs of Website & Content, with the path each lives at. */
export const WEBSITE_TABS = [
  ["Overview", ""],
  ["Pages", "pages"],
  ["Content", "content"],
  ["Technical", "technical"],
  ["Conversions", "conversions"],
] as const;

/** A site check older than this is labeled out of date. */
export const STALE_CHECK_DAYS = 30;
const DAY = 86_400_000;

const missingTile = (label: string, value: string, note: string): Tile => ({
  label,
  value,
  description: note,
  trend: null,
  missing: true,
});

const NO_TREND = "Change over time is not tracked yet";

// --- what the crawler reports, by typed code ---------------------------------------------

export type Severity = "high" | "medium" | "low";
export const SEVERITIES: readonly Severity[] = ["high", "medium", "low"];
export const severityChips: Record<Severity, Chip> = {
  high: { label: "High priority", tone: "error" },
  medium: { label: "Medium priority", tone: "warn" },
  low: { label: "Low priority", tone: "neutral" },
};
interface IssueInfo {
  label: string;
  severity: Severity;
  /** What to do about it, in a sentence. */
  action: string;
}
/** A page the crawler found closed to search engines is a finding of its own. */
export const NOT_INDEXABLE = "not_indexable";
const issueInfo: Record<string, IssueInfo> = {
  non_200_status: {
    label: "Page does not load correctly",
    severity: "high",
    action:
      "Fix or redirect the page so visitors and search engines can reach it.",
  },
  missing_title: {
    label: "Missing page title",
    severity: "high",
    action: "Add a title that names the page and its location or service.",
  },
  [NOT_INDEXABLE]: {
    label: "Closed to search engines",
    severity: "medium",
    action:
      "Confirm this is intended; otherwise remove the block so it can be found.",
  },
  missing_meta_description: {
    label: "Missing meta description",
    severity: "medium",
    action: "Add a short description so search results explain the page.",
  },
  missing_h1: {
    label: "Missing main heading",
    severity: "medium",
    action: "Add one clear heading that says what the page is about.",
  },
  multiple_h1: {
    label: "More than one main heading",
    severity: "medium",
    action: "Keep one main heading and demote the others.",
  },
  title_truncated: {
    label: "Page title is too long",
    severity: "low",
    action: "Shorten the title so it is not cut off in search results.",
  },
  meta_description_truncated: {
    label: "Meta description is too long",
    severity: "low",
    action: "Shorten the description so it is not cut off in search results.",
  },
  h1_truncated: {
    label: "Main heading is too long",
    severity: "low",
    action: "Shorten the heading.",
  },
  canonical_url_too_long: {
    label: "Preferred address is too long",
    severity: "low",
    action: "Use a shorter preferred address for the page.",
  },
  observed_url_too_long: {
    label: "Page address is too long",
    severity: "low",
    action: "Use a shorter address for the page.",
  },
  redirect_destination_too_long: {
    label: "Redirect destination is too long",
    severity: "low",
    action: "Point the redirect at a shorter address.",
  },
};
/** A code this app does not know is still shown, as a low-priority finding in plain words. */
export const issueFor = (code: string): IssueInfo =>
  issueInfo[code] ?? {
    label: humanize(code),
    severity: "low",
    action: "Open the page to review what the check found.",
  };

/** The technical issue codes a page carries; anything that is not a code is not shown. */
export const issuesOf = (page: PageSummary): string[] =>
  page.technical_issues.filter(
    (item): item is string => typeof item === "string",
  );
const closed = (page: PageSummary) => page.indexability === "not_indexable";
/** Every finding code for one page, including being closed to search engines. */
const findingsOf = (page: PageSummary): string[] => [
  ...issuesOf(page),
  ...(closed(page) ? [NOT_INDEXABLE] : []),
];
const hasIssues = (page: PageSummary) =>
  issuesOf(page).length > 0 || page.quality_status === "issues_detected";

// --- chips -------------------------------------------------------------------------------

export const indexChip = (indexability: string | null): Chip =>
  indexability === "indexable"
    ? { label: "Indexable", tone: "" }
    : indexability === "not_indexable"
      ? { label: "Not indexable", tone: "warn" }
      : { label: "Not checked", tone: "neutral" };
export const qualityChip = (quality: string): Chip =>
  quality === "clean"
    ? { label: "No issues", tone: "" }
    : quality === "issues_detected"
      ? { label: "Issues found", tone: "warn" }
      : quality === "partial"
        ? { label: "Partly checked", tone: "warn" }
        : { label: "Not checked", tone: "neutral" };
const crawlChips: Record<string, Chip> = {
  completed: { label: "Completed", tone: "" },
  succeeded: { label: "Completed", tone: "" },
  partial: { label: "Partly checked", tone: "warn" },
  running: { label: "Running", tone: "neutral" },
  queued: { label: "Queued", tone: "neutral" },
  failed: { label: "Failed", tone: "error" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};
export const crawlChip = (status: string): Chip =>
  crawlChips[status] ?? { label: "Not checked", tone: "neutral" };

// --- the site, its latest check and the header chip --------------------------------------

/** The most recent check, by when it finished (or started, while it runs). */
export function latestCrawl(crawls: Crawl[]): Crawl | null {
  const at = (c: Crawl) => Date.parse(c.completed_at ?? c.started_at ?? "");
  const known = crawls.filter((c) => !Number.isNaN(at(c)));
  if (!known.length) return crawls[0] ?? null;
  return known.reduce((best, c) => (at(c) > at(best) ? c : best));
}
const crawlTime = (c: Crawl) => c.completed_at ?? c.started_at;
const isStale = (c: Crawl, now: Date) => {
  const at = Date.parse(crawlTime(c) ?? "");
  return !Number.isNaN(at) && now.getTime() - at > STALE_CHECK_DAYS * DAY;
};

/** Why page figures cannot be shown, from the workspace's typed state; null when they can. */
export type PageGap =
  "no_website" | "no_access" | "unavailable" | "not_checked";
export function pageGap(view: WebsiteView): PageGap | null {
  if (view.websites.length === 0 || !view.website_id) return "no_website";
  if (view.page_availability === "permission_required") return "no_access";
  if (view.page_availability === "unavailable") return "unavailable";
  if (view.pages.length === 0) return "not_checked";
  return null;
}
const gapText: Record<PageGap, { value: string; note: string }> = {
  no_website: { value: "No website", note: "Add a website in Integrations" },
  no_access: { value: "No access", note: "Not available to your role" },
  unavailable: { value: "Unavailable", note: "Page data could not be read" },
  not_checked: { value: "Not checked", note: "Run a website check" },
};

export interface SiteStatus {
  chip: Chip;
  /** Typed state, for the page and its tests. */
  state:
    | "no_website"
    | "no_access"
    | "unavailable"
    | "never_checked"
    | "running"
    | "failed"
    | "stale"
    | "partial"
    | "current";
}
/** Everything the header chip stands for: the newest site check and whether it can be trusted. */
export function siteStatus(view: WebsiteView, now: Date): SiteStatus {
  const gap = pageGap(view);
  if (gap === "no_website")
    return {
      state: "no_website",
      chip: { label: "No website", tone: "neutral" },
    };
  if (gap === "no_access")
    return {
      state: "no_access",
      chip: { label: "No access", tone: "neutral" },
    };
  if (gap === "unavailable")
    return {
      state: "unavailable",
      chip: { label: "Pages unavailable", tone: "warn" },
    };
  const latest = latestCrawl(view.crawls);
  if (!latest)
    return {
      state: "never_checked",
      chip: { label: "Not checked yet", tone: "neutral" },
    };
  if (latest.status === "failed")
    return {
      state: "failed",
      chip: { label: "Last check failed", tone: "error" },
    };
  if (latest.status === "running" || latest.status === "queued")
    return {
      state: "running",
      chip: { label: "Check running", tone: "neutral" },
    };
  if (isStale(latest, now))
    return {
      state: "stale",
      chip: { label: "Check out of date", tone: "warn" },
    };
  const when = crawlTime(latest);
  const label = when
    ? `Checked ${reviewDate(when, now)
        .replace(/^Today$/, "today")
        .replace(/^Yesterday$/, "yesterday")}`
    : "Checked";
  return latest.status === "partial"
    ? { state: "partial", chip: { label: "Partly checked", tone: "warn" } }
    : { state: "current", chip: { label: label, tone: "" } };
}

// --- tiles -------------------------------------------------------------------------------

/** The pages count is a count of what was loaded; more pages exist when there is a next page. */
const partialNote = (view: WebsiteView) =>
  view.next_page_offset !== null
    ? `In the first ${view.pages.length} pages; more exist`
    : null;

function lastCheckTile(view: WebsiteView, now: Date): Tile {
  const gap = pageGap(view);
  const latest = latestCrawl(view.crawls);
  if (gap === "no_website" || gap === "no_access" || gap === "unavailable")
    return missingTile(
      "Last site check",
      gapText[gap].value,
      gapText[gap].note,
    );
  if (!latest || !crawlTime(latest))
    return missingTile("Last site check", "Not checked", "Run a website check");
  return {
    label: "Last site check",
    value: reviewDate(crawlTime(latest)!, now),
    description: crawlChip(latest.status).label,
    trend: null,
    missing: false,
  };
}

function countTile(
  view: WebsiteView,
  label: string,
  count: (pages: PageSummary[]) => number,
  note: string,
): Tile {
  const gap = pageGap(view);
  if (gap) return missingTile(label, gapText[gap].value, gapText[gap].note);
  return {
    label,
    value: fmt(count(view.pages)),
    description: partialNote(view) ?? note,
    trend: null,
    missing: false,
  };
}

/** The Overview's tiles: only what the page inventory supports, the rest marked as not tracked. */
export function overviewTiles(view: WebsiteView, now: Date): Tile[] {
  return [
    countTile(view, "Pages checked", (p) => p.length, NO_TREND),
    countTile(
      view,
      "Indexable pages",
      (p) => p.filter((x) => x.indexability === "indexable").length,
      "Open to search engines",
    ),
    countTile(
      view,
      "Pages with issues",
      (p) => p.filter(hasIssues).length,
      "At least one finding",
    ),
    lastCheckTile(view, now),
    missingTile(
      "Indexed by Google",
      "Not tracked",
      "Google's own index count is not collected yet",
    ),
  ];
}

export function technicalTiles(view: WebsiteView, now: Date): Tile[] {
  const groups = findingGroups(view, []);
  const urgent =
    groups.find((g) => g.severity === "high")?.findings.length ?? 0;
  const gap = pageGap(view);
  return [
    countTile(view, "Pages checked", (p) => p.length, NO_TREND),
    countTile(
      view,
      "Pages with issues",
      (p) => p.filter(hasIssues).length,
      "At least one finding",
    ),
    gap
      ? missingTile(
          "High-priority findings",
          gapText[gap].value,
          gapText[gap].note,
        )
      : {
          label: "High-priority findings",
          value: fmt(urgent),
          description: partialNote(view) ?? "Kinds of problem to fix first",
          trend: null,
          missing: false,
        },
    lastCheckTile(view, now),
  ];
}

/** Conversions have no source: every tile says so, none shows a number. */
export const conversionTiles = (): Tile[] =>
  ["Key events", "Conversion rate", "Pages with conversion data"].map((label) =>
    missingTile(label, "Not tracked", "Needs key events defined"),
  );

// --- the performance insight, chosen by a typed reason -----------------------------------

export type InsightReason =
  | "NO_WEBSITE"
  | "NO_ACCESS"
  | "PAGES_UNAVAILABLE"
  | "LAST_CHECK_FAILED"
  | "NEVER_CHECKED"
  | "ISSUES_FOUND"
  | "PAGES_NOT_INDEXABLE"
  | "CHECK_OUT_OF_DATE"
  | "ALL_CLEAR";
export interface Insight {
  reason: InsightReason;
  title: string;
  detail: string;
  action: {
    label: string;
    target: "integrations" | "technical" | "pages" | "check";
  };
}
const plural = (n: number, one: string, many: string) =>
  `${fmt(n)} ${n === 1 ? one : many}`;

/** The reason this site needs a person's attention first. Nothing here reads prose. */
export function insightReason(view: WebsiteView, now: Date): InsightReason {
  const status = siteStatus(view, now);
  if (status.state === "no_website") return "NO_WEBSITE";
  if (status.state === "no_access") return "NO_ACCESS";
  if (status.state === "unavailable") return "PAGES_UNAVAILABLE";
  if (status.state === "failed") return "LAST_CHECK_FAILED";
  if (status.state === "never_checked" || view.pages.length === 0)
    return "NEVER_CHECKED";
  if (view.pages.some(hasIssues)) return "ISSUES_FOUND";
  if (view.pages.some(closed)) return "PAGES_NOT_INDEXABLE";
  if (status.state === "stale") return "CHECK_OUT_OF_DATE";
  return "ALL_CLEAR";
}
export function websiteInsight(view: WebsiteView, now: Date): Insight {
  const reason = insightReason(view, now);
  const withIssues = view.pages.filter(hasIssues).length;
  const closedCount = view.pages.filter(closed).length;
  switch (reason) {
    case "NO_WEBSITE":
      return {
        reason,
        title: "No website is connected for this client.",
        detail:
          "Add the client's website in Integrations so its pages can be checked.",
        action: { label: "Open Integrations", target: "integrations" },
      };
    case "NO_ACCESS":
      return {
        reason,
        title: "Your role cannot see this website's pages.",
        detail: "Ask an administrator for access to website data.",
        action: { label: "Open Integrations", target: "integrations" },
      };
    case "PAGES_UNAVAILABLE":
      return {
        reason,
        title: "Page data could not be read right now.",
        detail: "Refresh in a moment. Nothing is estimated in its place.",
        action: { label: "Open Integrations", target: "integrations" },
      };
    case "LAST_CHECK_FAILED":
      return {
        reason,
        title: "The latest website check did not finish.",
        detail:
          "The pages below come from an earlier check. Run the check again to refresh them.",
        action: { label: "Run a website check", target: "check" },
      };
    case "NEVER_CHECKED":
      return {
        reason,
        title: "This website has not been checked yet.",
        detail:
          "Run a website check to see which pages search engines can reach and what needs fixing.",
        action: { label: "Run a website check", target: "check" },
      };
    case "ISSUES_FOUND":
      return {
        reason,
        title: `${plural(withIssues, "page has", "pages have")} technical issues.`,
        detail:
          "Fixing missing titles, descriptions and headings helps search engines understand these pages.",
        action: { label: "Review technical findings", target: "technical" },
      };
    case "PAGES_NOT_INDEXABLE":
      return {
        reason,
        title: `${plural(closedCount, "page is", "pages are")} closed to search engines.`,
        detail:
          "Confirm each is meant to be hidden. A page that should rank cannot while it is closed.",
        action: { label: "Review technical findings", target: "technical" },
      };
    case "CHECK_OUT_OF_DATE":
      return {
        reason,
        title: "The latest website check is out of date.",
        detail: "Run it again so these pages reflect the site as it is today.",
        action: { label: "Run a website check", target: "check" },
      };
    case "ALL_CLEAR":
      return {
        reason,
        title: "No technical issues were found in the pages checked.",
        detail:
          "This does not show how Google indexes the site; that count is not collected yet.",
        action: { label: "See all pages", target: "pages" },
      };
  }
}

// --- the page table ----------------------------------------------------------------------

export interface PageRow {
  id: string;
  href: string;
  label: string;
  path: string;
  httpText: string;
  /** "indexable", "not_indexable" or "unknown": for the table's own filter. */
  indexKey: string;
  index: Chip;
  quality: Chip;
  issuesText: string;
  observedText: string;
  observedAt: number;
  search: string;
  /** Higher sorts first under "Needs attention first". */
  attention: number;
  hasIssues: boolean;
  checked: boolean;
}
export function pageRows(
  view: WebsiteView,
  now: Date,
  href: (websiteId: string, pageId: string) => string,
): PageRow[] {
  return view.pages
    .map((p): PageRow => {
      const path = pagePath(p.normalized_url);
      const issues = issuesOf(p).length;
      const observed = p.observed_at ? Date.parse(p.observed_at) : NaN;
      return {
        id: p.id,
        href: href(p.website_id, p.id),
        label: p.title?.trim() || path,
        path,
        httpText: p.http_status === null ? "–" : String(p.http_status),
        indexKey:
          p.indexability === "indexable" || p.indexability === "not_indexable"
            ? p.indexability
            : "unknown",
        index: indexChip(p.indexability),
        quality: qualityChip(p.quality_status),
        issuesText: p.observed_at
          ? issues
            ? plural(issues, "issue", "issues")
            : p.quality_status === "issues_detected"
              ? "See page"
              : "None found"
          : "–",
        observedText: p.observed_at
          ? reviewDate(p.observed_at, now)
          : "Not checked",
        observedAt: Number.isNaN(observed) ? 0 : observed,
        search: `${p.title ?? ""} ${path}`.toLowerCase(),
        attention:
          (closed(p) ? 2 : 0) +
          issues +
          (p.http_status !== null && p.http_status >= 400 ? 5 : 0),
        hasIssues: hasIssues(p),
        checked: p.observed_at !== null,
      };
    })
    .sort((a, b) => b.attention - a.attention || a.path.localeCompare(b.path));
}

/** Filters the table offers. A filter whose evidence does not exist stays but cannot be chosen. */
export const PAGE_FILTERS: readonly {
  key: string;
  label: string;
  unavailable: string | null;
}[] = [
  { key: "all", label: "All pages", unavailable: null },
  { key: "indexable", label: "Indexable", unavailable: null },
  { key: "issues", label: "Has issues", unavailable: null },
  { key: "not_indexable", label: "Not indexable", unavailable: null },
  { key: "unchecked", label: "Not checked yet", unavailable: null },
  {
    key: "draft",
    label: "Drafts",
    unavailable: "Draft pages are not tracked yet",
  },
];
export const PAGE_SORTS: readonly {
  key: string;
  label: string;
  unavailable: boolean;
}[] = [
  {
    key: "attention",
    label: "Sort: Needs attention first",
    unavailable: false,
  },
  { key: "name", label: "Sort: Page name", unavailable: false },
  { key: "recent", label: "Sort: Recently checked", unavailable: false },
  {
    key: "clicks",
    label: "Sort: Organic clicks (not tracked)",
    unavailable: true,
  },
];

// --- technical findings ------------------------------------------------------------------

export interface Finding {
  code: string;
  label: string;
  severity: Severity;
  chip: Chip;
  pagesText: string;
  action: string;
  /** Where the next step happens: a proposed change when there is one, else the first page. */
  next: { label: string; href: string } | null;
}
export interface FindingGroup {
  severity: Severity;
  chip: Chip;
  findings: Finding[];
}
/** Findings grouped by how urgent they are. Each kind of problem appears once with its page count. */
export function findingGroups(
  view: WebsiteView,
  opportunities: { sourceType: string; pageId: string | null; href: string }[],
  pageHref: (websiteId: string, pageId: string) => string = () => "",
): FindingGroup[] {
  const byCode = new Map<string, PageSummary[]>();
  for (const page of view.pages)
    for (const code of new Set(findingsOf(page)))
      byCode.set(code, [...(byCode.get(code) ?? []), page]);
  const findings = [...byCode.entries()].map(([code, pages]): Finding => {
    const info = issueFor(code);
    const proposal = opportunities.find(
      (o) => o.sourceType === code && pages.some((p) => p.id === o.pageId),
    );
    const first = pages[0];
    return {
      code,
      label: info.label,
      severity: info.severity,
      chip: severityChips[info.severity],
      pagesText: plural(pages.length, "page", "pages"),
      action: info.action,
      next: proposal
        ? { label: "Review proposed change", href: proposal.href }
        : first
          ? {
              label: pages.length === 1 ? "Open page" : "Open first page",
              href: pageHref(first.website_id, first.id),
            }
          : null,
    };
  });
  return SEVERITIES.map((severity) => ({
    severity,
    chip: severityChips[severity],
    findings: findings
      .filter((f) => f.severity === severity)
      .sort((a, b) => a.label.localeCompare(b.label)),
  })).filter((g) => g.findings.length > 0);
}

// --- proposed site changes ---------------------------------------------------------------

export interface SiteChange {
  id: string;
  title: string;
  href: string;
  sourceType: string;
  pageId: string | null;
  classification: string;
  priority: string;
  next: string;
  evidence: string;
  evidenceSub: string;
  status: string;
}
/** The selected website's governed opportunities as rows; titles and states come from typed codes. */
export function siteChanges(
  items: OpportunityView[],
  slug: string,
  now: Date,
): SiteChange[] {
  return items.map((o) => ({
    id: o.source_id,
    title: opportunityTitle(o),
    href: `/clients/${slug}/opportunities/${o.source_id}/`,
    sourceType: o.source_type,
    pageId: o.page_id,
    classification: o.classification,
    priority: bandChip(o.priority_band),
    next: nextAction(o),
    evidence: evidenceHeadline(o),
    evidenceSub: evidenceSub(o, now),
    status: lifecycleLabel(o),
  }));
}

// --- the Details dialog ------------------------------------------------------------------

const notCollected: Record<string, string> = {
  named_cta_events: "Named call-to-action events",
  conversion_funnels: "Conversion funnels",
  page_health_score: "Page health score",
  google_indexation: "Google indexing status",
};
export interface WebsiteDetails {
  site: { name: string; origin: string } | null;
  chip: Chip;
  rows: { name: string; chip: Chip; note: string }[];
  checks: { chip: Chip; when: string; note: string }[];
  notCollected: string[];
}
const availabilityChips: Record<WebsiteView["page_availability"], Chip> = {
  available: { label: "Available", tone: "" },
  permission_required: { label: "No access", tone: "neutral" },
  unavailable: { label: "Unavailable", tone: "warn" },
};
export function websiteDetails(view: WebsiteView, now: Date): WebsiteDetails {
  const status = siteStatus(view, now);
  const site = view.websites.find((w) => w.id === view.website_id);
  const latest = latestCrawl(view.crawls);
  const worst: Tone = status.chip.tone;
  const rows: WebsiteDetails["rows"] = [
    {
      name: "Page data",
      chip: availabilityChips[view.page_availability],
      note:
        view.next_page_offset !== null
          ? `Showing ${fmt(view.pages.length)} pages; more are available`
          : `${countText(view.pages.length)} pages from the latest check`,
    },
    {
      name: "Latest site check",
      chip: status.chip,
      note:
        latest && crawlTime(latest)
          ? reviewDate(crawlTime(latest)!, now)
          : "No check has run yet",
    },
  ];
  return {
    site: site ? { name: site.name, origin: site.canonical_origin } : null,
    chip: { label: status.chip.label, tone: worst },
    rows,
    checks: [...view.crawls]
      .sort(
        (a, b) =>
          Date.parse(crawlTime(b) ?? "") - Date.parse(crawlTime(a) ?? ""),
      )
      .slice(0, 6)
      .map((c) => ({
        chip: crawlChip(c.status),
        when: crawlTime(c) ? reviewDate(crawlTime(c)!, now) : "Not started",
        note:
          c.status === "partial"
            ? "Stopped before every page was checked"
            : c.status === "failed"
              ? "The check did not finish"
              : "",
      })),
    notCollected: view.unsupported.map(
      (code) => notCollected[code] ?? humanize(code),
    ),
  };
}

// --- one page ----------------------------------------------------------------------------

type Json = unknown;
const record = (value: Json): Record<string, Json> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, Json>)
    : null;
const text = (value: Json): string | null =>
  typeof value === "string" && value.trim() ? value : null;
const number = (value: Json): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;
const items = (value: Json): Record<string, Json>[] => {
  const list = record(value)?.items;
  return Array.isArray(list)
    ? list.flatMap((row) => {
        const r = record(row);
        return r ? [r] : [];
      })
    : [];
};

export interface EvidenceRow {
  name: string;
  chip: Chip;
  value: string;
  note: string;
  missing: boolean;
}
const NOT_TRACKED_CHIP: Chip = { label: "Not tracked", tone: "neutral" };
const sum = (rows: Record<string, Json>[], key: string): number | null => {
  const values = rows.flatMap((r) => {
    const n = number(r[key]);
    return n === null ? [] : [n];
  });
  return values.length ? values.reduce((a, b) => a + b, 0) : null;
};
const periodOf = (a: Json, b: Json): string => {
  const start = text(a);
  return start ? rangeText(start, text(b)) : "";
};

export interface PageDetailView {
  label: string;
  path: string;
  site: string;
  index: Chip;
  quality: Chip;
  tiles: { label: string; value: string; missing: boolean }[];
  evidence: EvidenceRow[];
  mapping: MappingView;
  changes: ReturnType<typeof siteChanges>;
}
export interface MappingView {
  chip: Chip;
  mapped: boolean;
  explanation: string;
  repository: string | null;
  branch: string | null;
  fields: { label: string; path: string }[];
}
const mappingText: Record<string, string> = {
  SITE_MAPPING_REQUIRED:
    "This page is not linked to a file in the client's website repository, so a change cannot be proposed for it yet.",
};
export function mappingView(mapping: WebsitePageView["mapping"]): MappingView {
  const mapped = mapping.state === "mapped";
  return {
    mapped,
    chip: mapped
      ? { label: "Repository linked", tone: "" }
      : { label: "Repository not linked", tone: "warn" },
    explanation: mapped
      ? "Approved changes are written to this file. The exact approved revision is rechecked before anything is written."
      : ((mapping.code && mappingText[mapping.code]) ??
        "This page cannot take a proposed change yet."),
    repository: mapping.repository ?? null,
    branch: mapping.base_branch ?? null,
    fields: Object.entries(mapping.fields).map(([field, path]) => ({
      label: labelField(field),
      path,
    })),
  };
}

const changeText: Record<string, string> = {
  first_observation: "First time this page was checked",
  changed: "Changed since the previous check",
  no_change: "No change since the previous check",
  unavailable: "No earlier check to compare",
};

export function pageDetail(
  view: WebsitePageView,
  siteName: string | null,
  slug: string,
  now: Date,
): PageDetailView {
  const e = view.evidence;
  const path = pagePath(e.identity.normalized_url);
  const current = record(e.current_page) ?? {};
  const crawl = record(e.crawl) ?? {};
  const observation = record(crawl.observation);
  const content = record(e.content) ?? {};
  const label = text(current.title) ?? path;
  const indexability =
    text(observation?.indexability) ?? text(current.indexability);
  const quality = text(current.quality_status) ?? text(crawl.quality) ?? "";
  const http = number(observation?.http_status);
  const observed = text(content.observed_at) ?? text(crawl.observed_at);
  const words = number(content.word_count);
  const structured = content.structured_data_present;
  const tiles = [
    {
      label: "Page status",
      value: http === null ? "Not checked" : String(http),
      missing: http === null,
    },
    {
      label: "Last checked",
      value: observed ? reviewDate(observed, now) : "Not checked",
      missing: !observed,
    },
    {
      label: "Words on page",
      value: words === null ? "Not checked" : fmt(words),
      missing: words === null,
    },
    {
      label: "Structured data",
      value:
        typeof structured === "boolean"
          ? structured
            ? "Present"
            : "Not found"
          : "Not checked",
      missing: typeof structured !== "boolean",
    },
  ];

  const evidence: EvidenceRow[] = [];
  const gsc = record(e.gsc) ?? {};
  const gscRows = items(gsc.page);
  const clicks = sum(gscRows, "clicks");
  const impressions = sum(gscRows, "impressions");
  evidence.push(
    gsc.availability === "observed" && clicks !== null
      ? {
          name: "Search Console",
          chip: { label: "Available", tone: "" },
          value: `${fmt(clicks)} clicks${impressions === null ? "" : ` · ${fmt(impressions)} impressions`}`,
          note: periodOf(gsc.period_start, gsc.period_end),
          missing: false,
        }
      : {
          name: "Search Console",
          chip: NOT_TRACKED_CHIP,
          value: "Not available for this page",
          note: "Connect Search Console and map this website to see search traffic.",
          missing: true,
        },
  );
  const ga = record(e.ga4_organic_landing) ?? {};
  const keyEvents = items(ga.page).filter((r) => r.metric_key === "keyEvents");
  const events = sum(keyEvents, "value");
  evidence.push(
    ga.availability === "observed" && events !== null
      ? {
          name: "Key events from organic search",
          chip: { label: "Available", tone: "" },
          value: fmt(events),
          note: "Key events are not business outcomes.",
          missing: false,
        }
      : {
          name: "Key events from organic search",
          chip: NOT_TRACKED_CHIP,
          value: "Not available for this page",
          note: "Connect Analytics and define key events to see them here.",
          missing: true,
        },
  );
  const links = record(e.internal_links) ?? {};
  const inbound = number(links.mapped_inbound_count);
  const outbound = number(links.mapped_outbound_count);
  evidence.push(
    links.availability === "unavailable" ||
      (inbound === null && outbound === null)
      ? {
          name: "Internal links",
          chip: NOT_TRACKED_CHIP,
          value: "Not available for this page",
          note: "Run a website check to map the links between pages.",
          missing: true,
        }
      : {
          name: "Internal links",
          chip:
            links.availability === "partial"
              ? { label: "Partial", tone: "warn" }
              : { label: "Available", tone: "" },
          value: `${countText(inbound)} in · ${countText(outbound)} out`,
          note:
            links.availability === "partial"
              ? "Some links could not be matched to a page."
              : "",
          missing: false,
        },
  );
  const change = text(record(e.change)?.state);
  evidence.push({
    name: "Since the previous check",
    chip:
      change === "changed"
        ? { label: "Changed", tone: "warn" }
        : change === "no_change"
          ? { label: "No change", tone: "" }
          : { label: "No comparison", tone: "neutral" },
    value: (change && changeText[change]) ?? changeText.unavailable,
    note: "",
    missing: change === null || change === "unavailable",
  });

  return {
    label,
    path,
    site: siteName ?? "Website",
    index: indexChip(indexability),
    quality: qualityChip(quality),
    tiles,
    evidence,
    mapping: mappingView(view.mapping),
    changes: siteChanges(view.opportunities, slug, now),
  };
}
