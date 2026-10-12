import type {
  DeadLetterReason,
  HealthState,
  OnboardingBlocker,
  OnboardingRecord,
  OrganizationRecord,
  OrganizationStatus,
  PersonRecord,
  RemovalRecord,
  SystemRecord,
  SystemRole,
  UserAccess,
} from "../adapters/administration";
import { clientRoute } from "../config/routes";
import { ago, dateText, runTime } from "./present";
import {
  healthChips,
  onboardingChips,
  organizationChip,
  personChips,
  removalChips,
  type Chip,
  type PersonState,
} from "./status";
/** What the one action on a client's row does. */
export type OrganizationAction = "start_offboarding" | "archive" | "remove";
const LIVE: readonly OrganizationStatus[] = [
  "prospect",
  "onboarding",
  "active",
  "paused",
  "suspended",
];
/**
 * The single next step for a client, or none. Offboarding leads to archive and an archived
 * client to the removal of its data; nothing is offered that the API will refuse.
 */
export function nextAction(
  status: OrganizationStatus,
  removal: RemovalRecord | null,
): OrganizationAction | null {
  if (LIVE.includes(status)) return "start_offboarding";
  if (status === "offboarding") return "archive";
  if (status !== "archived") return null;
  if (removal === null || removal.state === null || removal.state === "failed")
    return "remove";
  return null;
}
export interface OrganizationRow {
  id: string;
  name: string;
  /** The client's website host, as a short line under the name. */
  site: string | null;
  /** A count, or null when it could not be read: never shown as 0. */
  locations: number | null;
  chip: Chip;
  removalChip: Chip | null;
  removalNote: string | null;
  /** The removal is still running, so its chip follows it. */
  removalRunning: boolean;
  action: OrganizationAction | null;
  actionLabel: string;
  version: number;
}
const ACTION_LABELS: Record<OrganizationAction, string> = {
  start_offboarding: "Start offboarding",
  archive: "Archive",
  remove: "Remove data permanently",
};
const hostOf = (url: string | null): string | null => {
  if (!url) return null;
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return null;
  }
};
export function organizationRows(
  organizations: OrganizationRecord[],
  locationCounts: Map<string, number | null>,
  removals: Map<string, RemovalRecord | null>,
): OrganizationRow[] {
  return organizations.map((org) => {
    const removal = removals.get(org.id) ?? null;
    const action = nextAction(org.status, removal);
    const failed = removal?.state === "failed";
    return {
      id: org.id,
      name: org.name,
      site: hostOf(org.website_url),
      locations: locationCounts.get(org.id) ?? null,
      chip: organizationChip(org.status),
      removalChip: removal?.state ? removalChips[removal.state] : null,
      removalNote: failed ? removalFailureText(removal.failure_code) : null,
      removalRunning:
        removal?.state === "requested" || removal?.state === "in_progress",
      action,
      actionLabel:
        action === "remove" && failed
          ? "Try removal again"
          : action
            ? ACTION_LABELS[action]
            : "",
      version: org.version,
    };
  });
}
/** What a failed removal means and what to do next; the code is the worker's, the words are ours. */
export function removalFailureText(code: string | null): string {
  switch (code) {
    case "ORGANIZATION_REMOVAL_FAILED":
    case null:
      return "The removal stopped before it finished. Nothing more was deleted. Try again; if it fails again, contact engineering with this client's name.";
    default:
      return "The removal stopped before it finished, and the system gave a reason this screen does not recognize. Try again; if it fails again, contact engineering with this client's name.";
  }
}
export interface ConfirmCopy {
  title: string;
  lines: string[];
  accept: string;
  dismiss?: string;
  /** The exact name the person must type before the action is allowed. */
  typedName: string | null;
  tone: "normal" | "danger";
}
/** Exactly what will happen, in the words of the dialog that asks first. */
export function confirmCopy(
  action: OrganizationAction,
  name: string,
): ConfirmCopy {
  if (action === "start_offboarding")
    return {
      title: `Start offboarding ${name}?`,
      lines: [
        `${name} leaves the client switcher and every client list. Nothing is deleted.`,
        "Archive it next to finish retiring the client.",
      ],
      accept: "Start offboarding",
      typedName: null,
      tone: "normal",
    };
  if (action === "archive")
    return {
      title: `Archive ${name}?`,
      lines: [
        "This cannot be undone. An archived client cannot be brought back from this screen.",
        "Its records are kept until you remove its data permanently.",
      ],
      accept: "Archive client",
      typedName: null,
      tone: "danger",
    };
  return {
    title: `Remove ${name}'s data permanently?`,
    lines: [
      "This deletes everything stored for this client — locations, reviews, content, reports and connections. It cannot be undone.",
      "Only a minimal record that the client existed is kept for the audit trail.",
    ],
    accept: "Remove data permanently",
    typedName: name,
    tone: "danger",
  };
}
const FAILURES: Record<string, string> = {
  ONBOARDING_INCOMPLETE:
    "Setup is not complete any more. Refresh to see what is still needed.",
  NO_PRIMARY_DOMAIN:
    "This client has no primary website address yet. Add one, then activate.",
  INVITATION_VERSION_CONFLICT:
    "This invitation changed since you opened the page. Refresh to see its current state.",
  INVITATION_CONFLICT:
    "This invitation was already answered or cancelled. Refresh to see its current state.",
  INVITATION_NOT_FOUND: "This invitation no longer exists. Refresh the page.",
  ACCESS_PARENT_STATE_CONFLICT:
    "Invitations cannot be changed for this client in its current state.",
  ORGANIZATION_REMOVAL_REQUIRES_ARCHIVED:
    "Only an archived client can have its data removed. Archive it first.",
  ORGANIZATION_REMOVAL_CONFIRMATION_MISMATCH:
    "The name you typed does not match this client. Type it exactly as shown.",
  ORGANIZATION_VERSION_CONFLICT:
    "This client changed since you opened the page. Refresh to see its current state.",
  ORGANIZATION_TRANSITION_CONFLICT:
    "That step is not available for this client any more. Refresh to see its current state.",
  ORGANIZATION_NOT_FOUND: "This client no longer exists. Refresh the page.",
  AUTHORIZATION_DENIED:
    "Only a verified platform administrator can do this. Verify your authenticator, then try again.",
  DATABASE_INTEGRITY_CONFLICT:
    "Another request changed this client at the same moment. Refresh and try again.",
  MUTATION_OUTCOME_UNCERTAIN:
    "We could not confirm what happened. Refresh to see the client's current state.",
  AUTH_REQUIRED: "Your session ended. Sign in again to continue.",
  CSRF_INVALID: "Your session expired. Refresh the page and try again.",
};
export const administrationFailureText = (code: string): string =>
  FAILURES[code] ??
  "That did not go through. Refresh to see the current state, then try again.";

