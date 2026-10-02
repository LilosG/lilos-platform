import { loadClients } from "./command-center";
import { APIError } from "./bff";
export interface Organization {
  organization_id: string;
  organization_slug: string;
  organization_name: string;
  organization_status: string;
  access: "member" | "platform_administrator";
}
export interface Workspace {
  clients: Organization[];
  platformAdministrator: boolean;
}
/** The clients this caller may open. Scope is decided by the API from the session alone. */
const loaded = new WeakMap<App.Locals, Promise<Workspace>>();
export function workspace(locals: App.Locals): Promise<Workspace> {
  let pending = loaded.get(locals);
  if (!pending) {
    pending = loadWorkspace(locals);
    loaded.set(locals, pending);
  }
  return pending;
}
async function loadWorkspace(locals: App.Locals): Promise<Workspace> {
  const result = await loadClients(locals);
  return {
    clients: result.data.map((row) => ({
      organization_id: row.organization_id,
      organization_slug: row.slug,
      organization_name: row.name,
      organization_status: row.status,
      access: row.access,
    })),
    platformAdministrator: result.platform_administrator,
  };
}
export async function organizations(
  locals: App.Locals,
): Promise<Organization[]> {
  return (await workspace(locals)).clients;
}
export function resolveSlug(rows: Organization[], slug: string): Organization {
  const organization = rows.find((row) => row.organization_slug === slug);
  if (!organization) throw new APIError(404, "CLIENT_NOT_FOUND");
  return organization;
}
