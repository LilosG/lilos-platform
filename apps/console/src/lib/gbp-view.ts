import type {
  GbpChangeSet,
  GbpCompleteness,
  GbpMedia,
  GbpMetric,
  GbpPerformanceView,
  GbpSpecialHours,
} from "../adapters/gbp";
import type { ProfileView } from "../adapters/local-search";
import {
  approvalChip,
  postChips,
  postState,
  type Chip,
  type PostState,
} from "./status";
import {
  chartModel,
  gbpTile,
  type ChartModel,
  type Tile,
} from "./local-search-view";
import { clockText, dateText, fmt, humanize, rangeText } from "./present";
export const GBP_VIEWS = [
  ["Performance", "performance"],
  ["Posts", "posts"],
  ["Photos", "photos"],
  ["Special hours", "special-hours"],
  ["Profile", "profile"],
] as const;
export type GbpViewKey = (typeof GBP_VIEWS)[number][1];
export const gbpViewKey = (value: string | null): GbpViewKey =>
  GBP_VIEWS.find(([, key]) => key === value)?.[1] ?? "performance";
const OPTIONAL: [GbpMetric, string][] = [
  ["BUSINESS_CONVERSATIONS", "Conversations"],
  ["BUSINESS_BOOKINGS", "Bookings"],
  ["BUSINESS_FOOD_ORDERS", "Food orders"],
  ["BUSINESS_FOOD_MENU_CLICKS", "Menu clicks"],
];
/** Profile views and the three actions every profile reports, then optional ones that have data. */
export function performanceTiles(
  perf: GbpPerformanceView,
  days: number,
): { views: Tile; actions: Tile[]; optional: Tile[] } {
  const found = perf.profile_views;
  const viewsValue = found.current.value;
  const views: Tile =
    viewsValue === null
      ? gbpTile(
          perf,
          "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
          "Profile views",
          days,
        )
      : {
          label: "Profile views",
          value: fmt(viewsValue),
          description:
            found.current.availability === "partial"
              ? `Partial period · ${found.current.days_covered} of ${found.current.days_expected} days synced`
              : found.change_percent === null
                ? "No earlier period"
                : `vs previous ${days} days`,
          trend:
            found.current.availability === "partial" ||
            found.change_percent === null
              ? null
              : Math.round(found.change_percent),
          missing: false,
        };
  if (viewsValue === null) views.label = "Profile views";
  return {
    views,
    actions: [
      gbpTile(perf, "CALL_CLICKS", "Calls", days),
      gbpTile(perf, "WEBSITE_CLICKS", "Website clicks", days),
      gbpTile(perf, "BUSINESS_DIRECTION_REQUESTS", "Direction requests", days),
    ],
    // Metrics a profile does not report are left out, never shown as zero.
    optional: OPTIONAL.filter(([metric]) => {
      const total = perf.metrics.find((m) => m.metric === metric)?.current;
      return total?.value !== null && total?.value !== undefined;
    }).map(([metric, label]) => gbpTile(perf, metric, label, days)),
  };
}
export interface SplitRow {
  label: string;
  value: string;
  share: number;
}
export interface Split {
  title: string;
  rows: SplitRow[];
}
const valueOf = (perf: GbpPerformanceView, metric: GbpMetric) =>
  perf.metrics.find((m) => m.metric === metric)?.current.value ?? null;
