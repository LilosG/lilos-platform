import { expect, test } from "@playwright/test";

const PRODUCTION_WEB_BASE = "https://lilos-platform-web.vercel.app";
const PRODUCTION_API_BASE = "https://lilos-api.onrender.com";
const EXPECTED_GBP_MODEL = "deepseek/deepseek-v4-flash-0731";
const EXPECTED_RUNTIME_RELEASE = "v2026.8.19";
const REQUIRED_FEATURES = [
  "run_submission",
  "run_status",
  "run_events_sse",
  "run_stop",
  "run_steer",
  "run_approval_response",
  "tool_progress_events",
  "approval_events",
] as const;
const REQUIRED_READ_TOOLS = [
  "read_client_business_facts",
  "read_website_knowledge",
  "read_gbp_state",
  "read_gbp_recent_posts",
] as const;
const MUTATING_GBP_TOOLS = new Set([
  "generate_gbp_post_proposal",
  "create_gbp_optimization_proposal",
  "submit_for_approval",
]);
const TERMINAL_WORKFLOW_STATUSES = new Set([
  "completed",
  "failed",
  "cancelled",
  "expired",
  "dead_lettered",
]);
const ACTIVE_AGENT_STATUSES = new Set([
  "queued",
  "running",
  "waiting_approval",
  "stopping",
]);

type ApiCallResult<T = unknown> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
  body?: string;
};

type ProductionContext = {
  orgId: string;
  locationId: string;
};

type AgentRunSummary = {
  id: string;
  location_id?: string | null;
  skill_key?: string;
  status?: string;
  model?: string | null;
  safe_error_code?: string | null;
  created_at?: string | null;
};