// ---- Onboarding ----

/** Clients that are not live yet: a prospect has not started, an onboarding client is mid-way. */
export const isOnboarding = (status: OrganizationStatus): boolean =>
  status === "prospect" || status === "onboarding";

type FixArea = "settings" | "integrations";
/**
 * What each stable control means to a person, and which console screen clears it. The API names
 * a control and a legacy route; the words and the destination are ours. A control with no
 * console screen yet has no destination and says so, rather than linking to a page that cannot
 * fix it.
 */
const BLOCKERS: Record<string, { label: string; area: FixArea | null }> = {
  "organization-profile": { label: "Create the business profile", area: null },
  locations: { label: "Add or finish a location", area: "settings" },
  "location-profile": {
    label: "Finish a location's profile",
    area: "settings",
  },
  "business-facts": { label: "Confirm the business details", area: "settings" },
  "website-domain": { label: "Add the website address", area: null },
  industry: { label: "Choose the industry", area: null },
  services: { label: "Choose the services offered", area: null },
  users: { label: "Give someone access", area: null },
  products: { label: "Choose the products", area: null },
  configuration: { label: "Finish the product settings", area: null },
  "approval-policy": { label: "Set how changes are approved", area: null },
  "runtime-controls": {
    label: "Review what may run automatically",
    area: null,
  },
  connections: { label: "Connect the missing accounts", area: "integrations" },
  activate: { label: "Finish the remaining setup", area: null },
};
const UNKNOWN_BLOCKER = { label: "Finish a setup step", area: null };

export interface BlockerRow {
  label: string;
  /** Where it is fixed in the console, or none yet. */
  href: string | null;
  hrefLabel: string | null;
}
export function blockerRows(
  blockers: OnboardingBlocker[],
  slug: string,
): BlockerRow[] {
  const seen = new Set<string>();
  const rows: BlockerRow[] = [];
  for (const blocker of blockers) {
    if (seen.has(blocker.control)) continue;
    seen.add(blocker.control);
    const known = BLOCKERS[blocker.control] ?? UNKNOWN_BLOCKER;
    rows.push({
      label: known.label,
      href:
        known.area === "settings"
          ? clientRoute(slug, "Settings")
          : known.area === "integrations"
            ? clientRoute(slug, "Integrations")
            : null,
      hrefLabel:
        known.area === "settings"
          ? "Open settings"
          : known.area === "integrations"
            ? "Open integrations"
            : null,
    });
  }
  return rows;
}

