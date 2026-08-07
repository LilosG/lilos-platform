"""Controlled GitHub/Astro repository adapter contract."""

from pathlib import PurePosixPath
from typing import Protocol


class RepositoryPublisher(Protocol):
    async def get_base_commit(self, repository_id: str, base_branch: str) -> str: ...
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
    async def checks(self, repository_id: str, revision_id: str) -> dict[str, str]: ...
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
