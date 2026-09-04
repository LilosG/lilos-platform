import { apiRequest, type ApiOutcome } from "./api-client";

export type SEOActionType =
  | "content_article"
  | "content_page"
  | "content_page_optimization";

export type SEOActionStart = {
  implementation_task_id: string;
  action_type: SEOActionType;
  status: string;
  content_item_id: string;
  workflow_run_id: string;
  next: string;
};

export function createSEOAction(
  organizationId: string,
  recommendationRevisionId: string,
  input: { actionType: SEOActionType; title?: string; slug?: string },
): Promise<ApiOutcome<SEOActionStart>> {
  return apiRequest<SEOActionStart>(
    `/api/v1/organizations/${organizationId}/seo/recommendations/${recommendationRevisionId}/actions`,
    {
      method: "POST",
      body: {
        action_type: input.actionType,
        title: input.title?.trim() || null,
        slug: input.slug?.trim() || null,
      },
    },
  );
}