function split(title: string, parts: [string, number | null][]): Split | null {
  const known = parts.filter(
    (part): part is [string, number] => part[1] !== null,
  );
  const sum = known.reduce((total, [, value]) => total + value, 0);
  if (!known.length || sum === 0) return null;
  return {
    title,
    rows: known.map(([label, value]) => ({
      label,
      value: fmt(value),
      share: Math.round((value / sum) * 100),
    })),
  };
}
/** Where profile views came from: Maps or Search, desktop or mobile. Parts with no data are left out. */
export function impressionSplits(perf: GbpPerformanceView): Split[] {
  const v = (metric: GbpMetric) => valueOf(perf, metric);
  const dm = v("BUSINESS_IMPRESSIONS_DESKTOP_MAPS");
  const ds = v("BUSINESS_IMPRESSIONS_DESKTOP_SEARCH");
  const mm = v("BUSINESS_IMPRESSIONS_MOBILE_MAPS");
  const ms = v("BUSINESS_IMPRESSIONS_MOBILE_SEARCH");
  const sum = (...values: (number | null)[]) =>
    values.every((x) => x === null)
      ? null
      : values.reduce<number>((total, x) => total + (x ?? 0), 0);
  return [
    split("Google Maps and Search", [
      ["Google Maps", sum(dm, mm)],
      ["Google Search", sum(ds, ms)],
    ]),
    split("Desktop and mobile", [
      ["Desktop", sum(dm, ds)],
      ["Mobile", sum(mm, ms)],
    ]),
  ].filter((item): item is Split => item !== null);
}
export interface DailyCharts {
  impressions: ChartModel | null;
  actions: ChartModel | null;
}
export function dailyCharts(perf: GbpPerformanceView): DailyCharts {
  const points = (key: "impressions" | "actions") =>
    perf.series.flatMap((p) =>
      p[key] === null ? [] : [{ day: p.day, value: p[key] }],
    );
  return {
    impressions: chartModel(points("impressions")),
    actions: chartModel(points("actions")),
  };
}
export interface KeywordRow {
  keyword: string;
  value: string;
  bounded: boolean;
}
/** Google reports only "fewer than N" for rare searches; that is shown as "< N", never as 0. */
export function keywordText(
  term: GbpPerformanceView["search_terms"]["terms"][number],
): string {
  if (term.value === null)
    return term.below_threshold === null
      ? "–"
      : `< ${fmt(term.below_threshold)}`;
  return term.below_threshold === null
    ? fmt(term.value)
    : `${fmt(term.value)}+`;
}
export function keywordRows(perf: GbpPerformanceView): KeywordRow[] {
  return perf.search_terms.terms.map((term) => ({
    keyword: term.keyword,
    value: keywordText(term),
    bounded: !term.is_exact,
  }));
}
export const keywordMonth = (perf: GbpPerformanceView): string =>
  perf.search_terms.month
    ? new Intl.DateTimeFormat("en-US", {
        timeZone: "UTC",
        month: "long",
        year: "numeric",
      }).format(new Date(`${perf.search_terms.month}T00:00:00Z`))
    : "";
export const performancePeriod = (perf: GbpPerformanceView): string =>
  rangeText(perf.current_range.start, perf.current_range.end);
const sourceFailure: Record<string, string> = {
  INTEGRATION_RECONNECT_REQUIRED: "Google needs to be reconnected.",
  GBP_SCOPE_REQUIRED: "Google access needs to be granted again.",
  GBP_PERFORMANCE_ACCESS_DENIED: "Google denied access to performance data.",
  GBP_PERFORMANCE_RATE_LIMITED:
    "Google limited the request; it will be retried.",
  GBP_PERFORMANCE_PROVIDER_UNAVAILABLE:
    "Google was unavailable; it will be retried.",
};
export interface PerformanceSource {
  chip: Chip;
  detail: string;
}
export function performanceSource(perf: GbpPerformanceView): PerformanceSource {
  const {
    last_status: status,
    last_synced_at: at,
    last_failure_code: code,
  } = perf.source;
  const synced = at
    ? `Last synced ${dateText(at)}`
    : "No sync has completed yet";
  if (status === "failed")
    return {
      chip: { label: "Sync failed", tone: "error" },
      detail: `${code ? (sourceFailure[code] ?? "The last sync did not finish.") : "The last sync did not finish."} ${synced}.`,
    };
  if (status === "partial")
    return {
      chip: { label: "Partly synced", tone: "warn" },
      detail: `Daily figures synced; search terms did not. ${synced}.`,
    };
  if (!at)
    return {
      chip: { label: "First sync scheduled", tone: "neutral" },
      detail: "Performance appears here after the first sync.",
    };
  return { chip: { label: "Up to date", tone: "" }, detail: `${synced}.` };
}
export type PostAction =
  "approve" | "reject" | "publish" | "recover" | "repost" | "discard";
