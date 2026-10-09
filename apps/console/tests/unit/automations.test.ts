import { describe, expect, it } from "vitest";
import {
  REASONS,
  STATUSES,
  WORKFLOW_TYPES,
  adaptAutomationDetail,
  adaptAutomations,
  type AutomationItem,
} from "../../src/adapters/automations";
import {
  ACTION_LABELS,
  REASON_COPY,
  SOURCE_NAMES,
  WORKFLOW_NAMES,
  applyFilters,
  dialogView,
  failureCode,
  filterQuery,
  multiLocationClients,
  overviewView,
  parseFilters,
  rowView,
  runFailureText,
  typeOptions,
} from "../../src/lib/automation-view";
import { durationText, frequencyText } from "../../src/lib/present";
import { portfolioHealthRows } from "../../src/lib/portfolio-view";

const now = new Date("2026-10-08T20:00:00Z");
const CLIENT = "11111111-1111-4111-8111-111111111111";
const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
type Run = NonNullable<AutomationItem["latest_run"]>;
function item(over: Partial<AutomationItem> & { n: number }): AutomationItem {
  const { n, ...rest } = over;
  return {
    id: id(n),
    workflow_type: "reviews.ingest",
    client: { id: CLIENT, name: "Park 101", slug: "park101" },
    location: null,
    frequency: {
      kind: "daily",
      interval: null,
      hour: 6,
      minute: 0,
      weekday: null,
      day_of_month: null,
      timezone: "America/Los_Angeles",
    },
    status: "healthy",
    latest_run: {
      status: "completed",
      outcome: "succeeded",
      reason: null,
      started_at: "2026-10-08T13:00:00Z",
      finished_at: "2026-10-08T13:01:00Z",
    },
    next_run_at: "2026-10-09T13:00:00Z",
    source: "reviews",
    attention: null,
    run_now_allowed: true,
    ...rest,
  };
}
const failed = (reason: Run["reason"]): Partial<AutomationItem> => ({
  status: "needs_attention",
  latest_run: {
    status: "failed",
    outcome: "failed",
    reason,
    started_at: "2026-10-08T12:00:00Z",
    finished_at: "2026-10-08T12:01:00Z",
  },
  attention: {
    reason: reason!,
    recovery_actions: ["reconnect_google_business_profile"],
    occurred_at: "2026-10-08T12:01:00Z",
  },
});
const list = (data: AutomationItem[]) => ({
  generated_at: now.toISOString(),
  counts: {
    total: data.length,
    healthy: data.filter((d) => d.status === "healthy").length,
    needs_attention: data.filter((d) => d.status === "needs_attention").length,
    running: data.filter((d) => d.status === "running").length,
    paused: data.filter((d) => d.status === "paused").length,
    not_run_yet: data.filter((d) => d.status === "not_run_yet").length,
  },
  data,
});
const ISO = /\d{4}-\d{2}-\d{2}T/;

describe("every failure code has plain-language copy", () => {
  it.each([...REASONS])("%s", (code) => {
    const copy = REASON_COPY[code];
    expect(copy.what.length).toBeGreaterThan(10);
    expect(copy.next.length).toBeGreaterThan(10);
    // Never raw system text.
    expect(copy.what + copy.next).not.toMatch(/[A-Z]{3,}_[A-Z_]+/);
  });
  it("covers exactly the contract's codes", () => {
    expect(Object.keys(REASON_COPY).sort()).toEqual([...REASONS].sort());
    expect(Object.keys(WORKFLOW_NAMES).sort()).toEqual(
      [...WORKFLOW_TYPES].sort(),
    );
    expect(Object.keys(ACTION_LABELS).length).toBe(5);
    expect(Object.keys(SOURCE_NAMES).length).toBe(7);
  });
  it("tells the named failures what to do", () => {
    expect(REASON_COPY.GBP_PERFORMANCE_ACCESS_DENIED.next).toMatch(
      /Reconnect Google Business Profile/,
    );
    expect(REASON_COPY.ANALYTICS_SYNC_INCOMPLETE.next).toMatch(
      /analytics connection/,
    );
    expect(REASON_COPY.SEO_ACTIVE_WEBSITE_MISSING.next).toMatch(/website/);
    expect(REASON_COPY.GBP_PERFORMANCE_RATE_LIMITED.next).toMatch(
      /try again on its own/,
    );
  });
});

