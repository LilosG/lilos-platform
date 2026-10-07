// @vitest-environment node
import { describe, it, expect } from "vitest";
import {
  adaptWebsite,
  adaptWebsitePage,
} from "../../src/adapters/website-content";
import {
  NOT_INDEXABLE,
  conversionTiles,
  crawlChip,
  findingGroups,
  indexChip,
  insightReason,
  issueFor,
  latestCrawl,
  mappingView,
  overviewTiles,
  pageDetail,
  pageGap,
  pageRows,
  qualityChip,
  siteChanges,
  siteStatus,
  technicalTiles,
  websiteDetails,
  websiteInsight,
} from "../../src/lib/website-view";
// @ts-expect-error The simulator is plain JavaScript.
import {
  pageDetail as simPage,
  workspace as simWorkspace,
} from "../browser/website-sim.mjs";
const org = "11111111-1111-4111-8111-111111111111";
const site = "11111111-1111-4111-8111-111111111111";
const now = new Date();
const view = (mode: string, requested?: string) =>
  adaptWebsite(simWorkspace(mode, org, requested), org);
const href = (w: string, p: string) => `/pages/${w}/${p}/`;
const ISO = /\d{4}-\d{2}-\d{2}T/;
const RAW =
  /\b[a-z]+(_[a-z0-9]+)+\b|\b[A-Z]+(_[A-Z]+)+\b|[0-9a-f]{8}-[0-9a-f]{4}-/;

describe("chips are typed states, never API strings", () => {
  it("labels every index and quality state, and an unknown one as not checked", () => {
    expect(indexChip("indexable")).toEqual({ label: "Indexable", tone: "" });
    expect(indexChip("not_indexable").label).toBe("Not indexable");
    expect(indexChip(null).label).toBe("Not checked");
    expect(indexChip("anything_else").label).toBe("Not checked");
    expect(qualityChip("clean").label).toBe("No issues");
    expect(qualityChip("issues_detected").label).toBe("Issues found");
    expect(qualityChip("partial").label).toBe("Partly checked");
    expect(qualityChip("surprise_value").label).toBe("Not checked");
    expect(crawlChip("partial").label).toBe("Partly checked");
    expect(crawlChip("made_up").label).toBe("Not checked");
  });
  it("words a crawler code once, and an unknown code in plain words", () => {
    expect(issueFor("missing_title")).toMatchObject({
      label: "Missing page title",
      severity: "high",
    });
    expect(issueFor("some_future_code").label).toBe("Some future code");
    expect(issueFor("some_future_code").severity).toBe("low");
  });
});

describe("site status and the header chip", () => {
  it("is available when a recent check completed", () => {
    const s = siteStatus(view("rich"), now);
    expect(s.state).toBe("current");
    expect(s.chip.label).toBe("Checked 2 days ago");
    expect(s.chip.tone).toBe("");
  });
  it("is partial when the latest check stopped early", () => {
    const v = view("rich");
    v.crawls = [v.crawls[1]];
    expect(siteStatus(v, now).state).toBe("partial");
  });
  it("is out of date after 30 days", () => {
    const v = view("rich");
    v.crawls = [
      {
        ...v.crawls[1],
        completed_at: new Date(now.getTime() - 40 * 86_400_000).toISOString(),
      },
    ];
    expect(siteStatus(v, now)).toMatchObject({ state: "stale" });
  });
  it("names missing states and never says checked", () => {
    expect(siteStatus(view("empty"), now).state).toBe("never_checked");
    expect(siteStatus(view("no_website"), now).state).toBe("no_website");
    expect(siteStatus(view("no_access"), now).state).toBe("no_access");
    expect(siteStatus(view("unavailable"), now).state).toBe("unavailable");
    expect(siteStatus(view("failed"), now)).toMatchObject({
      state: "failed",
      chip: { label: "Last check failed", tone: "error" },
    });
  });
  it("picks the newest check regardless of order", () => {
    const v = view("failed");
    expect(latestCrawl(v.crawls)?.status).toBe("failed");
    expect(latestCrawl([])).toBeNull();
  });
});

