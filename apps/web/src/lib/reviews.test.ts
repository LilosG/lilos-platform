import { describe, expect, it } from "vitest";
import {
  canDraftReviewResponse,
  isReviewSyncActiveStatus,
  reviewResponseSourceLabel,
  summarizeReviewStatuses,
} from "./reviews";

describe("review provider-reply presentation", () => {
  it("derives total, responded, new, and actionable counts from reconciled statuses", () => {
    expect(
      summarizeReviewStatuses({
        by_status: {
          responded: 90,
          new: 0,
          classified: 0,
          publishing: 2,
          publication_failed: 1,
          escalated: 1,
        },
        average_rating: 4.8,
        open_restricted_cases: 1,
      }),
    ).toEqual({
      total: 94,
      responded: 90,
      newCount: 0,
      needsResponse: 2,
    });
  });

  it("does not count pending provider moderation as unanswered", () => {
    expect(
      summarizeReviewStatuses({
        by_status: { publishing: 1 },
        average_rating: 5,
        open_restricted_cases: 0,
      }).needsResponse,
    ).toBe(0);
  });

  it("labels imported history as a Google response, not a LILOs publication", () => {
    expect(reviewResponseSourceLabel("imported")).toBe("Google response");
    expect(reviewResponseSourceLabel("user")).toBe("LILOs manual response");
    expect(reviewResponseSourceLabel("ai")).toBe("LILOs AI response");
  });

  it("does not offer duplicate response composition for provider-replied reviews", () => {
    expect(canDraftReviewResponse("responded")).toBe(false);
    expect(canDraftReviewResponse("publishing")).toBe(false);
    expect(canDraftReviewResponse("removed")).toBe(false);
    expect(canDraftReviewResponse("closed")).toBe(false);
    expect(canDraftReviewResponse("archived")).toBe(false);
    expect(canDraftReviewResponse("publication_failed")).toBe(true);
    expect(canDraftReviewResponse("classified")).toBe(true);
  });
});

describe("durable review sync run states", () => {
  it.each(["created", "queued", "running", "retry_scheduled"])(
    "treats %s as active so a refresh does not enqueue duplicate Google work",
    (status) => {
      expect(isReviewSyncActiveStatus(status)).toBe(true);
    },
  );

  it.each(["completed", "failed", "cancelled", "escalated"])(
    "treats %s as terminal",
    (status) => {
      expect(isReviewSyncActiveStatus(status)).toBe(false);
    },
  );
});
