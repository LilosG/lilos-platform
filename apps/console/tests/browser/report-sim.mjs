// Synthetic reports for browser tests only. Never imported by the app.
import {
  comparisonSlug,
  detail,
  monthsOf,
  narrativeFor,
  periodSlug,
} from "../fixtures/report.mjs";
const json = (status, body) => ({ status, body });
const fail = (status, code) => json(status, { error: { code } });
const names = {
  a: ["Synthetic Alpha", "synthetic-alpha"],
  b: ["Synthetic Beta", "synthetic-beta"],
};
const LAST_ENDED = "2026-09-01";
export const state = { clients: {}, mode: "default" };
// A drafted narrative whose numbers are worked out from the fixture's own report when it is stored.
const words = { auto: true, origin: "hermes" };
const rangeWords = {
  what_changed:
    "Across May to September, more people found Coco Maya on Google than in the five months before.\n\nSearch clicks and website visits from search both grew, and every new review was answered.",
  next_work:
    "We will keep publishing weekly posts and build on the private events page.\n\nWe will also keep watching the searches that bring people to the menu.",
  origin: "manual",
};
const PREVIOUS = {
  basis: "previous_period",
  baseline_start: null,
  baseline_end: null,
};
const BASELINE = {
  basis: "custom_baseline",
  baseline_start: "2025-12-01",
  baseline_end: "2026-04-01",
};
const key = (period, spec) =>
  `${periodSlug(period.start_month, period.end_month)}/${comparisonSlug(spec)}`;
const SEPTEMBER = { start_month: LAST_ENDED, end_month: LAST_ENDED };
const MAY_SEPTEMBER = { start_month: "2026-05-01", end_month: LAST_ENDED };
/** A stored report: one period, one comparison, its revisions and how its figures look. */
const report = (period, comparison, revisions, options = {}) => ({
  period,
  comparison,
  revisions: revisions.map((row) => {
    if (!row.narrative.auto) return row;
    const { auto: _auto, ...rest } = row.narrative;
    return {
      ...row,
      narrative: { ...rest, ...narrativeFor(period, comparison, options) },
    };
  }),
  options,
});
const revision = (number, status, narrative, extra = {}) => ({
  revision: number,
  status,
  approved_at: status === "draft" ? null : "2026-10-02T17:00:00Z",
  delivery:
    status === "sent"
      ? { sent_on: "2026-10-03", recorded_at: "2026-10-05T17:00:00Z" }
      : null,
  narrative,
  ...extra,
});
/**
 * "draft": alpha has a written draft. "sent": alpha's report was approved and sent.
 * "range": alpha also has an approved five-month report. "gaps": that report has partial and
 * missing data and a figure Google stopped reporting.
 */
