import { expect, test } from "@playwright/test";

const WEB_BASE = "https://lilos-platform-web.vercel.app";
const API_BASE = "https://lilos-api.onrender.com";
const GBP_MODEL = "deepseek/deepseek-v4-flash-0731";
const RUNTIME_RELEASE = "v2026.8.19";
const TARGET_ORG_NAME =
  process.env.LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME?.trim() ?? "";
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
const MUTATING_TOOLS = new Set([
  "generate_gbp_post_proposal",
  "create_gbp_optimization_proposal",
  "submit_for_approval",
]);
const TERMINAL_WORKFLOWS = new Set([
  "completed",
  "failed",
  "cancelled",
  "expired",
  "dead_lettered",
]);
const ACTIVE_AGENTS = new Set([
  "queued",
  "running",
  "waiting_approval",
  "stopping",
]);

type ApiResult<T = unknown> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
  body?: string;
};

type Context = {
  orgId: string;
  locationId: string;
};

type TargetOrganization = {
  id: string;
  name: string;
  source: "platform" | "membership";
};

type AgentRun = {
  id: string;
  skill_key?: string;
  status?: string;
};

type AgentDetail = {
  status?: string;
  model?: string | null;
  provider?: string | null;
  safe_error_code?: string | null;
  hermes_run_id?: string | null;
  hermes_session_id?: string | null;
  capabilities?: {
    runtime_release?: string | null;
    model?: string | null;
  };
  source_references?: string[];
  final_output?: { text?: string } | null;
  usage?: {
    input_tokens?: number | null;
    output_tokens?: number | null;
    latency_ms?: number | null;
  };
  events?: Array<{
    event_type?: string;
    event_document?: {
      tool?: string;
      error?: boolean;
    };
  }>;
};

function normalizeOrganizationName(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function orgPath(orgId: string, suffix: string): string {
  return `/api/v1/organizations/${orgId}${suffix}`;
}

async function ensureOrigin(
  page: import("@playwright/test").Page,
): Promise<void> {
  if (page.url().startsWith(WEB_BASE)) return;
  await page.goto(`${WEB_BASE}/`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#workspace-navigation", { timeout: 20_000 });
  await page.waitForTimeout(500);
}

async function authenticatedFetch<T>(
  page: import("@playwright/test").Page,
  method: "GET" | "POST",
  path: string,
  body?: Record<string, unknown>,
): Promise<ApiResult<T>> {
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

      let responseBody: string;
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
      apiBase: API_BASE,
      requestPath: path,
      requestMethod: method,
      requestBody: body,
    },
  ) as Promise<ApiResult<T>>;
}

