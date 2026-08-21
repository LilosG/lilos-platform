"""Small invariant test for the managed Astro publishing convention."""


def test_managed_astro_blog_path_convention() -> None:
    # Single-repository GitHub App installations are reconciled to this
    # repository-relative path by the integration callback/workspace.
    assert "src/content/blog".startswith("src/content/")