export function reset(mode = "default") {
  state.mode = mode;
  state.clients = {};
  if (mode === "draft" || mode === "sent")
    state.clients.a = {
      reports: {
        [key(SEPTEMBER, PREVIOUS)]: report(SEPTEMBER, PREVIOUS, [
          revision(1, mode === "sent" ? "sent" : "draft", words),
        ]),
      },
    };
  if (mode === "document")
    // A full report: cards, topics, gains, milestones and two locations.
    state.clients.a = {
      reports: {
        [key(SEPTEMBER, PREVIOUS)]: report(
          SEPTEMBER,
          PREVIOUS,
          [revision(1, "ready", words)],
          {
            search: "results",
            cards: true,
            names: ["Synthetic Alpha Downtown", "Synthetic Alpha Beach"],
            milestones: [
              {
                day: "2026-05-01",
                label:
                  "Lilos Growth begins Google Business Profile management.",
              },
              { day: "2026-07-17", label: "New website launches." },
            ],
          },
        ),
      },
    };
  if (mode === "sparse")
    // Shaped like a client with thin data: a draft, no search before May, four addresses for
    // the home page, a misspelled brand search, and Google no longer reporting bookings.
    state.clients.b = {
      reports: {
        [key(MAY_SEPTEMBER, BASELINE)]: report(
          MAY_SEPTEMBER,
          BASELINE,
          [revision(1, "draft", words)],
          {
            search: "alone",
            searchAlone: true,
            cards: true,
            urlVariants: true,
            bookings: true,
            bookingsCompared: 28,
            bookingsYear: 101,
            internalNames: ["Main"],
          },
        ),
      },
    };
  if (mode === "range" || mode === "gaps")
    state.clients.a = {
      reports: {
        [key(MAY_SEPTEMBER, PREVIOUS)]: report(
          MAY_SEPTEMBER,
          PREVIOUS,
          [revision(1, "ready", rangeWords)],
          mode === "gaps"
            ? { partialSearch: true, bookings: true, gone: ["analytics"] }
            : {},
        ),
      },
    };
}
const keyOf = (ids, id) => (id === ids.a ? "a" : id === ids.b ? "b" : null);
const store = (client) => (state.clients[client] ??= { reports: {} });
const view = (ids, client, stored, row, perms) => {
  const [name, slug] = names[client];
  return detail({
    organization_id: ids[client],
    client_name: name,
    client_slug: slug,
    period: stored.period,
    comparison: stored.comparison,
    options: stored.options,
    revision: row.revision,
    revision_count: stored.revisions.length,
    status: row.status,
    is_current: row.revision === stored.revisions.length,
    approved_at: row.approved_at,
    delivery: row.delivery,
    narrative: row.narrative,
    permissions: perms,
  });
};
const perms = (claims, ids) => ({
  can_generate: true,
  can_publish:
    claims.sub === ids.admin || claims.sub === ids.a || claims.sub === ids.b,
});
const rowOf = (stored, r) => ({
  period: stored.period,
  comparison: stored.comparison,
  revision: r.revision,
  status: r.status,
  readiness: "ready_with_note",
  is_current: r.revision === stored.revisions.length,
  created_at: "2026-10-01T15:00:00Z",
  approved_at: r.approved_at,
  delivery: r.delivery,
});
const MONTHS_BETWEEN = (a, b) => monthsOf(a, b).length;
/** The API's own checks on a request to generate, as typed codes. */
function refusal(body) {
  const { start_month: start, end_month: end, comparison = PREVIOUS } = body;
  if (end > LAST_ENDED) return "REPORT_MONTH_NOT_ENDED";
  if (end < start) return "REPORT_PERIOD_ORDER";
  if (MONTHS_BETWEEN(start, end) > 12) return "REPORT_PERIOD_TOO_LONG";
  if (comparison.basis === "custom_baseline") {
    if (!comparison.baseline_start || !comparison.baseline_end)
      return "REPORT_BASELINE_REQUIRED";
    if (comparison.baseline_end < comparison.baseline_start)
      return "REPORT_PERIOD_ORDER";
    if (comparison.baseline_end >= start) return "REPORT_BASELINE_OVERLAPS";
  }
  return null;
}
export function reports(req, url, claims, ids, body) {
  const path = url.pathname;
  if (state.mode === "error" && path.includes("/reports"))
    return fail(503, "DATABASE_UNAVAILABLE");
  if (path === "/api/v1/command-center/reports") {
    const visible = ["a", "b"].filter(
      (k) => claims.sub === ids.admin || claims.sub === ids[k],
    );
    const clients = visible.map((k) => {
      const stored = store(k).reports[key(SEPTEMBER, PREVIOUS)];
      const latest = stored?.revisions.at(-1);
      return {
        organization_id: ids[k],
        slug: names[k][1],
        name: names[k][0],
        month: LAST_ENDED,
        revision: latest?.revision ?? null,
        status: latest?.status ?? null,
        readiness: latest ? "ready_with_note" : null,
        sent_on: latest?.delivery?.sent_on ?? null,
      };
    });
    const open = clients.filter((c) => c.status !== "sent");
    return json(200, {
      month: LAST_ENDED,
      counts: {
        ready: 0,
        needs_attention: open.filter((c) => c.readiness === "ready_with_note")
          .length,
        missing_data: 0,
        sent: clients.filter((c) => c.status === "sent").length,
        not_generated: clients.filter((c) => c.status === null).length,
      },
      clients,
    });
  }
  const match = path.match(
    /^\/api\/v1\/organizations\/([^/]+)\/command-center\/reports(?:\/(generate|([^/]+)\/([^/]+)\/(\d+)(?:\/(narrative|draft-narrative|approve|mark-sent))?))?$/,
  );
  if (!match) return undefined;
  const [, id, head, periodPart, comparisonPart, rev, action] = match;
  const client = keyOf(ids, id);
  if (!client || !(claims.sub === ids.admin || claims.sub === id))
    return fail(403, "PERMISSION_DENIED");
  const mine = store(client);
  const p = perms(claims, ids);
  if (!head && req.method === "GET") {
    const all = Object.values(mine.reports);
    const history = all
      .flatMap((stored) =>
        [...stored.revisions].reverse().map((r) => rowOf(stored, r)),
      )
      .sort((x, y) => y.period.end_month.localeCompare(x.period.end_month));
    return json(200, {
      organization_id: id,
      current_month: LAST_ENDED,
      current:
        history.find(
          (row) =>
            row.period.start_month === LAST_ENDED &&
            row.period.end_month === LAST_ENDED &&
            row.comparison.basis === "previous_period" &&
            row.is_current,
        ) ?? null,
      history,
      upcoming: {
        kind: "generate_monthly_report",
        next_run_at: "2026-11-01T16:00:00Z",
        month: "2026-10-01",
      },
      permissions: p,
    });
  }
  if (head === "generate") {
    const code = refusal(body);
    if (code) return fail(400, code);
    const period = { start_month: body.start_month, end_month: body.end_month };
    const comparison = {
      basis: body.comparison.basis,
      baseline_start: body.comparison.baseline_start ?? null,
      baseline_end: body.comparison.baseline_end ?? null,
    };
    const name = key(period, comparison);
    const existing = mine.reports[name];
    if (!existing)
      mine.reports[name] = report(period, comparison, [
        revision(1, "draft", {
          what_changed: "",
          next_work: "",
          origin: "none",
        }),
      ]);
    const stored = mine.reports[name];
    return json(200, {
      report: view(ids, client, stored, stored.revisions.at(-1), p),
      created: !existing,
    });
  }
  const stored = mine.reports[`${periodPart}/${comparisonPart}`];
  const row = stored?.revisions.find((r) => r.revision === Number(rev));
  if (!row) return fail(404, "REPORT_NOT_FOUND");
  if (!action) return json(200, view(ids, client, stored, row, p));
  if (action === "narrative") {
    if (row.status !== "draft") return fail(409, "REPORT_NOT_EDITABLE");
    row.narrative = {
      ...body,
      origin: "manual",
      // The figures of a card are looked up again by their keys; only the words change.
      result_cards: body.result_cards
        ? body.result_cards.map((card) => ({
            ...card,
            figures:
              row.narrative.result_cards?.find(
                (old) => old.figure_keys.join() === card.figure_keys.join(),
              )?.figures ?? [],
          }))
        : (row.narrative.result_cards ?? undefined),
    };
    return json(200, view(ids, client, stored, row, p));
  }
  if (action === "draft-narrative") {
    row.narrative = {
      ...narrativeFor(stored.period, stored.comparison, stored.options),
      origin: "hermes",
      result_cards: row.narrative.result_cards,
    };
    return json(200, {
      report: view(ids, client, stored, row, p),
      outcome: "drafted",
      failure: null,
    });
  }
  if (!p.can_publish) return fail(403, "PERMISSION_DENIED");
  if (action === "approve") {
    if (!row.narrative.what_changed) return fail(409, "REPORT_NARRATIVE_EMPTY");
    row.status = "ready";
    row.approved_at = "2026-10-02T17:00:00Z";
    return json(200, view(ids, client, stored, row, p));
  }
  if (row.status === "draft") return fail(409, "REPORT_NOT_APPROVED");
  row.status = "sent";
  row.delivery ??= {
    sent_on: body.sent_on,
    recorded_at: "2026-10-05T17:00:00Z",
  };
  return json(200, view(ids, client, stored, row, p));
}
