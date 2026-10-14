// Synthetic monthly reports for browser tests only. Never imported by the app.
import { detail } from "../fixtures/report.mjs";
const json = (status, body) => ({ status, body });
const fail = (status, code) => json(status, { error: { code } });
const names = {
  a: ["Synthetic Alpha", "synthetic-alpha"],
  b: ["Synthetic Beta", "synthetic-beta"],
};
export const state = { clients: {}, mode: "default" };
export function reset(mode = "default") {
  state.mode = mode;
  state.clients = {};
}
const keyOf = (ids, id) => (id === ids.a ? "a" : id === ids.b ? "b" : null);
const store = (key) => (state.clients[key] ??= { revisions: [] });
const view = (ids, key, revision, perms) => {
  const [name, slug] = names[key];
  const row = revision;
  return detail({
    organization_id: ids[key],
    client_name: name,
    client_slug: slug,
    revision: row.revision,
    revision_count: store(key).revisions.length,
    status: row.status,
    is_current: row.revision === store(key).revisions.length,
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
const rowOf = (r) => ({
  month: "2026-09-01",
  revision: r.revision,
  status: r.status,
  readiness: "ready_with_note",
  is_current: true,
  created_at: "2026-10-01T15:00:00Z",
  approved_at: r.approved_at,
  delivery: r.delivery,
});
export function reports(req, url, claims, ids, body) {
  const path = url.pathname;
  if (state.mode === "error" && path.includes("/reports"))
    return fail(503, "DATABASE_UNAVAILABLE");
  if (path === "/api/v1/command-center/reports") {
    const visible = ["a", "b"].filter(
      (k) => claims.sub === ids.admin || claims.sub === ids[k],
    );
    const clients = visible.map((k) => {
      const latest = store(k).revisions.at(-1);
      return {
        organization_id: ids[k],
        slug: names[k][1],
        name: names[k][0],
        month: "2026-09-01",
        revision: latest?.revision ?? null,
        status: latest?.status ?? null,
        readiness: latest ? "ready_with_note" : null,
        sent_on: latest?.delivery?.sent_on ?? null,
      };
    });
    const open = clients.filter((c) => c.status !== "sent");
    return json(200, {
      month: "2026-09-01",
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
    /^\/api\/v1\/organizations\/([^/]+)\/command-center\/reports(?:\/(generate|(\d{4}-\d{2})\/(\d+)(?:\/(narrative|draft-narrative|approve|mark-sent))?))?$/,
  );
  if (!match) return undefined;
  const [, id, head, , rev, action] = match;
  const key = keyOf(ids, id);
  if (!key || !(claims.sub === ids.admin || claims.sub === id))
    return fail(403, "PERMISSION_DENIED");
  const mine = store(key);
  const p = perms(claims, ids);
  if (!head && req.method === "GET")
    return json(200, {
      organization_id: id,
      current_month: "2026-09-01",
      current: mine.revisions.length ? rowOf(mine.revisions.at(-1)) : null,
      history: [...mine.revisions].reverse().map(rowOf),
      upcoming: {
        kind: "generate_monthly_report",
        next_run_at: "2026-11-01T16:00:00Z",
        month: "2026-10-01",
      },
      permissions: p,
    });
  if (head === "generate") {
    if (!mine.revisions.length)
      mine.revisions.push({
        revision: 1,
        status: "draft",
        approved_at: null,
        delivery: null,
        narrative: { what_changed: "", next_work: "", origin: "none" },
      });
    return json(200, {
      report: view(ids, key, mine.revisions.at(-1), p),
      created: true,
    });
  }
  const row = mine.revisions.find((r) => r.revision === Number(rev));
  if (!row) return fail(404, "REPORT_NOT_FOUND");
  if (!action) return json(200, view(ids, key, row, p));
  if (action === "narrative") {
    if (row.status !== "draft") return fail(409, "REPORT_NOT_EDITABLE");
    row.narrative = { ...body, origin: "manual" };
    return json(200, view(ids, key, row, p));
  }
  if (action === "draft-narrative") {
    row.narrative = {
      what_changed:
        "Your profile was viewed 1,800 times in September, up from 1,530 in August.",
      next_work: "We will keep publishing posts and replying to every review.",
      origin: "hermes",
    };
    return json(200, {
      report: view(ids, key, row, p),
      outcome: "drafted",
      failure: null,
    });
  }
  if (!p.can_publish) return fail(403, "PERMISSION_DENIED");
  if (action === "approve") {
    if (!row.narrative.what_changed) return fail(409, "REPORT_NARRATIVE_EMPTY");
    row.status = "ready";
    row.approved_at = "2026-10-02T17:00:00Z";
    return json(200, view(ids, key, row, p));
  }
  if (row.status === "draft") return fail(409, "REPORT_NOT_APPROVED");
  row.status = "sent";
  row.delivery ??= {
    sent_on: body.sent_on,
    recorded_at: "2026-10-05T17:00:00Z",
  };
  return json(200, view(ids, key, row, p));
}
