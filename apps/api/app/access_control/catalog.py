"""Explicit deterministic immutable role and permission catalog seed."""

from dataclasses import dataclass, field
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.errors import CatalogConflictError
from apps.api.app.access_control.models import Permission, Role, RolePermission
from apps.api.app.access_control.repository import CatalogRepository
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService

CATALOG_NAMESPACE = UUID("c867a620-90ab-5caa-8fe8-bf6ce56e0617")

ROLE_CATALOG: dict[str, tuple[str, str]] = {
    "organization_owner": (
        "Organization Owner",
        "Complete initial organization permission catalog.",
    ),
    "organization_admin": (
        "Organization Admin",
        "Administrative access excluding role management.",
    ),
    "organization_manager": (
        "Organization Manager",
        "Operational organization and location management.",
    ),
    "organization_member": ("Organization Member", "Standard read access to organization context."),
    "organization_viewer": ("Organization Viewer", "Read-only organization context."),
}

PERMISSION_CATALOG: dict[str, tuple[str, str, str, str]] = {
    "organization.read": (
        "Read organization",
        "Read organization records.",
        "organization",
        "read",
    ),
    "organization.update": (
        "Update organization",
        "Update approved organization fields.",
        "organization",
        "update",
    ),
    "organization.members.manage": (
        "Manage members",
        "Administer organization memberships.",
        "organization_members",
        "manage",
    ),
    "organization.invitations.manage": (
        "Manage invitations",
        "Administer organization invitations.",
        "organization_invitations",
        "manage",
    ),
    "organization.roles.manage": (
        "Manage roles",
        "Administer organization role assignments.",
        "organization_roles",
        "manage",
    ),
    "organization.settings.manage": (
        "Manage settings",
        "Administer organization settings.",
        "organization_settings",
        "manage",
    ),
    "locations.read": ("Read locations", "Read organization locations.", "locations", "read"),
    "locations.create": (
        "Create locations",
        "Create organization locations.",
        "locations",
        "create",
    ),
    "locations.update": (
        "Update locations",
        "Update organization locations.",
        "locations",
        "update",
    ),
    "locations.lifecycle.manage": (
        "Manage location lifecycle",
        "Administer location lifecycle.",
        "location_lifecycle",
        "manage",
    ),
    "locations.groups.manage": (
        "Manage location groups",
        "Administer location groups.",
        "location_groups",
        "manage",
    ),
    "profiles.read": ("Read profiles", "Read controlled business profiles.", "profiles", "read"),
    "profiles.update": (
        "Update profiles",
        "Update controlled business profiles.",
        "profiles",
        "update",
    ),
    "business_identity.read": (
        "Read business identity",
        "Read resolved business identity.",
        "business_identity",
        "read",
    ),
    "audit.read": ("Read audit", "Read authorized audit records.", "audit", "read"),
    "services.read": (
        "Read services",
        "Read governed service catalog and assignments.",
        "services",
        "read",
    ),
    "services.manage": (
        "Manage services",
        "Administer governed services and assignments.",
        "services",
        "manage",
    ),
    "business_facts.read": (
        "Read business facts",
        "Read governed business facts.",
        "business_facts",
        "read",
    ),
    "business_facts.propose": (
        "Propose business facts",
        "Create governed fact proposals.",
        "business_facts",
        "propose",
    ),
    "business_facts.approve": (
        "Approve business facts",
        "Approve or reject governed facts.",
        "business_facts",
        "approve",
    ),
    "products.read": (
        "Read products",
        "Read product registry, entitlement, and readiness state.",
        "products",
        "read",
    ),
    "products.entitlements.manage": (
        "Manage entitlements",
        "Administer product entitlements.",
        "product_entitlements",
        "manage",
    ),
    "configuration.read": (
        "Read configuration",
        "Read effective governed configuration.",
        "configuration",
        "read",
    ),
    "configuration.manage": (
        "Manage configuration",
        "Create and activate configuration revisions.",
        "configuration",
        "manage",
    ),
    "policies.read": ("Read policies", "Read governed effective policies.", "policies", "read"),
    "policies.manage": (
        "Manage policies",
        "Create and activate policy revisions.",
        "policies",
        "manage",
    ),
    "feature_flags.read": (
        "Read feature flags",
        "Read resolved feature flags.",
        "feature_flags",
        "read",
    ),
    "feature_flags.manage": (
        "Manage feature flags",
        "Create governed feature-flag revisions.",
        "feature_flags",
        "manage",
    ),
    "runtime_controls.read": (
        "Read runtime controls",
        "Read resolved runtime controls.",
        "runtime_controls",
        "read",
    ),
    "runtime_controls.manage": (
        "Manage runtime controls",
        "Create restrictive runtime controls.",
        "runtime_controls",
        "manage",
    ),
    "onboarding.read": (
        "Read onboarding",
        "Read onboarding readiness and blockers.",
        "onboarding",
        "read",
    ),
    "onboarding.manage": (
        "Manage onboarding",
        "Administer onboarding requirements.",
        "onboarding",
        "manage",
    ),
    "offboarding.read": (
        "Read offboarding",
        "Read offboarding plans and blockers.",
        "offboarding",
        "read",
    ),
    "offboarding.manage": (
        "Manage offboarding",
        "Administer controlled offboarding plans.",
        "offboarding",
        "manage",
    ),
    "workflows.read": ("Read workflows", "Read workflow and job state.", "workflows", "read"),
    "workflows.execute": (
        "Execute workflows",
        "Submit governed workflows.",
        "workflows",
        "execute",
    ),
    "workflows.manage": ("Manage workflows", "Cancel or replay workflows.", "workflows", "manage"),
    "schedules.read": ("Read schedules", "Read workflow schedules.", "schedules", "read"),
    "schedules.manage": (
        "Manage schedules",
        "Administer workflow schedules.",
        "schedules",
        "manage",
    ),
    "notifications.read": (
        "Read notifications",
        "Read notification delivery status.",
        "notifications",
        "read",
    ),
    "notifications.manage": (
        "Manage notifications",
        "Administer notification definitions and preferences.",
        "notifications",
        "manage",
    ),
    "notifications.send": (
        "Send notifications",
        "Persist governed notification intent.",
        "notifications",
        "send",
    ),
    "integrations.read": (
        "Read integrations",
        "Read provider connection health.",
        "integrations",
        "read",
    ),
    "integrations.connect": (
        "Connect integrations",
        "Establish provider connections.",
        "integrations",
        "connect",
    ),
    "integrations.manage": (
        "Manage integrations",
        "Reconnect or disconnect providers.",
        "integrations",
        "manage",
    ),
    "synchronization.read": (
        "Read synchronization",
        "Read synchronization state and conflicts.",
        "synchronization",
        "read",
    ),
    "synchronization.execute": (
        "Execute synchronization",
        "Persist governed synchronization intent.",
        "synchronization",
        "execute",
    ),
    "synchronization.manage": (
        "Manage synchronization",
        "Resolve or retry synchronization.",
        "synchronization",
        "manage",
    ),
    "gbp.read": ("Read GBP", "Read mapped GBP profile state.", "gbp", "read"),
    "gbp.connect": ("Connect GBP", "Confirm GBP location mappings.", "gbp", "connect"),
    "gbp.sync": ("Synchronize GBP", "Run governed GBP synchronization.", "gbp", "sync"),
    "gbp.propose": ("Propose GBP change", "Create grounded GBP profile changes.", "gbp", "propose"),
    "gbp.approve": (
        "Approve GBP change",
        "Approve current GBP profile revisions.",
        "gbp",
        "approve",
    ),
    "gbp.publish": ("Publish GBP change", "Dispatch approved GBP changes.", "gbp", "publish"),
    "gbp.diagnostics": (
        "Read GBP diagnostics",
        "Read GBP operational diagnostics.",
        "gbp",
        "diagnostics",
    ),
    "reviews.read": ("Read reviews", "Read organization review operations.", "reviews", "read"),
    "reviews.generate_response": (
        "Draft review response",
        "Create grounded response revisions.",
        "reviews",
        "generate_response",
    ),
    "reviews.approve_response": (
        "Approve review response",
        "Approve current response revisions.",
        "reviews",
        "approve_response",
    ),
    "reviews.publish_response": (
        "Publish review response",
        "Dispatch approved responses.",
        "reviews",
        "publish_response",
    ),
    "reviews.escalate": (
        "Escalate review",
        "Manage restricted review cases.",
        "reviews",
        "escalate",
    ),
    "leads.read": ("Read leads", "Read authorized lead records.", "leads", "read"),
    "leads.respond": (
        "Respond to leads",
        "Plan consent-eligible lead communication.",
        "leads",
        "respond",
    ),
    "leads.assign": ("Assign leads", "Route and assign leads.", "leads", "assign"),
    "leads.manage_sources": (
        "Manage lead sources",
        "Administer verified lead intake sources.",
        "leads",
        "manage_sources",
    ),
    "leads.manage_consent": (
        "Manage lead consent",
        "Record consent and suppression evidence.",
        "leads",
        "manage_consent",
    ),
}

