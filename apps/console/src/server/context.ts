import { z } from "zod";
import type { components } from "@lilos/contracts/api";
import { read, APIError } from "./bff";
export type Organization = components["schemas"]["MyOrganizationData"];
const organization = z
  .object({
    organization_id: z.uuid(),
    organization_slug: z.string().regex(/^[a-z][a-z0-9-]{2,62}$/),
    organization_name: z.string(),
    organization_status: z.string(),
    membership_status: z.string(),
  })
  .loose();
export async function organizations(
  locals: App.Locals,
): Promise<Organization[]> {
  const payload = await read<{ data: Organization[] }>(
    locals,
    "me/organizations/",
  );
  return z
    .array(organization)
    .parse(payload.data)
    .filter(
      (row) =>
        row.organization_status === "active" &&
        row.membership_status === "active",
    ) as Organization[];
}
export function resolveSlug(rows: Organization[], slug: string): Organization {
  const organization = rows.find((row) => row.organization_slug === slug);
  if (!organization) throw new APIError(404, "CLIENT_NOT_FOUND");
  return organization;
}
