import { describe, expect, it } from "vitest";
import * as fixture from "../fixtures/report.mjs";
/* eslint-disable @typescript-eslint/no-explicit-any */
// The plain-JS fixture is shared with the browser simulator, so it is untyped here on purpose.
const detail = fixture.detail as (overrides?: object) => any;
const ORG: string = fixture.ORG;
import {
  adaptPortfolioReports,
  adaptReportDetail,
  adaptReportList,
} from "../../src/adapters/reports";
import {
  PREVIOUS,
  type ComparisonRef,
  type PeriodRef,
} from "../../src/lib/report-period";
import {
  comparisonTile,
  countText,
  currentPanel,
  gapText,
  headlineCards,
  historyRows,
  noteGroups,
  noteText,
  parsePortfolioFilter,
  periodErrorText,
  periodLabel,
  periodRange,
  portfolioRows,
  portfolioTiles,
  reportActions,
  reportFailureText,
  runText,
} from "../../src/lib/report-view";
const SEPTEMBER: PeriodRef = { start: "2026-09-01", end: "2026-09-01" };
const MAY_SEPTEMBER: PeriodRef = { start: "2026-05-01", end: "2026-09-01" };
const want = { organization: ORG, period: SEPTEMBER, revision: 1 };
const RANGE = {
  start_month: "2026-05-01",
  end_month: "2026-09-01",
};
const ranged = (comparison: object = fixture.PREVIOUS, options = {}) =>
  detail({ period: RANGE, comparison, options });
const typed = (overrides: object = {}) =>
  adaptReportDetail(detail(overrides), { organization: ORG });
