import { describe, expect, it, vi } from "vitest";

import {
  CONTENT_REQUIRED_FACT_KEYS,
  isContentOpportunityActionable,
  deriveSlug,
  createContentItem,
} from "./content";

vi.mock("./api-client", () => ({
  apiGet: vi.fn(),
  apiRequest: vi.fn(),
}));

describe("Content workflow contracts", () => {
  it("offers decisions only for statuses accepted by the API", () => {
    expect(isContentOpportunityActionable("identified")).toBe(true);
    expect(isContentOpportunityActionable("validated")).toBe(true);
    expect(isContentOpportunityActionable("accepted")).toBe(false);
    expect(isContentOpportunityActionable("rejected")).toBe(false);
  });

  it("grounds briefs in the current Content product fact requirements", () => {
    expect(CONTENT_REQUIRED_FACT_KEYS).toEqual([
      "business.name",
      "brand.approved_claims",
    ]);
  });
});

describe("deriveSlug", () => {
  it("converts a simple title to a lowercase slug", () => {
    expect(deriveSlug("Hello World")).toBe("hello-world");
  });

  it("strips special characters", () => {
    expect(deriveSlug("What's New in SEO?")).toBe("whats-new-in-seo");
  });

  it("collapses multiple spaces and hyphens", () => {
    expect(deriveSlug("My   Great--Post")).toBe("my-great-post");
  });

  it("removes leading and trailing hyphens", () => {
    expect(deriveSlug(" - Leading and Trailing - ")).toBe(
      "leading-and-trailing",
    );
  });

  it("handles already-valid slugs", () => {
    expect(deriveSlug("my-valid-slug-123")).toBe("my-valid-slug-123");
  });

  it("truncates to 200 characters", () => {
    const longTitle = "a".repeat(250);
    const slug = deriveSlug(longTitle);
    expect(slug.length).toBeLessThanOrEqual(200);
    expect(slug).toBe("a".repeat(200));
  });

  it("handles empty input", () => {
    expect(deriveSlug("")).toBe("");
  });

  it("handles title with only special characters", () => {
    expect(deriveSlug("!@#$%")).toBe("");
  });

  it("removes smart quotes and apostrophes", () => {
    expect(deriveSlug("It\u2019s a \u201Ctest\u201D")).toBe("its-a-test");
  });
});

describe("createContentItem", () => {
  it("calls apiRequest with standalone item data (no opportunityId)", async () => {
    const { apiRequest } = await import("./api-client");
    const mockApiRequest = vi.mocked(apiRequest);
    mockApiRequest.mockResolvedValue({
      kind: "ok",
      data: {
        id: "item-1",
        title: "My First Post",
        slug: "my-first-post",
        content_type: "blog",
        status: "idea",
        opportunity_id: null,
        location_id: null,
        published_at: null,
      },
    });

    const result = await createContentItem("org-1", {
      contentType: "blog",
      title: "My First Post",
      slug: "my-first-post",
    });

    expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/content",
      {
        method: "POST",
        body: {
          opportunity_id: null,
          location_id: null,
          content_type: "blog",
          title: "My First Post",
          slug: "my-first-post",
        },
      },
    );

    expect(result.kind).toBe("ok");
    if (result.kind === "ok") {
      expect(result.data.title).toBe("My First Post");
      expect(result.data.status).toBe("idea");
    }
  });

  it("calls apiRequest with optional opportunityId and locationId", async () => {
    const { apiRequest } = await import("./api-client");
    const mockApiRequest = vi.mocked(apiRequest);
    mockApiRequest.mockResolvedValue({
      kind: "ok",
      data: {
        id: "item-2",
        title: "SEO Page",
        slug: "seo-page",
        content_type: "page",
        status: "briefing",
        opportunity_id: "opp-1",
        location_id: "loc-1",
        published_at: null,
      },
    });

    await createContentItem("org-1", {
      opportunityId: "opp-1",
      locationId: "loc-1",
      contentType: "page",
      title: "SEO Page",
      slug: "seo-page",
    });

    expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/content",
      {
        method: "POST",
        body: {
          opportunity_id: "opp-1",
          location_id: "loc-1",
          content_type: "page",
          title: "SEO Page",
          slug: "seo-page",
        },
      },
    );
  });
});