describe("adapter", () => {
  it("accepts a consistent list and refuses mismatched counts or scope", () => {
    const data = [
      item({ n: 1 }),
      item({ n: 2, ...failed("GBP_PERFORMANCE_ACCESS_DENIED") }),
    ];
    expect(adaptAutomations(list(data)).counts.needs_attention).toBe(1);
    const bad = list(data);
    bad.counts.needs_attention = 0;
    expect(() => adaptAutomations(bad)).toThrow("AUTOMATION_COUNT_MISMATCH");
    expect(() => adaptAutomations(list(data), id(99))).toThrow(
      "AUTOMATION_SCOPE_MISMATCH",
    );
    expect(() =>
      adaptAutomations({ ...list(data), extra: 1 }, undefined),
    ).not.toThrow();
  });
  it("rejects an unknown status, code or extra item field", () => {
    expect(() =>
      adaptAutomations(list([item({ n: 1, status: "broken" as never })])),
    ).toThrow();
    expect(() =>
      adaptAutomations(
        list([{ ...item({ n: 1 }), cron_expression: "* * * * *" } as never]),
      ),
    ).toThrow();
  });
  it("checks a detail belongs to the schedule asked for", () => {
    const detail = { ...item({ n: 1 }), runs: [] };
    expect(adaptAutomationDetail(detail, id(1)).id).toBe(id(1));
    expect(() => adaptAutomationDetail(detail, id(2))).toThrow(
      "AUTOMATION_SCOPE_MISMATCH",
    );
  });
});

