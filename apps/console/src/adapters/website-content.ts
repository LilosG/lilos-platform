import { z } from "zod";
import type { components } from "@lilos/contracts/api";
import { adaptLocalSearch, adaptPage } from "./local-search";
import { adaptOpportunities } from "./opportunities";
const text = z.string();
const uuid = z.uuid();
const nullable = text.nullable();
const json = z.record(text, z.json());
const item = z.object({
  id: uuid,
  title: text,
  slug: text,
  content_type: text,
  stage: text,
  next_action: z.record(text, text),
  published_at: nullable,
  latest_revision_status: nullable,
  latest_revision_number: z.number().int().nullable(),
  publication_status: nullable,
  publication_job_status: nullable,
  technical_site_change: z.boolean(),
});
const requirements = z.object({
  target_selected: z.boolean(),
  target_id: uuid.nullable(),
  missing: z.array(text),
  requires_image: z.boolean(),
  requires_image_alt: z.boolean(),
  file_extensions: z.array(text),
});
export type WebsiteView = components["schemas"]["WebsiteWorkspace"];
export type ContentView = components["schemas"]["WebsiteContentDetail"];
export type WebsitePageView = components["schemas"]["WebsitePageDetail"];
export function adaptWebsite(
  payload: unknown,
  org: string,
  site?: string,
): WebsiteView {
  const raw = z
    .object({
      organization_id: uuid,
      website_id: uuid.nullable(),
      websites: z.array(
        z.object({
          id: uuid,
          name: text,
          canonical_origin: text,
          location_id: uuid.nullable(),
          status: text,
        }),
      ),
      pages: z.array(z.unknown()),
      crawls: z.array(z.unknown()),
      next_page_offset: z.number().int().nonnegative().nullable(),
      opportunities: z.array(z.unknown()),
      next_opportunity_offset: z.number().int().nonnegative().nullable(),
      content: z.array(item),
      next_content_offset: z.number().int().nonnegative().nullable(),
      page_availability: z.enum([
        "available",
        "permission_required",
        "unavailable",
      ]),
      content_availability: z.enum(["available", "permission_required"]),
      content_scope: z.literal("organization"),
      can_create: z.boolean(),
      can_crawl: z.boolean(),
      conversions: z.literal("unavailable_no_canonical_path_source"),
      unsupported: z.array(text),
    })
    .parse(payload);
  const search = adaptLocalSearch(
    {
      ...raw,
      syncs: [],
      google_status: null,
      search_console: null,
      analytics: null,
      analytics_scope: "organization_all_channels",
      analytics_availability: "permission_required",
      next_offset: raw.next_page_offset,
      profiles: [],
    },
    org,
    site,
  );
  const opportunities = adaptOpportunities(
    { data: raw.opportunities, next_offset: null },
    org,
  );
  if (opportunities.some((o) => o.website_id !== raw.website_id))
    throw new Error("WEBSITE_SCOPE_INVALID");
  return { ...raw, pages: search.pages, crawls: search.crawls, opportunities };
}
export function adaptWebsitePage(
  payload: unknown,
  org: string,
  site: string,
  page: string,
): WebsitePageView {
  const raw = z
    .object({
      evidence: z.unknown(),
      mapping: z.object({
        state: z.enum(["mapped", "unavailable"]),
        code: nullable,
        repository: nullable,
        base_branch: nullable,
        fields: z.record(text, text),
        verification: z.literal("executor_rechecks_before_write"),
      }),
      opportunities: z.array(z.unknown()),
    })
    .parse(payload);
  const opportunities = adaptOpportunities(
    { data: raw.opportunities, next_offset: null },
    org,
  );
  if (opportunities.some((o) => o.website_id !== site || o.page_id !== page))
    throw new Error("SOURCE_SCOPE_INVALID");
  return {
    ...raw,
    evidence: adaptPage(raw.evidence, org, site, page),
    opportunities,
  };
}
export function adaptContent(
  payload: unknown,
  org: string,
  id: string,
): ContentView {
  const parsed = item
    .extend({
      organization_id: uuid,
      briefs: z.array(
        z.object({
          id: uuid,
          revision_number: z.number().int(),
          audience: text,
          intent: text,
          target_reference: text,
          approved_fact_revision_ids: z.array(uuid),
          status: text,
        }),
      ),
      revisions: z.array(
        z.object({
          id: uuid,
          revision_number: z.number().int(),
          body: text,
          frontmatter: json,
          created_by_type: text,
          status: text,
          validation_document: json,
          approved_at: nullable,
        }),
      ),
      publications: z.array(
        z.object({
          id: uuid,
          status: text,
          target_path: text,
          external_pull_request_id: nullable,
          published_url: nullable,
          build_status: nullable,
          deployment_status: nullable,
          verified_at: nullable,
          safe_error_code: nullable,
          revision_id: uuid.nullable(),
          workflow_id: uuid,
          workflow_status: nullable,
          workflow_failure: nullable,
          correlation_id: nullable,
          approved_head_sha: nullable,
          external_revision_id: nullable,
          verification_status: nullable,
          verification_evidence: json.nullable(),
          can_recover: z.boolean(),
        }),
      ),
      publishing_targets: z.array(
        z.object({
          id: uuid,
          key: text,
          repository_id: text,
          base_branch: text,
          allowed_path_prefix: text,
          file_extensions: z.array(text),
          status: text,
        }),
      ),
      publishing_requirements: requirements,
      publishing_requirements_by_target: z.record(text, requirements),
      draft_runs: z.array(
        z.object({
          id: uuid,
          status: text,
          failure_code: nullable,
          correlation_id: nullable,
          started_at: nullable,
          completed_at: nullable,
        }),
      ),
      facts: z.array(z.object({ id: uuid, key: text, value: z.json() })),
      can_edit: z.boolean(),
      can_approve: z.boolean(),
      can_publish: z.boolean(),
    })
    .parse(payload);
  if (parsed.organization_id !== org || parsed.id !== id)
    throw new Error("SOURCE_SCOPE_INVALID");
  return parsed;
}