async function ensureProductionOrigin(
  page: import("@playwright/test").Page,
): Promise<void> {
  if (page.url().startsWith(PRODUCTION_WEB_BASE)) return;
  await page.goto(`${PRODUCTION_WEB_BASE}/`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#workspace-navigation", { timeout: 20_000 });
  await page.waitForTimeout(500);
}

async function authenticatedFetch<T>(
  page: import("@playwright/test").Page,
  method: "GET" | "POST",
  path: string,
  body?: Record<string, unknown>,
): Promise<ApiCallResult<T>> {
  return page.evaluate(
    async ({ apiBase, requestPath, requestMethod, requestBody }) => {
      const keys = Object.keys(localStorage);
      const authKey = keys.find(
        (key) => key.startsWith("sb-") && key.endsWith("-auth-token"),
      );
      let token = "";
      if (authKey) {
        try {
          const session = JSON.parse(localStorage.getItem(authKey) ?? "{}");
          token = session?.access_token ?? "";
        } catch {
          token = "";
        }
      }

      const headers: Record<string, string> = { Accept: "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;
      if (requestBody && requestMethod !== "GET") {
        headers["Content-Type"] = "application/json";
      }

      const options: RequestInit = { method: requestMethod, headers };
      if (requestBody && requestMethod !== "GET") {
        options.body = JSON.stringify(requestBody);
      }

      let response: Response;
      try {
        response = await fetch(`${apiBase}${requestPath}`, options);
      } catch (error) {
        return {
          ok: false,
          status: 0,
          error: `Network error: ${String(error)}`,
          body: "",
        };
      }

      let responseBody = "";
      try {
        const parsed = await response.json();
        if (response.ok) {
          return { ok: true, status: response.status, data: parsed };
        }
        responseBody = JSON.stringify(parsed);
      } catch {
        responseBody = await response.text().catch(() => "(unreadable)");
      }
      return {
        ok: false,
        status: response.status,
        error: `HTTP ${response.status} from ${requestMethod} ${requestPath}`,
        body: responseBody.slice(0, 500),
      };
    },
    {
      apiBase: PRODUCTION_API_BASE,
      requestPath: path,
      requestMethod: method,
      requestBody: body,
    },
  ) as Promise<ApiCallResult<T>>;
}

async function refreshSupabaseSession(
  page: import("@playwright/test").Page,
): Promise<boolean> {
  return page.evaluate(async () => {
    const keys = Object.keys(localStorage);
    const authKey = keys.find(
      (key) => key.startsWith("sb-") && key.endsWith("-auth-token"),
    );
    if (!authKey) return false;
    try {
      const session = JSON.parse(localStorage.getItem(authKey) ?? "{}");
      const refreshToken = session?.refresh_token;
      if (!refreshToken) return false;
      const projectRef = authKey
        .replace(/^sb-/, "")
        .replace(/-auth-token$/, "");
      const response = await fetch(
        `https://${projectRef}.supabase.co/auth/v1/token?grant_type=refresh_token`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        },
      );
      if (!response.ok) return false;
      const refreshed = await response.json();
      localStorage.setItem(authKey, JSON.stringify(refreshed));
      return true;
    } catch {
      return false;
    }
  });
}

async function apiCall<T = unknown>(
  page: import("@playwright/test").Page,
  method: "GET" | "POST",
  path: string,
  body?: Record<string, unknown>,
): Promise<ApiCallResult<T>> {
  await ensureProductionOrigin(page);
  const first = await authenticatedFetch<T>(page, method, path, body);
  if (first.status !== 401) return first;
  if (!(await refreshSupabaseSession(page))) return first;
  return authenticatedFetch<T>(page, method, path, body);
}

async function resolveProductionContext(
  page: import("@playwright/test").Page,
): Promise<ProductionContext> {
  await ensureProductionOrigin(page);
  await expect(page.locator("#sign-out-button")).toBeVisible({
    timeout: 15_000,
  });

  const organizations = await apiCall<{
    data?: Array<{
      id: string;
      organization_id: string;
      organization_name: string;
    }>;
  }>(page, "GET", "/api/v1/me/organizations");
  expect(organizations.status, organizations.error).toBe(200);
  const wheyland = (organizations.data?.data ?? []).find((organization) =>
    organization.organization_name?.toLowerCase().includes("wheyland"),
  );
  expect(
    wheyland,
    "Wheyland Electric must be available to production acceptance",
  ).toBeTruthy();
  const orgId = wheyland?.organization_id ?? wheyland?.id ?? "";
  expect(orgId).toBeTruthy();

  const locations = await apiCall<{
    data?: Array<{ id: string; display_name?: string }>;
  }>(page, "GET", `/api/v1/organizations/${orgId}/locations?limit=5`);
  expect(locations.status, locations.error).toBe(200);
  const locationId = locations.data?.data?.[0]?.id ?? "";
  expect(
    locationId,
    "Wheyland Electric must have a production location",
  ).toBeTruthy();

  return { orgId, locationId };
}

async function pollWorkflowRun(
  page: import("@playwright/test").Page,
  orgId: string,
  workflowRunId: string,
): Promise<Record<string, unknown>> {
  for (let attempt = 0; attempt < 160; attempt += 1) {
    const result = await apiCall<{
      data?: { status?: string; [key: string]: unknown };
    }>(
      page,
      "GET",
      `/api/v1/organizations/${orgId}/workflows/runs/${workflowRunId}`,
    );
    if (result.ok) {
      const workflow = result.data?.data;
      const status = workflow?.status;
      if (status && TERMINAL_WORKFLOW_STATUSES.has(status)) {
        return workflow as Record<string, unknown>;
      }
    }
    await page.waitForTimeout(3000);
  }
  throw new Error(
    `Hermes workflow ${workflowRunId} did not reach terminal state within 8 minutes`,
  );
}

test.describe.serial("Native Hermes production acceptance", () => {
  test("private Hermes runtime advertises the governed native-run contract", async ({
    page,
  }) => {
    const context = await resolveProductionContext(page);
    const capabilities = await apiCall<{
      data?: {
        available?: boolean;
        reason_code?: string | null;
        runtime_version?: string;
        runtime_release?: string | null;
        features?: Record<string, boolean>;
        sanctioned_tools?: string[];
        missing_required?: string[];
      };
    }>(
      page,
      "GET",
      `/api/v1/organizations/${context.orgId}/agents/capabilities`,
    );

    expect(capabilities.status, capabilities.error).toBe(200);
    const data = capabilities.data?.data;
    expect(data?.available, data?.reason_code ?? "Hermes unavailable").toBe(true);
    expect(data?.runtime_version).toBeTruthy();
    expect(data?.runtime_release).toBe(EXPECTED_RUNTIME_RELEASE);
    expect(data?.missing_required ?? []).toEqual([]);
    for (const feature of REQUIRED_FEATURES) {
      expect(
        data?.features?.[feature],
        `Missing Hermes capability: ${feature}`,
      ).toBe(true);
    }
    for (const tool of REQUIRED_READ_TOOLS) {
      expect(
        data?.sanctioned_tools ?? [],
        `Missing sanctioned LILOs tool: ${tool}`,
      ).toContain(tool);
    }
  });

  test("read-only GBP agent uses the governed OpenRouter model and LILOs tools end to end", async ({
    page,
  }) => {
    test.setTimeout(540_000);
    const context = await resolveProductionContext(page);

    const before = await apiCall<{ data?: AgentRunSummary[] }>(
      page,
      "GET",
      `/api/v1/organizations/${context.orgId}/agents/runs?location_id=${context.locationId}&limit=100`,
    );
    expect(before.status, before.error).toBe(200);
    const beforeRuns = before.data?.data ?? [];
    const active = beforeRuns.filter(
      (run) =>
        run.skill_key === "gbp.operator" &&
        ACTIVE_AGENT_STATUSES.has(run.status ?? ""),
    );
    expect(
      active,
      `Existing active GBP agent run prevents an isolated acceptance canary: ${active
        .map((run) => `${run.id}:${run.status}`)
        .join(", ")}`,
    ).toEqual([]);
    const previousIds = new Set(beforeRuns.map((run) => run.id));

    const idempotencyKey = `prod-hermes-readonly-${Date.now()}`;
    const started = await apiCall<{
      data?: {
        workflow_run_id?: string;
        status?: string;
        skill_key?: string;
      };
    }>(
      page,
      "POST",
      `/api/v1/organizations/${context.orgId}/agents/agent.gbp/runs`,
      {
        location_id: context.locationId,
        idempotency_key: idempotencyKey,
        objective:
          "Production acceptance, read-only. Read approved business facts, website knowledge, current GBP state, and recent GBP posts for the bound location. Do not create any proposal, do not submit anything for approval, and do not request any provider write. Return only a concise evidence-backed status summary.",
        context_reference: "production-acceptance:hermes-readonly-v1",
      },
    );
    expect(started.status, started.body ?? started.error).toBe(201);
    expect(started.data?.data?.skill_key).toBe("gbp.operator");
    const workflowRunId = started.data?.data?.workflow_run_id ?? "";
    expect(workflowRunId).toBeTruthy();

    const workflow = await pollWorkflowRun(
      page,
      context.orgId,
      workflowRunId,
    );
    expect(
      workflow.status,
      `Hermes workflow failed: failure_code=${String(
        workflow.failure_code ?? "none",
      )}`,
    ).toBe("completed");

    const after = await apiCall<{ data?: AgentRunSummary[] }>(
      page,
      "GET",
      `/api/v1/organizations/${context.orgId}/agents/runs?location_id=${context.locationId}&limit=100`,
    );
    expect(after.status, after.error).toBe(200);
    const createdRuns = (after.data?.data ?? []).filter(
      (run) => run.skill_key === "gbp.operator" && !previousIds.has(run.id),
    );
    expect(
      createdRuns.length,
      "Expected exactly one new governed GBP agent run",
    ).toBe(1);
    const agentRunId = createdRuns[0].id;

    const detailResponse = await apiCall<{
      data?: {
        id: string;
        status?: string;
        model?: string | null;
        provider?: string | null;
        safe_error_code?: string | null;
        hermes_run_id?: string | null;
        hermes_session_id?: string | null;
        capabilities?: {
          runtime_release?: string | null;
          model?: string | null;
          features?: Record<string, boolean>;
          sanctioned_tools?: string[];
        };
        source_references?: string[];
        final_output?: { text?: string } | null;
        usage?: {
          input_tokens?: number | null;
          output_tokens?: number | null;
          estimated_cost_microunits?: number | null;
          latency_ms?: number | null;
        };
        events?: Array<{
          event_type?: string;
          event_document?: {
            tool?: string;
            error?: boolean;
            [key: string]: unknown;
          };
        }>;
      };
    }>(
      page,
      "GET",
      `/api/v1/organizations/${context.orgId}/agents/runs/${agentRunId}`,
    );
    expect(detailResponse.status, detailResponse.error).toBe(200);
    const detail = detailResponse.data?.data;
    expect(
      detail?.status,
      detail?.safe_error_code ?? "Agent run did not complete",
    ).toBe("completed");
    expect(detail?.provider).toBe("hermes");
    expect(detail?.model).toBe(EXPECTED_GBP_MODEL);
    expect(detail?.hermes_run_id).toBeTruthy();
    expect(detail?.hermes_session_id).toBeTruthy();
    expect(detail?.capabilities?.runtime_release).toBe(EXPECTED_RUNTIME_RELEASE);
    expect(detail?.capabilities?.model).toBe(EXPECTED_GBP_MODEL);

    const events = detail?.events ?? [];
    const completedTools = events
      .filter(
        (event) =>
          event.event_type === "tool.completed" &&
          event.event_document?.error !== true,
      )
      .map((event) => String(event.event_document?.tool ?? ""));
    for (const tool of REQUIRED_READ_TOOLS) {
      expect(
        completedTools,
        `Hermes did not complete required read tool: ${tool}`,
      ).toContain(tool);
    }
    for (const tool of completedTools) {
      expect(
        MUTATING_GBP_TOOLS.has(tool),
        `Read-only canary invoked mutating tool: ${tool}`,
      ).toBe(false);
    }
    expect(
      events.some((event) => event.event_type === "run.completed"),
    ).toBe(true);
    expect(detail?.source_references?.length ?? 0).toBeGreaterThan(0);
    expect(detail?.final_output?.text?.trim().length ?? 0).toBeGreaterThan(0);
    expect(detail?.usage?.input_tokens ?? 0).toBeGreaterThan(0);
    expect(detail?.usage?.output_tokens ?? 0).toBeGreaterThan(0);
    expect(detail?.usage?.latency_ms ?? 0).toBeGreaterThan(0);
  });
});
