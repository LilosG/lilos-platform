import { z } from "zod";
import type { components } from "@lilos/contracts/api";
const uuid = z.uuid();
const text = z.string();
const nullableText = text.nullable();
const number = z.number().nullable();
const json = z.record(text, z.json());
const website = z.object({
  id: uuid,
  name: text,
  canonical_origin: text,
  location_id: uuid.nullable(),
  status: text,
});
const sync = z.object({
  id: uuid,
  status: text,
  failure_code: nullableText,
  started_at: nullableText,
  completed_at: nullableText,
  source_id: nullableText,
  source: z.enum(["search_console", "analytics"]),
});
const mapping = z.object({
  id: uuid,
  website_id: uuid.nullable(),
  external_property_id: text,
  mapping_status: text,
  freshness_status: text,
  last_synced_at: nullableText,
  property_type: nullableText,
  display_name: nullableText,
  can_sync: z.boolean(),
});
const metric = z.object({
  current: number,
  previous: number,
  delta: number,
  percent_delta: number,
  quality: text,
  label: nullableText,
});
const searchRow = {
  clicks: number,
  impressions: number,
  ctr: number,
  position: number,
};
const performance = z.object({
  connected: z.boolean(),
  properties: z.array(
    z.object({
      id: uuid,
      external_property_id: text,
      freshness_status: text,
      last_synced_at: nullableText,
    }),
  ),
  range: z
    .object({ start: text, end: text, days: z.number().int() })
    .nullable(),
  comparison_range: z
    .object({ start: text, end: text, days: z.number().int() })
    .nullable(),
  freshness: z.object({ last_synced_at: nullableText, status: text }),
  metrics: z.record(text, metric),
  series: z.array(json),
  top_queries: z.array(z.object({ query: text, ...searchRow })),
  top_pages: z.array(
    z.object({
      page: text,
      page_id: uuid.nullable().optional().default(null),
      index_status: z
        .enum(["indexable", "not_indexable", "not_crawled"])
        .optional()
        .default("not_crawled"),
      ...searchRow,
    }),
  ),
});
const tracked = z.object({
  state: z.enum(["tracked", "not_tracked"]),
  value: z.number().int().nullable(),
});
const integration = z.object({
  organization_id: uuid,
  syncs: z.array(sync),
  google: z.object({
    connection_status: text,
    connection_id: uuid.nullable(),
    token_expires_at: nullableText,
    last_verified_at: nullableText,
    capabilities: z.array(
      z.object({ key: text, label: text, enabled: z.boolean() }),
    ),
    mapped_resources: z.array(
      z.object({
        id: uuid,
        external_resource_id: text,
        platform_resource_id: uuid.nullable(),
        resource_type: text,
        status: text,
        display_name: nullableText,
        last_synced_at: nullableText,
        sync_freshness: text,
        gbp_location_id: uuid.nullable(),
        mapping_status: nullableText,
        write_enabled: z.boolean().nullable(),
      }),
    ),
    unmapped_count: z.number().int().nonnegative(),
  }),
  websites: z.array(website),
  locations: z.array(z.object({ id: uuid, name: text, can_map: z.boolean() })),
  search_properties: z.array(mapping),
  analytics_properties: z.array(mapping),
  unmapped_profiles: z.array(
    z.object({ id: uuid, business_name: text, external_location_id: text }),
  ),
  can_connect: z.boolean(),
  can_manage_search: z.boolean(),
  can_manage_analytics: z.boolean(),
  github_status: nullableText,
  github_limitation: z.literal(
    "publishing_configuration_remains_in_existing_control_plane",
  ),
});
const search = z.object({
  organization_id: uuid,
  websites: z.array(website),
  website_id: uuid.nullable(),
  syncs: z.array(sync),
  google_status: nullableText,
  search_console: performance.nullable(),
  analytics: performance.nullable(),
  analytics_scope: z.literal("organization_all_channels"),
  analytics_availability: z.enum(["available", "permission_required"]),
  pages: z.array(
    z.object({
      id: uuid,
      website_id: uuid,
      normalized_url: text,
      title: nullableText,
      http_status: number,
      indexability: nullableText,
      quality_status: text,
      observed_at: nullableText,
      technical_issues: z.array(z.json()),
    }),
  ),
  next_offset: z.number().int().nonnegative().nullable(),
  crawls: z.array(
    z.object({
      id: uuid,
      website_id: uuid,
      status: text,
      stop_reason: nullableText,
      started_at: nullableText,
      completed_at: nullableText,
      safe_result: json,
    }),
  ),
  profiles: z.array(
    z.object({
      id: uuid,
      location_id: uuid,
      business_name: text,
      mapping_status: text,
      write_enabled: z.boolean(),
      last_synced_at: nullableText,
    }),
  ),
  insights: z
    .array(
      z.object({
        code: z.enum([
          "QUERY_GAINING_CLICKS",
          "QUERY_LOSING_CLICKS",
          "PAGE_GAINING_CLICKS",
          "PAGE_LOSING_CLICKS",
          "SEARCH_CLICKS_UP",
          "SEARCH_CLICKS_DOWN",
          "IMPRESSIONS_OUTRUNNING_CLICKS",
          "PROFILE_ACTIONS_UP",
          "PROFILE_ACTIONS_DOWN",
          "QUERIES_NEAR_PAGE_ONE",
        ]),
        link: z.enum(["search_console", "pages", "google_business_profile"]),
        subject: nullableText,
        current: number,
        previous: number,
        percent_change: number,
        count: z.number().int().nullable(),
      }),
    )
    .default([]),
  technical_health: z
    .object({
      pages_crawled: tracked,
      indexable_pages: tracked,
      excluded_pages: tracked,
      pages_with_issues: tracked,
      structured_data_pages: tracked,
      google_indexed_pages: tracked,
      last_crawled_at: nullableText,
    })
    .nullable()
    .default(null),
  can_crawl: z.boolean(),
  unsupported: z.array(text),
});
export type IntegrationsView = components["schemas"]["IntegrationView"];
export type LocalSearchView = components["schemas"]["SearchView"];
export function adaptIntegrations(
  payload: unknown,
  org: string,
): IntegrationsView {
  const parsed = integration.parse(payload);
  if (parsed.organization_id !== org) throw new Error("SOURCE_SCOPE_INVALID");
  for (const item of [
    ...parsed.search_properties,
    ...parsed.analytics_properties,
  ])
    if (
      item.website_id &&
      !parsed.websites.some((w) => w.id === item.website_id)
    )
      throw new Error("WEBSITE_SCOPE_INVALID");
  return parsed;
}
export function adaptLocalSearch(
  payload: unknown,
  org: string,
  websiteId?: string,
): LocalSearchView {
  const parsed = search.parse(payload);
  if (
    parsed.organization_id !== org ||
    (websiteId && parsed.website_id !== websiteId) ||
    (parsed.website_id &&
      !parsed.websites.some((w) => w.id === parsed.website_id))
  )
    throw new Error("SOURCE_SCOPE_INVALID");
  if (
    [...parsed.pages, ...parsed.crawls].some(
      (row) => row.website_id !== parsed.website_id,
    )
  )
    throw new Error("WEBSITE_SCOPE_INVALID");
  return parsed;
}
export function value(value: unknown): string {
  if (value === null || value === undefined) return "Unavailable";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
export type PageIntelligence = components["schemas"]["PageIntelligenceView"];
export function adaptPage(
  payload: unknown,
  org: string,
  websiteId: string,
  pageId: string,
): PageIntelligence {
  const parsed = z
    .object({
      version: text,
      identity: z.object({
        organization_id: uuid,
        website_id: uuid,
        page_id: uuid,
        normalized_url: text,
        observed_url: text,
        canonical_url: nullableText,
      }),
      current_page: json,
      crawl: json,
      change: json,
      gsc: json,
      ga4_organic_landing: json,
      internal_links: json,
      content: json,
      workflow: json,
    })
    .parse(payload);
  if (
    parsed.identity.organization_id !== org ||
    parsed.identity.website_id !== websiteId ||
    parsed.identity.page_id !== pageId
  )
    throw new Error("SOURCE_SCOPE_INVALID");
  return parsed;
}
const publication = z.object({
  id: uuid,
  status: text,
  scheduled_for: nullableText,
  dispatched_at: nullableText,
  provider_post_id: nullableText,
  verified_at: nullableText,
  recovery_allowed: z.boolean(),
});
export type ProfileView = components["schemas"]["GBPDetailView"];
export function adaptProfile(
  payload: unknown,
  org: string,
  locationId: string,
  profileId: string,
): ProfileView {
  const parsed = z
    .object({
      organization_id: uuid,
      location_id: uuid,
      profile_id: uuid,
      snapshot_id: uuid.nullable(),
      profile: json.nullable(),
      observed_at: nullableText,
      health: json.nullable(),
      completeness: json.nullable(),
      completeness_code: nullableText,
      posts: z.array(
        z.object({
          id: uuid,
          post_key: uuid,
          revision: z.number().int(),
          post_type: text,
          content: text,
          call_to_action: json.nullable(),
          event_or_offer: json.nullable(),
          status: text,
          publication: publication.nullable(),
        }),
      ),
      provider_posts: z.array(
        z.object({
          id: uuid,
          provider_post_name: text,
          post_type: text,
          state: nullableText,
          summary: nullableText,
          status: text,
          observed_at: text,
        }),
      ),
      can_propose: z.boolean(),
      can_approve: z.boolean(),
      can_publish: z.boolean(),
    })
    .parse(payload);
  if (
    parsed.organization_id !== org ||
    parsed.location_id !== locationId ||
    parsed.profile_id !== profileId
  )
    throw new Error("SOURCE_SCOPE_INVALID");
  return parsed;
}
