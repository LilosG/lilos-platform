"""Controlled GitHub/Astro repository adapter contract."""

from pathlib import PurePosixPath
from typing import Protocol

# `deployment()` reports this state when the host refused to build the merged commit because
# of its own build quota. The change itself is fine, so it is not a deployment failure.
DEPLOYMENT_RATE_LIMITED = "rate_limited"
# The host marks that refusal in the commit status link; the prose description is not read.
VERCEL_BUILD_RATE_LIMIT_MARKER = "build-rate-limit"


class RepositoryPublisher(Protocol):
    async def get_base_commit(self, repository_id: str, base_branch: str) -> str: ...
    async def get_file(self, repository_id: str, ref: str, path: str) -> str | None: ...
    async def create_branch(
        self, repository_id: str, base_branch: str, base_commit: str, branch_name: str
    ) -> str: ...
    async def put_file(
        self,
        repository_id: str,
        branch_name: str,
        path: str,
        content: str,
        expected_blob_sha: str | None,
    ) -> str: ...
    async def create_pull_request(
        self,
        repository_id: str,
        branch_name: str,
        base_branch: str,
        title: str,
        idempotency_key: str,
    ) -> str: ...
    async def get_pull_request(self, repository_id: str, pr_number: str) -> dict[str, object]: ...
    async def checks(self, repository_id: str, revision_id: str) -> dict[str, str]:
        """`state` plus the `gate` that produced it: repository_ci, vercel_preview or none."""
        ...

    async def merge_pull_request(
        self, repository_id: str, pr_number: str, expected_head_sha: str
    ) -> str: ...
    async def deployment(self, repository_id: str, revision_id: str) -> dict[str, str]: ...


def validate_target_path(path: str, allowed_prefix: str) -> str:
    candidate = PurePosixPath(path)
    prefix = PurePosixPath(allowed_prefix)
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or not str(candidate).startswith(f"{prefix}/")
        or candidate.suffix not in {".md", ".mdx", ".astro"}
    ):
        raise ValueError("publishing target path is not allowed")
    if any(part in {".git", ".github", "node_modules"} for part in candidate.parts):
        raise ValueError("restricted repository path")
    return str(candidate)
