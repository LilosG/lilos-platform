"""Real GitHub repository publishing adapter for the Content product.

The adapter is deliberately idempotent across worker retries: branch, file and
pull-request creation first re-read provider state before attempting a write.
Publishing can therefore recover after an ambiguous network outcome without
creating duplicate branches or pull requests.
"""

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
GITHUB_PAGE_SIZE = 100
MAX_GITHUB_PAGES = 1_000


@dataclass(slots=True)
class GitHubRepositoryPublisher:
    """Concrete repository publisher backed by the GitHub REST API."""

    access_token: str
    timeout_seconds: float = 30.0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        expected_status: int | tuple[int, ...] = 200,
        **kwargs: Any,
    ) -> Any:
        from apps.api.app.config import EnvironmentName, Settings
        from apps.api.app.staging.write_boundary import (
            ProviderWriteDeniedError,
            require_github_scope,
        )

        settings = Settings()
        if settings.environment is EnvironmentName.STAGING:
            parts = path.split("/")
            if len(parts) < 5 or parts[1] != "repos":
                raise ProviderWriteDeniedError("STAGING_GITHUB_ROUTE_DENIED")
            repository = "/".join(parts[2:4])
            require_github_scope(settings, repository)
            if method != "GET":
                document = kwargs.get("json", {})
                if parts[4] == "contents":
                    require_github_scope(
                        settings,
                        repository,
                        path="/".join(parts[5:]),
                        branch=document.get("branch", ""),
                    )
                elif path.endswith("/git/refs"):
                    require_github_scope(
                        settings,
                        repository,
                        branch=str(document.get("ref", "")).removeprefix("refs/heads/"),
                    )
                elif parts[4] == "pulls" and method == "POST":
                    require_github_scope(settings, repository, branch=document.get("head", ""))
                    if document.get("base") != settings.staging_github_base_branch:
                        raise ProviderWriteDeniedError("STAGING_GITHUB_BASE_BRANCH_DENIED")
                elif not (parts[4] == "pulls" and path.endswith("/merge") and method == "PUT"):
                    raise ProviderWriteDeniedError("STAGING_GITHUB_ROUTE_DENIED")
        accepted = (expected_status,) if isinstance(expected_status, int) else expected_status
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.request(
                method, f"{GITHUB_API}{path}", headers=self._headers(), **kwargs
            )
        if response.status_code not in accepted:
            raise RuntimeError(
                f"GitHub API {method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        if response.status_code == 404 or not response.content:
            return None if response.status_code == 404 else {}
        return response.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int | tuple[int, ...] = 200,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = await self._request_json(method, path, expected_status=expected_status, **kwargs)
        if not isinstance(payload, dict):
            raise RuntimeError("invalid GitHub response")
        return payload

    async def get_base_commit(self, repository_id: str, base_branch: str) -> str:
        payload = await self._request("GET", f"/repos/{repository_id}/git/refs/heads/{base_branch}")
        return str(payload["object"]["sha"])

    async def get_file(self, repository_id: str, ref: str, path: str) -> str | None:
        """Read one UTF-8 text file at a ref, or None when it does not exist there."""
        import base64

        payload = await self._request_json(
            "GET",
            f"/repos/{repository_id}/contents/{path}",
            expected_status=(200, 404),
            params={"ref": ref},
        )
        if payload is None:
            return None
        if not isinstance(payload, dict) or payload.get("type") != "file":
            raise RuntimeError("GitHub path is not a file")
        if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
            raise RuntimeError("GitHub file content is unavailable")
        return base64.b64decode(payload["content"]).decode("utf-8")

    async def create_branch(
        self, repository_id: str, base_branch: str, base_commit: str, branch_name: str
    ) -> str:
        del base_branch
        existing = await self._request_json(
            "GET",
            f"/repos/{repository_id}/git/refs/heads/{branch_name}",
            expected_status=(200, 404),
        )
        if isinstance(existing, dict):
            return str(existing.get("object", {}).get("sha", base_commit))
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
        import base64

        existing = await self._request_json(
            "GET",
            f"/repos/{repository_id}/contents/{path}",
            expected_status=(200, 404),
            params={"ref": branch_name},
        )
        current_sha = expected_blob_sha
        if isinstance(existing, dict):
            current_sha = str(existing.get("sha") or "") or current_sha
            blob = f"blob {len(content.encode('utf-8'))}\0".encode() + content.encode("utf-8")
            if current_sha == hashlib.sha1(blob).hexdigest():
                return current_sha
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        document: dict[str, object] = {
            "message": "Publish governed content",
            "branch": branch_name,
            "content": encoded,
        }
        if current_sha:
            document["sha"] = current_sha
        payload = await self._request(
            "PUT",
            f"/repos/{repository_id}/contents/{path}",
            expected_status=(200, 201),
            json=document,
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
        owner = repository_id.split("/", 1)[0]
        existing = await self._request_json(
            "GET",
            f"/repos/{repository_id}/pulls",
            params={"state": "all", "head": f"{owner}:{branch_name}", "base": base_branch},
        )
        if isinstance(existing, list) and existing:
            number = existing[0].get("number")
            if number is not None:
                return str(number)
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
        runs: list[dict[str, Any]] = []
        provider_total: int | None = None
        for page_number in range(1, MAX_GITHUB_PAGES + 1):
            payload = await self._request(
                "GET",
                f"/repos/{repository_id}/commits/{revision_id}/check-runs",
                params={"page": page_number, "per_page": GITHUB_PAGE_SIZE},
            )
            raw_runs = payload.get("check_runs", [])
            if not isinstance(raw_runs, list) or not all(isinstance(run, dict) for run in raw_runs):
                raise RuntimeError("invalid GitHub check-runs page")
            page_runs = list(raw_runs)
            runs.extend(page_runs)
            raw_total = payload.get("total_count")
            if raw_total is not None:
                if isinstance(raw_total, bool) or not isinstance(raw_total, int) or raw_total < 0:
                    raise RuntimeError("invalid GitHub check-runs total_count")
                provider_total = max(provider_total or 0, raw_total)
            if provider_total is not None and len(runs) > provider_total:
                raise RuntimeError("GitHub check-runs exceeded provider total")
            if provider_total is not None and len(runs) == provider_total:
                break
            if provider_total is None and len(page_runs) < GITHUB_PAGE_SIZE:
                break
            if provider_total is not None and len(page_runs) < GITHUB_PAGE_SIZE:
                raise RuntimeError("GitHub check-runs pagination is incomplete")
        else:
            raise RuntimeError("GitHub check-runs pagination exceeded safety limit")

        status_payload = await self._request(
            "GET", f"/repos/{repository_id}/commits/{revision_id}/status"
        )
        raw_statuses = status_payload.get("statuses", [])
        if not isinstance(raw_statuses, list) or not all(
            isinstance(status, dict) for status in raw_statuses
        ):
            raise RuntimeError("invalid GitHub commit statuses response")

        # Vercel's Preview Comments check confirms only that a PR comment was
        # updated. The actual deployment result is a GitHub commit status.
        meaningful_runs = [
            run
            for run in runs
            if str(run.get("name") or "").strip().lower() != "vercel preview comments"
        ]
        vercel_statuses = [
            status
            for status in raw_statuses
            if str(status.get("context") or "").strip().lower().startswith("vercel")
        ]
        other_statuses = [status for status in raw_statuses if status not in vercel_statuses]

        # What gates a merge. The client's own CI wins when it exists; otherwise a
        # Vercel preview deployment status on the head commit stands in for a build.
        # With neither there is nothing to prove the change builds: state "none".
        if meaningful_runs or other_statuses:
            gate = "repository_ci"
        elif vercel_statuses:
            gate = "vercel_preview"
        else:
            return {"state": "none", "gate": "none"}

        # A failing Vercel status still fails a CI-gated change, and a pending one
        # keeps it waiting: every reported result must be green before merging.
        states = {
            str(run.get("conclusion") or run.get("status", "")).lower() for run in meaningful_runs
        }
        states.update(str(status.get("state") or "").lower() for status in raw_statuses)
        if states <= {"success", "neutral", "skipped"}:
            return {"state": "success", "gate": gate}
        if states & {"failure", "error", "cancelled", "timed_out", "action_required"}:
            return {"state": "failed", "gate": gate}
        return {"state": "pending", "gate": gate}

    async def merge_pull_request(
        self, repository_id: str, pr_number: str, expected_head_sha: str
    ) -> str:
        current = await self.get_pull_request(repository_id, pr_number)
        from apps.api.app.config import Settings
        from apps.api.app.staging.write_boundary import (
            ProviderWriteDeniedError,
            require_github_scope,
        )

        settings = Settings()
        if settings.environment.value == "staging":
            head_info = current.get("head", {})
            base_info = current.get("base", {})
            if not isinstance(head_info, dict) or not isinstance(base_info, dict):
                raise ProviderWriteDeniedError("STAGING_GITHUB_PULL_REQUEST_INVALID")
            require_github_scope(
                settings,
                str(head_info.get("repo", {}).get("full_name", "")),
                branch=str(head_info.get("ref", "")),
            )
            if (
                base_info.get("ref") != settings.staging_github_base_branch
                or base_info.get("repo", {}).get("full_name") != settings.staging_github_repository
            ):
                raise ProviderWriteDeniedError("STAGING_GITHUB_BASE_BRANCH_DENIED")
            files = await self._request_json(
                "GET", f"/repos/{repository_id}/pulls/{pr_number}/files", params={"per_page": 100}
            )
            if (
                not isinstance(files, list)
                or not files
                or len(files) >= 100
                or current.get("changed_files") != len(files)
            ):
                raise ProviderWriteDeniedError("STAGING_GITHUB_FILES_INCOMPLETE")
            for item in files:
                require_github_scope(settings, repository_id, path=str(item.get("filename", "")))
                if item.get("previous_filename"):
                    require_github_scope(
                        settings, repository_id, path=str(item["previous_filename"])
                    )
        head = current.get("head")
        head_sha = str(head.get("sha") or "") if isinstance(head, dict) else ""
        if head_sha != expected_head_sha:
            raise RuntimeError("approved content pull request head has changed")
        if bool(current.get("merged")):
            merge_sha = str(current.get("merge_commit_sha") or "")
            if merge_sha:
                return merge_sha
        payload = await self._request(
            "PUT",
            f"/repos/{repository_id}/pulls/{pr_number}/merge",
            expected_status=200,
            json={"merge_method": "squash", "sha": expected_head_sha},
        )
        if not bool(payload.get("merged")):
            raise RuntimeError(str(payload.get("message") or "GitHub pull request was not merged"))
        merge_sha = str(payload.get("sha") or "")
        if not merge_sha:
            raise RuntimeError("GitHub merge response did not contain a commit SHA")
        return merge_sha

    async def deployment(self, repository_id: str, revision_id: str) -> dict[str, str]:
        deployments: list[dict[str, Any]] = []
        for page_number in range(1, MAX_GITHUB_PAGES + 1):
            payload = await self._request_json(
                "GET",
                f"/repos/{repository_id}/deployments",
                params={
                    "sha": revision_id,
                    "page": page_number,
                    "per_page": GITHUB_PAGE_SIZE,
                },
            )
            if not isinstance(payload, list) or not all(
                isinstance(deployment, dict) for deployment in payload
            ):
                raise RuntimeError("invalid GitHub deployments page")
            page_deployments = list(payload)
            deployments.extend(page_deployments)
            if len(page_deployments) < GITHUB_PAGE_SIZE:
                break
        else:
            raise RuntimeError("GitHub deployment pagination exceeded safety limit")

        production = [
            deployment
            for deployment in deployments
            if str(deployment.get("environment") or "").lower() == "production"
        ]
        if not production:
            status_payload = await self._request(
                "GET", f"/repos/{repository_id}/commits/{revision_id}/status"
            )
            raw_statuses = status_payload.get("statuses", [])
            if not isinstance(raw_statuses, list) or not all(
                isinstance(status, dict) for status in raw_statuses
            ):
                raise RuntimeError("invalid GitHub commit statuses response")
            vercel_failures = [
                status
                for status in raw_statuses
                if str(status.get("context") or "").strip().lower() == "vercel"
                and str(status.get("state") or "").lower() in {"failure", "error"}
            ]
            if vercel_failures:
                target_url = str(vercel_failures[0].get("target_url") or "")
                return {"state": "failure", "url": target_url}
            return {"state": "none", "url": ""}
        deployment_id = production[0].get("id")
        if deployment_id is None:
            raise RuntimeError("GitHub deployment did not contain an id")
        statuses = await self._request_json(
            "GET",
            f"/repos/{repository_id}/deployments/{deployment_id}/statuses",
            params={"per_page": 1},
        )
        if not isinstance(statuses, list) or not statuses:
            return {"state": "pending", "url": ""}
        latest = statuses[0]
        if not isinstance(latest, dict):
            raise RuntimeError("invalid GitHub deployment status")
        state = str(latest.get("state") or "pending").lower()
        url = str(latest.get("environment_url") or latest.get("target_url") or "")
        if state in {"success", "active"} and not url.startswith("https://"):
            return {"state": "pending", "url": ""}
        return {"state": state, "url": url}
