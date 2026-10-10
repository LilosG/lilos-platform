import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const org = `organizations/${uuid}`;
const location = `${org}/locations/${uuid}`;
const route = (
  pattern: string,
  method: "GET" | "POST" | "DELETE",
  body?: z.ZodType,
  query: string[] = [],
  idempotency = false,
) => ({
  pattern: new RegExp(`^${pattern}/$`),
  method,
  upstream: "",
  query,
  ...(body ? { body } : {}),
  ...(idempotency ? { idempotency: true } : {}),
});
const empty = z.object({}).strict();
const decide = z.object({ approve: z.boolean() }).strict();
const ops = `${location}/gbp/operations`;
/** A photo is uploaded as multipart; the API checks its type, size and dimensions. The room
 * above Google's 5 MB limit is the form's own fields and boundaries. */
export const PHOTO_UPLOAD_MAX_BYTES = 5 * 1024 * 1024 + 64 * 1024;
const upload = (pattern: string) => ({
  pattern: new RegExp(`^${pattern}/$`),
  method: "POST" as const,
  upstream: "",
  query: [] as string[],
  multipart: { maxBytes: PHOTO_UPLOAD_MAX_BYTES },
});
const hours = z
  .object({
    closed: z.boolean(),
    service_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    periods: z
      .array(
        z
          .object({
            opens: z.string().regex(/^\d{2}:\d{2}$/),
            closes: z.string().regex(/^\d{2}:\d{2}$/),
          })
          .strict(),
      )
      .max(10),
    source: z.literal("console"),
  })
  .strict()
  // Closed all day has no periods; open hours need at least one.
  .refine((value) => value.closed === (value.periods.length === 0));
// What a profile edit may change today, each as one exact field and value to approve.
const profileEdit = z
  .object({
    capability_key: z.enum(["profile", "phoneNumbers", "websiteUri"]),
    field_changes: z
      .array(
        z
          .object({
            field: z.enum(["description", "phoneNumbers", "websiteUri"]),
            value: z.string().min(1).max(750),
          })
          .strict(),
      )
      .length(1),
    evidence: empty,
    risk: z.literal("low"),
    idempotency_key: z.string().min(8).max(128),
  })
  .strict();
// A media publish needs a reserved workflow run; the console reserves one for this workflow only.
const reserveMediaRun = z
  .object({
    location_id: z.uuid(),
    idempotency_key: z.string().min(8).max(128),
    input_document: empty,
    execute: z.literal(false),
  })
  .strict();
const sync = z.object({ days: z.number().int().min(7).max(365) }).strict();
const key = z.object({ idempotency_key: z.string().min(8).max(128) }).strict();
export const searchRoutes = [
  route(`${org}/command-center/integrations`, "GET"),
  // Website publishing: the repositories GitHub offers, and linking one as the publishing target.
  route(`${org}/command-center/integrations/publishing/repositories`, "GET"),
  route(
    `${org}/command-center/integrations/publishing/target`,
    "POST",
    z.object({ repository_id: z.string().min(1).max(255) }).strict(),
    [],
    true,
  ),
  route(
    `${org}/integrations/github/install`,
    "POST",
    z.object({ return_app: z.literal("console") }).strict(),
  ),
  route(`${org}/command-center/gbp/performance`, "GET", undefined, [
    "period",
    "month",
    "location_id",
  ]),
  route(`${org}/command-center/local-search`, "GET", undefined, [
    "website_id",
    "days",
    "offset",
  ]),
  route(
    `${org}/command-center/local-search/websites/${uuid}/pages/${uuid}`,
    "GET",
  ),
  route(
    `${org}/command-center/local-search/locations/${uuid}/profiles/${uuid}`,
    "GET",
  ),
  route(
    `${org}/integrations/google/connect`,
    "POST",
    z
      .object({
        products: z
          .array(z.enum(["gbp", "search_console", "analytics"]))
          .min(1)
          .max(3),
        return_app: z.literal("console"),
      })
      .strict(),
  ),
  route(`${org}/integrations/google/(disconnect|discover)`, "POST", empty),
  route(`${org}/integrations/google/locations/${uuid}/sync`, "POST", empty),
  route(`${org}/seo/websites/${uuid}/search-console/discover`, "GET"),
  route(
    `${org}/insights/analytics/discover`,
    "POST",
    z.object({ website_id: z.uuid() }).strict(),
  ),
  route(
    `${org}/integrations/google/search-console/properties/map`,
    "POST",
    z
      .object({
        website_id: z.uuid(),
        external_property_id: z.string().min(1).max(1000),
        property_type: z.enum(["domain", "url_prefix"]),
      })
      .strict(),
  ),
  route(
    `${org}/integrations/google/analytics/properties/map`,
    "POST",
    z
      .object({
        website_id: z.uuid(),
        external_property_id: z.string().min(1).max(500),
        property_number: z.string().min(1).max(64),
        display_name: z.string().min(1).max(300),
      })
      .strict(),
  ),
  route(
    `${location}/gbp-mapping/${uuid}/confirm`,
    "POST",
    z.object({ location_id: z.uuid(), write_enabled: z.boolean() }).strict(),
  ),
  route(`${location}/gbp-mapping/${uuid}`, "DELETE"),
  route(
    `${org}/seo/websites/${uuid}/search-properties/${uuid}/sync`,
    "POST",
    sync,
  ),
  route(`${org}/insights/analytics/properties/${uuid}/sync`, "POST", sync),
  route(`${org}/seo/websites/${uuid}/check`, "POST", key),
  route(
    `${location}/gbp/operations/locations/${uuid}/posts`,
    "POST",
    z
      .object({
        post_key: z.uuid().nullable().optional(),
        post_type: z.enum(["standard", "event", "offer", "alert"]),
        content: z.string().min(1).max(1500),
        call_to_action: z.record(z.string(), z.json()).nullable().optional(),
        event_or_offer: z.record(z.string(), z.json()).nullable().optional(),
      })
      .strict(),
  ),
  route(
    `${location}/gbp/operations/posts/${uuid}/decision`,
    "POST",
    z.object({ approve: z.boolean() }).strict(),
  ),
  route(`${location}/gbp/operations/posts/${uuid}/dispatch`, "POST", key),
  route(
    `${location}/gbp/operations/posts/publications/${uuid}/recover`,
    "POST",
    empty,
  ),
  route(`${ops}/posts/publications/${uuid}/(repost|discard)`, "POST", empty),
  route(`${ops}/locations/${uuid}/posts/reconcile`, "POST", empty),
  route(`${ops}/locations/${uuid}/media`, "GET"),
  upload(`${ops}/locations/${uuid}/media`),
  route(`${ops}/media/${uuid}/decide`, "POST", decide),
  route(
    `${ops}/media/${uuid}/publish`,
    "POST",
    z
      .object({
        workflow_run_id: z.uuid(),
        idempotency_key: key.shape.idempotency_key,
      })
      .strict(),
  ),
  route(`${ops}/locations/${uuid}/special-hours`, "GET"),
  route(`${ops}/locations/${uuid}/special-hours`, "POST", hours),
  route(`${ops}/special-hours/${uuid}/decision`, "POST", decide),
  route(`${ops}/special-hours/${uuid}/retry`, "POST", key),
  route(`${ops}/locations/${uuid}/completeness`, "GET"),
  route(`${ops}/locations/${uuid}/change-sets`, "GET"),
  route(`${ops}/locations/${uuid}/change-sets`, "POST", profileEdit),
  route(`${ops}/change-sets/${uuid}/decision`, "POST", decide),
  route(`${org}/workflows/gbp.upload_media/runs`, "POST", reserveMediaRun),
];
