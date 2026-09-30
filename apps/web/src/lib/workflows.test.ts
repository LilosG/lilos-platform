import { beforeEach, describe, expect, it, vi } from "vitest";

const apiRequest = vi.fn();
vi.mock("./api-client", () => ({
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import { describeRunFailureCode, waitForWorkflowRun } from "./workflows";

const run = (status: string, failure_code: string | null = null) => ({
  kind: "ok",
  data: { id: "run-1", status, failure_code },
});

describe("waitForWorkflowRun", () => {
  const sleep = vi.fn(async () => {});
  beforeEach(() => {
    apiRequest.mockReset();
    sleep.mockClear();
  });

  it("polls until the run completes", async () => {
    apiRequest
      .mockResolvedValueOnce(run("queued"))
      .mockResolvedValueOnce(run("running"))
      .mockResolvedValueOnce(run("completed"));
    const outcome = await waitForWorkflowRun("org-1", "run-1", { sleep });
    expect(outcome.kind).toBe("ok");
    expect(apiRequest).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenCalledTimes(2);
  });

  it("turns a terminal failure into an error carrying the typed code", async () => {
    apiRequest.mockResolvedValueOnce(
      run("failed", "SEARCH_CONSOLE_SYNC_INCOMPLETE"),
    );
    const outcome = await waitForWorkflowRun("org-1", "run-1", { sleep });
    expect(outcome).toMatchObject({
      kind: "error",
      code: "WORKFLOW_RUN_FAILED",
      details: [{ code: "SEARCH_CONSOLE_SYNC_INCOMPLETE" }],
    });
    expect(outcome.kind === "error" && outcome.message).toContain(
      "previous data is unchanged",
    );
  });

  it("stops waiting after the timeout and says the run is still going", async () => {
    apiRequest.mockResolvedValue(run("running"));
    const outcome = await waitForWorkflowRun("org-1", "run-1", {
      sleep,
      intervalMs: 1_000,
      timeoutMs: 3_000,
    });
    expect(outcome).toMatchObject({
      kind: "error",
      code: "WORKFLOW_RUN_PENDING",
    });
  });

  it("passes a transport failure straight through", async () => {
    apiRequest.mockResolvedValueOnce({ kind: "disconnected" });
    expect(await waitForWorkflowRun("org-1", "run-1", { sleep })).toEqual({
      kind: "disconnected",
    });
  });
});

describe("describeRunFailureCode", () => {
  it("never renders a raw code as the only explanation", () => {
    expect(describeRunFailureCode("INTEGRATION_RECONNECT_REQUIRED")).toContain(
      "reconnected",
    );
    expect(describeRunFailureCode("SOMETHING_NEW")).toContain("SOMETHING_NEW");
    expect(describeRunFailureCode(null)).toBe("The sync did not finish.");
  });
});
