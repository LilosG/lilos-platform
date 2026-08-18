import { describe, expect, it, vi } from "vitest";

import type { ApiOutcome } from "./api-client";
import {
  CONTENT_REQUIRED_FACT_KEYS,
  isContentOpportunityActionable,
  deriveSlug,
  createContentItem,
  CONTENT_GOAL_MAXLENGTH,
  AUDIENCE_MAXLENGTH,
  formatCharacterCount,
  isOverCharacterLimit,
  renderDocumentBody,
  fieldErrorFromDetails,
  describeContentFailure,
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

describe("Content validation constants", () => {
  it("sets content goal maxlength to 500 characters", () => {
    expect(CONTENT_GOAL_MAXLENGTH).toBe(500);
  });

  it("sets audience maxlength to 500 characters", () => {
    expect(AUDIENCE_MAXLENGTH).toBe(500);
  });
});

describe("formatCharacterCount", () => {
  it("formats zero characters correctly", () => {
    expect(formatCharacterCount(0, 500)).toBe("0 / 500 characters");
  });

  it("formats partial count correctly", () => {
    expect(formatCharacterCount(142, 500)).toBe("142 / 500 characters");
  });

  it("formats at-limit count correctly", () => {
    expect(formatCharacterCount(500, 500)).toBe("500 / 500 characters");
  });

  it("shows negative count as zero", () => {
    expect(formatCharacterCount(-5, 500)).toBe("0 / 500 characters");
  });
});

describe("isOverCharacterLimit", () => {
  it("returns false when count is under limit", () => {
    expect(isOverCharacterLimit(499, 500)).toBe(false);
  });

  it("returns false when count equals limit", () => {
    expect(isOverCharacterLimit(500, 500)).toBe(false);
  });

  it("returns true when count exceeds limit", () => {
    expect(isOverCharacterLimit(501, 500)).toBe(true);
  });
});

describe("renderDocumentBody", () => {
  it("returns an article element with content-document class", () => {
    const article = renderDocumentBody("Hello world");
    expect(article.tagName).toBe("ARTICLE");
    expect(article.classList.contains("content-document")).toBe(true);
  });

  it("renders plain text as a single paragraph", () => {
    const article = renderDocumentBody("Just a single paragraph.");
    const paragraphs = article.querySelectorAll("p");
    expect(paragraphs).toHaveLength(1);
    expect(paragraphs[0]!.textContent).toBe("Just a single paragraph.");
  });

  it("renders blank-line-separated blocks as separate paragraphs", () => {
    const article = renderDocumentBody("First paragraph.\n\nSecond paragraph.");
    const paragraphs = article.querySelectorAll("p");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0]!.textContent).toBe("First paragraph.");
    expect(paragraphs[1]!.textContent).toBe("Second paragraph.");
  });

  it("renders ATX headings with appropriate levels", () => {
    const article = renderDocumentBody(
      "# H1 title\n\n## H2 section\n\n### H3 subsection",
    );
    const h1 = article.querySelectorAll("h1");
    const h2 = article.querySelectorAll("h2");
    const h3 = article.querySelectorAll("h3");
    expect(h1).toHaveLength(1);
    expect(h1[0]!.textContent).toBe("H1 title");
    expect(h2).toHaveLength(1);
    expect(h2[0]!.textContent).toBe("H2 section");
    expect(h3).toHaveLength(1);
    expect(h3[0]!.textContent).toBe("H3 subsection");
  });

  it("renders unordered lists from hyphens", () => {
    const article = renderDocumentBody(
      "- First item\n- Second item\n- Third item",
    );
    const ul = article.querySelectorAll("ul");
    expect(ul).toHaveLength(1);
    const items = ul[0]!.querySelectorAll("li");
    expect(items).toHaveLength(3);
    expect(items[0]!.textContent).toBe("First item");
    expect(items[1]!.textContent).toBe("Second item");
    expect(items[2]!.textContent).toBe("Third item");
  });

  it("renders unordered lists from asterisks", () => {
    const article = renderDocumentBody("* Item A\n* Item B");
    const items = article.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0]!.textContent).toBe("Item A");
  });

  it("collapses single newlines within paragraph blocks to spaces", () => {
    const article = renderDocumentBody("Line one\nLine two\nLine three");
    const p = article.querySelector("p");
    expect(p).not.toBeNull();
    expect(p!.textContent).toBe("Line one Line two Line three");
  });

  it("handles empty input gracefully", () => {
    const article = renderDocumentBody("");
    expect(article.textContent).toContain("No document body available");
  });

  it("handles whitespace-only input gracefully", () => {
    const article = renderDocumentBody("   \n\n  ");
    expect(article.textContent).toContain("No document body available");
  });

  it("does not inject raw HTML from user content (XSS defense)", () => {
    const article = renderDocumentBody(
      "<script>alert('xss')</script>\n\n<p>Safe text</p>",
    );
    // The `<script>` and `<p>` tags should appear as literal text, not be
    // parsed as DOM elements — both blocks become `<p>` elements via
    // textContent assignment.
    expect(article.querySelectorAll("script")).toHaveLength(0);
    // Both blocks are rendered as text paragraphs.
    const paragraphs = article.querySelectorAll("p");
    expect(paragraphs.length).toBe(2);
    expect(paragraphs[0]!.textContent).toContain("alert('xss')");
    expect(paragraphs[1]!.textContent).toContain("<p>Safe text</p>");
  });

  it("renders a realistic long-form draft", () => {
    const body = [
      "# The Benefits of Commercial Solar",
      "",
      "Commercial solar installations offer significant advantages for businesses of all sizes. By generating electricity on-site, companies can reduce their dependence on grid power.",
      "",
      "## Financial Benefits",
      "",
      "- Reduced electricity costs",
      "- Tax incentives and accelerated depreciation",
      "- Increased property value",
      "",
      "## Environmental Impact",
      "",
      "Switching to solar energy demonstrates a commitment to sustainability that resonates with modern consumers.",
    ].join("\n");

    const article = renderDocumentBody(body);
    expect(article.querySelectorAll("h1")).toHaveLength(1);
    expect(article.querySelectorAll("h2")).toHaveLength(2);
    expect(article.querySelectorAll("li")).toHaveLength(3);
    // Two plain-text blocks are rendered as <p>: the intro and the
    // environmental-impact paragraph.  Headings and lists are separate.
    expect(article.querySelectorAll("p")).toHaveLength(2);
  });

  it("does not produce empty paragraph elements", () => {
    const article = renderDocumentBody("Valid text\n\n\n\nMore text");
    const paragraphs = article.querySelectorAll("p");
    // No empty paragraphs — blank blocks are skipped.
    for (const p of paragraphs) {
      expect(p.textContent?.trim().length).toBeGreaterThan(0);
    }
  });
});

