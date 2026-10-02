// Synthetic Command Center read feeds for browser tests only. Never imported by the app.
const gamma = "99999999-9999-4999-8999-999999999999";
const metric = (source, availability, current = null, previous = null) => ({
  current,
  previous,
  percent_delta:
    current !== null && previous
      ? ((current - previous) / previous) * 100
      : null,
  source,
  availability,
  freshness_at: null,
});
const missing = (source, availability) => metric(source, availability);
const now = () => new Date().toISOString();
const inDays = (days) => new Date(Date.now() + days * 86400000).toISOString();
export function directory(ids) {
  return {
    [ids.a]: { slug: "synthetic-alpha", name: "Synthetic Alpha" },
    [ids.b]: { slug: "synthetic-beta", name: "Synthetic Beta" },
    [ids.admin]: { slug: "synthetic-admin", name: "Synthetic Admin" },
    [gamma]: { slug: "synthetic-gamma", name: "Synthetic Gamma" },
  };
}
function rows(ids) {
  const dir = directory(ids);
  const base = (id) => ({
    organization_id: id,
    slug: dir[id].slug,
    name: dir[id].name,
    average_local_rank: missing("rank_scan", "not_tracked"),
    local_visibility: missing("rank_scan", "not_tracked"),
    average_position: missing("search_console", "not_connected"),
    search_clicks: missing("search_console", "not_connected"),
  });
  return {
    [ids.a]: {
      ...base(ids.a),
      location: "Carlsbad, CA",
      category: "Restaurant",
      location_count: 1,
      organic_sessions: metric("ga4", "available", 1240, 1100),
      leads: metric("leads", "available", 8, 5),
      reviews: {
        availability: "available",
        total: 40,
        new_in_period: 3,
        average_rating: 4.6,
      },
      open_opportunities: 2,
      health: "needs_attention",
      health_reasons: ["GOOGLE_RECONNECT_REQUIRED", "WORKFLOW_ATTENTION"],
      last_activity: {
        workflow_key: "gbp.publish_post",
        status: "completed",
        at: inDays(-1),
        failure_code: null,
      },
      next_work: {
        workflow_key: "seo.crawl_or_analysis",
        status: "scheduled",
        at: inDays(1),
        failure_code: null,
      },
    },
    [ids.b]: {
      ...base(ids.b),
      location: "San Diego, CA",
      category: "Bar",
      location_count: 2,
      organic_sessions: missing("ga4", "not_connected"),
      leads: metric("leads", "available", 0, 0),
      reviews: {
        availability: "available",
        total: 12,
        new_in_period: 0,
        average_rating: 4.2,
      },
      open_opportunities: 0,
      health: "healthy",
      health_reasons: [],
      last_activity: null,
      next_work: null,
    },
    [gamma]: {
      ...base(gamma),
      location: null,
      category: null,
      location_count: 0,
      organic_sessions: missing("ga4", "not_permitted"),
      leads: missing("leads", "not_permitted"),
      reviews: {
        availability: "no_data",
        total: null,
        new_in_period: null,
        average_rating: null,
      },
      open_opportunities: null,
      health: "not_configured",
      health_reasons: ["GOOGLE_NOT_CONNECTED"],
      last_activity: null,
      next_work: null,
    },
  };
}
const owner = (row) => ({
  organization_id: row.organization_id,
  organization_name: row.name,
  organization_slug: row.slug,
});
const attention = (row) =>
  row.organization_id === gamma || row.health === "healthy"
    ? []
    : [
        {
          ...owner(row),
          code: "GOOGLE_RECONNECT_REQUIRED",
          severity: "critical",
          occurred_at: null,
          reference: null,
        },
        {
          ...owner(row),
          code: "WORKFLOW_FAILED",
          severity: "high",
          occurred_at: now(),
          reference: "gbp.publish_post:PROVIDER_REJECTED",
        },
      ];
