import type { ApiOutcome } from "./api-client";
import type { AdminOrganization } from "./platform-admin";

/**
 * Where a permanent-removal request stands. These are the backend's
 * `OrganizationRemovalState` values; the page chooses its wording from them,
 * never from text the API sent.
 */
export type OrganizationRemovalState =
  "requested" | "in_progress" | "completed";

/** Body of a successful `POST /organizations/{id}/remove`. */
export type OrganizationRemoval = {
  organization: AdminOrganization;
  state: OrganizationRemovalState;
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
