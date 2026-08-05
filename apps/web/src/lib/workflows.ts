import { apiRequest, type ApiOutcome } from "./api-client";

export type WorkflowRunStart = {
  workflow_run_id: string;
  status: string;
  product_key: string | null;
};

/**
 * Start (or idempotently resolve) a real, persisted workflow run.
 *
 * This is the only supported way to obtain a workflow_run_id for a product
 * action (content publication, SEO crawl/analysis, GBP change or post
 * publication). No caller may generate its own workflow_run_id — the id
 * returned here always references a real WorkflowRun row.
 */
export function startWorkflowRun(
  organizationId: string,
  workflowKey: string,
  options: {
    locationId?: string;
    idempotencyKey: string;
    inputDocument?: Record<string, unknown>;
  },
): Promise<ApiOutcome<WorkflowRunStart>> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/workflows/${workflowKey}/runs`,
    {
      method: "POST",
      body: {
        location_id: options.locationId ?? null,
        idempotency_key: options.idempotencyKey,
        input_document: options.inputDocument ?? {},
      },
    },
  );
}