ALL_PERMISSIONS = frozenset(PERMISSION_CATALOG)
ROLE_MAPPINGS: dict[str, frozenset[str]] = {
    "organization_owner": ALL_PERMISSIONS,
    "organization_admin": ALL_PERMISSIONS - {"organization.roles.manage"},
    "organization_manager": frozenset(
        {
            "organization.read",
            "organization.members.manage",
            "organization.invitations.manage",
            "locations.read",
            "locations.create",
            "locations.update",
            "locations.lifecycle.manage",
            "locations.groups.manage",
            "profiles.read",
            "profiles.update",
            "business_identity.read",
            "audit.read",
            "services.read",
            "services.manage",
            "business_facts.read",
            "business_facts.propose",
            "products.read",
            "configuration.read",
            "configuration.manage",
            "policies.read",
            "feature_flags.read",
            "onboarding.read",
            "onboarding.manage",
            "workflows.read",
            "workflows.execute",
            "schedules.read",
            "notifications.read",
            "notifications.manage",
            "notifications.send",
            "integrations.read",
            "integrations.connect",
            "synchronization.read",
            "synchronization.execute",
            "gbp.read",
            "gbp.connect",
            "gbp.sync",
            "gbp.propose",
            "gbp.diagnostics",
            "reviews.read",
            "reviews.generate_response",
            "reviews.escalate",
            "leads.read",
            "leads.respond",
            "leads.assign",
        }
    ),
    "organization_member": frozenset(
        {
            "organization.read",
            "locations.read",
            "profiles.read",
            "business_identity.read",
            "services.read",
            "business_facts.read",
            "products.read",
            "configuration.read",
            "policies.read",
            "feature_flags.read",
            "onboarding.read",
            "workflows.read",
            "schedules.read",
            "notifications.read",
            "integrations.read",
            "synchronization.read",
            "gbp.read",
            "reviews.read",
            "leads.read",
        }
    ),
    "organization_viewer": frozenset(
        {
            "organization.read",
            "locations.read",
            "profiles.read",
            "business_identity.read",
            "services.read",
            "business_facts.read",
            "products.read",
            "configuration.read",
            "policies.read",
            "feature_flags.read",
            "onboarding.read",
            "workflows.read",
            "schedules.read",
            "notifications.read",
            "integrations.read",
            "synchronization.read",
            "gbp.read",
            "reviews.read",
            "leads.read",
        }
    ),
}


