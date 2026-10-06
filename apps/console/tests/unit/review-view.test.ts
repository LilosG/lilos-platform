import { describe, expect, it } from "vitest";
import fixtures from "../fixtures/phase3.json";
import { adaptReviews, reviewFilter } from "../../src/adapters/reviews";
import { reviewer, reviewMetrics, sourceView } from "../../src/lib/review-view";
import { reviewChip } from "../../src/lib/status";
import { failureMessage } from "../../src/lib/review-actions";
const org = fixtures.workspace.organization_id;
const view = adaptReviews(fixtures.workspace, org);
describe("reviewer identity", () => {
  it("names, anonymises and never prints 'unavailable'", () => {
    const [named, anon, unknown] = [0, 1, 2].map((i) =>
      reviewer(view.items[i]),
    );
    expect(named).toMatchObject({
      kind: "named",
      name: "Jordan Sample",
      initials: "JS",
    });
    expect(anon).toMatchObject({ kind: "anonymous", name: "Google user" });
    expect(unknown).toMatchObject({
      kind: "unknown",
      name: "Google reviewer",
      initials: "G",
    });
  });
  it("loads only https photos", () => {
    const item = {
      ...view.items[0],
      reviewer_photo_url: "http://x.test/a.png",
    };
    expect(reviewer(item).photo).toBeNull();
  });
});
describe("review metrics, filters and chips", () => {
  it("shows a dash, never zero, for missing numbers", () => {
    const cells = reviewMetrics({
      ...view,
      inventory_count: null,
      average_rating: null,
      awaiting_response_count: null,
    });
    expect(cells.map((c) => c.value)).toEqual(["—", "—", "—"]);
    expect(cells.every((c) => c.missing)).toBe(true);
    expect(
      reviewMetrics({
        ...view,
        inventory_count: 0,
        awaiting_response_count: 0,
      })[0].value,
    ).toBe("0");
  });
  it("accepts only typed filters", () => {
    expect(reviewFilter(null)).toBe("all");
    expect(reviewFilter("published")).toBe("published");
    expect(reviewFilter("bogus")).toBeNull();
  });
  it("derives chips from typed state", () => {
    expect(reviewChip("classified", null).label).toBe("Needs response");
    expect(reviewChip("classified", "awaiting_approval").label).toBe(
      "Awaiting approval",
    );
    expect(reviewChip("escalated", "approved").label).toBe("Escalated");
    expect(reviewChip("responded", "published").label).toBe("Published");
  });
  it("keeps connection detail out of the chip text", () => {
    expect(sourceView(view.source).chip.label).toBe("Reconnect Google");
  });
  it("never shows an error code", () => {
    expect(failureMessage("SOME_CODE")).not.toContain("SOME_CODE");
  });
});
