import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const org = `organizations/${uuid}`;
const route = (
  pattern: string,
  method: "GET" | "POST" | "PATCH",
  body?: z.ZodType,
  query: string[] = [],
) => ({
  pattern: new RegExp(`^${pattern}/$`),
  method,
  upstream: "",
  query,
  ...(body ? { body } : {}),
});
export const automationRoutes = [
  route(`${org}/command-center/automations`, "GET", undefined, [
    "location_id",
    "offset",
  ]),
  route(`${org}/command-center/automations/runs/${uuid}`, "GET"),
  route(
    `${org}/workflows/schedules/${uuid}`,
    "PATCH",
    z
      .object({
        status: z.enum(["active", "paused", "cancelled"]).optional(),
        cron_expression: z.string().min(5).max(100).optional(),
        timezone: z.string().min(1).max(64).optional(),
        next_run_at: z.iso.datetime({ offset: true }).optional(),
      })
      .strict()
      .refine((v) => Object.keys(v).length > 0),
  ),
  route(
    `${org}/workflows/schedules`,
    "POST",
    z
      .object({
        workflow_key: z.enum(["gbp.sync", "reviews.ingest"]),
        key: z.string().min(3).max(128),
        cron_expression: z.string().min(5).max(100),
        timezone: z.string().min(1).max(64),
        next_run_at: z.iso.datetime({ offset: true }),
        location_id: z.uuid().nullable().optional(),
      })
      .strict(),
  ),
  route(
    `${org}/agents/(agent\\.(gbp|seo|content|reviews|leads|insights|growth))/runs`,
    "POST",
    z
      .object({
        location_id: z.uuid(),
        idempotency_key: z.string().min(8).max(128),
        objective: z.string().min(1).max(4000).optional(),
      })
      .strict(),
  ),
  // Only standalone canonical workflows. Publication dispatch stays in its owning product.
  route(
    `${org}/workflows/(gbp\\.sync|reviews\\.ingest)/runs`,
    "POST",
    z
      .object({
        location_id: z.uuid().nullable().optional(),
        idempotency_key: z.string().min(8).max(128),
        input_document: z.object({}).strict(),
        execute: z.literal(true),
      })
      .strict(),
  ),
  route(`${org}/agents/runs/${uuid}/stop`, "POST", z.object({}).strict()),
  route(
    `${org}/agents/runs/${uuid}/steer`,
    "POST",
    z.object({ text: z.string().min(1).max(4000) }).strict(),
  ),
  route(
    `${org}/agents/runs/${uuid}/approval`,
    "POST",
    z.object({ choice: z.enum(["once", "deny"]) }).strict(),
  ),
];
