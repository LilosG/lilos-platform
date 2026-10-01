import { describe, expect, it, vi } from "vitest";
import fixtures from "../fixtures/phase3.json";
import {
  adaptReviews,
  adaptReviewDetail,
  metric,
} from "../../src/adapters/reviews";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
import { reviewFailure } from "../../src/lib/review-actions";
const org = fixtures.workspace.organization_id,
  loc = fixtures.workspace.location_id;
const settings = {
  origin: "https://console.test",
  apiOrigin: "https://api.test",
  supabaseUrl: "https://auth.test",
  supabaseKey: "key",
  csrfSecret: "x".repeat(32),
  local: false,
};
const locals = {
  settings,
  userId: org,
  token: "server-only",
  binding: "binding",
  csrf: "",
  correlationId: "reviews-test",
  auth: {} as App.Locals["auth"],
};
describe("Reviews authoritative adapter", () => {
  it("preserves zero, missing, stale, partial and reconnect", () => {
    const view = adaptReviews(fixtures.workspace, org, loc);
    expect(view.source?.connection_status).toBe("reconnect_required");
    expect(view.source?.freshness).toBe("stale");
    expect(view.source?.quality).toBe("partial");
    expect(metric(null)).toBe("Unavailable");
    expect(metric(0)).toBe("0");
    expect(
      adaptReviews(
        { ...fixtures.workspace, inventory_count: null, items: [] },
        org,
      ).inventory_count,
    ).toBeNull();
    expect(
      adaptReviews(
        { ...fixtures.workspace, inventory_count: 0, items: [] },
        org,
      ).inventory_count,
    ).toBe(0);
  });
  it("rejects substituted tenant, location, review and unknown response states", () => {
    expect(() => adaptReviews(fixtures.workspace, loc)).toThrow();
    expect(() => adaptReviews(fixtures.workspace, org, org)).toThrow();
    expect(() =>
      adaptReviewDetail(fixtures.detail, org, org, fixtures.detail.review.id),
    ).toThrow();
    expect(() =>
      adaptReviewDetail(
        {
          ...fixtures.detail,
          responses: [{ ...fixtures.detail.responses[0], status: "done" }],
        },
        org,
        loc,
        fixtures.detail.review.id,
      ),
    ).toThrow();
  });
  it("keeps exact revision, policy, queued/published/read-back/failure/history distinct", () => {
    for (const state of [
      "publishing",
      "published",
      "reconciliation_required",
      "failed",
      "superseded",
    ]) {
      const view = adaptReviewDetail(
        {
          ...fixtures.detail,
          responses: [
            {
              ...fixtures.detail.responses[0],
              status: state,
              workflow_status: "retry_scheduled",
              safe_error_code: "VERIFICATION_REREAD_FAILED",
            },
          ],
        },
        org,
        loc,
        fixtures.detail.review.id,
      );
      expect(view.responses[0].status).toBe(state);
      expect(view.responses[0].published_at).toBeNull();
      expect(view.responses[0].history).toHaveLength(1);
    }
    const provider = adaptReviewDetail(
      {
        ...fixtures.detail,
        responses: [
          {
            ...fixtures.detail.responses[0],
            generated_by: "imported",
            approval_required: false,
            policy_code: "provider_observation_no_local_approval",
          },
        ],
      },
      org,
      loc,
      fixtures.detail.review.id,
    );
    expect(provider.responses[0].approval_required).toBe(false);
  });
});
describe("Reviews closed BFF", () => {
  it("allows UUID reads, rejects invalid/duplicate location and foreign query keys", async () => {
    const path = `organizations/${org}/command-center/reviews/`;
    for (const query of [
      "location_id=oops",
      `location_id=${loc}&location_id=${loc}`,
      "url=https://evil.test",
      "limit=50",
    ]) {
      const fetcher = vi.fn();
      const r = await forward(
        new Request(settings.origin + "/api/" + path + "?" + query),
        path,
        locals,
        fetcher,
      );
      expect(r.status).toBe(400);
      expect(fetcher).not.toHaveBeenCalled();
    }
  });
  it("allows canonical body only, enforces CSRF and no-store, rejects unsupported retries", async () => {
    const path = `organizations/${org}/locations/${loc}/reviews/${fixtures.detail.review.id}/responses/${org}/publish/`;
    const headers = {
      "Content-Type": "application/json",
      Origin: settings.origin,
      "X-CSRF-Token": csrfToken(
        locals.binding,
        locals.userId,
        settings.csrfSecret,
      ),
    };
    const fetcher = vi.fn(
      async () =>
        new Response(JSON.stringify({ data: { status: "publishing" } }), {
          status: 202,
          headers: { "Content-Type": "application/json", "Set-Cookie": "bad" },
        }),
    );
    const r = await forward(
      new Request(settings.origin + "/api/" + path, {
        method: "POST",
        headers,
        body: JSON.stringify({ idempotency_key: "exact-revision-key" }),
      }),
      path,
      locals,
      fetcher,
    );
    expect(r.status).toBe(202);
    expect(r.headers.get("Cache-Control")).toBe("private, no-store");
    expect(r.headers.has("Set-Cookie")).toBe(false);
    for (const body of [
      { idempotency_key: "exact-revision-key", approved: true },
      {},
    ])
      expect(
        (
          await forward(
            new Request(settings.origin + "/api/" + path, {
              method: "POST",
              headers,
              body: JSON.stringify(body),
            }),
            path,
            locals,
            fetcher,
          )
        ).status,
      ).toBe(400);
    expect(
      (
        await forward(
          new Request(settings.origin + "/api/" + path, {
            method: "POST",
            body: "{}",
          }),
          path,
          locals,
          fetcher,
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await forward(
          new Request(settings.origin + "/api/" + path),
          path.replace("/publish/", "/retry/"),
          locals,
          fetcher,
        )
      ).status,
    ).toBe(404);
  });
});

it("renders safe provider/reconnect/policy action error codes without provider prose", () => {
  expect(
    reviewFailure({ error: { code: "INTEGRATION_RECONNECT_REQUIRED" } }, 409),
  ).toBe("INTEGRATION_RECONNECT_REQUIRED");
  expect(reviewFailure({ code: "MUTATION_OUTCOME_UNCERTAIN" }, 504)).toBe(
    "MUTATION_OUTCOME_UNCERTAIN",
  );
  expect(
    reviewFailure({ code: "<script>unsafe provider text</script>" }, 502),
  ).toBe("HTTP_502");
});
