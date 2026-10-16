import { describe, expect, it } from "vitest";
import * as fixture from "../fixtures/report.mjs";
/* eslint-disable @typescript-eslint/no-explicit-any */
const detail = fixture.detail as (overrides?: object) => any;
import { adaptReportDetail } from "../../src/adapters/reports";
import { toneOf } from "../../src/lib/report-view";
import {
  documentView,
  mergePages,
  monthlyChart,
  pageLabel,
  notIncluded,
  scorecard,
  searchView,
  termsView,
  workLines,
} from "../../src/lib/report-document";
const RANGE = { start_month: "2026-05-01", end_month: "2026-09-01" };
const report = (options = {}, comparison: object = fixture.PREVIOUS) =>
  adaptReportDetail(detail({ period: RANGE, comparison, options }), {
    organization: fixture.ORG,
  });
// What a person reads: every string except the machine fields that only choose a style.
const MACHINE = new Set(["key", "id", "direction", "tone", "group", "class"]);
const strings = (value: unknown): string[] =>
  typeof value === "string"
    ? [value]
    : Array.isArray(value)
      ? value.flatMap(strings)
      : value && typeof value === "object"
        ? Object.entries(value)
            .filter(([name]) => !MACHINE.has(name))
            .flatMap(([, item]) => strings(item))
        : [];
