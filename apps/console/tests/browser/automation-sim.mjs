// Synthetic Automations feeds for browser tests only. Never imported by the app.
const gamma = "99999999-9999-4999-8999-999999999999";
const hoursAgo = (h) => new Date(Date.now() - h * 3600000).toISOString();
const inHours = (h) => new Date(Date.now() + h * 3600000).toISOString();
const sid = (n) => `a0a0a0a0-0000-4000-8000-${String(n).padStart(12, "0")}`;
const daily = (hour, minute = 0) => ({
  kind: "daily",
  interval: null,
  hour,
  minute,
  weekday: null,
  day_of_month: null,
  timezone: "America/Los_Angeles",
});
const every = (kind, interval) => ({
  kind,
  interval,
  hour: null,
  minute: kind === "interval_hours" ? 0 : null,
  weekday: null,
  day_of_month: null,
  timezone: "America/Los_Angeles",
});
const done = (h) => ({
  status: "completed",
  outcome: "succeeded",
  reason: null,
  started_at: hoursAgo(h + 0.02),
  finished_at: hoursAgo(h),
});
const stopped = (h, status, outcome, reason) => ({
  status,
  outcome,
  reason,
  started_at: hoursAgo(h + 0.02),
  finished_at: hoursAgo(h),
});
function build(ids) {
  const alpha = { id: ids.a, name: "Synthetic Alpha", slug: "synthetic-alpha" };
  const beta = { id: ids.b, name: "Synthetic Beta", slug: "synthetic-beta" };
  const third = { id: gamma, name: "Synthetic Gamma", slug: "synthetic-gamma" };
  const place = (id, name) => ({ id: `d0d0d0d0-0000-4000-8000-${id}`, name });
  const carlsbad = place("000000000001", "Carlsbad");
  const dontUse = place("000000000002", "DONT USE");
  const make = (n, client, type, source, extra) => ({
    id: sid(n),
    workflow_type: type,
    client,
    location: null,
    frequency: daily(5),
    status: "healthy",
    latest_run: done(6),
    next_run_at: inHours(18),
    source,
    attention: null,
    run_now_allowed: true,
    ...extra,
  });
  const failedRun = (reason, actions) => ({
    status: "needs_attention",
    latest_run: stopped(5, "failed", "failed", reason),
    attention: {
      reason,
      recovery_actions: actions,
      occurred_at: hoursAgo(5),
    },
  });
  return [
    make(1, alpha, "reviews.ingest", "reviews", {
      location: carlsbad,
      frequency: every("interval_hours", 6),
    }),
    // Alpha has a second location with the same schedule: the rows differ only by place.
    make(10, alpha, "reviews.ingest", "reviews", {
      location: dontUse,
      frequency: every("interval_hours", 6),
    }),
    make(2, alpha, "gbp.sync_performance", "google_business_profile", {
      location: carlsbad,
      frequency: daily(6, 15),
      ...failedRun("GBP_PERFORMANCE_ACCESS_DENIED", [
        "reconnect_google_business_profile",
      ]),
    }),
    make(3, alpha, "gbp.sync", "google_business_profile", {
      status: "paused",
      next_run_at: null,
      latest_run: stopped(30, "failed", "failed", "GBP_SYNC_FAILED"),
      run_now_allowed: false,
    }),
    make(4, alpha, "seo.crawl_or_analysis", "website", {
      status: "not_run_yet",
      latest_run: null,
      frequency: {
        kind: "weekly",
        interval: null,
        hour: 7,
        minute: 0,
        weekday: 1,
        day_of_month: null,
        timezone: "America/Los_Angeles",
      },
    }),
    make(5, alpha, "gbp.generate_post", "google_business_profile", {
      run_now_allowed: false,
      frequency: {
        kind: "weekly",
        interval: null,
        hour: 16,
        minute: 0,
        weekday: 2,
        day_of_month: null,
        timezone: "America/Los_Angeles",
      },
    }),
    // Beta has one location: nothing extra is shown for it.
    make(6, beta, "reviews.ingest", "reviews", {
      location: place("000000000003", "Encinitas"),
      frequency: every("interval_minutes", 30),
    }),
    make(7, beta, "seo.sync_search_console", "search_console", {
      ...failedRun("SEARCH_CONSOLE_SYNC_INCOMPLETE", [
        "check_search_console_connection",
      ]),
    }),
    make(8, beta, "gbp.sync_performance", "google_business_profile", {
      latest_run: stopped(
        2,
        "retry_scheduled",
        "will_retry",
        "GBP_PERFORMANCE_RATE_LIMITED",
      ),
    }),
    make(9, third, "insights.sync_analytics", "analytics", {
      ...failedRun("ANALYTICS_SYNC_INCOMPLETE", ["check_analytics_connection"]),
    }),
  ];
}
export const state = { mode: "default", running: new Set(), runs: [] };
export function reset(mode = "default") {
  state.mode = mode;
  state.running.clear();
  state.runs = [];
}
const counts = (data) => {
  const n = (s) => data.filter((d) => d.status === s).length;
  return {
    total: data.length,
    healthy: n("healthy"),
    needs_attention: n("needs_attention"),
    running: n("running"),
    paused: n("paused"),
    not_run_yet: n("not_run_yet"),
  };
};
const key = "Idempotency-Key".toLowerCase();
/** Returns {status, body} for an Automations request, or null for any other path. */
export function automations(req, url, claims, ids) {
  const match = url.pathname.match(
    /^\/api\/v1\/command-center\/automations(?:\/([^/]+)(\/run)?)?$/,
  );
  if (!match) return null;
  const admin = claims.sub === ids.admin && claims.aal === "aal2";
  const visible = admin ? [ids.a, ids.b, gamma] : [claims.sub];
  if (state.mode === "error") return { status: 503, body: { code: "DOWN" } };
  const items = (state.mode === "empty" ? [] : build(ids))
    .filter((i) => visible.includes(i.client.id))
    .map((i) =>
      state.running.has(i.id)
        ? {
            ...i,
            status: "running",
            attention: null,
            latest_run: {
              status: "running",
              outcome: "in_progress",
              reason: null,
              started_at: hoursAgo(0.01),
              finished_at: null,
            },
          }
        : i,
    );
  const [, scheduleId, run] = match;
  if (!scheduleId) {
    const only = url.searchParams.get("organization_id");
    if (only && !visible.includes(only))
      return { status: 404, body: { code: "NOT_FOUND" } };
    const data = items.filter((i) => !only || i.client.id === only);
    return {
      status: 200,
      body: {
        generated_at: new Date().toISOString(),
        counts: counts(data),
        data,
      },
    };
  }
  const item = items.find((i) => i.id === scheduleId);
  if (!item) return { status: 404, body: { code: "NOT_FOUND" } };
  if (run) {
    if (req.method !== "POST") return { status: 405, body: {} };
    const given = req.headers[key];
    if (!given || given.length < 8)
      return { status: 422, body: { error: { code: "VALIDATION_ERROR" } } };
    if (!item.run_now_allowed && item.status === "paused")
      return { status: 409, body: { error: { code: "AUTOMATION_PAUSED" } } };
    if (!item.run_now_allowed)
      return {
        status: 403,
        body: { error: { code: "AUTOMATION_RUN_NOT_ALLOWED" } },
      };
    const replayed = state.runs.some(
      (r) => r.id === item.id && r.key === given,
    );
    if (state.mode === "busy" && !replayed)
      return {
        status: 409,
        body: { error: { code: "AUTOMATION_RUN_IN_PROGRESS" } },
      };
    if (!replayed) state.runs.push({ id: item.id, key: given });
    state.running.add(item.id);
    return {
      status: 202,
      body: {
        schedule_id: item.id,
        run_id: "b0b0b0b0-0000-4000-8000-000000000001",
        run_status: "queued",
        replayed,
      },
    };
  }
  const runs = [
    item.latest_run && {
      id: "c0c0c0c0-0000-4000-8000-000000000001",
      status: item.latest_run.status,
      outcome: item.latest_run.outcome,
      reason: item.latest_run.reason,
      started_at: item.latest_run.started_at,
      finished_at: item.latest_run.finished_at,
      duration_seconds: item.latest_run.finished_at ? 72 : null,
    },
    item.latest_run && {
      id: "c0c0c0c0-0000-4000-8000-000000000002",
      status: "completed",
      outcome: "succeeded",
      reason: null,
      started_at: hoursAgo(30),
      finished_at: hoursAgo(29.98),
      duration_seconds: 65,
    },
  ].filter(Boolean);
  return { status: 200, body: { ...item, runs } };
}