export interface OnboardingRow {
  id: string;
  name: string;
  site: string | null;
  chip: Chip;
  /** Ready to activate, or could not be loaded; absent while setup is simply under way. */
  readiness: Chip | null;
  /** A percentage, or null when it is unknown or not started: never shown as 0%. */
  percent: number | null;
  blockers: BlockerRow[];
  canActivate: boolean;
  version: number;
  /** The state could not be read, so the row offers a retry instead of a guess. */
  unavailable: boolean;
  note: string | null;
}
/** `states` holds a client's readiness, or null when it could not be read. */
export function onboardingRows(
  organizations: OrganizationRecord[],
  states: Map<string, OnboardingRecord | null>,
): OnboardingRow[] {
  return organizations
    .filter((org) => isOnboarding(org.status))
    .map((org) => {
      const base = {
        id: org.id,
        name: org.name,
        site: hostOf(org.website_url),
        chip: organizationChip(org.status),
        version: org.version,
      };
      if (org.status === "prospect")
        return {
          ...base,
          readiness: onboardingChips.not_started,
          percent: null,
          blockers: [],
          canActivate: false,
          unavailable: false,
          note: "Onboarding has not started for this client yet.",
        };
      const state = states.get(org.id) ?? null;
      if (!state)
        return {
          ...base,
          readiness: onboardingChips.unavailable,
          percent: null,
          blockers: [],
          canActivate: false,
          unavailable: true,
          note: "We could not read this client's setup, so nothing is shown rather than a guess.",
        };
      return {
        ...base,
        version: state.version,
        readiness: state.activation_eligible ? onboardingChips.ready : null,
        percent: state.progress_percent,
        blockers: blockerRows(state.blockers, org.slug),
        canActivate: state.activation_eligible,
        unavailable: false,
        note: state.activation_eligible
          ? "Everything needed is in place."
          : state.blockers.length === 0
            ? "Setup is still under way."
            : null,
      };
    });
}

export const activateConfirm = (name: string): ConfirmCopy => ({
  title: `Activate ${name}?`,
  lines: [
    `${name} becomes an active client and its first website crawl starts.`,
    "This is recorded in the audit trail.",
  ],
  accept: "Activate client",
  typedName: null,
  tone: "normal",
});

// ---- Users ----

const ROLE_LABELS: Record<SystemRole, string> = {
  organization_owner: "Owner",
  organization_admin: "Admin",
  organization_manager: "Manager",
  organization_member: "Member",
  organization_viewer: "Viewer",
};
const ROLE_ORDER = Object.keys(ROLE_LABELS) as SystemRole[];
const SHOWN_CLIENTS = 3;

export interface PendingInvitationRow {
  invitationId: string;
  organizationId: string;
  client: string;
  version: number;
  expires: string;
}
export interface PersonRow {
  id: string;
  name: string;
  email: string | null;
  roles: string;
  clients: { name: string; chip: Chip | null }[];
  /** Clients beyond the ones listed. */
  moreClients: number;
  chip: Chip;
  invitations: PendingInvitationRow[];
}
const accessChip = (access: UserAccess): Chip | null =>
  access.membership_status === "active"
    ? null
    : access.membership_status === "invited"
      ? personChips.invited
      : personChips.suspended;
export function personState(person: PersonRecord): PersonState {
  if (person.status === "deactivated") return "deactivated";
  const states = person.access.map((a) => a.membership_status);
  if (states.includes("active") || person.platform_administrator)
    return "active";
  if (states.includes("invited")) return "invited";
  if (states.includes("suspended")) return "suspended";
  return "no_access";
}
export function roleText(person: PersonRecord): string {
  const roles = new Set<SystemRole>(person.access.flatMap((a) => a.roles));
  const labels = ROLE_ORDER.filter((role) => roles.has(role)).map(
    (role) => ROLE_LABELS[role],
  );
  if (person.platform_administrator) labels.unshift("Platform administrator");
  return labels.length ? labels.join(", ") : "No role yet";
}
export function personRows(people: PersonRecord[]): PersonRow[] {
  return people.map((person) => ({
    id: person.id,
    name: person.display_name ?? person.email ?? "Unnamed person",
    email: person.display_name ? person.email : null,
    roles: roleText(person),
    clients: person.access
      .slice(0, SHOWN_CLIENTS)
      .map((a) => ({ name: a.organization_name, chip: accessChip(a) })),
    moreClients: Math.max(0, person.access_total - SHOWN_CLIENTS),
    chip: personChips[personState(person)],
    invitations: person.access.flatMap((a) =>
      a.invitation
        ? [
            {
              invitationId: a.invitation.id,
              organizationId: a.organization_id,
              client: a.organization_name,
              version: a.invitation.version,
              expires: dateText(a.invitation.expires_at),
            },
          ]
        : [],
    ),
  }));
}
export const cancelInvitationConfirm = (
  person: string,
  client: string,
): ConfirmCopy => ({
  title: `Cancel ${person}'s invitation?`,
  lines: [
    `${person} will no longer be able to join ${client} with this invitation.`,
    "Their access to other clients does not change.",
  ],
  accept: "Cancel invitation",
  dismiss: "Keep invitation",
  typedName: null,
  tone: "normal",
});
/** Previous and next pages of people; a link is absent when there is no such page. */
export function userPaging(
  offset: number,
  nextOffset: number | null,
  size: number,
): { previous: string | null; next: string | null } {
  const at = (value: number) =>
    value <= 0
      ? "/administration/users/"
      : `/administration/users/?offset=${value}`;
  return {
    previous: offset > 0 ? at(offset - size) : null,
    next: nextOffset === null ? null : at(nextOffset),
  };
}

