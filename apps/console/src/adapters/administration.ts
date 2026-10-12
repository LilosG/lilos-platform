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

/** What the platform says is still needed before a client can go live, parsed to what is shown. */
export interface OnboardingBlocker {
  /** The stable control that clears it; the sentence the API also sends is never kept. */
  control: string;
  route: string;
}
export interface OnboardingRecord {
  progress_percent: number;
  activation_eligible: boolean;
  /** The version to activate against, read together with the blockers it was judged on. */
  version: number;
  blockers: OnboardingBlocker[];
}
export function adaptOnboarding(raw: unknown): OnboardingRecord {
  const { data } = z
    .object({
      data: z
        .object({
          progress_percent: z.number().int().min(0).max(100),
          activation_eligible: z.boolean(),
          organization_version: z.number().int().min(1),
          blocker_details: z.array(
            z
              .object({
                resolution: z
                  .object({ control: z.string(), route: z.string() })
                  .loose(),
              })
              .loose(),
          ),
        })
        .loose(),
    })
    .loose()
    .parse(raw);
  return {
    progress_percent: data.progress_percent,
    activation_eligible: data.activation_eligible,
    version: data.organization_version,
    blockers: data.blocker_details.map((blocker) => ({
      control: blocker.resolution.control,
      route: blocker.resolution.route,
    })),
  };
}

export const MEMBERSHIP_STATUSES = [
  "invited",
  "active",
  "suspended",
  "revoked",
  "expired",
] as const;
export type MembershipStatus = (typeof MEMBERSHIP_STATUSES)[number];
export const MEMBERSHIP_TYPES = [
  "internal",
  "client",
  "partner",
  "support",
] as const;
export const SYSTEM_ROLES = [
  "organization_owner",
  "organization_admin",
  "organization_manager",
  "organization_member",
  "organization_viewer",
] as const;
export type SystemRole = (typeof SYSTEM_ROLES)[number];
const access = z.object({
  organization_id: z.uuid(),
  organization_name: z.string(),
  membership_type: z.enum(MEMBERSHIP_TYPES),
  membership_status: z.enum(MEMBERSHIP_STATUSES),
  roles: z.array(z.enum(SYSTEM_ROLES)),
  invitation: z
    .object({
      id: z.uuid(),
      version: z.number().int().min(1),
      expires_at: z.string(),
    })
    .loose()
    .nullable(),
});
export type UserAccess = z.infer<typeof access>;
const person = z.object({
  id: z.uuid(),
  display_name: z.string().nullable(),
  email: z.string().nullable(),
  status: z.enum(["active", "deactivated"]),
  platform_administrator: z.boolean(),
  access: z.array(access),
  access_total: z.number().int().min(0),
});
export type PersonRecord = z.infer<typeof person>;
export interface UserPage {
  people: PersonRecord[];
  next_offset: number | null;
}
export function adaptUsers(raw: unknown): UserPage {
  const { data } = z
    .object({
      data: z
        .object({
          items: z.array(person),
          next_offset: z.number().int().nullable(),
        })
        .loose(),
    })
    .loose()
    .parse(raw);
  return { people: data.items, next_offset: data.next_offset };
}

export const HEALTH_STATES = ["healthy", "attention", "unknown"] as const;
export type HealthState = (typeof HEALTH_STATES)[number];
export const DEAD_LETTER_REASONS = [
  "permanent_failure",
  "retries_exhausted",
  "lease_expired",
  "timed_out",
  "outcome_uncertain",
  "unrecorded",
] as const;
export type DeadLetterReason = (typeof DEAD_LETTER_REASONS)[number];
const health = z.enum(HEALTH_STATES);
const count = z.number().int().min(0).nullable();
export interface SystemRecord {
  overall: HealthState;
  evaluated_at: string;
  database: HealthState;
  scheduler: {
    status: HealthState;
    active_schedules: number | null;
    last_dispatch_at: string | null;
    overdue: boolean | null;
  };
  queue: {
    status: HealthState;
    dead_letter_count: number | null;
    groups: { reason: DeadLetterReason; count: number }[];
    oldest_pending_at: string | null;
    backlogged: boolean | null;
  };
  failed_runs: { status: HealthState; failed_last_24h: number | null };
  integrations: { status: HealthState; needing_attention: number | null };
}
export function adaptSystem(raw: unknown): SystemRecord {
  const { data } = z
    .object({
      data: z
        .object({
          overall: health,
          evaluated_at: z.string(),
          database: z.object({ status: health }).loose(),
          scheduler: z
            .object({
              status: health,
              active_schedules: count,
              last_dispatch_at: z.string().nullable(),
              overdue: z.boolean().nullable(),
            })
            .loose(),
          worker_queue: z
            .object({
              status: health,
              dead_letter_count: count,
              dead_letter_groups: z.array(
                z.object({
                  reason: z.enum(DEAD_LETTER_REASONS),
                  count: z.number().int().min(0),
                }),
              ),
              oldest_pending_at: z.string().nullable(),
              backlogged: z.boolean().nullable(),
            })
            .loose(),
          failed_runs: z
            .object({ status: health, failed_last_24h: count })
            .loose(),
          integrations: z
            .object({ status: health, needing_attention: count })
            .loose(),
        })
        .loose(),
    })
    .loose()
    .parse(raw);
  return {
    overall: data.overall,
    evaluated_at: data.evaluated_at,
    database: data.database.status,
    scheduler: data.scheduler,
    queue: {
      status: data.worker_queue.status,
      dead_letter_count: data.worker_queue.dead_letter_count,
      groups: data.worker_queue.dead_letter_groups,
      oldest_pending_at: data.worker_queue.oldest_pending_at,
      backlogged: data.worker_queue.backlogged,
    },
    failed_runs: data.failed_runs,
    integrations: data.integrations,
  };
}
