"""Provider selection at existing service/handler construction seams."""

from apps.api.app.config import Settings
from apps.api.app.products.analytics.adapter import (
    GoogleAnalyticsAdapter,
    GoogleAnalyticsAdminAdapter,
)
from apps.api.app.products.gbp.adapter import (
    GBPAdapter,
    GBPPerformanceAdapter,
    GoogleBusinessProfileAdapter,
)
from apps.api.app.products.seo.search_console_adapter import (
    GoogleSearchConsoleAdapter,
    SearchConsoleAdapter,
)


def search_console_adapter() -> SearchConsoleAdapter:
    if Settings().google_provider_mode == "fixture":
        from apps.api.app.staging.provider_fixtures import FixtureSearchConsoleAdapter

        return FixtureSearchConsoleAdapter()
    return GoogleSearchConsoleAdapter()


def analytics_adapter() -> GoogleAnalyticsAdapter:
    if Settings().google_provider_mode == "fixture":
        from apps.api.app.staging.provider_fixtures import FixtureAnalyticsAdapter

        return FixtureAnalyticsAdapter()
    return GoogleAnalyticsAdminAdapter()


def gbp_adapter() -> GBPAdapter:
    if Settings().google_provider_mode == "fixture":
        from apps.api.app.staging.provider_fixtures import FixtureGBPAdapter

        return FixtureGBPAdapter()
    return GoogleBusinessProfileAdapter()


def gbp_performance_adapter() -> GBPPerformanceAdapter:
    """The Performance API shares the Business Profile transport and its provider-mode switch."""
    if Settings().google_provider_mode == "fixture":
        from apps.api.app.staging.provider_fixtures import FixtureGBPAdapter

        return FixtureGBPAdapter()
    return GoogleBusinessProfileAdapter()
