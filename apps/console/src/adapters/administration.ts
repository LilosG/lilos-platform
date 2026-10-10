import { z } from "zod";
/**
 * The platform's client lifecycle, a client's locations and its business facts, parsed at the
 * edge. A shape this app does not know is refused here rather than shown half-understood.
 */
export const ORGANIZATION_STATUSES = [
  "prospect",
  "onboarding",
  "active",
  "paused",
  "suspended",
  "offboarding",
  "archived",
] as const;
export type OrganizationStatus = (typeof ORGANIZATION_STATUSES)[number];
export const LOCATION_STATUSES = [
  "setup_required",
  "active",
  "paused",
  "closed_temporarily",
  "closed_permanently",
  "archived",
] as const;
export type LocationStatus = (typeof LOCATION_STATUSES)[number];
export const REMOVAL_STATES = [
  "requested",
  "in_progress",
  "completed",
  "failed",
] as const;
export type RemovalState = (typeof REMOVAL_STATES)[number];
const organization = z.object({
  id: z.uuid(),
  name: z.string(),
  slug: z.string(),
  status: z.enum(ORGANIZATION_STATUSES),
  website_url: z.string().nullable(),
  version: z.number().int().min(1),
});
export type OrganizationRecord = z.infer<typeof organization>;
export function adaptOrganizations(raw: unknown): OrganizationRecord[] {
  return z
    .object({ data: z.object({ items: z.array(organization) }).loose() })
    .loose()
    .parse(raw).data.items;
}
const location = z.object({
  id: z.uuid(),
  name: z.string(),
  status: z.enum(LOCATION_STATUSES),
  location_type: z.string(),
  address_line_1: z.string().nullable(),
  address_line_2: z.string().nullable(),
  city: z.string().nullable(),
  region: z.string().nullable(),
  postal_code: z.string().nullable(),
  service_area_description: z.string().nullable(),
  is_primary: z.boolean(),
  version: z.number().int().min(1),
});
export type LocationRecord = z.infer<typeof location>;
/** Both location lists answer `{ data }`: a bare list for a client, a page for the platform. */
export function adaptLocations(raw: unknown): LocationRecord[] {
  const data = z.object({ data: z.unknown() }).loose().parse(raw).data;
  return Array.isArray(data)
    ? z.array(location).parse(data)
    : z
        .object({ items: z.array(location) })
        .loose()
        .parse(data).items;
}
export interface RemovalRecord {
  state: RemovalState | null;
  failure_code: string | null;
}
export function adaptRemoval(raw: unknown): RemovalRecord {
  const { data } = z
    .object({
      data: z
        .object({
          state: z.enum(REMOVAL_STATES).nullable(),
          failure_code: z.string().nullable(),
        })
        .loose(),
    })
    .loose()
    .parse(raw);
  return { state: data.state, failure_code: data.failure_code };
}
export const FACT_AUTHORITIES = [
  "client_approved",
  "operator_verified",
  "provider_observed",
  "imported",
  "system_derived",
  "industry_default",
  "ai_suggested",
] as const;
export type FactAuthority = (typeof FACT_AUTHORITIES)[number];
const fact = z.object({
  fact_key: z.string(),
  fact_identity: z.uuid(),
  value: z.unknown(),
  value_type: z.string(),
  location_id: z.uuid().nullable(),
  authority: z.enum(FACT_AUTHORITIES),
  revision: z.number().int().min(1),
});
export type FactRecord = z.infer<typeof fact>;
/** The facts in effect, and the proposals still waiting for someone to approve them. */
export function adaptFacts(
  effective: unknown,
  waiting: unknown,
): { effective: FactRecord[]; waiting: FactRecord[] } {
  const list = z.object({ data: z.array(fact) }).loose();
  return {
    effective: list.parse(effective).data,
    waiting: list.parse(waiting).data,
  };
}