describe("presenters", () => {
  it("formats frequency from the typed value in the schedule's zone", () => {
    const base = item({ n: 1 }).frequency;
    expect(frequencyText(base, now)).toBe("Daily · 6:00 AM");
    expect(
      frequencyText({ ...base, kind: "interval_minutes", interval: 30 }, now),
    ).toBe("Every 30 minutes");
    expect(
      frequencyText({ ...base, kind: "interval_hours", interval: 6 }, now),
    ).toBe("Every 6 hours");
    expect(
      frequencyText({ ...base, kind: "weekly", weekday: 1, hour: 7 }, now),
    ).toBe("Weekly · Monday · 7:00 AM");
    expect(
      frequencyText(
        { ...base, kind: "monthly", day_of_month: 1, hour: 8 },
        now,
      ),
    ).toBe("Monthly · 1st · 8:00 AM");
    expect(frequencyText({ ...base, kind: "custom" }, now)).toBe(
      "Custom schedule",
    );
    expect(
      frequencyText({ ...base, timezone: "America/New_York", hour: 9 }, now),
    ).toBe("Daily · 9:00 AM EDT");
  });
  it("formats durations", () => {
    expect(durationText(42)).toBe("42 sec");
    expect(durationText(180)).toBe("3 min");
    expect(durationText(3900)).toBe("1 h 5 min");
    expect(durationText(null)).toBe("");
  });
  it("never shows ISO timestamps, enum values or ids in a row", () => {
    const rows = [
      item({ n: 1 }),
      item({ n: 2, ...failed("GBP_PERFORMANCE_ACCESS_DENIED") }),
      item({ n: 3, status: "paused", next_run_at: null }),
      item({ n: 4, status: "not_run_yet", latest_run: null }),
    ].map((i) => {
      // `status` is the row's data attribute; everything else is shown.
      const { status, ...shown } = rowView(i, now);
      void status;
      return JSON.stringify(shown);
    });
    for (const text of rows) {
      expect(text).not.toMatch(ISO);
      expect(text).not.toMatch(/needs_attention|not_run_yet|GBP_PERFORMANCE/);
    }
  });
  it("says Not run yet and Paused instead of showing a blank or a zero", () => {
    const never = rowView(
      item({ n: 4, status: "not_run_yet", latest_run: null }),
      now,
    );
    expect([never.last, never.outcome]).toEqual(["Not run yet", "Not run yet"]);
    expect(
      rowView(item({ n: 3, status: "paused", next_run_at: null }), now).next,
    ).toBe("Paused");
  });
  it("shows a rate limit as will retry, in neutral tone, not failed", () => {
    const limited = item({
      n: 5,
      latest_run: {
        status: "retry_scheduled",
        outcome: "will_retry",
        reason: "GBP_PERFORMANCE_RATE_LIMITED",
        started_at: "2026-10-08T12:00:00Z",
        finished_at: "2026-10-08T12:01:00Z",
      },
    });
    const row = rowView(limited, now);
    expect(row.outcomeChip).toEqual({ label: "Will retry", tone: "neutral" });
    expect(row.outcome).toBe("Google is limiting requests right now.");
    expect(row.statusChip.label).toBe("Healthy");
  });
  it("builds the dialog: human action vs run outcome, recovery links, run-now only where allowed", () => {
    const attention = {
      ...item({ n: 2, ...failed("GBP_PERFORMANCE_ACCESS_DENIED") }),
      runs: [
        {
          id: id(50),
          status: "failed" as const,
          outcome: "failed" as const,
          reason: "GBP_PERFORMANCE_ACCESS_DENIED" as const,
          started_at: "2026-10-08T12:00:00Z",
          finished_at: "2026-10-08T12:01:00Z",
          duration_seconds: 60,
        },
      ],
    };
    const view = dialogView(attention, now);
    expect(view.heading).toBe("Human action required");
    expect(view.actions).toEqual([
      {
        label: "Reconnect Google Business Profile",
        href: "/clients/park101/integrations/",
      },
    ]);
    expect(view.canRun).toBe(true);
    expect(view.history[0].duration).toBe("1 min");
    expect(JSON.stringify(view)).not.toMatch(ISO);
    const post = dialogView(
      {
        ...item({
          n: 6,
          workflow_type: "gbp.generate_post",
          run_now_allowed: false,
        }),
        runs: [],
      },
      now,
    );
    expect(post.heading).toBe("Run outcome");
    expect(post.canRun).toBe(false);
    const running = dialogView(
      { ...item({ n: 7, status: "running" }), runs: [] },
      now,
    );
    expect(running.canRun).toBe(false);
    expect(running.running).toBe(true);
  });
  it("maps run-now failures to typed messages with a fallback", () => {
    expect(runFailureText("AUTOMATION_RUN_IN_PROGRESS")).toMatch(
      /already running/,
    );
    expect(runFailureText("AUTOMATION_RUN_NOT_ALLOWED")).toMatch(/schedule/);
    expect(runFailureText("AUTOMATION_LOCATION_RETIRED")).toMatch(
      /no longer in use/,
    );
    expect(runFailureText("SOMETHING_ELSE")).toMatch(/did not start/);
    expect(failureCode({ error: { code: "AUTOMATION_PAUSED" } }, 409)).toBe(
      "AUTOMATION_PAUSED",
    );
    expect(failureCode({ code: "CSRF_INVALID" }, 403)).toBe("CSRF_INVALID");
    expect(failureCode("nope", 502)).toBe("HTTP_502");
  });
});

