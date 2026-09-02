import { describe, expect, it } from "vitest";
import { describeFailure } from "./errors";

/**
 * The backend distinguishes six causes of a refusal and says what to do about
 * each. The transport discarded the 403 body and this function printed one
 * canned sentence, so every cause reached the operator identically — an
 * unactivated client read the same as a missing role, and the only way to act
 * on either was to guess.
 */
describe("refusals name their cause", () => {
  it("surfaces an unactivated client instead of a generic refusal", () => {
    expect(
      describeFailure(
        {
          kind: "forbidden",
          code: "ORGANIZATION_NOT_ACTIVE",
          message:
            "This client is not active yet. Finish onboarding activation before connecting providers or running product work.",
        },
        "Business profile",
      ),
    ).toBe(
      "Business profile: This client is not active yet. Finish onboarding activation before connecting providers or running product work.",
    );
  });

  it("surfaces a product that was never enabled", () => {
    expect(
      describeFailure({
        kind: "forbidden",
        code: "PRODUCT_NOT_ENABLED",
        message:
          "The product this action belongs to is not enabled for this client. Enable it in Administration, then try again.",
      }),
    ).toContain("Enable it in Administration");
  });

  it("surfaces a required step-up", () => {
    expect(
      describeFailure({
        kind: "forbidden",
        code: "STEP_UP_REQUIRED",
        message:
          "This action requires stronger authentication. Sign in again with multi-factor authentication.",
      }),
    ).toContain("multi-factor authentication");
  });

  it("keeps the canned sentence for the non-disclosing generic denial", () => {
    // AUTHORIZATION_DENIED is deliberately opaque — it is what a non-member
    // sees, so that probing organization ids reveals nothing. Its own message
    // ("Authorization is required for this action.") is vaguer than the canned
    // line, so the canned line wins.
    expect(
      describeFailure({
        kind: "forbidden",
        code: "AUTHORIZATION_DENIED",
        message: "Authorization is required for this action.",
      }),
    ).toBe("You do not have permission to view this.");
  });

  it("falls back when the refusal carries nothing at all", () => {
    expect(describeFailure({ kind: "forbidden" }, "Domains")).toBe(
      "Domains: You do not have permission to view this.",
    );
  });

  it("ignores a code that arrives with an empty message", () => {
    expect(
      describeFailure({
        kind: "forbidden",
        code: "PERMISSION_NOT_GRANTED",
        message: "   ",
      }),
    ).toBe("You do not have permission to view this.");
  });
});

describe("other outcomes keep their existing language", () => {
  it("reports a missing resource", () => {
    expect(describeFailure({ kind: "not-found" }, "Website")).toBe(
      "Website: The requested resource could not be found.",
    );
  });

  it("reports an expired session", () => {
    expect(describeFailure({ kind: "unauthenticated" })).toBe(
      "Your session has expired. Sign in again.",
    );
  });

  it("distinguishes an operation timeout from an unreachable API", () => {
    expect(
      describeFailure(
        { kind: "timeout", timeoutMs: 90_000 },
        "Search Console sync",
      ),
    ).toBe(
      "Search Console sync: The platform API did not finish within 90 seconds.",
    );
  });

  it("prefers field-level validation detail over the envelope message", () => {
    expect(
      describeFailure({
        kind: "error",
        status: 422,
        code: "VALIDATION_FAILED",
        message: "The request failed.",
        details: [
          {
            field: "intent",
            message: "Content goal must be 500 characters or fewer.",
          },
        ],
      }),
    ).toBe("Content goal must be 500 characters or fewer.");
  });

  it("returns nothing for a success", () => {
    expect(describeFailure({ kind: "ok", data: {} })).toBe("");
  });
});