describe("tiles never show a missing figure as zero", () => {
  it("counts what the inventory supports and marks Google indexing as not tracked", () => {
    const tiles = overviewTiles(view("rich"), now);
    expect(tiles.map((t) => t.label)).toEqual([
      "Pages checked",
      "Indexable pages",
      "Pages with issues",
      "Last site check",
      "Indexed by Google",
    ]);
    expect(tiles[0]).toMatchObject({ value: "8", missing: false });
    expect(tiles[1].value).toBe("6");
    expect(tiles[2].value).toBe("4");
    expect(tiles[3]).toMatchObject({ value: "2 days ago", missing: false });
    expect(tiles[4]).toMatchObject({ value: "Not tracked", missing: true });
    // No earlier period exists, so no tile claims a trend.
    expect(tiles.every((t) => t.trend === null)).toBe(true);
  });
  it("labels a count taken from the first pages only", () => {
    const v = view("rich");
    v.next_page_offset = 50;
    expect(overviewTiles(v, now)[0].description).toBe(
      "In the first 8 pages; more exist",
    );
  });
  it.each([
    ["empty", "Not checked"],
    ["no_website", "No website"],
    ["no_access", "No access"],
    ["unavailable", "Unavailable"],
  ])("shows %s as a reason, not 0", (mode, text) => {
    for (const tile of [
      ...overviewTiles(view(mode), now),
      ...technicalTiles(view(mode), now),
    ])
      expect(tile.value).not.toBe("0");
    const tiles = overviewTiles(view(mode), now);
    expect(tiles[0]).toMatchObject({ value: text, missing: true });
  });
  it("counts high-priority findings for the Technical tab", () => {
    const tiles = technicalTiles(view("rich"), now);
    expect(tiles.map((t) => t.label)).toEqual([
      "Pages checked",
      "Pages with issues",
      "High-priority findings",
      "Last site check",
    ]);
    expect(tiles[2].value).toBe("2");
  });
  it("marks every conversion tile as not tracked", () => {
    expect(
      conversionTiles().every((t) => t.missing && t.value === "Not tracked"),
    ).toBe(true);
  });
});

describe("the insight is chosen by a typed reason", () => {
  it.each([
    ["no_website", "NO_WEBSITE"],
    ["no_access", "NO_ACCESS"],
    ["unavailable", "PAGES_UNAVAILABLE"],
    ["failed", "LAST_CHECK_FAILED"],
    ["empty", "NEVER_CHECKED"],
    ["rich", "ISSUES_FOUND"],
    ["clean", "ALL_CLEAR"],
  ])("%s is %s", (mode, reason) => {
    expect(insightReason(view(mode), now)).toBe(reason);
    expect(websiteInsight(view(mode), now).reason).toBe(reason);
  });
  it("reports closed pages when nothing else is wrong, and a stale check last", () => {
    const v = view("clean");
    v.pages[0].indexability = "not_indexable";
    expect(insightReason(v, now)).toBe("PAGES_NOT_INDEXABLE");
    const old = view("clean");
    old.crawls[0].completed_at = new Date(
      now.getTime() - 60 * 86_400_000,
    ).toISOString();
    expect(insightReason(old, now)).toBe("CHECK_OUT_OF_DATE");
  });
  it("is not derived from wording: changing prose changes nothing", () => {
    const v = view("rich");
    v.crawls[0].stop_reason = "Looks like everything is fine";
    v.pages[1].title = "No technical issues";
    expect(insightReason(v, now)).toBe("ISSUES_FOUND");
  });
  it("counts the pages in its sentence", () => {
    expect(websiteInsight(view("rich"), now).title).toBe(
      "4 pages have technical issues.",
    );
  });
});

describe("page rows", () => {
  const rows = pageRows(view("rich"), now, href);
  it("puts the pages that need attention first", () => {
    expect(rows[0].path).toBe("/old-menu/");
    expect(rows.at(-1)!.hasIssues).toBe(false);
  });
  it("formats time, status and chips without raw values", () => {
    const menu = rows.find((r) => r.path === "/menu/")!;
    expect(menu).toMatchObject({
      label: "Synthetic menu",
      httpText: "200",
      issuesText: "2 issues",
      observedText: "2 days ago",
    });
    expect(menu.quality.label).toBe("Issues found");
    for (const row of rows) {
      expect(
        JSON.stringify([
          row.observedText,
          row.issuesText,
          row.index,
          row.quality,
        ]),
      ).not.toMatch(ISO);
    }
  });
  it("shows a page that was never checked as such, with no invented figures", () => {
    const jobs = rows.find((r) => r.path === "/jobs/")!;
    expect(jobs).toMatchObject({
      observedText: "Not checked",
      issuesText: "–",
      checked: false,
      indexKey: "unknown",
    });
    expect(jobs.index.label).toBe("Not checked");
    const about = rows.find((r) => r.path === "/about/")!;
    expect(about.httpText).toBe("–");
  });
  it("falls back to the path when a page has no title", () => {
    expect(rows.find((r) => r.path === "/gift-cards/")!.label).toBe(
      "/gift-cards/",
    );
  });
});

