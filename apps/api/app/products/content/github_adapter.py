"""Real GitHub repository publishing adapter for the Content product.

Implements the ``RepositoryPublisher`` protocol against the GitHub REST API
(https://api.github.com).  The adapter is configured per-organization through
the existing ``PublishingTarget`` model (``repository_id``, ``base_branch``,
``allowed_path_prefix``) and the ``IntegrationConnection`` credential store —
no credentials or repository values are hard-coded here.

The adapter performs: branch creation from the base ref, file put (content
blob), and pull-request creation.  CI/CD checks and deployment are read
best-effort so the publication status is always truthful — a publication is
only marked ``verified`` when the PR exists and checks have passed.
"""

from dataclasses import dataclass
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"


@dataclass(slots=True)
class GitHubRepositoryPublisher:
    """Concrete ``RepositoryPublisher`` backed by the GitHub REST API."""

    access_token: str
    timeout_seconds: float = 30.0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self, method: str, path: str, *, expected_status: int = 200, **kwargs: Any
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.request(
                method, f"{GITHUB_API}{path}", headers=self._headers(), **kwargs
            )
        if response.status_code != expected_status:
            raise RuntimeError(
                f"GitHub API {method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        if not response.content:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("invalid GitHub response")
        return payload

    async def get_base_commit(self, repository_id: str, base_branch: str) -> str:
        """Return the SHA of the base branch head."""
        payload = await self._request("GET", f"/repos/{repository_id}/git/refs/heads/{base_branch}")
        return str(payload["object"]["sha"])

    async def create_branch(
        self, repository_id: str, base_branch: str, base_commit: str, branch_name: str
    ) -> str:
        del base_branch
        await self._request(
            "POST",
            f"/repos/{repository_id}/git/refs",
            expected_status=201,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_commit},
        )
        return base_commit

    async def put_file(
        self,
        repository_id: str,
        branch_name: str,
        path: str,
        content: str,
        expected_blob_sha: str | None,
    ) -> str:
        del expected_blob_sha
        import base64

        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload = await self._request(
            "PUT",
            f"/repos/{repository_id}/contents/{path}",
            expected_status=200,
            json={
                "message": "Publish governed content",
                "branch": branch_name,
                "content": encoded,
            },
        )
        return str(payload.get("content", {}).get("sha", ""))

    async def create_pull_request(
        self,
        repository_id: str,
        branch_name: str,
        base_branch: str,
        title: str,
        idempotency_key: str,
    ) -> str:
        payload = await self._request(
            "POST",
            f"/repos/{repository_id}/pulls",
            expected_status=201,
            json={
                "title": title,
                "head": branch_name,
                "base": base_branch,
                "body": f"Governed content publication (idempotency: {idempotency_key})",
            },
        )
        return str(payload["number"])

    async def get_pull_request(self, repository_id: str, pr_number: str) -> dict[str, object]:
        return await self._request("GET", f"/repos/{repository_id}/pulls/{pr_number}")

    async def checks(self, repository_id: str, revision_id: str) -> dict[str, str]:
        payload = await self._request(
            "GET",
            f"/repos/{repository_id}/commits/{revision_id}/check-runs",
        )
        runs = list(payload.get("check_runs", []))
        if not runs:
            return {"state": "none"}
        states = {str(run.get("conclusion") or run.get("status", "")).lower() for run in runs}
        if states == {"success"}:
            return {"state": "success"}
        if "failure" in states or "cancelled" in states:
            return {"state": "failed"}
        return {"state": "pending"}

    async def deployment(self, repository_id: str, revision_id: str) -> dict[str, str]:
        payload = await self._request(
            "GET",
            f"/repos/{repository_id}/deployments",
            params={"sha": revision_id},
        )
        deployments: list[dict[str, Any]] = list(payload) if isinstance(payload, list) else []
        if not deployments:
            return {"state": "none", "url": ""}
        latest = deployments[0]
        return {"state": str(latest.get("state", "pending")), "url": str(latest.get("id", ""))}