// ---- Platform / system ----

export type ComponentKey =
  "database" | "scheduler" | "queue" | "runs" | "integrations";
export interface ComponentRow {
  key: ComponentKey;
  name: string;
  chip: Chip;
  sentence: string;
  /** The row opens the details dialog. */
  details: boolean;
  /** The row sends the person to Integrations. */
  integrations: boolean;
}
const plural = (n: number, one: string, many: string) =>
  `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
const REASON_TEXT: Record<DeadLetterReason, string> = {
  permanent_failure: "Failed for good",
  retries_exhausted: "Ran out of retries",
  lease_expired: "The worker stopped responding",
  timed_out: "Took too long",
  outcome_uncertain: "The outcome could not be confirmed",
  unrecorded: "No reason was recorded",
};
export const deadLetterReasonText = (reason: DeadLetterReason): string =>
  REASON_TEXT[reason];
const row = (
  key: ComponentKey,
  name: string,
  state: HealthState,
  sentence: string,
  extra: Partial<Pick<ComponentRow, "details" | "integrations">> = {},
): ComponentRow => ({
  key,
  name,
  chip: healthChips[state],
  sentence,
  details: false,
  integrations: false,
  ...extra,
});
export function componentRows(system: SystemRecord): ComponentRow[] {
  const { scheduler, queue, failed_runs, integrations } = system;
  const waiting = queue.backlogged === true;
  const given = queue.dead_letter_count ?? 0;
  return [
    row(
      "database",
      "Database",
      system.database,
      system.database === "healthy"
        ? "The database is reachable."
        : system.database === "attention"
          ? "The database is not responding."
          : "We could not check the database.",
    ),
    row(
      "scheduler",
      "Scheduled work",
      scheduler.status,
      scheduler.status === "unknown"
        ? "We could not check the schedule."
        : scheduler.overdue
          ? "Scheduled work is running late."
          : scheduler.active_schedules === 0
            ? "No scheduled work is set up yet."
            : "Scheduled work is being dispatched on time.",
      { details: scheduler.status !== "unknown" },
    ),
    row(
      "queue",
      "Background work",
      queue.status,
      queue.status === "unknown"
        ? "We could not check the work queue."
        : given > 0 && waiting
          ? `${plural(given, "job gave up", "jobs gave up")} after failing, and due work is waiting longer than expected.`
          : given > 0
            ? `${plural(given, "job gave up", "jobs gave up")} after failing.`
            : waiting
              ? "Due work is waiting longer than expected."
              : "Nothing has given up and nothing is waiting too long.",
      { details: queue.status !== "unknown" },
    ),
    row(
      "runs",
      "Workflow runs",
      failed_runs.status,
      failed_runs.failed_last_24h === null
        ? "We could not check recent workflow runs."
        : failed_runs.failed_last_24h > 0
          ? `${plural(failed_runs.failed_last_24h, "workflow run", "workflow runs")} failed in the last 24 hours.`
          : "No workflow runs failed in the last 24 hours.",
    ),
    row(
      "integrations",
      "Integrations",
      integrations.status,
      integrations.needing_attention === null
        ? "We could not check the connections."
        : integrations.needing_attention > 0
          ? `${plural(integrations.needing_attention, "connection needs", "connections need")} attention.`
          : "Every connection is working.",
      { integrations: integrations.status === "attention" },
    ),
  ];
}
export interface SystemDetails {
  checked: string;
  lastDispatch: string | null;
  oldestWaiting: string | null;
  reasons: { text: string; count: number }[];
}
/** The technical facts, formatted for the details dialog and nowhere else. */
export function systemDetails(system: SystemRecord, now: Date): SystemDetails {
  return {
    checked: ago(system.evaluated_at, now),
    lastDispatch: system.scheduler.last_dispatch_at
      ? runTime(system.scheduler.last_dispatch_at, now)
      : null,
    oldestWaiting: system.queue.oldest_pending_at
      ? ago(system.queue.oldest_pending_at, now)
      : null,
    reasons: system.queue.groups.map((group) => ({
      text: REASON_TEXT[group.reason],
      count: group.count,
    })),
  };
}
