// @vitest-environment node
import { describe, it, expect } from "vitest";
import fixtures from "../fixtures/phase4.json";
import { adaptContent } from "../../src/adapters/website-content";
import type {
  WebsiteView,
  ContentView,
} from "../../src/adapters/website-content";
import {
  COMPOSE_TYPES,
  anyWriting,
  approvalStage,
  contentRows,
  exactChange,
  failureFor,
  isPageType,
  pathOf,
  publicationChip,
  review,
  revisionChip,
  stageChip,
  typeLabel,
} from "../../src/lib/content-view";
import { outline, renderMarkdown, wordCount } from "../../src/lib/markdown";

type Row = WebsiteView["content"][number];
const id = (n: number) =>
  `${n.toString(16).padStart(8, "0")}-0000-4000-8000-000000000000`;
const row = (over: Partial<Row> = {}): Row => ({
  id: id(1),
  title: "Why Miss B's is the Packers bar",
  slug: "packers-bar",
  content_type: "blog_post",
  stage: "editorial_review",
  next_action: { key: "approve_editorial", label: "Approve editorial review" },
  published_at: null,
  latest_revision_status: "awaiting_editorial",
  latest_revision_number: 1,
  publication_status: null,
  publication_job_status: null,
  technical_site_change: false,
  word_count: 1520,
  compose: null,
  ...over,
});
// Nothing a person reads may look like an enum, a code, an id or a timestamp.
const RAW =
  /[a-z]+_[a-z0-9_]+|[A-Z]+_[A-Z_]+|[0-9a-f]{8}-[0-9a-f]{4}|\d{4}-\d{2}-\d{2}T/;

describe("content type and state labels", () => {
  it("names every type a person can pick and never leaks an unknown key", () => {
    expect(COMPOSE_TYPES.map((t) => t.label)).toEqual([
      "Let Claude decide",
      "Blog post",
      "Listicle",
      "Landing page",
      "Service page",
      "Location page",
      "Guide",
    ]);
    expect(COMPOSE_TYPES[0].key).toBeNull();
    expect(typeLabel("blog_post")).toBe("Blog post");
    expect(typeLabel("local-guide")).toBe("Guide");
    expect(typeLabel("some_new_type")).toBe("Content");
  });
  it("separates landing, service and location pages from articles", () => {
    for (const key of ["landing_page", "service-page", "location_page", "page"])
      expect(isPageType(key)).toBe(true);
    for (const key of ["blog_post", "listicle", "guide"])
      expect(isPageType(key)).toBe(false);
  });
  it("gives each stage, revision and publication state a chip with no raw text", () => {
    const stages = [
      "writing",
      "compose_failed",
      "brief_needed",
      "draft_needed",
      "drafting",
      "editorial_review",
      "client_review",
      "revision_needed",
      "ready_to_publish",
      "publishing",
      "published",
      "needs_attention",
    ];
    for (const stage of stages) expect(stageChip(stage).label).not.toMatch(RAW);
    expect(stageChip("writing")).toEqual({ label: "Writing", tone: "neutral" });
    expect(stageChip("compose_failed").tone).toBe("error");
    expect(stageChip("brand_new_stage")).toEqual({
      label: "In progress",
      tone: "neutral",
    });
    expect(revisionChip("awaiting_editorial").label).toBe("Awaiting review");
    expect(revisionChip("anything_else").label).toBe("Draft");
    expect(publicationChip("verified")).toEqual({ label: "Live", tone: "" });
    expect(publicationChip("checks_failed").tone).toBe("error");
    expect(publicationChip("unknown_state").label).toBe("In progress");
  });
  it("maps a revision status to the approval stage it is waiting on", () => {
    expect(approvalStage("awaiting_editorial")).toBe("editorial");
    expect(approvalStage("awaiting_client")).toBe("client");
    expect(approvalStage("approved")).toBeNull();
  });
});

describe("why a piece could not be written", () => {
  it("gives every typed code its own reason and never echoes the code", () => {
    for (const code of [
      "CONTENT_WEBSITE_NOT_CRAWLED",
      "CONTENT_BELOW_QUALITY_FLOOR",
      "CONTENT_TOPIC_OVERLAP",
      "CONTENT_PLAN_INVALID",
      "AI_PROVIDER_CONFIGURATION_ERROR",
      "AI_PROVIDER_TEMPORARY_FAILURE",
    ]) {
      const failure = failureFor(code);
      expect(failure.title).not.toBe(failureFor("OTHER").title);
      expect(`${failure.title} ${failure.detail}`).not.toMatch(RAW);
    }
    expect(failureFor(null).title).toBe("The draft could not be written");
    expect(failureFor("SOMETHING_NEW").detail).not.toMatch(/SOMETHING_NEW/);
  });
});

