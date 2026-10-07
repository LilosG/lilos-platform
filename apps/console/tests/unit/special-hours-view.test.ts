import { describe, it, expect } from "vitest";
import { hoursRows } from "../../src/lib/gbp-view";
import { hoursState } from "../../src/lib/status";
import type { GbpSpecialHours } from "../../src/adapters/gbp";

const item = (over: Partial<GbpSpecialHours>): GbpSpecialHours => ({
  id: "11111111-1111-4111-8111-111111111111",
  service_date: "2026-12-25",
  revision: 1,
  closed: false,
  periods: [{ opens: "09:00", closes: "17:00" }],
  source: "console",
  status: "approved",
  safe_error_code: null,
  verified_at: null,
  ...over,
});
const row = (over: Partial<GbpSpecialHours>, canApprove = true) =>
  hoursRows([item(over)], canApprove)[0];

describe("special hours states", () => {
  it("maps every status to one of the four states a person sees", () => {
    const label = (status: string) => row({ status }).chip.label;
    expect(label("awaiting_approval")).toBe("Awaiting approval");
    expect(label("approved")).toBe("Publishing");
    expect(label("publishing")).toBe("Publishing");
    expect(label("published")).toBe("Live on Google");
    expect(label("failed")).toBe("Needs attention");
    expect(label("reconciliation_required")).toBe("Needs attention");
  });

  it("treats a status it does not know as needing attention, never as live", () => {
    expect(hoursState("something_new")).toBe("needs_attention");
  });

  it("hides dates that a newer approved revision replaced", () => {
    expect(hoursRows([item({ status: "superseded" })], true)).toEqual([]);
  });

  it("confirms a live date only when Google confirmed it", () => {
    expect(
      row({ status: "published", verified_at: "2026-10-02T15:30:00Z" }).note,
    ).toMatch(/^Confirmed on Google \w+ \d+, 2026$/);
    expect(row({ status: "published", verified_at: null }).note).toBe("");
  });

  it("gives a failed date a clear next step and a retry, with no raw code", () => {
    const failed = row({
      status: "failed",
      safe_error_code: "WRITE_NOT_ENABLED",
    });
    expect(failed.nextStep).toBe(
      "Editing is not turned on for this location. Turn it on in Integrations, then try again.",
    );
    expect(failed.actions).toEqual(["retry"]);
    expect(failed.nextStep).not.toMatch(/WRITE_NOT_ENABLED|[A-Z]+_[A-Z]+/);
  });

  it("explains an unconfirmed write and offers to check it again", () => {
    const unconfirmed = row({
      status: "reconciliation_required",
      safe_error_code: "VERIFICATION_CONTENT_MISMATCH",
    });
    expect(unconfirmed.nextStep).toMatch(/Try again to check/);
    expect(unconfirmed.actions).toEqual(["retry"]);
  });

  it("explains Google refusing a request and an unknown code in plain words", () => {
    expect(
      row({ status: "failed", safe_error_code: "PROVIDER_REJECTED_400" })
        .nextStep,
    ).toBe(
      "Google did not accept these hours. Check the date and times, then try again.",
    );
    expect(
      row({ status: "failed", safe_error_code: "BRAND_NEW_CODE" }).nextStep,
    ).toMatch(/^Something went wrong sending these hours to Google\./);
  });

  it("offers no retry for a date that passed, only the reason", () => {
    const passed = row({
      status: "failed",
      safe_error_code: "SERVICE_DATE_PASSED",
    });
    expect(passed.actions).toEqual([]);
    expect(passed.retryable).toBe(false);
    expect(passed.nextStep).toMatch(/passed before it was sent/);
  });

  it("offers no actions without a verified authenticator, but still says what to do", () => {
    const blocked = row(
      { status: "failed", safe_error_code: "WRITE_NOT_ENABLED" },
      false,
    );
    expect(blocked.actions).toEqual([]);
    expect(blocked.retryable).toBe(true);
    expect(blocked.nextStep).not.toBe("");
  });

  it("shows no next step for a date that is fine", () => {
    for (const status of ["awaiting_approval", "approved", "published"]) {
      expect(row({ status }).nextStep).toBe("");
    }
  });
});
