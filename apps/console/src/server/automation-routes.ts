import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const base = "command-center/automations";
/**
 * Automations through the BFF: the list and one automation's detail, and Run now, which
 * carries the caller's Idempotency-Key header to the API unchanged.
 */
export const automationRoutes = [
  {
    pattern: new RegExp(`^${base}/$`),
    method: "GET",
    upstream: "",
    query: ["organization_id"],
  },
  {
    pattern: new RegExp(`^${base}/${uuid}/$`),
    method: "GET",
    upstream: "",
    query: ["runs"],
  },
  {
    pattern: new RegExp(`^${base}/${uuid}/run/$`),
    method: "POST",
    upstream: "",
    query: [],
    body: z.object({}).strict(),
    idempotency: true,
  },
] as const;
export const idempotencyKey = /^[A-Za-z0-9_-]{8,64}$/;