describe("the content list", () => {
  it("shows stage, words, revision and publication through formatters", () => {
    const [published] = contentRows(
      [
        row({
          stage: "published",
          publication_status: "verified",
          latest_revision_status: "approved",
        }),
      ],
      "/clients/x/website-content/",
    );
    expect(published.href).toBe(`/clients/x/website-content/content/${id(1)}/`);
    expect(published.words).toBe("1,520");
    expect(published.stage.label).toBe("Published");
    expect(published.revision?.label).toBe("Approved");
    expect(published.publication?.label).toBe("Live");
    expect(
      JSON.stringify([published.type, published.stage, published.revision]),
    ).not.toMatch(RAW);
  });
  it("never shows a missing word count as 0", () => {
    const [writing] = contentRows(
      [
        row({
          word_count: null,
          latest_revision_status: null,
          latest_revision_number: null,
          stage: "writing",
          compose: {
            status: "writing",
            failure_code: null,
            prompt: "write a blog",
            workflow_run_id: id(9),
          },
        }),
      ],
      "/b/",
    );
    expect(writing.words).toBe("–");
    expect(writing.words).not.toBe("0");
    expect(writing.writing).toBe(true);
    expect(writing.revision).toBeNull();
    expect(writing.stage.label).toBe("Writing");
  });
  it("carries a failed item's typed reason and the prompt to retry", () => {
    const [failed] = contentRows(
      [
        row({
          word_count: null,
          stage: "compose_failed",
          latest_revision_status: null,
          compose: {
            status: "failed",
            failure_code: "CONTENT_BELOW_QUALITY_FLOOR",
            prompt: "listicle: best places to watch Packers games",
            workflow_run_id: id(9),
          },
        }),
      ],
      "/b/",
    );
    expect(failed.failed).toBe(true);
    expect(failed.failure?.title).toBe(
      "The draft was not long or well linked enough",
    );
    expect(failed.retryPrompt).toBe(
      "listicle: best places to watch Packers games",
    );
  });
  it("detects whether anything is still being written", () => {
    expect(anyWriting([row()])).toBe(false);
    expect(
      anyWriting([
        row({
          compose: {
            status: "writing",
            failure_code: null,
            prompt: null,
            workflow_run_id: id(9),
          },
        }),
      ]),
    ).toBe(true);
  });
});

const doc = {
  quality: {
    floor: { minimum_words: 1400 },
    checks: [
      { code: "article_too_thin", passed: true },
      { code: "article_internal_link_unverified", passed: false },
      { code: "article_not_yet_known", passed: true },
    ],
    links: [
      { anchor: "our menu", url: "/menu", verified: true, kind: "menu" },
      { anchor: "an old page", url: "/gone", verified: false, kind: null },
    ],
  },
  claims: [
    { claim_id: "a1", text: "Opened in 1987.", status: "needs_confirmation" },
    { claim_id: "a2", text: "A Packers bar.", status: "backed" },
    { claim_id: "a3", text: "Has a patio.", status: "confirmed" },
  ],
  inbound_links: [
    {
      status: "proposed",
      page_url: "https://missbs.example/events",
      anchor: "game day",
      before: "Join us for game day.",
      after: "Join us for [game day](/blog/packers).",
    },
    { status: "unavailable", code: "NO_NATURAL_ANCHOR", page_url: "/about" },
    { status: "unavailable", code: "SOME_FUTURE_CODE", page_url: "/jobs" },
  ],
};
const detail = (over: Record<string, unknown> = {}): ContentView => {
  const base = structuredClone(fixtures.detail) as Record<string, unknown>;
  const revisions = base.revisions as Record<string, unknown>[];
  revisions[0] = {
    ...revisions[0],
    body: "## Why Packers fans come here\n\nSee [our menu](/menu) today. ".repeat(
      40,
    ),
    frontmatter: {
      title: "t",
      seo_title: "Packers Bar in San Diego",
      description: "Where to watch Packers games.",
      faqs: [
        { question: "Do you show every game?", answer: "Yes, every game." },
        { question: "", answer: "dropped" },
      ],
    },
    validation_document: doc,
  };
  return adaptContent(
    { ...base, organization_id: fixtures.workspace.organization_id, ...over },
    fixtures.workspace.organization_id,
    fixtures.detail.id,
  );
};