export interface PostRow {
  id: string;
  /** The revision's own id; actions on a publication use `publicationId`. */
  publicationId: string | null;
  kind: string;
  content: string;
  chip: Chip;
  state: PostState;
  detail: string;
  cta: string | null;
  actions: PostAction[];
  editable: boolean;
  postKey: string;
  postType: ProfileView["posts"][number]["post_type"];
}
const postKind: Record<string, string> = {
  standard: "Update",
  event: "Event",
  offer: "Offer",
  alert: "Alert",
};
const ctaLabel: Record<string, string> = {
  BOOK: "Book",
  ORDER: "Order online",
  SHOP: "Shop",
  LEARN_MORE: "Learn more",
  SIGN_UP: "Sign up",
  CALL: "Call",
};
const ctaOf = (cta: Record<string, unknown> | null): string | null => {
  const type = cta?.actionType;
  return typeof type === "string" ? (ctaLabel[type] ?? humanize(type)) : null;
};
export interface PostPermissions {
  canApprove: boolean;
  canPublish: boolean;
  canPropose: boolean;
  canWrite: boolean;
}
export function postRows(view: ProfileView, can: PostPermissions): PostRow[] {
  return view.posts.map((post) => {
    const state = postState(post.status, post.publication?.status ?? null);
    const actions: PostAction[] = [];
    if (state === "awaiting_approval" && can.canApprove)
      actions.push("approve", "reject");
    if (state === "approved" && can.canPublish && can.canWrite)
      actions.push("publish");
    if (post.publication?.recovery_allowed && can.canPublish)
      actions.push("recover");
    if (state === "not_published" && can.canPublish)
      actions.push("repost", "discard");
    const publication = post.publication;
    return {
      id: post.id,
      publicationId: publication?.id ?? null,
      kind: postKind[post.post_type] ?? humanize(post.post_type),
      content: post.content,
      chip: postChips[state],
      state,
      detail: publication?.verified_at
        ? `Published ${dateText(publication.verified_at)}`
        : publication?.scheduled_for
          ? `Scheduled ${dateText(publication.scheduled_for)}`
          : `Version ${post.revision}`,
      cta: ctaOf(post.call_to_action),
      actions,
      editable: state === "awaiting_approval" || state === "rejected",
      postKey: post.post_key,
      postType: post.post_type,
    };
  });
}
export const postActionLabel: Record<PostAction, string> = {
  approve: "Approve",
  reject: "Reject",
  publish: "Publish",
  recover: "Retry publishing",
  repost: "Repost",
  discard: "Discard",
};
export interface PhotoRow {
  id: string;
  /** Shown only for an https address; anything else renders as a placeholder. */
  url: string | null;
  kind: string;
  chip: Chip;
  rights: string;
  verified: string;
  actions: ("approve" | "reject" | "publish")[];
}
const mediaKind: Record<GbpMedia["media_type"], string> = {
  photo: "Photo",
  video: "Video",
  logo: "Logo",
  cover: "Cover photo",
};
const secure = (value: string) => {
  try {
    return new URL(value).protocol === "https:" ? value : null;
  } catch {
    return null;
  }
};
export function photoRows(
  items: GbpMedia[],
  can: { canApprove: boolean; canWrite: boolean },
): PhotoRow[] {
  return items.map((item) => ({
    id: item.id,
    url: secure(item.source_reference),
    kind: mediaKind[item.media_type],
    chip: approvalChip(item.status),
    rights: item.rights_authority,
    verified: item.verified_at ? `Verified ${dateText(item.verified_at)}` : "",
    actions: [
      ...(item.status === "awaiting_approval" && can.canApprove
        ? (["approve", "reject"] as const)
        : []),
      ...(item.status === "approved" && can.canWrite
        ? (["publish"] as const)
        : []),
    ],
  }));
}
export interface HoursRow {
  id: string;
  date: string;
  times: string;
  chip: Chip;
  actions: ("approve" | "reject")[];
}
const times = (periods: GbpSpecialHours["periods"]) =>
  periods
    .map((p) => `${clockText(p.opens)} – ${clockText(p.closes)}`)
    .join(", ");
