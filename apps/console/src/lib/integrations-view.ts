import type { IntegrationsView } from "../adapters/local-search";
import { syncFailure } from "./local-search-view";
import { ago, dateText } from "./present";
import {
  connectionChips,
  connectionState,
  freshnessChip,
  githubConnectionChips,
  matchChip,
  publishingChips,
  syncChip,
  type Chip,
  type PublishingState,
} from "./status";
/** What a person reads about each part of the integrations screen; no API value reaches the page. */
export interface DetailRow {
  name: string;
  chip?: Chip;
  detail?: string;
}
export interface GoogleRow {
  chip: Chip;
  capabilities: string;
  verified: string;
  connectLabel: string;
  canConnect: boolean;
  canDisconnect: boolean;
  details: DetailRow[];
  syncs: { name: string; chip: Chip; when: string; note: string }[];
}
const sourceName = { search_console: "Search Console", analytics: "Analytics" };
export function googleRow(v: IntegrationsView, now: Date): GoogleRow {
  const g = v.google;
  const state = connectionState(g.connection_status);
  const granted = g.capabilities.filter((c) => c.enabled).map((c) => c.label);
  return {
    chip: connectionChips[state],
    capabilities: granted.length
      ? granted.join(" · ")
      : "No access granted yet",
    verified: g.last_verified_at
      ? `Verified ${ago(g.last_verified_at, now)}`
      : "Not verified yet",
    connectLabel: state === "connected" ? "Reconnect Google" : "Connect Google",
    canConnect: v.can_connect,
    canDisconnect: v.can_connect && g.connection_id !== null,
    details: [
      ...g.capabilities.map((c) => ({
        name: c.label,
        chip: c.enabled
          ? ({ label: "Allowed", tone: "" } as Chip)
          : ({ label: "Not allowed", tone: "neutral" } as Chip),
      })),
      {
        name: "Access renews",
        detail: g.token_expires_at
          ? dateText(g.token_expires_at)
          : "Not available",
      },
    ],
    syncs: v.syncs.slice(0, 6).map((s) => ({
      name: `${sourceName[s.source]} sync`,
      chip: syncChip(s.status),
      when: ago(s.completed_at ?? s.started_at, now) || "Not started",
      note: s.failure_code
        ? (syncFailure[s.failure_code] ?? "The sync did not finish.")
        : "",
    })),
  };
}
export type PublishingAction = "select" | "connect_github" | "verify" | "none";
export interface PublishingRow {
  state: PublishingState | "unavailable";
  chip: Chip;
  detail: string;
  action: PublishingAction;
  details: DetailRow[];
}
const githubChip = (status: string | null): Chip =>
  status === "connected"
    ? githubConnectionChips.connected
    : !status || status === "none"
      ? githubConnectionChips.not_connected
      : githubConnectionChips.reconnect;
