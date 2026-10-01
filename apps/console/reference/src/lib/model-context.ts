import { clients } from "../data/fixtures";
import { route } from "../config/routes";
interface ToolDefinition {
  name: string;
  title: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, { type: "string" }>;
    required: string[];
    additionalProperties: false;
  };
  annotations: { readOnlyHint: true };
  execute(input: unknown): Record<string, unknown>;
}
interface ModelContext {
  registerTool(tool: ToolDefinition): void | Promise<void>;
}
declare global {
  interface Document {
    modelContext?: ModelContext;
  }
}
function stringArgument(input: unknown, key: string): string {
  if (typeof input !== "object" || input === null || !(key in input))
    throw new Error(`Missing ${key}`);
  const value = Reflect.get(input, key) as unknown;
  if (typeof value !== "string") throw new Error(`${key} must be a string`);
  return value;
}
export function registerPortfolioTools() {
  const capability = document.modelContext;
  if (!capability) return;
  const definitions: ToolDefinition[] = [
    {
      name: "search_client_portfolio",
      title: "Search client portfolio",
      description:
        "Filter the visible agency portfolio by a client name, location or category.",
      inputSchema: {
        type: "object",
        properties: { query: { type: "string" } },
        required: ["query"],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true },
      execute(input) {
        const query = stringArgument(input, "query");
        location.href =
          route("clients") + "?query=" + encodeURIComponent(query);
        return {
          clients: clients
            .filter((c) =>
              (c.name + " " + c.location + " " + c.category)
                .toLowerCase()
                .includes(query.toLowerCase()),
            )
            .map((c) => ({ id: c.id, name: c.name, status: c.status })),
        };
      },
    },
    {
      name: "open_client_workspace",
      title: "Open client workspace",
      description:
        "Navigate to the overview of a sample client by its client ID.",
      inputSchema: {
        type: "object",
        properties: { clientId: { type: "string" } },
        required: ["clientId"],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true },
      execute(input) {
        const id = stringArgument(input, "clientId");
        const client = clients.find((c) => c.id === id);
        if (!client) throw new Error("Unknown client ID");
        location.href = route("client", id);
        return { client: client.name, section: "Overview" };
      },
    },
  ];
  for (const definition of definitions)
    Promise.resolve(capability.registerTool(definition)).catch((error) =>
      console.error("Portfolio tool registration failed", error),
    );
}