async function refreshSession(
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
      const url = `https://${projectRef}.supabase.co/auth/v1/token`;
      const response = await fetch(`${url}?grant_type=refresh_token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
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
): Promise<ApiResult<T>> {
  await ensureOrigin(page);
  const first = await authenticatedFetch<T>(page, method, path, body);
  if (first.status !== 401) return first;
  if (!(await refreshSession(page))) return first;
  return authenticatedFetch<T>(page, method, path, body);
}

async function resolveTargetOrganization(
  page: import("@playwright/test").Page,
  targetName: string,
): Promise<TargetOrganization> {
  const target = normalizeOrganizationName(targetName);
  const platformMatches: Array<{ id: string; name: string }> = [];
  let platformAvailable = true;
  let offset = 0;

  for (let pageNumber = 0; pageNumber < 100; pageNumber += 1) {
    const result = await apiCall<{
      data?: {
        items?: Array<{ id: string; name: string }>;
        has_more?: boolean;
        next_offset?: number | null;
      };
    }>(
      page,
      "GET",
      `/api/v1/platform/organizations?limit=100&offset=${offset}`,
    );

    if (result.status === 403) {
      platformAvailable = false;
      break;
    }
    if (result.status !== 200) {
      throw new Error(
        `Platform organization lookup failed: HTTP ${result.status} — ${result.body ?? result.error ?? "no response body"}`,
      );
    }

    const payload = result.data?.data;
    for (const organization of payload?.items ?? []) {
      if (normalizeOrganizationName(organization.name) === target) {
        platformMatches.push(organization);
      }
    }

    if (!payload?.has_more) break;
    const nextOffset = payload.next_offset;
    if (typeof nextOffset !== "number" || nextOffset <= offset) {
      throw new Error(
        "Platform organization pagination returned an invalid next_offset.",
      );
    }
    offset = nextOffset;
  }

  if (platformAvailable) {
    if (platformMatches.length === 1) {
      return { ...platformMatches[0], source: "platform" };
    }
    if (platformMatches.length > 1) {
      throw new Error(
        `Target organization "${targetName}" is ambiguous in platform administration.`,
      );
    }
    throw new Error(
      `Target organization "${targetName}" was not found in platform administration.`,
    );
  }

  const memberships = await apiCall<{
    data?: Array<{
      id: string;
      organization_id: string;
      organization_name: string;
    }>;
  }>(page, "GET", "/api/v1/me/organizations");
  if (memberships.status !== 200) {
    throw new Error(
      `Membership organization lookup failed: HTTP ${memberships.status} — ${memberships.body ?? memberships.error ?? "no response body"}`,
    );
  }

  const matches = (memberships.data?.data ?? []).filter(
    (organization) =>
      normalizeOrganizationName(organization.organization_name ?? "") ===
      target,
  );
  if (matches.length !== 1) {
    throw new Error(
      `Target organization "${targetName}" must resolve to exactly one accessible organization; found ${matches.length}.`,
    );
  }

  const organization = matches[0];
  return {
    id: organization.organization_id ?? organization.id,
    name: organization.organization_name,
    source: "membership",
  };
}

async function resolveLocationIds(
  page: import("@playwright/test").Page,
  organization: TargetOrganization,
): Promise<string[]> {
  if (organization.source === "platform") {
    const ids: string[] = [];
    let offset = 0;

    for (let pageNumber = 0; pageNumber < 100; pageNumber += 1) {
      const path = `/api/v1/platform/organizations/${organization.id}/locations?limit=100&offset=${offset}`;
      const result = await apiCall<{
        data?: {
          items?: Array<{ id: string }>;
          has_more?: boolean;
          next_offset?: number | null;
        };
      }>(page, "GET", path);
      if (result.status !== 200) {
        throw new Error(
          `Platform location lookup failed: HTTP ${result.status} — ${result.body ?? result.error ?? "no response body"}`,
        );
      }

      const payload = result.data?.data;
      ids.push(...(payload?.items ?? []).map((location) => location.id));
      if (!payload?.has_more) break;
      const nextOffset = payload.next_offset;
      if (typeof nextOffset !== "number" || nextOffset <= offset) {
        throw new Error(
          "Platform location pagination returned an invalid next_offset.",
        );
      }
      offset = nextOffset;
    }

    return ids;
  }

  const result = await apiCall<{
    data?: Array<{ id: string }>;
  }>(page, "GET", orgPath(organization.id, "/locations?limit=100"));
  if (result.status !== 200) {
    throw new Error(
      `Organization location lookup failed: HTTP ${result.status} — ${result.body ?? result.error ?? "no response body"}`,
    );
  }
  return (result.data?.data ?? []).map((location) => location.id);
}

async function resolveContext(
  page: import("@playwright/test").Page,
): Promise<Context> {
  await ensureOrigin(page);
  await expect(page.locator("#sign-out-button")).toBeVisible({
    timeout: 15_000,
  });
  expect(
    TARGET_ORG_NAME,
    "LILOS_PRODUCTION_ACCEPTANCE_ORG_NAME is required for production acceptance",
  ).toBeTruthy();

  const organization = await resolveTargetOrganization(page, TARGET_ORG_NAME);
  const locationIds = await resolveLocationIds(page, organization);
  expect(
    locationIds.length,
    `Target organization "${organization.name}" must have at least one location`,
  ).toBeGreaterThan(0);

  const gbpMappings = await apiCall<{
    data?: Array<{
      location_id: string;
      mapping_status: string;
    }>;
  }>(page, "GET", orgPath(organization.id, "/gbp/locations"));
  expect(gbpMappings.status, gbpMappings.body ?? gbpMappings.error).toBe(200);

  const knownLocationIds = new Set(locationIds);
  const confirmedMappings = (gbpMappings.data?.data ?? [])
    .filter(
      (mapping) =>
        mapping.mapping_status === "confirmed" &&
        knownLocationIds.has(mapping.location_id),
    )
    .sort((left, right) => left.location_id.localeCompare(right.location_id));
  expect(
    confirmedMappings.length,
    `Target organization "${organization.name}" must have a confirmed GBP mapping for the Hermes production canary`,
  ).toBeGreaterThan(0);

  const locationId = confirmedMappings[0]?.location_id ?? "";
  expect(locationId).toBeTruthy();

  return { orgId: organization.id, locationId };
}

async function pollWorkflow(
  page: import("@playwright/test").Page,
  context: Context,
  workflowRunId: string,
): Promise<Record<string, unknown>> {
  const suffix = `/workflows/runs/${workflowRunId}`;
  const path = orgPath(context.orgId, suffix);

  for (let attempt = 0; attempt < 160; attempt += 1) {
    const result = await apiCall<{
      data?: { status?: string; [key: string]: unknown };
    }>(page, "GET", path);
    if (result.ok) {
      const workflow = result.data?.data;
      const status = workflow?.status;
      if (status && TERMINAL_WORKFLOWS.has(status)) {
        return workflow as Record<string, unknown>;
      }
    }
    await page.waitForTimeout(3000);
  }

  throw new Error(`Hermes workflow ${workflowRunId} exceeded 8 minutes`);
}

test.describe.serial("Native Hermes production acceptance", () => {
  test("Hermes capabilities are production-ready", async ({ page }) => {
    const context = await resolveContext(page);
    const path = orgPath(context.orgId, "/agents/capabilities");
    const result = await apiCall<{
      data?: {
        available?: boolean;
        reason_code?: string | null;
        runtime_version?: string;
        runtime_release?: string | null;
        features?: Record<string, boolean>;
        sanctioned_tools?: string[];
        missing_required?: string[];
      };
    }>(page, "GET", path);

    expect(result.status, result.error).toBe(200);
    const data = result.data?.data;
    expect(data?.available, data?.reason_code ?? "Hermes unavailable").toBe(
      true,
    );
    expect(data?.runtime_version).toBeTruthy();
    expect(data?.runtime_release).toBe(RUNTIME_RELEASE);
    expect(data?.missing_required ?? []).toEqual([]);

    for (const feature of REQUIRED_FEATURES) {
      const message = `Missing Hermes capability: ${feature}`;
      expect(data?.features?.[feature], message).toBe(true);
    }
    for (const tool of REQUIRED_READ_TOOLS) {
      const message = `Missing sanctioned LILOs tool: ${tool}`;
      expect(data?.sanctioned_tools ?? [], message).toContain(tool);
    }
  });

  test("GBP read-only canary completes through Hermes", async ({ page }) => {
    test.setTimeout(540_000);
    const context = await resolveContext(page);
    const listSuffix = `/agents/runs?location_id=${context.locationId}&limit=100`;
    const listPath = orgPath(context.orgId, listSuffix);

    const before = await apiCall<{ data?: AgentRun[] }>(page, "GET", listPath);
    expect(before.status, before.error).toBe(200);
    const beforeRuns = before.data?.data ?? [];
    const active = beforeRuns.filter((run) => {
      const isGbp = run.skill_key === "gbp.operator";
      return isGbp && ACTIVE_AGENTS.has(run.status ?? "");
    });
    const activeMessage = active
      .map((run) => `${run.id}:${run.status}`)
      .join(", ");
    expect(active, `Existing active GBP run: ${activeMessage}`).toEqual([]);
    const previousIds = new Set(beforeRuns.map((run) => run.id));

    const startPath = orgPath(context.orgId, "/agents/agent.gbp/runs");
    const started = await apiCall<{
      data?: {
        workflow_run_id?: string;
        skill_key?: string;
      };
    }>(page, "POST", startPath, {
      location_id: context.locationId,
      idempotency_key: `prod-hermes-readonly-${Date.now()}`,
      objective:
        "Production acceptance, read-only. Read approved business facts, website knowledge, current GBP state, and recent GBP posts for the bound location. Do not create any proposal, do not submit anything for approval, and do not request any provider write. Return only a concise evidence-backed status summary.",
      context_reference: "production-acceptance:hermes-readonly-v1",
    });
    expect(started.status, started.body ?? started.error).toBe(201);
    expect(started.data?.data?.skill_key).toBe("gbp.operator");
    const workflowRunId = started.data?.data?.workflow_run_id ?? "";
    expect(workflowRunId).toBeTruthy();

    const workflow = await pollWorkflow(page, context, workflowRunId);
    const failureCode = String(workflow.failure_code ?? "none");
    expect(workflow.status, `Workflow failure: ${failureCode}`).toBe(
      "completed",
    );

    const after = await apiCall<{ data?: AgentRun[] }>(page, "GET", listPath);
    expect(after.status, after.error).toBe(200);
    const createdRuns = (after.data?.data ?? []).filter((run) => {
      return run.skill_key === "gbp.operator" && !previousIds.has(run.id);
    });
    expect(createdRuns.length, "Expected one new GBP agent run").toBe(1);
    const agentRunId = createdRuns[0].id;

    const detailPath = orgPath(context.orgId, `/agents/runs/${agentRunId}`);
    const detailResult = await apiCall<{ data?: AgentDetail }>(
      page,
      "GET",
      detailPath,
    );
    expect(detailResult.status, detailResult.error).toBe(200);

    const detail = detailResult.data?.data;
    const runError = detail?.safe_error_code ?? "Agent run did not complete";
    expect(detail?.status, runError).toBe("completed");
    expect(detail?.provider).toBe("hermes");
    expect(detail?.model).toBe(GBP_MODEL);
    expect(detail?.hermes_run_id).toBeTruthy();
    expect(detail?.hermes_session_id).toBeTruthy();
    expect(detail?.capabilities?.runtime_release).toBe(RUNTIME_RELEASE);
    expect(detail?.capabilities?.model).toBe(GBP_MODEL);

    const events = detail?.events ?? [];
    const completedTools = events
      .filter((event) => {
        const completed = event.event_type === "tool.completed";
        return completed && event.event_document?.error !== true;
      })
      .map((event) => String(event.event_document?.tool ?? ""));

    for (const tool of REQUIRED_READ_TOOLS) {
      const message = `Hermes did not complete required read tool: ${tool}`;
      expect(completedTools, message).toContain(tool);
    }
    for (const tool of completedTools) {
      const message = `Read-only canary invoked mutating tool: ${tool}`;
      expect(MUTATING_TOOLS.has(tool), message).toBe(false);
    }

    const completed = events.some((event) => {
      return event.event_type === "run.completed";
    });
    expect(completed).toBe(true);
    expect(detail?.source_references?.length ?? 0).toBeGreaterThan(0);
    expect(detail?.final_output?.text?.trim().length ?? 0).toBeGreaterThan(0);
    expect(detail?.usage?.input_tokens ?? 0).toBeGreaterThan(0);
    expect(detail?.usage?.output_tokens ?? 0).toBeGreaterThan(0);
    expect(detail?.usage?.latency_ms ?? 0).toBeGreaterThan(0);
  });

  test("steer and stop control a live Hermes run", async ({ page }) => {
    test.setTimeout(180_000);
    const context = await resolveContext(page);
    const listPath = orgPath(
      context.orgId,
      `/agents/runs?location_id=${context.locationId}&limit=100`,
    );
    const before = await apiCall<{ data?: AgentRun[] }>(page, "GET", listPath);
    expect(before.status, before.error).toBe(200);
    const beforeRuns = before.data?.data ?? [];
    const active = beforeRuns.filter(
      (run) =>
        run.skill_key === "gbp.operator" && ACTIVE_AGENTS.has(run.status ?? ""),
    );
    expect(
      active,
      "A prior active GBP agent run would make control acceptance ambiguous",
    ).toEqual([]);
    const previousIds = new Set(beforeRuns.map((run) => run.id));

    const started = await apiCall<{
      data?: { workflow_run_id?: string; skill_key?: string };
    }>(page, "POST", orgPath(context.orgId, "/agents/agent.gbp/runs"), {
      location_id: context.locationId,
      idempotency_key: `prod-hermes-control-${Date.now()}`,
      objective:
        "Production acceptance control canary, strictly read-only. Read approved business facts, website knowledge, current GBP state, and recent GBP posts in that order. Do not create proposals, do not submit anything for approval, and do not request provider writes. Continue through the full read sequence unless an operator steer changes the read-only emphasis.",
      context_reference: "production-acceptance:hermes-control-v1",
    });
    expect(started.status, started.body ?? started.error).toBe(201);
    expect(started.data?.data?.skill_key).toBe("gbp.operator");

    let run: AgentRun | undefined;
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const listed = await apiCall<{ data?: AgentRun[] }>(
        page,
        "GET",
        listPath,
      );
      expect(listed.status, listed.error).toBe(200);
      const created = (listed.data?.data ?? []).filter(
        (candidate) =>
          candidate.skill_key === "gbp.operator" &&
          !previousIds.has(candidate.id),
      );
      expect(
        created.length,
        "Control canary must create at most one native GBP agent run",
      ).toBeLessThanOrEqual(1);
      const candidate = created[0];
      if (candidate?.status === "running") {
        run = candidate;
        break;
      }
      if (
        candidate?.status &&
        !new Set(["queued", "running"]).has(candidate.status)
      ) {
        throw new Error(
          `Control canary became ${candidate.status} before steer could be exercised`,
        );
      }
      await page.waitForTimeout(250);
    }
    expect(run?.id, "Control canary never reached running state").toBeTruthy();
    const agentRunId = run?.id ?? "";

    const steer = await apiCall<{ data?: { id?: string; status?: string } }>(
      page,
      "POST",
      orgPath(context.orgId, `/agents/runs/${agentRunId}/steer`),
      {
        text: "Remain read-only. Give current GBP profile state priority in the final evidence summary and do not create any proposal.",
      },
    );
    expect(steer.status, steer.body ?? steer.error).toBe(200);
    expect(steer.data?.data?.id).toBe(agentRunId);
    expect(steer.data?.data?.status).toBe("running");

    const stopped = await apiCall<{
      data?: { id?: string; status?: string };
    }>(page, "POST", orgPath(context.orgId, `/agents/runs/${agentRunId}/stop`));
    expect(stopped.status, stopped.body ?? stopped.error).toBe(200);
    expect(stopped.data?.data?.id).toBe(agentRunId);
    expect(stopped.data?.data?.status).toBe("stopping");

    let finalDetail: AgentDetail | undefined;
    for (let attempt = 0; attempt < 160; attempt += 1) {
      const detail = await apiCall<{ data?: AgentDetail }>(
        page,
        "GET",
        orgPath(context.orgId, `/agents/runs/${agentRunId}`),
      );
      expect(detail.status, detail.error).toBe(200);
      const candidate = detail.data?.data;
      if (candidate?.status === "cancelled") {
        finalDetail = candidate;
        break;
      }
      if (
        candidate?.status &&
        ["completed", "failed"].includes(candidate.status)
      ) {
        throw new Error(
          `Control canary became ${candidate.status} after stop instead of cancelled`,
        );
      }
      await page.waitForTimeout(250);
    }

    expect(
      finalDetail?.status,
      "Stopped Hermes run did not become cancelled",
    ).toBe("cancelled");
    expect(finalDetail?.provider).toBe("hermes");
    expect(finalDetail?.model).toBe(GBP_MODEL);
    expect(finalDetail?.hermes_run_id).toBeTruthy();
    const events = finalDetail?.events ?? [];
    expect(events.some((event) => event.event_type === "run.cancelled")).toBe(
      true,
    );
    const completedTools = events
      .filter(
        (event) =>
          event.event_type === "tool.completed" &&
          event.event_document?.error !== true,
      )
      .map((event) => String(event.event_document?.tool ?? ""));
    for (const tool of completedTools) {
      expect(
        MUTATING_TOOLS.has(tool),
        `Control canary invoked mutating tool before cancellation: ${tool}`,
      ).toBe(false);
    }
  });

  test("agent run and location reads remain tenant-scoped", async ({
    page,
  }) => {
    const context = await resolveContext(page);
    const targetRuns = await apiCall<{ data?: AgentRun[] }>(
      page,
      "GET",
      orgPath(
        context.orgId,
        `/agents/runs?location_id=${context.locationId}&limit=100`,
      ),
    );
    expect(targetRuns.status, targetRuns.error).toBe(200);
    const targetRun = (targetRuns.data?.data ?? []).find(
      (run) => run.skill_key === "gbp.operator",
    );
    expect(
      targetRun?.id,
      "Expected a target-tenant GBP run for isolation proof",
    ).toBeTruthy();

    const memberships = await apiCall<{
      data?: Array<{
        id: string;
        organization_id: string;
        organization_name: string;
      }>;
    }>(page, "GET", "/api/v1/me/organizations");
    expect(memberships.status, memberships.body ?? memberships.error).toBe(200);
    const otherOrganization = (memberships.data?.data ?? []).find((row) => {
      const id = row.organization_id ?? row.id;
      return Boolean(id) && id !== context.orgId;
    });
    expect(
      otherOrganization,
      "Production isolation acceptance requires a second accessible organization",
    ).toBeTruthy();
    const otherOrgId =
      otherOrganization?.organization_id ?? otherOrganization?.id ?? "";

    const crossTenantDetail = await apiCall(
      page,
      "GET",
      orgPath(otherOrgId, `/agents/runs/${targetRun?.id ?? ""}`),
    );
    expect(
      crossTenantDetail.status,
      "A run from the target tenant must be invisible through another organization",
    ).toBe(404);

    const otherLocations = await apiCall<{
      data?: Array<{ id: string }>;
    }>(page, "GET", orgPath(otherOrgId, "/locations?limit=100"));
    expect(
      otherLocations.status,
      otherLocations.body ?? otherLocations.error,
    ).toBe(200);
    const otherLocationId = otherLocations.data?.data?.[0]?.id ?? "";
    expect(otherLocationId).toBeTruthy();

    const foreignLocationInTarget = await apiCall<{ data?: AgentRun[] }>(
      page,
      "GET",
      orgPath(
        context.orgId,
        `/agents/runs?location_id=${otherLocationId}&limit=100`,
      ),
    );
    expect(
      foreignLocationInTarget.status,
      foreignLocationInTarget.body ?? foreignLocationInTarget.error,
    ).toBe(200);
    expect(foreignLocationInTarget.data?.data ?? []).toEqual([]);

    const targetLocationInOther = await apiCall<{ data?: AgentRun[] }>(
      page,
      "GET",
      orgPath(
        otherOrgId,
        `/agents/runs?location_id=${context.locationId}&limit=100`,
      ),
    );
    expect(
      targetLocationInOther.status,
      targetLocationInOther.body ?? targetLocationInOther.error,
    ).toBe(200);
    expect(targetLocationInOther.data?.data ?? []).toEqual([]);
  });
});