export function publishingRow(v: IntegrationsView): PublishingRow {
  const p = v.publishing;
  if (!p)
    return {
      state: "unavailable",
      chip: { label: "No access", tone: "neutral" },
      detail: "You do not have access to website publishing for this client.",
      action: "none",
      details: [],
    };
  const detail =
    p.state === "linked" || p.state === "format_unverified"
      ? [p.repository, p.branch ? `Branch ${p.branch}` : null]
          .filter(Boolean)
          .join(" · ")
      : p.state === "not_linked"
        ? "Choose the repository this client's blog is published to."
        : "Connect GitHub so LILOs can publish to this client's website.";
  const action: PublishingAction =
    p.state === "not_linked"
      ? p.can_manage
        ? "select"
        : "verify"
      : p.state === "github_not_connected"
        ? p.can_manage
          ? "connect_github"
          : "verify"
        : "none";
  return {
    state: p.state,
    chip: publishingChips[p.state],
    detail,
    action,
    details: [
      { name: "GitHub", chip: githubChip(v.github_status) },
      ...(p.repository ? [{ name: "Repository", detail: p.repository }] : []),
      ...(p.branch ? [{ name: "Branch", detail: p.branch }] : []),
      {
        name: "Blog format",
        chip:
          p.state === "linked"
            ? { label: "Checked", tone: "" }
            : p.state === "format_unverified"
              ? publishingChips.format_unverified
              : { label: "Not applicable yet", tone: "neutral" },
      },
    ],
  };
}
/** "sc-domain:example.test" or "https://www.example.test/" read as the site they name. */
export function propertyName(id: string, displayName: string | null): string {
  if (displayName) return displayName;
  const bare = id.replace(/^sc-domain:/, "");
  try {
    return new URL(bare).hostname.replace(/^www\./, "");
  } catch {
    return bare;
  }
}
export interface ResourceRow {
  name: string;
  chips: Chip[];
  detail: string;
  syncUrl: string | null;
  unmapUrl: string | null;
  canSync: boolean;
  canUnmap: boolean;
}
export function resourceRows(
  v: IntegrationsView,
  api: string,
  now: Date,
): ResourceRow[] {
  return v.google.mapped_resources.map((m) => ({
    name: m.display_name ?? "Business Profile",
    chips: [matchChip(m.mapping_status), freshnessChip(m.sync_freshness)],
    detail: m.last_synced_at
      ? `Last synced ${ago(m.last_synced_at, now)}`
      : "Not synced yet",
    syncUrl: m.gbp_location_id
      ? `${api}integrations/google/locations/${m.gbp_location_id}/sync/`
      : null,
    unmapUrl:
      m.gbp_location_id && m.platform_resource_id
        ? `${api}locations/${m.platform_resource_id}/gbp-mapping/${m.gbp_location_id}/`
        : null,
    canSync: v.can_connect && m.gbp_location_id !== null,
    canUnmap: v.locations.some(
      (l) => l.id === m.platform_resource_id && l.can_map,
    ),
  }));
}
export interface PropertyRow {
  name: string;
  source: string;
  website: string;
  chips: Chip[];
  detail: string;
  syncUrl: string;
  canSync: boolean;
}
export function propertyRows(
  v: IntegrationsView,
  api: string,
  now: Date,
): PropertyRow[] {
  const site = (id: string | null) =>
    v.websites.find((w) => w.id === id)?.name ?? "No website chosen";
  const rows = [
    ...v.search_properties.map((p) => ({ p, source: "Search Console" })),
    ...v.analytics_properties.map((p) => ({ p, source: "Analytics" })),
  ];
  return rows.map(({ p, source }) => ({
    name: propertyName(p.external_property_id, p.display_name ?? null),
    source,
    website: site(p.website_id),
    chips: [matchChip(p.mapping_status), freshnessChip(p.freshness_status)],
    detail: p.last_synced_at
      ? `Last synced ${ago(p.last_synced_at, now)}`
      : "Not synced yet",
    syncUrl:
      source === "Analytics"
        ? `${api}insights/analytics/properties/${p.id}/sync/`
        : `${api}seo/websites/${p.website_id}/search-properties/${p.id}/sync/`,
    canSync:
      p.can_sync && p.website_id !== null && p.mapping_status === "mapped",
  }));
}
/** What a person reads when an action on this screen does not go through. */
export interface Failure {
  title: string;
  text: string;
  next: "retry" | "verify" | "refresh";
}
const failures: Record<string, Failure> = {
  AAL2_REQUIRED: {
    title: "Verify your authenticator",
    text: "This change needs a verified sign-in. Verify your authenticator, then try again.",
    next: "verify",
  },
  MFA_REQUIRED: {
    title: "Verify your authenticator",
    text: "This change needs a verified sign-in. Verify your authenticator, then try again.",
    next: "verify",
  },
  PERMISSION_DENIED: {
    title: "You do not have access",
    text: "Your role cannot make this change. Ask an administrator to do it.",
    next: "refresh",
  },
  PUBLISHING_FORMAT_UNVERIFIED: {
    title: "Blog format not checked yet",
    text: "Publishing stays paused for this repository until its blog format has been checked.",
    next: "refresh",
  },
  PUBLISHING_TARGET_EXISTS: {
    title: "A repository is already linked",
    text: "This client already has a publishing repository. Refresh to see it.",
    next: "refresh",
  },
  PUBLISHING_REPOSITORY_NOT_ACCESSIBLE: {
    title: "That repository is not available",
    text: "GitHub no longer shares it with this client. Choose another repository.",
    next: "retry",
  },
  PUBLISHING_GITHUB_NOT_CONNECTED: {
    title: "GitHub is not connected",
    text: "Connect GitHub for this client, then choose a repository.",
    next: "refresh",
  },
  PUBLISHING_REPOSITORIES_UNAVAILABLE: {
    title: "Repositories could not be loaded",
    text: "GitHub did not answer. Nothing has changed. Try again in a moment.",
    next: "retry",
  },
  PUBLISHING_IDEMPOTENCY_CONFLICT: {
    title: "That request was already used",
    text: "Close this window, reopen it and choose the repository again.",
    next: "refresh",
  },
  MUTATION_OUTCOME_UNCERTAIN: {
    title: "We could not confirm what happened",
    text: "Refresh to see the current state before trying again.",
    next: "refresh",
  },
  AUTH_REQUIRED: {
    title: "Your session ended",
    text: "Sign in again to continue.",
    next: "refresh",
  },
  OAUTH_TARGET_INVALID: {
    title: "That sign-in address was not expected",
    text: "Nothing was changed. Try again, and tell us if it keeps happening.",
    next: "retry",
  },
};
export const failureView = (code: string): Failure =>
  failures[code] ?? {
    title: "That did not go through",
    text: "Refresh to see the current state, then try again.",
    next: "retry",
  };
/** The one place a GitHub address from the API is accepted before the browser follows it. */
export function githubInstallTarget(url: string): string | null {
  try {
    const u = new URL(url);
    return u.origin === "https://github.com" && u.pathname.startsWith("/apps/")
      ? u.href
      : null;
  } catch {
    return null;
  }
}
export function googleAuthTarget(url: string): string | null {
  try {
    const u = new URL(url);
    return u.origin === "https://accounts.google.com" &&
      u.pathname === "/o/oauth2/v2/auth"
      ? u.href
      : null;
  } catch {
    return null;
  }
}