describe("report adapter", () => {
  it("accepts a stored report and refuses another client's, period or comparison", () => {
    expect(adaptReportDetail(detail(), want).client_name).toBe("Coco Maya");
    expect(() =>
      adaptReportDetail(detail(), { ...want, organization: "x" }),
    ).toThrow("REPORT_SCOPE_MISMATCH");
    expect(() =>
      adaptReportDetail(detail(), { ...want, period: MAY_SEPTEMBER }),
    ).toThrow("REPORT_SCOPE_MISMATCH");
    const other: ComparisonRef = { kind: "year-ago" };
    expect(() =>
      adaptReportDetail(detail(), { ...want, comparison: other }),
    ).toThrow("REPORT_SCOPE_MISMATCH");
    expect(
      adaptReportDetail(detail(), { ...want, comparison: PREVIOUS }).revision,
    ).toBe(1);
  });
  it("refuses a figure that has a number and says it is unavailable", () => {
    const bad = detail();
    bad.snapshot.analytics.organic_sessions.current = {
      availability: "unavailable",
      value: 0,
      reason: "not_synced",
    };
    expect(() => adaptReportDetail(bad, want)).toThrow();
  });
  it("refuses a month point that is missing but carries a number", () => {
    const bad = detail();
    bad.snapshot.monthly[0].period[0] = {
      month: "2026-09-01",
      availability: "unavailable",
      value: 0,
    };
    expect(() => adaptReportDetail(bad, want)).toThrow();
  });
  it("refuses a snapshot whose readiness or comparison disagrees with the report", () => {
    const readiness = detail();
    readiness.snapshot.readiness = "ready";
    expect(() => adaptReportDetail(readiness, want)).toThrow(
      "REPORT_SCOPE_MISMATCH",
    );
    const basis = detail();
    basis.snapshot.comparison.basis = "same_period_last_year";
    expect(() => adaptReportDetail(basis, want)).toThrow(
      "REPORT_SCOPE_MISMATCH",
    );
  });
  it("refuses a headline that carries two figures", () => {
    const bad = detail();
    bad.snapshot.headlines[0].rate = bad.snapshot.gbp.actions.action_rate;
    expect(() => adaptReportDetail(bad, want)).toThrow();
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
  });
});
describe("periods in words", () => {
  it("labels a month, a range and a range across years", () => {
    expect(periodLabel(SEPTEMBER)).toBe("September 2026");
    expect(periodLabel(MAY_SEPTEMBER)).toBe("May – September 2026");
    expect(periodLabel({ start: "2025-11-01", end: "2026-02-01" })).toBe(
      "November 2025 – February 2026",
    );
  });
  it("states the days a period covers", () => {
    expect(periodRange({ start: "2028-02-01", end: "2028-02-01" })).toBe(
      "February 1–29, 2028",
    );
    expect(periodRange(MAY_SEPTEMBER)).toBe("May 1 – September 30, 2026");
    expect(periodRange({ start: "2025-11-01", end: "2026-02-01" })).toBe(
      "November 1, 2025 – February 28, 2026",
    );
  });
  it("gives every period error a sentence", () => {
    expect(periodErrorText.REPORT_PERIOD_TOO_LONG).toBe(
      "A report covers 1 to 12 whole months.",
    );
    expect(reportFailureText("REPORT_BASELINE_OVERLAPS")).toContain("baseline");
    expect(reportFailureText("SOMETHING_NEW")).not.toMatch(/[A-Z]+_[A-Z]+/);
  });
});
describe("headlines", () => {
  it("map to words, with the change against what the report was compared with", () => {
    const cards = headlineCards(typed({ options: {} }).snapshot);
    expect(cards.map((card) => card.label)).toEqual([
      "Profile views",
      "Profile actions",
      "Website search clicks",
      "Visits from search",
    ]);
    expect(cards[0].value).toMatch(/^[\d,]+$/);
    expect(cards[0].change).toMatch(/^\+\d+(\.\d)?% vs August 2026$/);
    expect(cards[0].direction).toBe("up");
    expect(cards[0].line).toBe(
      "Times people saw your business on Google Search and Google Maps.",
    );
  });
  it("say monthly average when the baseline is a different length", () => {
    const baseline = {
      basis: "custom_baseline",
      baseline_start: "2026-01-01",
      baseline_end: "2026-02-01",
    };
    const snap = adaptReportDetail(ranged(baseline), {
      organization: ORG,
    }).snapshot;
    expect(snap.comparison.compared_as).toBe("monthly_average");
    expect(headlineCards(snap)[0].change).toContain(
      "vs the monthly average of January – February 2026",
    );
  });
  it("never state a headline for a figure that is not there", () => {
    const report = adaptReportDetail(
      ranged(fixture.PREVIOUS, { gone: ["search_console", "analytics"] }),
      { organization: ORG },
    );
    const labels = headlineCards(report.snapshot).map((card) => card.label);
    expect(labels).not.toContain("Website search clicks");
    expect(labels).not.toContain("Visits from search");
    expect(labels.length).toBeLessThanOrEqual(4);
  });
});
describe("missing data is never zero", () => {
  const snap = typed().snapshot;
  it("shows an unavailable tile as unavailable, with its reason", () => {
    const missing = {
      ...snap.gbp.profile_views.total,
      current: { availability: "unavailable", reason: "not_synced" },
    } as any;
    expect(comparisonTile("Profile views", missing, snap)).toMatchObject({
      value: "Unavailable",
      missing: true,
      description: "Not synced yet",
    });
  });
  it("gives a missing figure no count, and a reason in words", () => {
    const figure = { availability: "unavailable", reason: "no_data" } as const;
    expect(countText(figure)).toBeNull();
    expect(gapText(figure)).toBe("No data reported");
    expect(countText({ availability: "available", value: 0 })).toBe("0");
  });
  it("marks a partial figure and withholds its trend", () => {
    const partial = {
      ...snap.gbp.profile_views.total,
      current: {
        availability: "partial",
        value: 1700,
        months_covered: 4,
        months_expected: 5,
      },
      change: null,
      change_percent: null,
    } as any;
    const tile = comparisonTile("Profile views", partial, snap);
    expect(tile.trend).toBeNull();
    expect(tile.value).toBe("1,700*");
    expect(tile.description).toBe("Partial · 4 of 5 months synced");
  });
});
describe("data notes", () => {
  const report = adaptReportDetail(
    ranged(fixture.PREVIOUS, { bookings: true, partialSearch: true }),
    { organization: ORG },
  );
  it("word a figure Google stopped reporting as a question of reporting, not demand", () => {
    const note = report.snapshot.notes.find(
      (item) => item.code === "optional_figure_not_reported",
    )!;
    expect(noteText(note)).toBe(
      "Google reported no bookings this period (45 in the comparison period). This can reflect a change in how Google reports it, not lower demand.",
    );
  });
  it("say how many months are missing", () => {
    const note = report.snapshot.notes.find(
      (item) => item.code === "search_console_months_missing",
    )!;
    expect(noteText(note)).toContain("1 month of search data has not synced");
    expect(noteGroups(report.snapshot).map((group) => group.section)).toContain(
      "Search Console",
    );
  });
});
describe("actions", () => {
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
  });
});
describe("lists", () => {
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
  it("filters the portfolio and counts tiles from the real counts", () => {
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
    const notGenerated = portfolioRows(view, "not_generated")[0];
    expect(notGenerated).toMatchObject({
      delivery: "Not generated",
      action: "Open reports",
    });
    expect(portfolioRows(view, "sent")[0].delivery).toBe("Sent Oct 3, 2026");
    expect(portfolioRows(view, "all")[0].href).toBe(
      "/clients/a/reports/2026-09/",
    );
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
  it("lists each stored report with its period, comparison and address", () => {
    const base = {
      revision: 1,
      status: "draft",
      readiness: "ready",
      is_current: true,
      created_at: "2026-10-01T15:00:00Z",
      approved_at: null,
      delivery: null,
    };
    const list = adaptReportList(
      {
        organization_id: ORG,
        current_month: "2026-09-01",
        current: null,
        history: [
          {
            ...base,
            period: RANGE,
            comparison: {
              basis: "custom_baseline",
              baseline_start: "2026-01-01",
              baseline_end: "2026-03-01",
            },
          },
          {
            ...base,
            period: RANGE,
            comparison: fixture.PREVIOUS,
            revision: 2,
          },
          {
            ...base,
            period: RANGE,
            comparison: fixture.PREVIOUS,
            revision: 1,
            is_current: false,
          },
        ],
        upcoming: null,
        permissions: { can_generate: true, can_publish: true },
      },
      ORG,
    );
    const rows = historyRows(list, "coco-maya");
    expect(rows[0]).toMatchObject({
      period: "May – September 2026",
      comparison: "vs January – March 2026",
      version: null,
    });
    expect(rows[0].href).toBe(
      "/clients/coco-maya/reports/2026-05_2026-09/?vs=2026-01_2026-03&revision=1",
    );
    expect(rows[1]).toMatchObject({
      comparison: "vs previous period",
      version: "Version 2",
    });
    expect(rows[2].href).toBe(
      "/clients/coco-maya/reports/2026-05_2026-09/?revision=1",
    );
  });
});
