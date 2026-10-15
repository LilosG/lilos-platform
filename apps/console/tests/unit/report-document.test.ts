import { describe, expect, it } from "vitest";
import * as fixture from "../fixtures/report.mjs";
/* eslint-disable @typescript-eslint/no-explicit-any */
const detail = fixture.detail as (overrides?: object) => any;
import { adaptReportDetail } from "../../src/adapters/reports";
import {
  documentView,
  monthlyChart,
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
const MACHINE = new Set(["key", "id", "direction", "group", "class"]);
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
  it("opens with the client, the period, the comparison and where it covers", () => {
    const { cover } = documentView(report());
    expect(cover).toMatchObject({
      client: "Coco Maya",
      title: "Performance report",
      period: "May – September 2026",
      compared: "Compared with: December 2025 – April 2026",
      locations: ["Coco Maya Downtown", "Coco Maya Beach"],
      preparedBy: "Lilos Growth",
    });
    expect(cover.preparedOn).toBe("October 1, 2026");
  });
  it("words the comparison by its basis", () => {
    expect(
      documentView(report({}, { basis: "same_period_last_year" })).cover
        .compared,
    ).toBe("Compared with: the same period last year (May – September 2025)");
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
      ).cover.compared,
    ).toBe("Compared with: January – February 2026, as monthly averages");
  });
  it("leads with four headline cards from the headlines the API chose", () => {
    const view = documentView(report());
    expect(view.headlines).toHaveLength(4);
    expect(view.headlines[0]).toMatchObject({
      label: "Profile views",
      direction: "up",
    });
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
      "Website search",
      "Website traffic",
      "Reviews",
    ]);
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
    expect(card.rowNotes).toEqual([
      "Google reported no bookings this period (45 in the comparison period). This can reflect a change in how Google reports it, not lower demand.",
    ]);
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
    expect(views.current).toMatch(/\(\d[\d,]* a month\)$/);
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
  it("list the top non-branded searches and say how much brand there was", () => {
    const search = searchView(snap, "Coco Maya")!;
    expect(search.queries).toHaveLength(10);
    expect(search.queries.map((row) => row.label)).not.toContain("coco maya");
    expect(search.brandedNote).toContain("31%");
    expect(search.topNote).toContain("not totals of every search");
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