describe("technical findings", () => {
  const v = view("rich");
  const changes = siteChanges(v.opportunities, "synthetic-alpha", now);
  const groups = findingGroups(v, changes, href);
  it("groups each kind of problem once by severity, most urgent first", () => {
    expect(groups.map((g) => g.severity)).toEqual(["high", "medium", "low"]);
    const high = groups[0].findings.map((f) => f.label).sort();
    expect(high).toEqual([
      "Missing page title",
      "Page does not load correctly",
    ]);
    const meta = groups[1].findings.find(
      (f) => f.code === "missing_meta_description",
    )!;
    expect(meta.pagesText).toBe("2 pages");
    expect(groups[1].findings.some((f) => f.code === NOT_INDEXABLE)).toBe(true);
  });
  it("shows an unknown code in plain words as a low finding", () => {
    expect(groups[2].findings.map((f) => f.label)).toContain(
      "Some future code",
    );
  });
  it("links a finding to its proposed change when one exists, else to a page", () => {
    const title = groups[0].findings.find((f) => f.code === "missing_title")!;
    expect(title.next).toMatchObject({ label: "Review proposed change" });
    expect(title.next!.href).toMatch(/\/opportunities\//);
    const notFound = groups[0].findings.find(
      (f) => f.code === "non_200_status",
    )!;
    expect(notFound.next).toMatchObject({ label: "Open page" });
  });
  it("has no groups for a clean site or one with no pages", () => {
    expect(findingGroups(view("clean"), [], href)).toEqual([]);
    expect(findingGroups(view("empty"), [], href)).toEqual([]);
  });
  it("never shows a finding code", () => {
    expect(
      JSON.stringify(
        groups.flatMap((g) =>
          g.findings.map((f) => [f.label, f.action, f.pagesText]),
        ),
      ),
    ).not.toMatch(RAW);
  });
});

describe("the details dialog", () => {
  it("lists checks, availability and what is not collected", () => {
    const d = websiteDetails(view("rich"), now);
    expect(d.checks.map((c) => c.chip.label)).toEqual([
      "Completed",
      "Partly checked",
    ]);
    expect(d.checks[1].note).toBe("Stopped before every page was checked");
    expect(d.notCollected).toEqual([
      "Named call-to-action events",
      "Conversion funnels",
      "Page health score",
      "Google indexing status",
    ]);
    expect(d.rows[0].chip.label).toBe("Available");
    expect(JSON.stringify(d)).not.toMatch(ISO);
  });
  it("says so when no check has run", () => {
    const d = websiteDetails(view("empty"), now);
    expect(d.checks).toEqual([]);
    expect(d.rows[1].note).toBe("No check has run yet");
    expect(websiteDetails(view("no_access"), now).rows[0].chip.label).toBe(
      "No access",
    );
    expect(pageGap(view("no_website"))).toBe("no_website");
  });
});

describe("one page", () => {
  const detail = (mode: string) => {
    const w = simWorkspace(mode, org, undefined);
    const first = w.pages[1];
    return pageDetail(
      adaptWebsitePage(simPage(mode, org, site, first.id), org, site, first.id),
      "Synthetic hospitality site",
      "synthetic-alpha",
      now,
    );
  };
  it("shows available evidence with figures and a linked repository", () => {
    const d = detail("rich");
    expect(d.label).toBe("Synthetic menu");
    expect(d.tiles.map((t) => [t.label, t.value])).toEqual([
      ["Page status", "200"],
      ["Last checked", "2 days ago"],
      ["Words on page", "640"],
      ["Structured data", "Present"],
    ]);
    const evidence = Object.fromEntries(d.evidence.map((e) => [e.name, e]));
    expect(evidence["Search Console"].value).toBe(
      "150 clicks · 4,300 impressions",
    );
    expect(evidence["Search Console"].note).toBe("Sep 1 – Sep 28, 2026");
    expect(evidence["Key events from organic search"].value).toBe("18");
    expect(evidence["Internal links"].value).toBe("6 in · 14 out");
    expect(evidence["Since the previous check"].chip.label).toBe("Changed");
    expect(d.mapping.mapped).toBe(true);
    expect(d.mapping.fields.map((f) => f.label)).toEqual([
      "SEO title",
      "Meta description",
    ]);
    expect(d.changes).toHaveLength(1);
  });
  it("shows missing evidence as not tracked and an unlinked repository with a reason", () => {
    const d = detail("clean");
    for (const row of d.evidence.slice(0, 3)) {
      expect(row).toMatchObject({ missing: true });
      expect(row.chip.label).toBe("Not tracked");
      expect(row.value).toBe("Not available for this page");
    }
    expect(d.tiles[2]).toMatchObject({ value: "Not checked", missing: true });
    expect(d.mapping).toMatchObject({ mapped: false });
    expect(d.mapping.chip.label).toBe("Repository not linked");
    expect(d.mapping.explanation).toMatch(/not linked to a file/);
    expect(d.mapping.explanation).not.toMatch(/SITE_MAPPING_REQUIRED/);
  });
  it("words an unknown mapping code generically", () => {
    expect(
      mappingView({
        state: "unavailable",
        code: "SOMETHING_NEW",
        repository: null,
        base_branch: null,
        fields: {},
        verification: "executor_rechecks_before_write",
      }).explanation,
    ).toBe("This page cannot take a proposed change yet.");
  });
  it("keeps raw system text off the page", () => {
    for (const mode of ["rich", "clean"]) {
      const d = detail(mode);
      const text = JSON.stringify([
        d.label,
        d.tiles,
        d.evidence,
        d.mapping.chip,
        d.mapping.explanation,
      ]);
      expect(text).not.toMatch(ISO);
      expect(text).not.toMatch(/_/);
    }
  });
});