def catalog_id(kind: str, key: str) -> UUID:
    return uuid5(CATALOG_NAMESPACE, f"{kind}:{key}")


@dataclass(frozen=True, slots=True)
class CatalogSeedResult:
    roles_created: int
    permissions_created: int
    mappings_created: int


@dataclass(frozen=True, slots=True)
class AccessCatalogSeeder:
    repository: CatalogRepository = field(default_factory=CatalogRepository)
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def seed(self, session: AsyncSession, *, correlation_id: str) -> CatalogSeedResult:
        existing_roles = {item.key: item for item in await self.repository.list_roles(session)}
        existing_permissions = {
            item.key: item for item in await self.repository.list_permissions(session)
        }
        if set(existing_roles) - set(ROLE_CATALOG) or set(existing_permissions) - set(
            PERMISSION_CATALOG
        ):
            raise CatalogConflictError
        roles_created = permissions_created = mappings_created = 0
        for key, (name, description) in ROLE_CATALOG.items():
            role_item = existing_roles.get(key)
            expected_id = catalog_id("role", key)
            if role_item is None:
                role_item = Role(
                    id=expected_id,
                    key=key,
                    name=name,
                    description=description,
                    status="active",
                    is_system=True,
                    version=1,
                )
                await self.repository.seed_add(session, role_item)
                existing_roles[key] = role_item
                roles_created += 1
            elif (
                role_item.id,
                role_item.name,
                role_item.description,
                role_item.status.value,
                role_item.is_system,
                role_item.version,
            ) != (expected_id, name, description, "active", True, 1):
                raise CatalogConflictError
        for key, (name, description, resource, action) in PERMISSION_CATALOG.items():
            permission_item = existing_permissions.get(key)
            expected_id = catalog_id("permission", key)
            if permission_item is None:
                permission_item = Permission(
                    id=expected_id,
                    key=key,
                    name=name,
                    description=description,
                    resource=resource,
                    action=action,
                )
                await self.repository.seed_add(session, permission_item)
                existing_permissions[key] = permission_item
                permissions_created += 1
            elif (
                permission_item.id,
                permission_item.name,
                permission_item.description,
                permission_item.resource,
                permission_item.action,
            ) != (expected_id, name, description, resource, action):
                raise CatalogConflictError
        expected_pairs = {
            (existing_roles[role].id, existing_permissions[permission].id)
            for role, permissions in ROLE_MAPPINGS.items()
            for permission in permissions
        }
        existing_pairs = await self.repository.list_mapping_pairs(session)
        if existing_pairs - expected_pairs:
            raise CatalogConflictError
        missing = expected_pairs - existing_pairs
        if missing:
            await self.repository.seed_add(
                session,
                *(
                    RolePermission(role_id=role_id, permission_id=permission_id)
                    for role_id, permission_id in sorted(
                        missing, key=lambda item: (str(item[0]), str(item[1]))
                    )
                ),
            )
            mappings_created = len(missing)
        for event_type, action, count in (
            ("platform.role_catalog.seeded", "role_catalog.seed", roles_created),
            ("platform.permission_catalog.seeded", "permission_catalog.seed", permissions_created),
            (
                "platform.role_permission_catalog.seeded",
                "role_permission_catalog.seed",
                mappings_created,
            ),
        ):
            if count:
                await self.audit.record(
                    session,
                    AuditEventCreate(
                        event_type=event_type,
                        action=action,
                        result=AuditResult.SUCCEEDED,
                        actor_type=AuditActorType.SYSTEM,
                        product_key="platform",
                        resource_type="access_catalog",
                        correlation_id=correlation_id,
                        summary="Immutable access catalog records seeded.",
                        metadata={"operation": "seeded", "records_created": count},
                    ),
                )
        return CatalogSeedResult(roles_created, permissions_created, mappings_created)
