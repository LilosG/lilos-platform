import type { ApiOutcome } from "./api-client";
import type { AdminOrganization } from "./platform-admin";

/**
 * Where a permanent-removal request stands. These are the backend's
 * `OrganizationRemovalState` values; the page chooses its wording from them,
 * never from text the API sent.
 */
export type OrganizationRemovalState =
  "requested" | "in_progress" | "completed" | "failed";

/** Body of a successful `POST /organizations/{id}/remove`. */
export type OrganizationRemoval = {
  organization: AdminOrganization;
  state: OrganizationRemovalState;
  workflow_run_id: string | null;
};

/** Body of `GET /organizations/{id}/removal`; `state` is null if none was requested. */
export type OrganizationRemovalStatus = {
  state: OrganizationRemovalState | null;
  failure_code: string | null;
  workflow_run_id: string | null;
};

/** Typed refusal codes (`OrganizationRemovalErrorCode` on the backend). */
export const REMOVAL_REQUIRES_ARCHIVED =
  "ORGANIZATION_REMOVAL_REQUIRES_ARCHIVED";
export const REMOVAL_CONFIRMATION_MISMATCH =
  "ORGANIZATION_REMOVAL_CONFIRMATION_MISMATCH";

/**
 * What a removal permanently deletes, shown in the confirmation. The wording is
 * deliberately plain: an operator is about to destroy a client's data.
 */
export const REMOVAL_DELETES: readonly string[] = [
  "Every location, review, lead, post, report and piece of content held for this client",
  "SEO crawls, analytics and Business Profile history",
  "Integration mappings, saved connections and stored sign-in tokens",
  "Uploaded photos and every other stored file",
  "Schedules, queued work and pending approvals",
];

/** What a removal leaves alone, shown in the same confirmation. */
export const REMOVAL_UNTOUCHED: readonly string[] = [
  "The client's Google Business Profile and any other provider account",
  "The client's website and its repository",
];

/** Only an archived client that has not already been removed can be removed. */
export function canRemoveOrganization(
  organization: Pick<AdminOrganization, "status" | "removed_at">,
): boolean {
  return organization.status === "archived" && !organization.removed_at;
}

/**
 * The typed confirmation matches the client name, ignoring case and
 * surrounding spaces. The server applies the same rule; this only decides
 * whether the confirm button is enabled.
 */
export function removalConfirmationMatches(
  typed: string,
  organizationName: string,
): boolean {
  const wanted = organizationName.trim().toLowerCase();
  return wanted.length > 0 && typed.trim().toLowerCase() === wanted;
}

/**
 * The message for a failed removal request, chosen from the typed error code.
 * English text from the API is never shown; an unrecognized code falls back to
 * the shared failure wording the caller supplies.
 */
export function removalFailureMessage(
  outcome: ApiOutcome<unknown>,
  fallback: string,
): string {
  if (outcome.kind === "error") {
    if (outcome.code === REMOVAL_REQUIRES_ARCHIVED) {
      return "Only a retired client can be removed. Retire it first.";
    }
    if (outcome.code === REMOVAL_CONFIRMATION_MISMATCH) {
      return "That does not match the client name. Type the name exactly as shown.";
    }
  }
  return fallback;
}

/** The message shown once a removal request has been accepted. */
export function removalProgressMessage(
  name: string,
  state: OrganizationRemovalState,
): string {
  return state === "completed"
    ? `${name} has been removed.`
    : `Removing ${name}. Its data is being deleted and it will leave this list when that finishes.`;
}

/** A removal has finished once the organization carries its removal time. */
export function isRemovalComplete(
  organization: Pick<AdminOrganization, "removed_at">,
): boolean {
  return Boolean(organization.removed_at);
}

/** A removal the worker is still carrying out (or about to). */
export function isRemovalPending(
  state: OrganizationRemovalState | null | undefined,
): boolean {
  return state === "requested" || state === "in_progress";
}

/**
 * What to tell the operator when the worker could not finish a removal, chosen
 * from the worker's typed failure code. API text is never shown.
 */
export function removalFailedMessage(
  name: string,
  code: string | null | undefined,
): string {
  const retry = "Nothing further is deleted until you try again.";
  switch (code) {
    case "ORGANIZATION_REMOVAL_STORAGE_UNAVAILABLE":
      return `Removing ${name} stopped because file storage could not be reached. ${retry}`;
    case "ORGANIZATION_REMOVAL_WAITING_FOR_ACTIVE_JOBS":
      return `Removing ${name} stopped because work for this client was still running. ${retry}`;
    case "ORGANIZATION_REMOVAL_BLOCKED_BY_PROTECTED_HISTORY":
    case "ORGANIZATION_REMOVAL_BLOCKED":
    case "ORGANIZATION_REMOVAL_STALLED":
      return `Removing ${name} stopped because some of its records could not be deleted. ${retry} If it fails again, contact engineering.`;
    default:
      return `Removing ${name} did not finish. ${retry}`;
  }
}
