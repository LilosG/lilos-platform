import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const org = `organizations/${uuid}`;
const reviews = `${org}/locations/${uuid}/reviews`;
const facts = z.array(z.uuid()).min(1).max(50);
const key = z.string().min(8).max(128);
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
export const reviewRoutes = [
  route(`${org}/command-center/reviews`, "GET", undefined, [
    "location_id",
    "offset",
  ]),
  route(`${org}/command-center/reviews/locations/${uuid}/${uuid}`, "GET"),
  route(`${reviews}/ingest`, "POST", z.object({}).strict()),
  route(
    `${reviews}/${uuid}/responses`,
    "POST",
    z
      .object({
        review_revision_id: z.uuid(),
        response_text: z.string().min(1).max(5000),
        generated_by_type: z.literal("user"),
        approved_fact_revision_ids: facts,
      })
      .strict(),
  ),
  route(
    `${reviews}/${uuid}/responses/ai-draft`,
    "POST",
    z
      .object({
        review_revision_id: z.uuid(),
        approved_fact_revision_ids: facts,
        idempotency_key: key,
      })
      .strict(),
  ),
  route(
    `${reviews}/${uuid}/responses/${uuid}/approve`,
    "POST",
    z.object({}).strict(),
  ),
  route(
    `${reviews}/${uuid}/responses/${uuid}/publish`,
    "POST",
    z.object({ idempotency_key: key }).strict(),
  ),
];
