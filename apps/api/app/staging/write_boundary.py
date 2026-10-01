"""Small provider-specific extension of the existing global write switch."""

import re
from pathlib import PurePosixPath
from urllib.parse import unquote

from apps.api.app.config import EnvironmentName, Settings


class ProviderWriteDeniedError(ValueError):
    """A provider mutation is outside this environment's authorized scope."""


def require_google_write(settings: Settings) -> None:
    if settings.environment is EnvironmentName.STAGING or not settings.provider_writes_enabled:
        raise ProviderWriteDeniedError("GOOGLE_WRITES_DISABLED")


def require_github_scope(
    settings: Settings,
    repository: str,
    *,
    installation: str | None = None,
    path: str | None = None,
    branch: str | None = None,
) -> None:
    if settings.environment is not EnvironmentName.STAGING:
        return
    if not settings.provider_writes_enabled:
        raise ProviderWriteDeniedError("PROVIDER_WRITES_DISABLED")
    if not settings.staging_github_repository or repository != settings.staging_github_repository:
        raise ProviderWriteDeniedError("STAGING_GITHUB_REPOSITORY_DENIED")
    if installation is not None and installation != settings.staging_github_installation_id:
        raise ProviderWriteDeniedError("STAGING_GITHUB_INSTALLATION_DENIED")
    if path is not None:
        prefix = settings.staging_github_path_prefix
        if (
            not prefix
            or not path.startswith(prefix)
            or unquote(path) != path
            or any(character in path for character in ("\\", "?", "#"))
            or path.startswith("/")
            or any(part in {".", "..", ""} for part in path.split("/"))
            or str(PurePosixPath(path)) != path
        ):
            raise ProviderWriteDeniedError("STAGING_GITHUB_PATH_DENIED")
    if branch is not None and (
        not re.fullmatch(r"lilos-(?:content|site-change)-[0-9a-f-]{36}", branch)
        or ".." in branch
        or "//" in branch
        or branch.endswith("/")
    ):
        raise ProviderWriteDeniedError("STAGING_GITHUB_BRANCH_DENIED")
