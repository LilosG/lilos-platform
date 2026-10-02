import { z } from "zod";
import type { components } from "@lilos/contracts/api";
import { read } from "./bff";
export type PortfolioOverview = components["schemas"]["PortfolioOverview"];
export type ClientOverview = components["schemas"]["ClientOverview"];
export type ClientRow = components["schemas"]["ClientRow"];
export type MetricValue = components["schemas"]["MetricValue"];
export type VisibleClient = components["schemas"]["VisibleClient"];
export const REPORTING_DAYS = [7, 28, 90] as const;
export type ReportingDays = (typeof REPORTING_DAYS)[number];
export function reportingDays(value: string | null): ReportingDays | null {
  if (value === null) return 28;
  const days = Number(value);
  return (REPORTING_DAYS as readonly number[]).includes(days)
    ? (days as ReportingDays)
    : null;
}
const uuid = z.uuid();
const availability = z.enum([
  "available",
  "no_data",
  "not_connected",
  "not_tracked",
  "not_permitted",
]);
const metric = z.object({
  current: z.number().nullable(),
  previous: z.number().nullable(),
  percent_delta: z.number().nullable(),
  source: z.enum(["ga4", "search_console", "leads", "reviews", "rank_scan"]),
  availability,
  freshness_at: z.string().nullable().optional(),
});
const workItem = z
  .object({
    workflow_key: z.string(),
    status: z.string(),
    at: z.string().nullable(),
    failure_code: z.string().nullable().optional(),
  })
  .nullable();
const row = z.object({
  organization_id: uuid,
  slug: z.string(),
  name: z.string(),
  location: z.string().nullable(),
  category: z.string().nullable(),
  location_count: z.number().int(),
  organic_sessions: metric,
  search_clicks: metric,
  average_position: metric,
  average_local_rank: metric,
  leads: metric,
  local_visibility: metric,
  reviews: z.object({
    availability,
    total: z.number().nullable(),
    new_in_period: z.number().nullable(),
    average_rating: z.number().nullable(),
  }),
  open_opportunities: z.number().nullable(),
  health: z.enum(["healthy", "needs_attention", "not_configured"]),
  health_reasons: z.array(z.string()),
  last_activity: workItem,
  next_work: workItem,
});
const owner = {
  organization_id: uuid,
  organization_name: z.string(),
  organization_slug: z.string(),
};
const attention = z.object({
  ...owner,
  code: z.string(),
  severity: z.enum(["critical", "high", "medium"]),
  occurred_at: z.string().nullable(),
  reference: z.string().nullable(),
});
const opportunity = z.object({
  id: uuid,
  ...owner,
  opportunity_type: z.string(),
  classification: z.enum(["Issue", "Growth Opportunity"]),
  status: z.string(),
  priority: z.number().nullable(),
  query: z.string().nullable(),
  page: z.string().nullable(),
  impressions: z.number().nullable(),
});
const activity = z.object({
  ...owner,
  workflow_key: z.string(),
  completed_at: z.string(),
});
const upcoming = z.object({
  ...owner,
  workflow_key: z.string(),
  next_run_at: z.string(),
});
const window = {
  generated_at: z.string(),
  days: z.number().int(),
  period_start: z.string(),
  period_end: z.string(),
};
const portfolio = z.object({
  ...window,
  client_count: z.number().int(),
  location_count: z.number().int(),
  totals: z.object({
    website_leads: metric,
    organic_sessions: metric,
    new_reviews: z.number().nullable(),
    average_rating: z.number().nullable(),
    reporting_attention: z.number().int(),
    local_visibility: metric,
  }),
  clients: z.array(row),
  attention: z.array(attention),
  opportunities: z.array(opportunity),
  activity: z.array(activity),
  upcoming: z.array(upcoming),
  systems: z.array(
    z.object({
      key: z.enum(["google", "analytics", "automations"]),
      status: z.enum(["healthy", "needs_attention", "error", "not_connected"]),
      affected_clients: z.number().int(),
    }),
  ),
});
const counts = z.record(z.string(), z.number().int());
const overview = z.object({
  ...window,
  access: z.enum(["member", "platform_administrator"]),
  client: row,
  attention: z.array(attention),
  opportunities: z.array(opportunity),
  activity: z.array(activity),
  upcoming: z.array(upcoming),
  systems: z.array(
    z.object({
      key: z.enum(["google", "analytics", "search_console", "automations"]),
      status: z.enum([
        "healthy",
        "needs_attention",
        "error",
        "not_connected",
        "not_permitted",
      ]),
    }),
  ),
  insights: z.object({
    availability,
    workflow_runs: counts,
    growth_outcomes: counts,
    seo_opportunities: counts,
    seo_opportunities_blocked: z.number().nullable(),
    content_publications: counts,
    reviews: counts,
  }),
});
const visible = z.object({
  platform_administrator: z.boolean(),
  data: z.array(
    z.object({
      organization_id: uuid,
      slug: z.string().regex(/^[a-z][a-z0-9-]{2,62}$/),
      name: z.string(),
      status: z.string(),
      access: z.enum(["member", "platform_administrator"]),
    }),
  ),
});
export async function loadClients(locals: App.Locals) {
  return visible.parse(await read(locals, "command-center/clients/"));
}
export async function loadPortfolio(
  locals: App.Locals,
  days: ReportingDays,
): Promise<PortfolioOverview> {
  return portfolio.parse(
    await read(locals, `command-center/portfolio/?days=${days}`),
  ) as PortfolioOverview;
}
export async function loadOverview(
  locals: App.Locals,
  organizationId: string,
  days: ReportingDays,
): Promise<ClientOverview> {
  const result = overview.parse(
    await read(
      locals,
      `command-center/clients/${organizationId}/overview/?days=${days}`,
    ),
  );
  if (result.client.organization_id !== organizationId)
    throw new Error("SOURCE_SCOPE_INVALID");
  return result as ClientOverview;
}