export function hoursRows(
  items: GbpSpecialHours[],
  canApprove: boolean,
): HoursRow[] {
  return [...items]
    .sort((a, b) => a.service_date.localeCompare(b.service_date))
    .map((item) => ({
      id: item.id,
      date: new Intl.DateTimeFormat("en-US", {
        timeZone: "UTC",
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
      }).format(new Date(`${item.service_date}T00:00:00Z`)),
      times: times(item.periods),
      chip: approvalChip(item.status),
      actions:
        item.status === "awaiting_approval" && canApprove
          ? ["approve", "reject"]
          : [],
    }));
}
const fieldLabel: Record<string, string> = {
  title: "Business name",
  storefrontAddress: "Address",
  regularHours: "Opening hours",
  profile: "Description",
  description: "Description",
  phoneNumbers: "Phone number",
  websiteUri: "Website",
  categories: "Categories",
  serviceArea: "Service area",
  openInfo: "Opening status",
  specialHours: "Special hours",
  moreHours: "More hours",
  labels: "Labels",
  serviceItems: "Services",
  name: "Profile name",
};
export const labelOf = (field: string): string =>
  fieldLabel[field] ?? humanize(field);
type Json = Record<string, unknown>;
const asRecord = (value: unknown): Json | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Json)
    : null;
