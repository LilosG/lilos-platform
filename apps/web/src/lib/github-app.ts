import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type GitHubRepository = {
  repository_id: string;
  name: string;
  default_branch: string;
  private: boolean;
};

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/integrations/github`;
}

export function beginGitHubInstall(
  organizationId: string,
): Promise<ApiOutcome<{ authorization_url: string }>> {
  return apiRequest<{ authorization_url: string }>(
    `${base(organizationId)}/install`,
    { method: "POST" },
  );
}

export function fetchGitHubRepositories(
  organizationId: string,
): Promise<ApiOutcome<GitHubRepository[]>> {
  return apiGet<GitHubRepository[]>(`${base(organizationId)}/repositories`);
}
