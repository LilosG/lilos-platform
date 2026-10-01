import { z } from "zod";
const uuid =
  "([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})";
const org = `organizations/${uuid}`;
const lead = `${org}/leads/${uuid}`;
export const leadStatuses = [
  "new",
  "validating",
  "unassigned",
  "assigned",
  "acknowledged",
  "contact_attempted",
  "contacted",
  "qualifying",
  "qualified",
  "appointment_requested",
  "appointment_scheduled",
  "nurture",
  "unresponsive",
  "archived",
] as const;
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
const text = (max: number) => z.string().min(1).max(max);
export const leadRoutes = [
  route(`${org}/command-center/leads`, "GET", undefined, [
    "location_id",
    "offset",
  ]),
  route(`${org}/command-center/leads/${uuid}`, "GET", undefined, [
    "location_id",
  ]),
  route(`${org}/leads/assignees`, "GET"),
  route(
    `${lead}/status`,
    "POST",
    z
      .object({
        to_status: z.enum(leadStatuses),
        safe_reason: z.string().max(500).nullable().optional(),
      })
      .strict(),
  ),
  route(
    `${lead}/assign`,
    "POST",
    z.object({ assigned_to_user_id: z.uuid() }).strict(),
  ),
  route(
    `${lead}/convert`,
    "POST",
    z
      .object({
        converted_value_cents: z
          .number()
          .int()
          .nonnegative()
          .nullable()
          .optional(),
      })
      .strict(),
  ),
  route(
    `${lead}/loss`,
    "POST",
    z
      .object({
        to_status: z.enum(["lost", "disqualified", "spam", "cancelled"]),
        loss_reason: text(500),
      })
      .strict(),
  ),
  route(`${lead}/notes`, "POST", z.object({ body: text(5000) }).strict()),
  route(
    `${lead}/tasks`,
    "POST",
    z
      .object({
        title: text(200),
        description: z.string().max(5000).nullable().optional(),
        due_at: z.iso.datetime({ offset: true }).nullable().optional(),
        assigned_to_user_id: z.uuid().nullable().optional(),
      })
      .strict(),
  ),
  route(`${lead}/tasks/${uuid}/complete`, "POST", z.object({}).strict()),
  route(
    `${lead}/consents`,
    "POST",
    z
      .object({
        channel: z.enum(["email", "sms", "phone"]),
        consent_type: z.enum([
          "transactional_email",
          "marketing_email",
          "transactional_sms",
          "marketing_sms",
          "phone_call",
          "automated_call",
        ]),
        status: z.enum([
          "granted",
          "denied",
          "unknown",
          "not_required",
          "withdrawn",
          "expired",
        ]),
        source: text(64),
        disclosure_version: text(64),
        evidence_reference: text(500),
        captured_at: z.iso.datetime({ offset: true }),
      })
      .strict(),
  ),
  route(
    `${lead}/communications`,
    "POST",
    z
      .object({
        channel: z.enum(["email", "sms"]),
        consent_type: z.enum([
          "transactional_email",
          "marketing_email",
          "transactional_sms",
          "marketing_sms",
        ]),
        message_reference: text(500),
        idempotency_key: z.string().min(8).max(128),
      })
      .strict(),
  ),
];
