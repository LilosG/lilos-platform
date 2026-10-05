import { z } from "zod";
import type { components } from "@lilos/contracts/api";
const uuid = z.uuid();
const availability = z.enum([
  "available",
  "partial",
  "no_data",
  "not_synced",
  "not_connected",
]);
const total = z.object({
  availability,
  value: z.number().int().nullable(),
  days_covered: z.number().int(),
  days_expected: z.number().int(),
});
const comparison = {
  current: total,
  previous: total,
  change: z.number().int().nullable(),
  change_percent: z.number().nullable(),
};
const range = z.object({
  start: z.string(),
  end: z.string(),
  days: z.number().int(),
});
export const GBP_METRICS = [
  "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
  "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
  "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
  "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
  "CALL_CLICKS",
  "WEBSITE_CLICKS",
  "BUSINESS_DIRECTION_REQUESTS",
  "BUSINESS_CONVERSATIONS",
  "BUSINESS_BOOKINGS",
  "BUSINESS_FOOD_ORDERS",
  "BUSINESS_FOOD_MENU_CLICKS",
] as const;
export type GbpMetric = (typeof GBP_METRICS)[number];
const performance = z.object({
  organization_id: uuid,
  period: z.enum(["7d", "28d", "90d", "month"]),
  month: z.string().nullable(),
  location_id: uuid.nullable(),
  locations: z.array(
    z.object({ id: uuid, name: z.string(), mapped: z.boolean() }),
  ),
  availability,
  current_range: range,
  previous_range: range,
  profile_views: z.object(comparison),
  metrics: z.array(z.object({ metric: z.enum(GBP_METRICS), ...comparison })),
  search_terms: z.object({
    availability,
    month: z.string().nullable(),
    terms: z.array(
      z.object({
        keyword: z.string(),
        value: z.number().int().nullable(),
        below_threshold: z.number().int().nullable(),
        is_exact: z.boolean(),
      }),
    ),
  }),
  series: z.array(
    z.object({
      day: z.string(),
      impressions: z.number().int().nullable(),
      actions: z.number().int().nullable(),
    }),
  ),
  source: z.object({
    last_synced_at: z.string().nullable(),
    last_status: z
      .enum(["running", "succeeded", "partial", "failed"])
      .nullable(),
    last_failure_code: z.string().nullable(),
  }),
});
export type GbpPerformanceView = components["schemas"]["GBPPerformanceView"];
export function adaptGbpPerformance(
  payload: unknown,
  org: string,
): GbpPerformanceView {
  const parsed = performance.parse(payload);
  if (parsed.organization_id !== org) throw new Error("SOURCE_SCOPE_INVALID");
  return parsed;
}
const list = <T extends z.ZodType>(item: T) =>
  z.object({ data: z.array(item) });
const mediaRow = z.object({
  id: uuid,
  media_type: z.enum(["photo", "video", "logo", "cover"]),
  source_reference: z.string(),
  rights_authority: z.string(),
  status: z.string(),
  verified_at: z.string().nullable(),
});
export type GbpMedia = z.infer<typeof mediaRow>;
export const adaptMedia = (payload: unknown): GbpMedia[] =>
  list(mediaRow).parse(payload).data;
const hoursRow = z.object({
  id: uuid,
  service_date: z.string(),
  revision: z.number().int(),
  periods: z.array(z.object({ opens: z.string(), closes: z.string() })),
  source: z.string(),
  status: z.string(),
});
export type GbpSpecialHours = z.infer<typeof hoursRow>;
export const adaptSpecialHours = (payload: unknown): GbpSpecialHours[] =>
  list(hoursRow).parse(payload).data;
const changeSet = z.object({
  id: uuid,
  revision: z.number().int(),
  field_changes: z.array(
    z.object({ field: z.string(), value: z.unknown() }).loose(),
  ),
  risk: z.string(),
  status: z.string(),
});
export type GbpChangeSet = z.infer<typeof changeSet>;
export const adaptChangeSets = (payload: unknown): GbpChangeSet[] =>
  list(changeSet).parse(payload).data;
const completeness = z.object({
  data: z.object({
    complete: z.boolean(),
    known: z.array(z.string()),
    unknown: z.array(z.string()),
  }),
});
export type GbpCompleteness = z.infer<typeof completeness>["data"];
export const adaptCompleteness = (payload: unknown): GbpCompleteness =>
  completeness.parse(payload).data;
