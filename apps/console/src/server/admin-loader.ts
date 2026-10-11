import { APIError, read } from "./bff";
import {
  adaptFacts,
  adaptLocations,
  adaptOrganizations,
  adaptRemoval,
  type RemovalRecord,
} from "../adapters/administration";
import {
  organizationRows,
  type OrganizationRow,
} from "../lib/administration-view";
import {
  factRows,
  locationRows,
  type FactRow,
  type LocationRow,
} from "../lib/settings-view";
export type Section<T> =
  | { kind: "ok"; rows: T[] }
  | { kind: "forbidden" }
  | { kind: "unauthenticated" }
  | { kind: "error" };
const PAGE = 100;
type Failed = Exclude<Section<never>, { kind: "ok" }>;
const failure = (error: unknown): Failed =>
  error instanceof APIError && error.status === 401
    ? { kind: "unauthenticated" }
    : error instanceof APIError && error.status === 403
      ? { kind: "forbidden" }
      : { kind: "error" };
/** Run `work` over `items` a few at a time, so a long client list does not open a hundred calls at once. */
async function inGroups<T, R>(
  items: T[],
  work: (item: T) => Promise<R>,
): Promise<R[]> {
  const out: R[] = [];
  for (let i = 0; i < items.length; i += 10)
    out.push(...(await Promise.all(items.slice(i, i + 10).map(work))));
  return out;
}
export interface AdministrationClients {
  rows: OrganizationRow[];
  /** More clients exist than one page shows. */
  more: boolean;
}
/** Every client with its location count and, for an archived one, where its removal stands. */
export async function loadClientsTable(
  locals: App.Locals,
): Promise<{ kind: "ok"; clients: AdministrationClients } | Failed> {
  let page: unknown;
  try {
    page = await read(locals, `platform/organizations/?limit=${PAGE}`);
  } catch (error) {
    return failure(error);
  }
  let organizations;
  try {
    organizations = adaptOrganizations(page);
  } catch {
    return { kind: "error" };
  }
  const more = Boolean(
    (page as { data?: { has_more?: boolean } }).data?.has_more,
  );
  const counts = new Map<string, number | null>();
  const removals = new Map<string, RemovalRecord | null>();
  await inGroups(organizations, async (org) => {
    // A count that could not be read stays unknown: it is never shown as 0.
    try {
      counts.set(
        org.id,
        adaptLocations(
          await read(
            locals,
            `platform/organizations/${org.id}/locations/?limit=${PAGE}`,
          ),
        ).filter((location) => location.status !== "archived").length,
      );
    } catch {
      counts.set(org.id, null);
    }
    if (org.status !== "archived") return;
    try {
      removals.set(
        org.id,
        adaptRemoval(
          await read(locals, `platform/organizations/${org.id}/removal/`),
        ),
      );
    } catch {
      removals.set(org.id, null);
    }
  });
  return {
    kind: "ok",
    clients: { rows: organizationRows(organizations, counts, removals), more },
  };
}
/** One client's locations. */
export async function loadLocations(
  locals: App.Locals,
  organizationId: string,
): Promise<Section<LocationRow>> {
  try {
    return {
      kind: "ok",
      rows: locationRows(
        adaptLocations(
          await read(
            locals,
            `organizations/${organizationId}/locations/?limit=${PAGE}`,
          ),
        ),
      ),
    };
  } catch (error) {
    return failure(error);
  }
}
/** One client's business facts in effect, with proposals still waiting for approval. */
export async function loadFacts(
  locals: App.Locals,
  organizationId: string,
): Promise<Section<FactRow>> {
  try {
    const base = `organizations/${organizationId}/business-facts`;
    const [effective, waiting] = await Promise.all([
      read(locals, `${base}/effective/`),
      read(locals, `${base}/candidates/`),
    ]);
    const facts = adaptFacts(effective, waiting);
    return { kind: "ok", rows: factRows(facts.effective, facts.waiting) };
  } catch (error) {
    return failure(error);
  }
}
