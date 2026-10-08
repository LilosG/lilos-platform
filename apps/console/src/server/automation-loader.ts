import {
  adaptAutomationDetail,
  adaptAutomations,
  type AutomationDetailView,
  type AutomationsView,
} from "../adapters/automations";
import { parseFilters, type Filters } from "../lib/automation-view";
import { APIError, read } from "./bff";
export type AutomationsPage =
  | { kind: "list"; view: AutomationsView; filters: Filters }
  | { kind: "detail"; detail: AutomationDetailView; filters: Filters }
  | { kind: "invalid" }
  | { kind: "notfound" }
  | { kind: "unauthenticated" }
  | { kind: "error" };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/**
 * The Automations list or one automation's detail. `client` scopes the page to one client;
 * without it the page shows every client the caller may open.
 */
export async function loadAutomationsPage(
  locals: App.Locals,
  params: URLSearchParams,
  options: { client?: string; schedule?: string },
): Promise<AutomationsPage> {
  const parsed = parseFilters(params);
  if (!parsed) return { kind: "invalid" };
  const filters: Filters = options.client
    ? { ...parsed, client: options.client }
    : parsed;
  try {
    if (options.schedule) {
      if (!uuid.test(options.schedule)) return { kind: "notfound" };
      return {
        kind: "detail",
        filters,
        detail: adaptAutomationDetail(
          await read(
            locals,
            `command-center/automations/${options.schedule}/?runs=10`,
          ),
          options.schedule,
          options.client,
        ),
      };
    }
    const scope = options.client ? `?organization_id=${options.client}` : "";
    return {
      kind: "list",
      filters,
      view: adaptAutomations(
        await read(locals, `command-center/automations/${scope}`),
        options.client,
      ),
    };
  } catch (e) {
    if (e instanceof APIError && e.status === 401)
      return { kind: "unauthenticated" };
    if (e instanceof APIError && [403, 404].includes(e.status))
      return { kind: "notfound" };
    return { kind: "error" };
  }
}