const opportunities = (row) =>
  row.open_opportunities
    ? [
        {
          id: "33333333-3333-4333-8333-333333333333",
          ...owner(row),
          opportunity_type: "missing_meta_description",
          classification: "Issue",
          status: "identified",
          priority: 82,
          query: null,
          page: "/menu",
          impressions: 900,
        },
        {
          id: "33333333-3333-4333-8333-333333333334",
          ...owner(row),
          opportunity_type: "ranking_opportunity",
          classification: "Growth Opportunity",
          status: "recommended",
          priority: 64,
          query: "brunch carlsbad",
          page: null,
          impressions: 1200,
        },
      ]
    : [];
const activity = (row) =>
  row.last_activity
    ? [
        {
          ...owner(row),
          workflow_key: row.last_activity.workflow_key,
          completed_at: row.last_activity.at,
        },
      ]
    : [];
const upcoming = (row) =>
  row.next_work
    ? [
        {
          ...owner(row),
          workflow_key: row.next_work.workflow_key,
          next_run_at: row.next_work.at,
        },
      ]
    : [];
const window = (days) => ({
  generated_at: now(),
  days,
  period_start: inDays(-days),
  period_end: now(),
});
export function commandCenter(url, claims, ids) {
  const match = url.pathname.match(/^\/api\/v1\/command-center\/(.*)$/);
  if (!match) return null;
  const admin = claims.sub === ids.admin;
  const all = rows(ids);
  const visibleIds = admin ? [ids.a, ids.b, gamma] : [claims.sub];
  if (!admin && !all[claims.sub])
    return { status: 404, body: { code: "NOT_FOUND" } };
  const access = (id) =>
    id === claims.sub ? "member" : "platform_administrator";
  const days = Number(url.searchParams.get("days") ?? 28);
  const path = match[1];
  if (path === "clients")
    return {
      body: {
        platform_administrator: admin,
        data: visibleIds.map((id) => ({
          organization_id: id,
          slug: directory(ids)[id].slug,
          name: directory(ids)[id].name,
          status: "active",
          access: access(id),
        })),
      },
    };
  if (path === "portfolio") {
    const clients = visibleIds.map((id) => all[id]);
    const attentionAll = clients.flatMap(attention);
    return {
      body: {
        ...window(days),
        client_count: clients.length,
        location_count: clients.reduce((n, c) => n + c.location_count, 0),
        totals: {
          website_leads: metric("leads", "available", 8, 5),
          organic_sessions: metric("ga4", "available", 1240, 1100),
          new_reviews: 3,
          average_rating: 4.4,
          reporting_attention: clients.filter((c) => c.health !== "healthy")
            .length,
          local_visibility: missing("rank_scan", "not_tracked"),
        },
        clients,
        attention: attentionAll,
        opportunities: clients.flatMap(opportunities),
        activity: clients.flatMap(activity),
        upcoming: clients.flatMap(upcoming),
        systems: [
          { key: "google", status: "needs_attention", affected_clients: 1 },
          { key: "analytics", status: "healthy", affected_clients: 0 },
          { key: "automations", status: "error", affected_clients: 1 },
        ],
      },
    };
  }
  const overview = path.match(/^clients\/([^/]+)\/overview$/);
  if (overview) {
    const id = overview[1];
    if (!visibleIds.includes(id))
      return { status: 404, body: { code: "NOT_FOUND" } };
    const row = all[id];
    return {
      body: {
        ...window(days),
        access: access(id),
        client: row,
        attention: attention(row),
        opportunities: opportunities(row),
        activity: activity(row),
        upcoming: upcoming(row),
        systems: [
          {
            key: "google",
            status: row.health_reasons.includes("GOOGLE_NOT_CONNECTED")
              ? "not_connected"
              : row.health_reasons.includes("GOOGLE_RECONNECT_REQUIRED")
                ? "needs_attention"
                : "healthy",
          },
          { key: "analytics", status: "healthy" },
          { key: "search_console", status: "not_connected" },
          { key: "automations", status: "error" },
        ],
        insights: {
          availability: "available",
          workflow_runs: { completed: 12, failed: 1 },
          growth_outcomes: {},
          seo_opportunities: {},
          seo_opportunities_blocked: null,
          content_publications: {},
          reviews: {},
        },
      },
    };
  }
  return { status: 404, body: { code: "NOT_FOUND" } };
}
