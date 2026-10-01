import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const org = `organizations/${uuid}`;
const route = (
  pattern: string,
  method: "GET" | "POST",
  body?: z.ZodType,
  query: string[] = [],
) => ({
  pattern: new RegExp(`^${pattern}/$`),
  method,
  upstream: "",
  query,
  ...(body ? { body } : {}),
});
const facts = z.array(z.uuid()).min(1).max(100);
const strings = z.array(z.string()).max(100);
export const websiteRoutes = [
  route(`${org}/command-center/website-content`, "GET", undefined, [
    "website_id",
    "offset",
  ]),
  route(
    `${org}/command-center/website-content/websites/${uuid}/pages/${uuid}`,
    "GET",
  ),
  route(`${org}/command-center/website-content/content/${uuid}`, "GET"),
  route(
    `${org}/content`,
    "POST",
    z
      .object({
        title: z.string().min(1).max(300),
        slug: z
          .string()
          .min(1)
          .max(200)
          .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
        content_type: z.string().min(1).max(32),
      })
      .strict(),
  ),
  route(
    `${org}/content/${uuid}/briefs`,
    "POST",
    z
      .object({
        audience: z.string().min(1).max(500),
        intent: z.string().min(1).max(500),
        target_reference: z.string().min(1).max(500),
        approved_fact_revision_ids: facts,
        required_claims: strings.optional(),
        prohibited_claims: strings.optional(),
        required_local_references: strings.optional(),
        source_evidence_references: strings.optional(),
        validation_requirements: z.record(z.string(), z.json()).optional(),
      })
      .strict(),
  ),
  route(
    `${org}/content/${uuid}/revisions`,
    "POST",
    z
      .object({
        body: z.string().min(1).max(200000),
        frontmatter: z.record(z.string(), z.json()),
        created_by_type: z.literal("user"),
        approved_fact_revision_ids: facts,
        prohibited_claims: strings.optional(),
      })
      .strict(),
  ),
  route(
    `${org}/content/${uuid}/revisions/ai-draft`,
    "POST",
    z
      .object({
        brief_id: z.uuid(),
        idempotency_key: z.string().min(8).max(128),
      })
      .strict(),
  ),
  route(
    `${org}/content-operations/${uuid}/revisions/${uuid}/decision`,
    "POST",
    z
      .object({ stage: z.enum(["editorial", "client"]), approve: z.boolean() })
      .strict(),
  ),
  route(
    `${org}/content-operations/${uuid}/publish`,
    "POST",
    z
      .object({
        idempotency_key: z.string().min(8).max(96),
        publishing_target_id: z.uuid().nullable().optional(),
        image: z.string().max(1000).nullable().optional(),
        image_alt: z.string().max(500).nullable().optional(),
      })
      .strict(),
  ),
  route(
    `${org}/content-operations/${uuid}/publications/${uuid}/recover`,
    "POST",
    z.object({}).strict(),
  ),
  route(
    `${org}/content-operations/${uuid}/publishing-assets`,
    "GET",
    undefined,
    ["target_id"],
  ),
];
