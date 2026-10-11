import type {
  OrganizationRecord,
  OrganizationStatus,
  RemovalRecord,
} from "../adapters/administration";
import { organizationChip, removalChips, type Chip } from "./status";
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