describe("location", () => {
  const place = (n: number, name: string) => ({ id: id(900 + n), name });
  const two = [
    item({ n: 1, location: place(1, "Downtown") }),
    item({ n: 2, location: place(2, "DONT USE") }),
    item({ n: 3, location: null }),
  ];
  const other = "22222222-2222-4222-8222-222222222222";
  const solo = item({
    n: 4,
    client: { id: other, name: "Solo", slug: "solo" },
    location: place(3, "Only place"),
  });
  it("names the location only for a client with several locations", () => {
    const multi = multiLocationClients([...two, solo]);
    expect([...multi]).toEqual([CLIENT]);
    const rows = [...two, solo].map((i) => rowView(i, now, multi));
    expect(rows.map((r) => r.locationName)).toEqual([
      "Downtown",
      "DONT USE",
      null,
      null,
    ]);
    // Without the set (single-location, or unknown) nothing extra shows.
    expect(rowView(two[0], now).locationName).toBeNull();
  });
  it("carries the location into the overview rows and the dialog", () => {
    const multi = multiLocationClients(two);
    const overview = overviewView(two, now, 5, multi);
    expect(overview.upcoming.map((r) => r.locationName)).toContain("DONT USE");
    const dialog = dialogView({ ...two[1], runs: [] }, now, multi);
    expect(dialog.locationName).toBe("DONT USE");
    expect(dialogView({ ...two[1], runs: [] }, now).locationName).toBeNull();
  });
  it("accepts a client-wide schedule and rejects a malformed location", () => {
    expect(adaptAutomations(list(two)).data[2].location).toBeNull();
    const bad = list([item({ n: 1, location: { id: "x", name: "y" } })]);
    expect(() => adaptAutomations(bad)).toThrow();
  });
});

describe("filters and overview", () => {
  const data = [
    item({ n: 1 }),
    item({
      n: 2,
      workflow_type: "gbp.sync_performance",
      source: "google_business_profile",
      ...failed("GBP_PERFORMANCE_ACCESS_DENIED"),
    }),
    item({
      n: 3,
      workflow_type: "gbp.sync",
      status: "paused",
      next_run_at: null,
    }),
  ];
  it("parses filters and refuses unknown values", () => {
    expect(parseFilters(new URLSearchParams(""))).toEqual({
      view: "overview",
      status: "all",
      client: "all",
      type: "all",
    });
    expect(
      parseFilters(new URLSearchParams("status=needs_attention&view=all"))
        ?.status,
    ).toBe("needs_attention");
    for (const bad of [
      "status=bad",
      "type=content.nope",
      "organization_id=x",
      "view=zzz",
    ])
      expect(parseFilters(new URLSearchParams(bad))).toBeNull();
    expect(STATUSES.length).toBe(5);
  });
  it("filters by status, client and type and lists only existing types", () => {
    const f = parseFilters(new URLSearchParams("status=needs_attention"))!;
    expect(applyFilters(data, f).map((i) => i.id)).toEqual([id(2)]);
    expect(
      typeOptions(data)
        .map((t) => t.value)
        .sort(),
    ).toEqual(["gbp.sync", "gbp.sync_performance", "reviews.ingest"]);
    expect(
      typeOptions(data).some((t) => t.value === ("seo.analyze" as never)),
    ).toBe(false);
    expect(filterQuery({ view: "all", status: "needs_attention" })).toBe(
      "?view=all&status=needs_attention",
    );
    expect(filterQuery({})).toBe("");
  });
  it("overview counts come from the same statuses the server counted", () => {
    const view = adaptAutomations(list(data));
    const overview = overviewView(view.data, now, 5);
    expect(overview.attention.length).toBe(view.counts.needs_attention);
    expect(
      overview.health.find((h) => h.label === "Require attention")?.count,
    ).toBe(view.counts.needs_attention);
    expect(overview.upcoming.some((r) => r.status === "paused")).toBe(false);
  });
  it("the dashboard health link lands on the filtered Automations view", () => {
    const system = (affected: number) =>
      ({
        systems: [
          {
            key: "automations",
            status: affected ? "needs_attention" : "healthy",
            affected_clients: affected,
          },
        ],
      }) as never;
    expect(portfolioHealthRows(system(2))[0].href).toBe(
      "/automations/?status=needs_attention",
    );
    expect(portfolioHealthRows(system(0))[0].href).toBe("/automations/");
  });
});
