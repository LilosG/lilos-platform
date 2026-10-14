import { describe, expect, it } from "vitest";
import * as fixture from "../fixtures/report.mjs";
/* eslint-disable @typescript-eslint/no-explicit-any */
// The plain-JS fixture is shared with the browser simulator, so it is untyped here on purpose.
const detail = fixture.detail as (overrides?: object) => any;
const snapshot = fixture.snapshot as (overrides?: object) => any;
const ORG: string = fixture.ORG;
import {
  adaptPortfolioReports,
  adaptReportDetail,
  adaptReportList,
} from "../../src/adapters/reports";
import {
  comparisonRows,
  currentPanel,
  dailyCharts,
  figureText,
  monthLabel,
  monthRange,
  noteGroups,
  noteText,
  parsePortfolioFilter,
  portfolioRows,
  portfolioTiles,
  profileTiles,
  reportActions,
  reviewsView,
  runText,
  splitViews,
  termRows,
} from "../../src/lib/report-view";
const want = { organization: ORG, month: "2026-09-01", revision: 1 };
const withGbp = (patch: object) => {
  const base = snapshot();
  return snapshot({ gbp: { ...base.gbp, ...patch } });
};
describe("report adapter", () => {
  it("accepts a stored report and refuses another client's", () => {
    expect(adaptReportDetail(detail(), want).client_name).toBe("Coco Maya");
    expect(() =>
      adaptReportDetail(detail(), { ...want, organization: "x" }),
    ).toThrow("REPORT_SCOPE_MISMATCH");
  });
  it("refuses a figure that has a number and says it is unavailable", () => {
    const bad = snapshot();
    bad.analytics.organic_sessions.current = {
      availability: "unavailable",
      value: 0,
      reason: "not_synced",
    };
    expect(() => adaptReportDetail(detail({ snapshot: bad }), want)).toThrow();
  });
  it("refuses a snapshot whose readiness disagrees with the report", () => {
    expect(() =>
      adaptReportDetail(
        detail({ snapshot: snapshot({ readiness: "ready" }) }),
        want,
      ),
    ).toThrow("REPORT_SCOPE_MISMATCH");
  });
  it("checks portfolio counts against the rows", () => {
    const row = (status: string | null, readiness: string | null) => ({
      organization_id: ORG,
      slug: "a",
      name: "A",
      month: "2026-09-01",
      revision: status ? 1 : null,
      status,
      readiness,
      sent_on: status === "sent" ? "2026-10-03" : null,
    });
    const view = {
      month: "2026-09-01",
      counts: {
        ready: 1,
        needs_attention: 0,
        missing_data: 0,
        sent: 1,
        not_generated: 1,
      },
      clients: [row("draft", "ready"), row("sent", "ready"), row(null, null)],
    };
    expect(adaptPortfolioReports(view).clients).toHaveLength(3);
    expect(() =>
      adaptPortfolioReports({ ...view, counts: { ...view.counts, ready: 2 } }),
    ).toThrow("REPORT_COUNT_MISMATCH");
    expect(
      adaptReportList(
        {
          organization_id: ORG,
          current_month: "2026-09-01",
          current: null,
          history: [],
          upcoming: null,
          permissions: { can_generate: true, can_publish: false },
        },
        ORG,
      ).history,
    ).toEqual([]);
  });
});
describe("report presenters", () => {
  const snap = adaptReportDetail(detail(), want).snapshot;
  it("names months and ranges", () => {
    expect(monthLabel("2026-09-01")).toBe("September 2026");
    expect(monthRange("2028-02-01")).toBe("February 1–29, 2028");
  });
  it("builds tiles with trend and a year comparison", () => {
    const [views, calls] = profileTiles(snap).headline;
    expect(views).toMatchObject({
      label: "Profile views",
      value: "1,800",
      trend: 18,
    });
    expect(views.description).toContain("vs August");
    expect(views.description).toContain("vs last year");
    expect(calls.value).toBe("200");
  });
  it("never shows a missing figure as zero", () => {
    const missing = snapshot();
    missing.gbp.profile_views.total.current = {
      availability: "unavailable",
      reason: "not_synced",
    };
    const tile = profileTiles(missing).headline[0];
    expect(tile).toMatchObject({
      value: "Unavailable",
      missing: true,
      description: "Not synced yet",
    });
    expect(figureText({ availability: "unavailable", reason: "no_data" })).toBe(
      "–",
    );
    expect(figureText({ availability: "available", value: 0 })).toBe("0");
  });
  it("shows optional tiles only when reported, and a reported zero as 0", () => {
    const optional = profileTiles(snap).optional;
    expect(optional.map((t) => [t.label, t.value])).toEqual([
      ["Bookings", "0"],
    ]);
  });
  it("marks a partial month and withholds the trend", () => {
    const partial = snapshot();
    partial.gbp.profile_views.total.current = {
      availability: "partial",
      value: 1700,
      days_covered: 29,
      days_expected: 30,
    };
    const tile = profileTiles(partial).headline[0];
    expect(tile.trend).toBeNull();
    expect(tile.description).toBe("Partial month · 29 of 30 days synced");
  });
  it("draws splits only when every part is known", () => {
    expect(splitViews(snap).complete).toBe(true);
    const partial = withGbp({
      profile_views: {
        ...snap.gbp.profile_views,
        maps_search: {
          parts: [
            {
              key: "maps",
              figure: { availability: "partial", value: 5 },
              share_percent: null,
            },
            {
              key: "search",
              figure: { availability: "partial", value: 5 },
              share_percent: null,
            },
          ],
        },
      },
    });
    expect(splitViews(partial).complete).toBe(false);
  });
  it("shows a bound as a limit, never as zero", () => {
    expect(termRows(snap).map((t) => t.value)).toEqual(["120", "80", "< 15"]);
    expect(termRows(snap)[2].bounded).toBe(true);
  });
  it("charts synced days and says which are missing", () => {
    expect(dailyCharts(snap).views).not.toBeNull();
    const gap = withGbp({
      daily: { ...snap.gbp.daily, missing_days: ["2026-09-30"] },
    });
    expect(dailyCharts(gap).note).toBe(
      "1 day was not synced yet and is left out.",
    );
  });
  it("lists every profile figure beside last month and last year", () => {
    const rows = comparisonRows(snap);
    expect(rows.map((r) => r.label)).toContain("Google Maps on mobile");
    expect(rows.at(-1)).toMatchObject({
      label: "Action rate",
      current: "28.6%",
      change: "−2.8 pts",
    });
    expect(rows[0]).toMatchObject({
      current: "1,800",
      previous: "1,530",
      change: "+270 (+17.6%)",
    });
  });
  it("turns data note codes into sentences, grouped by section", () => {
    expect(noteText(snap.notes[0])).toBe(
      "Google has not published this month’s search terms yet.",
    );
    expect(noteGroups(snap)[0].section).toBe("Search terms");
  });
  it("summarizes reviews with a distribution", () => {
    const reviews = reviewsView(snap);
    expect(reviews.ratingText).toBe("4.8");
    expect(reviews.distribution[0]).toMatchObject({ stars: 5, count: 260 });
  });
  it("decides what a person may do", () => {
    const draft = adaptReportDetail(detail(), want);
    expect(reportActions(draft).approve).toEqual({
      allowed: false,
      why: "Write both narrative sections first.",
    });
    const ready = adaptReportDetail(
      detail({
        narrative: { what_changed: "a", next_work: "b", origin: "manual" },
      }),
      want,
    );
    expect(reportActions(ready).approve.allowed).toBe(true);
    const viewer = adaptReportDetail(
      detail({ permissions: { can_generate: false, can_publish: false } }),
      want,
    );
    expect(reportActions(viewer).approve.allowed).toBe(false);
    const missing = adaptReportDetail(
      detail({
        readiness: "missing_data",
        snapshot: snapshot({ readiness: "missing_data" }),
        narrative: { what_changed: "a", next_work: "b", origin: "manual" },
      }),
      want,
    );
    expect(reportActions(missing).approve.why).toContain("missing");
  });
  it("filters the portfolio and counts tiles from the real counts", () => {
    const row = (
      name: string,
      status: string | null,
      readiness: string | null,
    ) => ({
      organization_id: ORG,
      slug: name,
      name,
      month: "2026-09-01",
      revision: status ? 1 : null,
      status,
      readiness,
      sent_on: status === "sent" ? "2026-10-03" : null,
    });
    const view = adaptPortfolioReports({
      month: "2026-09-01",
      counts: {
        ready: 0,
        needs_attention: 1,
        missing_data: 1,
        sent: 1,
        not_generated: 1,
      },
      clients: [
        row("a", "draft", "ready_with_note"),
        row("b", "draft", "missing_data"),
        row("c", "sent", "ready"),
        row("d", null, null),
      ],
    });
    expect(portfolioTiles(view).map((t) => t.value)).toEqual([
      "0",
      "1",
      "1",
      "1",
    ]);
    expect(portfolioRows(view, "needs_attention").map((r) => r.name)).toEqual([
      "a",
    ]);
    expect(portfolioRows(view, "not_generated")[0]).toMatchObject({
      delivery: "–",
      action: "Open reports",
    });
    expect(portfolioRows(view, "sent")[0].delivery).toBe("Sent Oct 3, 2026");
    expect(parsePortfolioFilter("bogus")).toBeNull();
    expect(parsePortfolioFilter(null)).toBe("all");
  });
  it("describes the current report and the schedule without system text", () => {
    const list = adaptReportList(
      {
        organization_id: ORG,
        current_month: "2026-09-01",
        current: null,
        history: [],
        upcoming: {
          kind: "generate_monthly_report",
          next_run_at: "2026-11-01T16:00:00Z",
          month: "2026-10-01",
        },
        permissions: { can_generate: true, can_publish: true },
      },
      ORG,
    );
    const panel = currentPanel(list, "coco-maya");
    expect(panel.generate).toBe(true);
    expect(panel.text).toContain("Nov 1, 8:00 AM Pacific");
    expect(runText("2026-11-01T16:00:00Z")).toBe("Nov 1, 8:00 AM Pacific");
  });
});
