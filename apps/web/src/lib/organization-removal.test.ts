import { describe, expect, it } from "vitest";

import type { ApiOutcome } from "./api-client";
import {
  REMOVAL_CONFIRMATION_MISMATCH,
  REMOVAL_DELETES,
  REMOVAL_REQUIRES_ARCHIVED,
  REMOVAL_UNTOUCHED,
  canRemoveOrganization,
  isRemovalComplete,
  isRemovalPending,
  removalFailedMessage,
  removalConfirmationMatches,
  removalFailureMessage,
  removalProgressMessage,
} from "./organization-removal";

function failure(
  code: string,
  message = "English text from the API",
): ApiOutcome<never> {
  return { kind: "error", status: 409, code, message, details: [] };
}

describe("canRemoveOrganization", () => {
  it("is offered only for an archived client that has not been removed", () => {
    expect(
      canRemoveOrganization({ status: "archived", removed_at: null }),
    ).toBe(true);
    expect(canRemoveOrganization({ status: "archived" })).toBe(true);
    expect(
      canRemoveOrganization({
        status: "archived",
        removed_at: "2026-10-06T00:00:00Z",
      }),
    ).toBe(false);
    for (const status of [
      "prospect",
      "onboarding",
      "active",
      "paused",
      "suspended",
      "offboarding",
    ] as const) {
      expect(canRemoveOrganization({ status, removed_at: null })).toBe(false);
    }
  });
});

describe("removalConfirmationMatches", () => {
  it("matches the typed name ignoring case and surrounding spaces", () => {
    expect(
      removalConfirmationMatches("  wheyland ELECTRIC ", "Wheyland Electric"),
    ).toBe(true);
  });

  it("rejects anything that is not the whole name", () => {
    expect(removalConfirmationMatches("Wheyland", "Wheyland Electric")).toBe(
      false,
    );
    expect(removalConfirmationMatches("", "Wheyland Electric")).toBe(false);
    expect(removalConfirmationMatches("anything", "   ")).toBe(false);
  });
});

describe("removalFailureMessage", () => {
  it("chooses the message from the typed code, never from API text", () => {
    const requiresArchived = removalFailureMessage(
      failure(REMOVAL_REQUIRES_ARCHIVED),
      "fallback",
    );
    const mismatch = removalFailureMessage(
      failure(REMOVAL_CONFIRMATION_MISMATCH),
      "fallback",
    );
    expect(requiresArchived).toMatch(/retire/i);
    expect(mismatch).toMatch(/name/i);
    expect(requiresArchived).not.toContain("English text");
    expect(mismatch).not.toContain("English text");
  });

  it("falls back for any other outcome", () => {
    expect(removalFailureMessage(failure("SOMETHING_ELSE"), "fallback")).toBe(
      "fallback",
    );
    expect(removalFailureMessage({ kind: "disconnected" }, "fallback")).toBe(
      "fallback",
    );
  });
});

describe("removal wording", () => {
  it("says what is deleted and what is left alone", () => {
    expect(REMOVAL_DELETES.length).toBeGreaterThan(0);
    expect(REMOVAL_UNTOUCHED.join(" ")).toMatch(/provider/i);
    expect(REMOVAL_UNTOUCHED.join(" ")).toMatch(/website/i);
  });

  it("shows a Removing state until the removal completes", () => {
    expect(removalProgressMessage("Acme", "requested")).toMatch(
      /^Removing Acme/,
    );
    expect(removalProgressMessage("Acme", "in_progress")).toMatch(
      /^Removing Acme/,
    );
    expect(removalProgressMessage("Acme", "completed")).toBe(
      "Acme has been removed.",
    );
  });

  it("treats a removal time as completion", () => {
    expect(isRemovalComplete({ removed_at: "2026-10-06T00:00:00Z" })).toBe(
      true,
    );
    expect(isRemovalComplete({ removed_at: null })).toBe(false);
    expect(isRemovalComplete({})).toBe(false);
  });
});

describe("failed removals", () => {
  it("tells pending states from finished ones", () => {
    expect(isRemovalPending("requested")).toBe(true);
    expect(isRemovalPending("in_progress")).toBe(true);
    expect(isRemovalPending("failed")).toBe(false);
    expect(isRemovalPending("completed")).toBe(false);
    expect(isRemovalPending(null)).toBe(false);
  });

  it("explains a failure from the typed code and invites a retry", () => {
    const storage = removalFailedMessage(
      "Acme",
      "ORGANIZATION_REMOVAL_STORAGE_UNAVAILABLE",
    );
    const blocked = removalFailedMessage(
      "Acme",
      "ORGANIZATION_REMOVAL_BLOCKED",
    );
    const unknown = removalFailedMessage("Acme", "SOMETHING_NEW");
    expect(storage).toMatch(/storage/i);
    expect(blocked).toMatch(/could not be deleted/i);
    for (const message of [storage, blocked, unknown]) {
      expect(message).toMatch(/try again/i);
      expect(message).not.toMatch(/ORGANIZATION_REMOVAL|SOMETHING_NEW/);
    }
    expect(removalFailedMessage("Acme", null)).toMatch(/did not finish/i);
  });
});