describe("fieldErrorFromDetails", () => {
  it("returns null when outcome is ok", () => {
    const outcome = { kind: "ok", data: {} } as const;
    expect(fieldErrorFromDetails(outcome, "intent")).toBeNull();
  });

  it("returns null when outcome has no details", () => {
    const outcome: ApiOutcome<unknown> = {
      kind: "error",
      status: 422,
      code: "VALIDATION_ERROR",
      message: "Validation failed.",
      details: [],
    };
    expect(fieldErrorFromDetails(outcome, "intent")).toBeNull();
  });
  it("extracts a matching field-level message", () => {
    const outcome: ApiOutcome<unknown> = {
      kind: "error",
      status: 422,
      code: "VALIDATION_ERROR",
      message: "Validation failed.",
      details: [
        {
          field: "intent",
          code: "too_long",
          message: "Content goal must be 500 characters or fewer.",
        },
      ],
    };
    expect(fieldErrorFromDetails(outcome, "intent")).toBe(
      "Content goal must be 500 characters or fewer.",
    );
  });

  it("is case-insensitive for field names", () => {
    const outcome: ApiOutcome<unknown> = {
      kind: "error",
      status: 422,
      code: "VALIDATION_ERROR",
      message: "Validation failed.",
      details: [
        {
          field: "Intent",
          code: "required",
          message: "Intent is required.",
        },
      ],
    };
    expect(fieldErrorFromDetails(outcome, "intent")).toBe(
      "Intent is required.",
    );
  });

  it("returns null when no detail matches the field", () => {
    const outcome: ApiOutcome<unknown> = {
      kind: "error",
      status: 422,
      code: "VALIDATION_ERROR",
      message: "Validation failed.",
      details: [
        {
          field: "audience",
          code: "required",
          message: "Audience is required.",
        },
      ],
    };
    expect(fieldErrorFromDetails(outcome, "intent")).toBeNull();
  });
});

describe("describeContentFailure", () => {
  it("returns field-level validation messages in priority", () => {
    const outcome: ApiOutcome<unknown> = {
      kind: "error",
      status: 422,
      code: "VALIDATION_ERROR",
      message: "The request did not pass validation.",
      details: [
        {
          field: "intent",
          code: "too_long",
          message: "Content goal must be 500 characters or fewer.",
        },
      ],
    };

    const msg = describeContentFailure(outcome, "Brief");
    expect(msg).toBe("Content goal must be 500 characters or fewer.");
    // Generic envelope message is NOT included.
    expect(msg).not.toContain("did not pass validation");
  });

  it("joins multiple detail messages with spaces", () => {
    const outcome: ApiOutcome<unknown> = {
      kind: "error",
      status: 422,
      code: "VALIDATION_ERROR",
      message: "Failed.",
      details: [
        {
          field: "audience",
          message: "Audience is required.",
        },
        {
          field: "intent",
          message: "Content goal must be 500 characters or fewer.",
        },
      ],
    };

    const msg = describeContentFailure(outcome);
    expect(msg).toContain("Audience is required.");
    expect(msg).toContain("Content goal must be 500 characters or fewer.");
  });

  it("describes disconnected with durable-AI-aware language", () => {
    const outcome = { kind: "disconnected" } as const;
    const msg = describeContentFailure(outcome, "Generation");
    expect(msg).toContain("could not reach the platform");
    expect(msg).toContain("may still be processing");
  });

  it("falls back to generic message when error has no details", () => {
    const outcome: ApiOutcome<unknown> = {
      kind: "error",
      status: 500,
      code: "INTERNAL_ERROR",
      message: "Something went wrong.",
      details: [],
    };

    const msg = describeContentFailure(outcome, "Brief");
    expect(msg).toBe("Something went wrong.");
  });

  it("returns empty string for ok outcome", () => {
    const outcome = { kind: "ok", data: {} } as const;
    expect(describeContentFailure(outcome)).toBe("");
  });

  it("returns context-prefixed messages for forbidden/not-found/etc.", () => {
    expect(describeContentFailure({ kind: "forbidden" } as const, "Test")).toBe(
      "Test: You do not have permission to perform this action.",
    );

    expect(describeContentFailure({ kind: "not-found" } as const, "Test")).toBe(
      "Test: The requested resource could not be found.",
    );
  });
});
