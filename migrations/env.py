"""Alembic environment using the application's async PostgreSQL configuration."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from apps.api.app.access_control.models import (
    MembershipPermissionDeny,
    MembershipRoleAssignment,
    OrganizationInvitation,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
)
from apps.api.app.administration.models import (
    BusinessFactRevision,
    ConfigurationDefinition,
    ConfigurationRevision,
    FeatureFlagRevision,
    OffboardingPlan,
    OffboardingStep,
    OnboardingChecklistItem,
    PolicyRevision,
    Product,
    ProductEntitlement,
    ProductEntitlementLocation,
    RuntimeControlRevision,
    ServiceAssignment,
    ServiceDefinition,
)
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import Settings
from apps.api.app.execution.models import (
    IdempotencyRecord,
    Job,
    JobAttempt,
    Schedule,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
    WorkflowVersion,
)
from apps.api.app.industries.models import Industry
from apps.api.app.insights.models import (
    InsightAnnotation,
    InsightGoal,
    InsightRecord,
    InsightSource,
    MetricDefinition,
    MetricObservation,
    ReportDefinition,
    ReportDelivery,
    ReportRevision,
)
from apps.api.app.integrations.models import (
    IntegrationConnection,
    OAuthAuthorizationIntent,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.location_groups.models import LocationGroup, LocationGroupMembership
from apps.api.app.locations.models import Location
from apps.api.app.notifications.models import (
    NotificationDelivery,
    NotificationDeliveryAttempt,
    NotificationEvent,
    NotificationPreference,
    NotificationTemplate,
)
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)
from apps.api.app.products.gbp.models import (
    GBPAccount,
    GBPLocation,
    GBPProfileChangeRevision,
    GBPProfileSnapshot,
    GBPPublication,
)
from apps.api.app.products.gbp.operations_models import (
    GBPCapabilitySnapshot,
    GBPCategory,
    GBPChangeSet,
    GBPMedia,
    GBPPostPublication,
    GBPPostRevision,
    GBPSpecialHours,
    GBPSuspensionCase,
)
from apps.api.app.products.leads.models import (
    CRMLeadMapping,
    Lead,
    LeadCommunication,
    LeadConsent,
    LeadSource,
    LeadStatusHistory,
    LeadSubmission,
    LeadSuppression,
)
from apps.api.app.products.reviews.models import (
    Review,
    ReviewEscalation,
    ReviewResponseRevision,
    ReviewRevision,
    ReviewRiskFlag,
)
from apps.api.app.products.seo.models import (
    SEOCrawlRun,
    SEOImplementationTask,
    SEOOpportunity,
    SEOOutcome,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile
from apps.api.app.synchronization.models import (
    ProviderStateSnapshot,
    SyncChangeIntent,
    SyncCheckpoint,
    SyncConflict,
    SyncDefinition,
    SyncRun,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Organization.metadata
assert AuditEvent.metadata is target_metadata
assert Location.metadata is target_metadata
assert Industry.metadata is target_metadata
assert LocationGroup.metadata is target_metadata
assert LocationGroupMembership.metadata is target_metadata
assert OrganizationProfile.metadata is target_metadata
assert LocationProfile.metadata is target_metadata
assert UserProfile.metadata is target_metadata
assert OrganizationMembership.metadata is target_metadata
assert OrganizationInvitation.metadata is target_metadata
assert Role.metadata is target_metadata
assert Permission.metadata is target_metadata
assert RolePermission.metadata is target_metadata
assert MembershipRoleAssignment.metadata is target_metadata
assert MembershipPermissionDeny.metadata is target_metadata
for phase4_model in (
    ServiceDefinition,
    ServiceAssignment,
    BusinessFactRevision,
    Product,
    ProductEntitlement,
    ProductEntitlementLocation,
    ConfigurationDefinition,
    ConfigurationRevision,
    PolicyRevision,
    FeatureFlagRevision,
    RuntimeControlRevision,
    OnboardingChecklistItem,
    OffboardingPlan,
    OffboardingStep,
):
    assert phase4_model.metadata is target_metadata
for execution_model in (
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowRun,
    WorkflowStep,
    Job,
    JobAttempt,
    Schedule,
    IdempotencyRecord,
):
    assert execution_model.metadata is target_metadata
for notification_model in (
    NotificationTemplate,
    NotificationEvent,
    NotificationDelivery,
    NotificationDeliveryAttempt,
    NotificationPreference,
):
    assert notification_model.metadata is target_metadata
for integration_model in (
    Provider,
    IntegrationConnection,
    OAuthAuthorizationIntent,
    ProviderResourceMapping,
):
    assert integration_model.metadata is target_metadata
for sync_model in (
    SyncDefinition,
    SyncRun,
    SyncCheckpoint,
    ProviderStateSnapshot,
    SyncChangeIntent,
    SyncConflict,
):
    assert sync_model.metadata is target_metadata
for seo_model in (
    SEOWebsite,
    SEOSearchProperty,
    SEOPage,
    SEOCrawlRun,
    SEOSearchObservation,
    SEOOpportunity,
    SEORecommendationRevision,
    SEOImplementationTask,
    SEOOutcome,
):
    assert seo_model.metadata is target_metadata
for gbp_operation_model in (
    GBPCapabilitySnapshot,
    GBPCategory,
    GBPChangeSet,
    GBPSpecialHours,
    GBPMedia,
    GBPPostRevision,
    GBPPostPublication,
    GBPSuspensionCase,
):
    assert gbp_operation_model.metadata is target_metadata
for insight_model in (
    InsightSource,
    MetricDefinition,
    MetricObservation,
    InsightGoal,
    InsightAnnotation,
    ReportDefinition,
    ReportRevision,
    ReportDelivery,
    InsightRecord,
):
    assert insight_model.metadata is target_metadata
for gbp_model in (
    GBPAccount,
    GBPLocation,
    GBPProfileSnapshot,
    GBPProfileChangeRevision,
    GBPPublication,
):
    assert gbp_model.metadata is target_metadata
for reviews_model in (
    AITaskDefinition,
    AIExecution,
    Review,
    ReviewRevision,
    ReviewRiskFlag,
    ReviewResponseRevision,
    ReviewEscalation,
):
    assert reviews_model.metadata is target_metadata
for leads_model in (
    LeadSource,
    Lead,
    LeadSubmission,
    LeadConsent,
    LeadSuppression,
    LeadStatusHistory,
    LeadCommunication,
    CRMLeadMapping,
):
    assert leads_model.metadata is target_metadata
for content_model in (
    ContentOpportunity,
    PublishingTarget,
    ContentItem,
    ContentBrief,
    ContentRevision,
    ContentPublication,
):
    assert content_model.metadata is target_metadata


def configured_database_url() -> str:
    """Resolve a migration URL without exposing it in errors or logs."""
    database_url = Settings().alembic_database_url()
    if database_url is None:
        raise RuntimeError(
            "Database migrations require LILOS_MIGRATION_DATABASE_URL or LILOS_DATABASE_URL"
        )
    return database_url


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""
    context.configure(
        url=configured_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migration operations on a synchronous connection adapter."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a short-lived async engine and execute migrations."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = configured_database_url().replace("%", "%%")
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"timeout": Settings().database_connect_timeout_seconds},
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations through SQLAlchemy's asyncpg dialect."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
