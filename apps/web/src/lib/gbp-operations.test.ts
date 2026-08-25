import { beforeEach, describe, expect, it, vi } from "vitest";

const apiRequest = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: vi.fn(),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import {
  postPresentation,
  postPublicationIdempotencyKey,
  providerPostCounts,
  publishPost,
  type GBPPostPublicationItem,
  type GBPPostRevisionItem,
  type GBPProviderPostItem,
} from "./gbp-operations";

function revision(
  status: string,
  publication: GBPPostPublicationItem | null = null,
): GBPPostRevisionItem {
  return {
    id: "revision-1",
    post_key: "post-1",
    revision: 1,
    post_type: "STANDARD",
    content: "Approved provider-safe post",
    status,
    publication,
  };
}

function publication(
  status: string,
  recoveryAllowed = false,
): GBPPostPublicationItem {
  return {
    id: "publication-1",
    status,
    scheduled_for: null,
    dispatched_at: status === "reserved" ? null : "2026-08-24T12:00:00Z",
    provider_post_id:
      status === "reconciliation_required" ? "localPosts/provider-1" : null,
    verified_at: status === "verified" ? "2026-08-24T12:01:00Z" : null,
    recovery_allowed: recoveryAllowed,
  };
}

function providerPost(
  id: string,
  state: string,
  status: "present" | "not_seen" = "present",
): GBPProviderPostItem {
  return {
    id,
    provider_post_name: `localPosts/${id}`,
    post_type: "STANDARD",
    state,
    summary: id,
    content_hash: id.repeat(8),
    status,
    first_seen_at: "2026-08-24T12:00:00Z",
    last_seen_at: "2026-08-24T12:01:00Z",
    observed_at: "2026-08-24T12:01:00Z",
  };
}

describe("GBP post publication truth", () => {
  beforeEach(() => {
    apiRequest.mockReset();
    apiRequest.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("renders revision and publication lifecycle states without offering duplicate Publish", () => {
    expect(postPresentation(revision("awaiting_approval")).label).toBe(
      "Awaiting approval",
    );
    expect(postPresentation(revision("approved"))).toMatchObject({
      label: "Approved / never submitted",
      canPublish: true,
    });

    const cases = [
      ["reserved", "Reserved / queued"],
      ["dispatched", "Dispatched / publishing"],
      [
        "reconciliation_required",
        "Provider processing / reconciliation required",
      ],
      ["verified", "Published / verified"],
      ["failed", "Failed / rejected"],
      ["cancelled", "Cancelled"],
      ["expired", "Expired"],
    ] as const;
    for (const [status, label] of cases) {
      expect(
        postPresentation(revision("approved", publication(status))),
      ).toMatchObject({ label, canPublish: false });
    }
  });

  it("exposes recovery only when the backend read model permits it", () => {
    expect(
      postPresentation(
        revision("approved", publication("reconciliation_required", true)),
      ),
    ).toMatchObject({ canPublish: false, canRecover: true });
  });

  it("reuses one deterministic key across double-click and rerender attempts", async () => {
    const firstRenderKey = postPublicationIdempotencyKey("revision-1");
    const rerenderKey = postPublicationIdempotencyKey("revision-1");
    expect(rerenderKey).toBe(firstRenderKey);

    await Promise.all([
      publishPost("org-1", "location-1", "revision-1", "run-1", firstRenderKey),
      publishPost("org-1", "location-1", "revision-1", "run-1", rerenderKey),
    ]);

    expect(apiRequest).toHaveBeenCalledTimes(2);
    for (const call of apiRequest.mock.calls) {
      expect(call[1]).toMatchObject({
        method: "POST",
        body: { idempotency_key: "web-post-publish-revision-1" },
      });
    }
  });
});

describe("GBP provider Local Post counts", () => {
  it("counts only present LIVE rows as live", () => {
    const counts = providerPostCounts([
      providerPost("live", "LIVE"),
      providerPost("processing", "PROCESSING"),
      providerPost("rejected", "REJECTED"),
      providerPost("historical", "LIVE", "not_seen"),
    ]);

    expect(counts).toEqual({
      live: 1,
      processing: 1,
      rejected: 1,
      observed: 4,
    });
  });
});