describe("the client document", () => {
  it("opens with a title, one line of context and who prepared it", () => {
    const { cover } = documentView(report());
    expect(cover).toMatchObject({
      title: "May – September 2026 performance report",
      intro:
        "How Coco Maya performed in May – September 2026, compared with the months before (December 2025 – April 2026).",
      preparedBy: "Lilos Growth",
      kicker: "Lilos Growth · Coco Maya",
      milestones: null,
    });
    expect(cover.preparedOn).toBe("October 1, 2026");
  });
  it("words the comparison by its basis", () => {
    expect(
      documentView(report({}, { basis: "same_period_last_year" })).cover.intro,
    ).toContain("the same months last year (May – September 2025)");
    expect(
      documentView(
        report(
          {},
          {
            basis: "custom_baseline",
            baseline_start: "2026-01-01",
            baseline_end: "2026-02-01",
          },
        ),
      ).cover.intro,
    ).toContain("January – February 2026, as monthly averages");
  });
  it("shows the timeline only when the client has milestones, and the cover names more than one location by its profile", () => {
    expect(documentView(report()).cover.milestones).toBeNull();
    const view = documentView(
      report({
        names: ["Coco Maya by Miss B's", "Coco Maya Beach"],
        milestones: [{ day: "2026-05-01", label: "We began." }],
      }),
    );
    expect(view.cover.milestones).toEqual([
      { date: "May 1, 2026", label: "We began." },
      { date: "May – September 2026", label: "The period this report covers." },
    ]);
    expect(view.cover.kicker).toBe(
      "Lilos Growth · Coco Maya · Coco Maya by Miss B's · Coco Maya Beach",
    );
    // The internal location names never reach the cover.
    expect(strings(view.cover).join(" ")).not.toContain("Coco Maya Downtown");
  });
  it("shows result cards, never invented ones, and a draft is marked", () => {
    expect(documentView(report()).glance).toBeNull();
    const view = documentView(report({ cards: true, search: "results" }));
    expect(view.draft).toBe(true);
    const cards = view.glance!.cards;
    expect(cards).toHaveLength(4);
    expect(cards[0]).toMatchObject({
      value: "+80%",
      tone: "good",
      headline: true,
      title: "More first-page Google rankings",
    });
    expect(cards[0].footer).toContain("Search Console");
    expect(cards.filter((card) => card.headline)).toHaveLength(1);
  });
  it("never shows a missing figure as 0, NaN, a dash, an ISO date or an enum", () => {
    for (const options of [
      {},
      { gone: ["search_console", "analytics", "reviews"] },
      { partialSearch: true, bookings: true },
    ]) {
      const text = strings(documentView(report(options))).join("\n");
      expect(text).not.toMatch(/NaN|undefined|null/);
      expect(text).not.toMatch(/\d{4}-\d{2}-\d{2}/);
      expect(text).not.toMatch(/\b[a-z]+(_[a-z]+)+\b|\b[A-Z]+(_[A-Z]+)+\b/);
      expect(text).not.toMatch(/(^|\n)[–-](\n|$)/);
    }
  });
});
describe("the scorecard", () => {
  it("groups the figures and leaves out those that are not available", () => {
    const full = scorecard(report().snapshot);
    expect(full.groups.map((group) => group.title)).toEqual([
      "Google Business Profile",
      "Website and Google search",
      "Website visits",
      "Reviews",
    ]);
    // Every row says where its figure comes from, and each group says what it is set against.
    expect(full.groups[0].rows.every((row) => row.source !== "")).toBe(true);
    expect(full.groups[0].kicker).toContain("vs. December 2025 – April 2026");
    expect(full.hasYear).toBe(true);
    const bare = scorecard(
      report({ gone: ["search_console", "analytics"] }).snapshot,
    );
    expect(bare.groups.map((group) => group.title)).toEqual([
      "Google Business Profile",
      "Reviews",
    ]);
  });
  it("shows the year column only when some row has a year", () => {
    const sameYear = scorecard(
      report({}, { basis: "same_period_last_year" }).snapshot,
    );
    expect(sameYear.hasYear).toBe(false);
  });
  it("marks a partial figure and footnotes it", () => {
    const card = scorecard(report({ partialSearch: true }).snapshot);
    const clicks = card.groups
      .flatMap((group) => group.rows)
      .find((row) => row.label === "Search clicks")!;
    expect(clicks.current).toMatch(/\*$/);
    expect(clicks.change).toBe("Not comparable");
    expect(card.footnotes.join(" ")).toContain("Search figures cover only");
  });
  it("lists a figure Google stopped reporting as not comparable, with its note", () => {
    const card = scorecard(report({ bookings: true }).snapshot);
    const bookings = card.groups
      .flatMap((group) => group.rows)
      .find((row) => row.label === "Bookings")!;
    expect(bookings).toMatchObject({
      current: "Not reported",
      compared: "45",
      change: "Not comparable",
    });
    // The reason sits next to the figure, not in a footnote.
    expect(bookings.note).toBe(
      "Google reported no bookings this period (45 in the comparison period). This can reflect a change in how Google reports it, not lower demand.",
    );
  });
  it("compares counts as monthly averages when the baseline is another length", () => {
    const card = scorecard(
      report(
        {},
        {
          basis: "custom_baseline",
          baseline_start: "2026-01-01",
          baseline_end: "2026-02-01",
        },
      ).snapshot,
    );
    const views = card.groups[0].rows[0];
    expect(views.currentSub).toMatch(/^\d[\d,]* a month$/);
    expect(views.compared).toMatch(/ a month$/);
  });
});
describe("sections", () => {
  const snap = report().snapshot;
  it("show the top 10 search terms and how many more there are", () => {
    const terms = termsView(snap)!;
    expect(terms.rows).toHaveLength(10);
    expect(terms.more).toBe(97 - 10);
    expect(
      terms.rows.find((row) => row.keyword === "private event venue")!.value,
    ).toBe("< 15");
  });
  it("group searches by topic and show what gained ground, or say nothing was compared", () => {
    const withResults = report({ search: "results" });
    const view = searchView(
      withResults.snapshot,
      withResults.search_results ?? null,
      [],
    )!;
    expect(view.tiles.map((tile) => tile.value)).toEqual([
      "171",
      "64",
      "542",
      "37,290",
    ]);
    expect(view.tiles[0]).toMatchObject({
      line: "+76 searches (+80%) from 95",
      tone: "good",
    });
    expect(view.tiles[3].line).toBe("+7,304 (+24%) from 29,986");
    expect(view.topics[0]).toMatchObject({
      label: "Private events & groups",
      top10: { before: "2", after: "32" },
    });
    const first = view.gains[0].rows[0];
    expect(first.position).toEqual({ before: "#7.5", after: "#3.2" });
    expect(
      view.gains.flatMap((g) => g.rows.map((r) => r.position.before)),
    ).toContain("New");
    expect(view.topicNote).toContain("not totals of every search");
    const alone = report({ search: "alone", searchAlone: true });
    const bare = searchView(alone.snapshot, alone.search_results ?? null, [])!;
    // No comparison months: only where the period stands, never a "before" of zero.
    expect(bare.comparable).toBe(false);
    expect(bare.gains).toEqual([]);
    expect(bare.tiles[0].line).toBeNull();
    expect(bare.topics.every((topic) => topic.top10.before === null)).toBe(
      true,
    );
  });
  it("adds up the addresses of one page", () => {
    const merged = mergePages(
      [
        "https://a.example/",
        "http://a.example/",
        "https://www.a.example/",
        "https://a.example/index.html",
        "https://a.example/menu/",
      ].map((page, index) => ({
        page,
        clicks: 10,
        impressions: 100,
        ctr: 10,
        position: 2 + index,
        compared_clicks: null,
        clicks_change: null,
      })),
    );
    expect(merged.map((row) => [row.page, row.clicks])).toEqual([
      ["/", 40],
      ["/menu", 10],
    ]);
    expect(merged[0].impressions).toBe(400);
    expect(pageLabel("https://a.example/")).toBe("Home page");
  });
  it("names at most ten posts and counts the rest", () => {
    const base = report().snapshot;
    const crowded = {
      ...base,
      work: {
        groups: [
          {
            kind: "gbp_post" as const,
            count: 14,
            titles: Array.from({ length: 10 }, (_, i) => `Post ${i + 1}.`),
          },
        ],
      },
    };
    expect(workLines(crowded)[0]).toMatchObject({ count: "14", more: 4 });
    expect(workLines(crowded)[0].titles).toHaveLength(10);
  });
  it("chart the comparison period beside the period, with its monthly average", () => {
    const chart = monthlyChart(
      snap,
      "profile_views",
      "Profile views by month",
    )!;
    expect(chart.model.bars.map((bar) => bar.group)).toEqual([
      ...Array(5).fill("compared"),
      ...Array(5).fill("period"),
    ]);
    expect(chart.model.baseline!.label).toContain("Comparison average");
    expect(chart.model.description).toContain("Profile views by month");
  });
  it("draw a month not synced as a gap and name it as not included", () => {
    const gappy = report({
      missing: ["2026-06-01"],
      partialSearch: true,
    }).snapshot;
    const chart = monthlyChart(
      gappy,
      "search_clicks",
      "Search clicks by month",
    )!;
    expect(chart.model.bars.filter((bar) => bar.missing)).toHaveLength(1);
    expect(notIncluded(gappy).join("\n")).toContain(
      "Website search figures for June 2026: not synced yet",
    );
  });
  it("leave out a section with nothing to say and list why", () => {
    const bare = report({ gone: ["search_console", "analytics", "reviews"] });
    const view = documentView(bare);
    expect(view.search).toBeNull();
    expect(view.reviews).toBeNull();
    const lines = view.notes.notIncluded;
    expect(lines).toContain("Local search ranking: not tracked yet");
    expect(lines).toContain(
      "Website search from Search Console: not connected",
    );
    expect(lines).toContain(
      "Website visits from Google Analytics: not connected",
    );
    expect(lines).toContain("Reviews: not synced yet");
  });
  it("list work that was done and nothing that was not", () => {
    const lines = workLines(snap);
    expect(lines.map((line) => line.label)).not.toContain(
      "Business Profile changes applied",
    );
    expect(lines[0]).toMatchObject({
      label: "Business Profile posts published",
      count: "20",
    });
  });
  it("define the branded split and the monthly-average comparison in the notes", () => {
    const view = documentView(
      report(
        {},
        {
          basis: "custom_baseline",
          baseline_start: "2026-01-01",
          baseline_end: "2026-02-01",
        },
      ),
    );
    const terms = view.notes.definitions.map((item) => item.term);
    expect(terms).toContain("Branded searches");
    expect(terms).toContain("Compared as monthly averages");
  });
});

describe("tone of a change", () => {
  const rows = () =>
    scorecard(report().snapshot).groups.flatMap((group) => group.rows);
  it("treats a lower average position as good", () => {
    expect(toneOf("down", "lower")).toBe("good");
    expect(toneOf("up", "lower")).toBe("bad");
    const row = rows().find((r) => r.label.startsWith("Average position"));
    expect(row?.direction).toBe("down");
    expect(row?.tone).toBe("good");
  });
  it("treats more views as good and fewer as bad", () => {
    expect(toneOf("up")).toBe("good");
    expect(toneOf("down")).toBe("bad");
  });
  it("leaves no change and no comparison neutral", () => {
    expect(toneOf("flat")).toBe("neutral");
    expect(toneOf("none", "lower")).toBe("neutral");
  });
});