const str = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value : null;
export interface ProfileSummary {
  rows: { label: string; value: string }[];
  hours: { day: string; text: string }[];
  description: string | null;
}
const DAYS = [
  "MONDAY",
  "TUESDAY",
  "WEDNESDAY",
  "THURSDAY",
  "FRIDAY",
  "SATURDAY",
  "SUNDAY",
];
const timeOf = (value: unknown): string => {
  const t = asRecord(value);
  return t ? clockText(`${t.hours ?? 0}:${t.minutes ?? 0}`) : "";
};
/** The provider's profile as a person reads it: name, address, phone, website, category and hours. */
export function profileSummary(
  profile: ProfileView["profile"],
): ProfileSummary {
  const data = asRecord(profile) ?? {};
  const address = asRecord(data.storefrontAddress);
  const lines = Array.isArray(address?.addressLines)
    ? address.addressLines.filter((l): l is string => typeof l === "string")
    : [];
  const place = [
    address?.locality,
    [address?.administrativeArea, address?.postalCode]
      .filter((v) => typeof v === "string" && v)
      .join(" "),
  ]
    .filter((v) => typeof v === "string" && v)
    .join(", ");
  const phones = asRecord(data.phoneNumbers);
  const category = asRecord(data.categories);
  const primary = asRecord(category?.primaryCategory);
  const rows = [
    ["Business name", str(data.title)],
    ["Address", [...lines, place].filter(Boolean).join(", ") || null],
    ["Phone", str(phones?.primaryPhone)],
    ["Website", str(data.websiteUri)],
    ["Primary category", str(primary?.displayName)],
  ].flatMap(([label, value]) =>
    value ? [{ label: label as string, value: value as string }] : [],
  );
  const periods = Array.isArray(asRecord(data.regularHours)?.periods)
    ? (asRecord(data.regularHours)!.periods as unknown[])
    : [];
  const byDay = new Map<string, string[]>();
  for (const raw of periods) {
    const period = asRecord(raw);
    const day = str(period?.openDay);
    if (!period || !day) continue;
    byDay.set(day, [
      ...(byDay.get(day) ?? []),
      `${timeOf(period.openTime)} – ${timeOf(period.closeTime)}`,
    ]);
  }
  return {
    rows,
    hours: DAYS.map((day) => ({
      day: humanize(day.toLowerCase()),
      text: byDay.get(day)?.join(", ") ?? "Closed",
    })),
    description: str(asRecord(data.profile)?.description),
  };
}
export interface CompletenessView {
  percent: number;
  known: string[];
  missing: string[];
}
export function completenessView(report: GbpCompleteness): CompletenessView {
  const total = report.known.length + report.unknown.length;
  return {
    percent: total ? Math.round((report.known.length / total) * 100) : 0,
    known: report.known.map(labelOf),
    missing: report.unknown.map(labelOf),
  };
}
const warningText: Record<string, string> = {
  business_name_missing: "The business name is missing",
  address_unavailable: "Google has no address on file",
  hours_missing: "Opening hours are missing",
  description_missing: "The description is missing",
  provider_snapshot_stale: "The profile has not been refreshed this week",
};
export interface HealthView {
  chip: Chip;
  issues: string[];
}
export function healthView(health: ProfileView["health"]): HealthView | null {
  const data = asRecord(health);
  if (!data) return null;
  const codes = [
    ...(Array.isArray(data.blockers) ? data.blockers : []),
    ...(Array.isArray(data.warnings) ? data.warnings : []),
  ].filter((c): c is string => typeof c === "string");
  const issues = codes.map(
    (c) => warningText[c] ?? "A profile detail needs a look",
  );
  return {
    chip: data.healthy
      ? issues.length
        ? { label: "Needs a look", tone: "warn" }
        : { label: "Healthy", tone: "" }
      : { label: "Needs attention", tone: "error" },
    issues,
  };
}
export interface ChangeRow {
  id: string;
  label: string;
  after: string;
  before: string;
  chip: Chip;
  canDecide: boolean;
}
/** What would change, exactly as it will be approved: the field, today's value and the new one. */
export function changeRows(
  sets: GbpChangeSet[],
  profile: ProfileView["profile"],
  canApprove: boolean,
): ChangeRow[] {
  const data = asRecord(profile) ?? {};
  const observed = (field: string): string => {
    if (field === "description")
      return str(asRecord(data.profile)?.description) ?? "Not set";
    if (field === "phoneNumbers")
      return str(asRecord(data.phoneNumbers)?.primaryPhone) ?? "Not set";
    return str(data[field]) ?? "Not set";
  };
  return sets
    .filter((set) => set.status === "awaiting_approval")
    .flatMap((set) =>
      set.field_changes.map((change) => ({
        id: set.id,
        label: labelOf(change.field),
        after:
          typeof change.value === "string" ? change.value : "Updated value",
        before: observed(change.field),
        chip: approvalChip(set.status),
        canDecide: canApprove,
      })),
    );
}
export interface GbpLocationOption {
  /** The Business Profile record, used by every write. */
  gbpId: string;
  /** The platform location the profile belongs to. */
  locationId: string;
  name: string;
  writeEnabled: boolean;
}
/** Everything the Business Profile tab renders; a null read failed and shows its own error. */
export interface GbpTabData {
  view: GbpViewKey;
  organizationId: string;
  locations: GbpLocationOption[];
  selected: GbpLocationOption | null;
  performance: GbpPerformanceView | null;
  detail: ProfileView | null;
  media: GbpMedia[] | null;
  hours: GbpSpecialHours[] | null;
  changes: GbpChangeSet[] | null;
  completeness: GbpCompleteness | null;
  /** Where to verify an authenticator, then return to this screen. */
  verifyHref: string;
}