describe("the draft review", () => {
  it("measures the draft against its floor and reads the SEO fields and FAQs", () => {
    const r = review(detail());
    expect(r.floorWords).toBe(1400);
    expect(r.words).toBeGreaterThan(0);
    expect(r.meetsFloor).toBe(r.words >= 1400);
    expect(r.seoTitle).toBe("Packers Bar in San Diego");
    expect(r.metaDescription).toBe("Where to watch Packers games.");
    expect(r.faqs).toEqual([
      { question: "Do you show every game?", answer: "Yes, every game." },
    ]);
    expect(r.outline[0]).toEqual({
      level: 2,
      text: "Why Packers fans come here",
    });
  });
  it("turns typed check codes into chips, and an unknown code into a neutral one", () => {
    const r = review(detail());
    expect(r.checks[0].chip).toEqual({ label: "Meets length", tone: "" });
    expect(r.checks[1].chip).toEqual({
      label: "Unverified link",
      tone: "error",
    });
    expect(r.checks[2].chip.label).toBe("Check");
    expect(JSON.stringify(r.checks.map((c) => c.chip))).not.toMatch(RAW);
  });
  it("marks every outbound link verified or not, showing paths only", () => {
    const r = review(detail());
    expect(r.links).toEqual([
      expect.objectContaining({
        url: "/menu",
        chip: { label: "Verified", tone: "" },
      }),
      expect.objectContaining({
        url: "/gone",
        chip: { label: "Not verified", tone: "error" },
      }),
    ]);
  });
  it("shows inbound edits as before and after, and a typed reason when none could be made", () => {
    const r = review(detail());
    expect(r.inbound[0]).toMatchObject({
      page: "/events",
      anchor: "game day",
      before: "Join us for game day.",
      after: "Join us for [game day](/blog/packers).",
    });
    expect(r.inbound[0].chip.label).toBe("Proposed");
    expect(r.inbound[1].chip.label).toBe("No natural place to add the link");
    expect(r.inbound[2].chip.label).toBe("No edit could be proposed");
  });
  it("counts the claims that still block approval", () => {
    const r = review(detail());
    expect(r.unresolved).toBe(1);
    expect(r.claims.map((c) => c.chip.label)).toEqual([
      "Needs confirmation",
      "Backed by facts",
      "Confirmed",
    ]);
  });
  it("lists revisions with who wrote them", () => {
    const r = review(detail());
    expect(r.revisions[0]).toMatchObject({
      label: "Revision 1",
      author: "Edited by a person",
      current: true,
    });
  });
  it("has no floor, checks or links for a revision the writing service did not record", () => {
    const base = detail();
    base.revisions[0].validation_document = { status: "valid" };
    const r = review(base);
    expect(r.floorWords).toBeNull();
    expect(r.meetsFloor).toBeNull();
    expect(r.checks).toEqual([]);
    expect(r.links).toEqual([]);
    expect(r.inbound).toEqual([]);
    expect(r.claims).toEqual([]);
  });
});

describe("the exact change an approval signs off on", () => {
  it("names the repository, branch, file and whether it is new", () => {
    const change = exactChange(
      detail(),
      fixtures.detail.publishing_targets[0].id,
    );
    expect(change).toEqual({
      repository: "synthetic/test",
      branch: "main",
      filePath: "src/content/blog/synthetic-article.mdx",
      kind: "new_file",
      kindLabel: "A new file is added",
    });
  });
  it("says an existing file is replaced, and is null when no target is connected", () => {
    const view = detail();
    view.publish_preview = [
      { ...view.publish_preview[0], change_kind: "edit" },
    ];
    expect(exactChange(view, null)?.kindLabel).toBe(
      "The existing file is replaced",
    );
    view.publish_preview = [];
    expect(exactChange(view, null)).toBeNull();
  });
});

describe("addresses and markdown", () => {
  it("shows a page by its path", () => {
    expect(pathOf("https://missbs.example/events/?x=1")).toBe("/events/");
    expect(pathOf("/menu")).toBe("/menu");
  });
  it("renders headings, lists, emphasis and safe links", () => {
    const html = renderMarkdown(
      "## Where to watch\n\nA **bold** and *soft* line with [our menu](/menu).\n\n- one\n- two\n\n1. first\n2. second",
    );
    expect(html).toContain("<h2>Where to watch</h2>");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<em>soft</em>");
    expect(html).toContain('<a href="/menu">our menu</a>');
    expect(html).toContain("<ul>\n<li>one</li>\n<li>two</li>\n</ul>");
    expect(html).toContain("<ol>\n<li>first</li>\n<li>second</li>\n</ol>");
  });
  it("cannot inject markup or scripts", () => {
    const html = renderMarkdown(
      "<script>alert(1)</script> [x](javascript:alert(1)) [y](//evil.example) ![i](/a.png) <img src=x onerror=1>",
    );
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain('href="//evil');
    expect(html).toContain("&lt;script&gt;");
  });
  it("outlines headings and counts words the way the server does", () => {
    expect(outline("## A\n\ntext\n\n### B *c*\n\n#### D")).toEqual([
      { level: 2, text: "A" },
      { level: 3, text: "B c" },
    ]);
    expect(wordCount("Miss B's is a Packers-bar, in San Diego.")).toBe(8);
    expect(wordCount("")).toBe(0);
  });
});
