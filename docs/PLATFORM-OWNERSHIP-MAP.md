# LILOs Platform Ownership Map

**Created:** 2026-08-11
**Purpose:** Define exact module ownership, shared contracts, and concurrency boundaries for the Platform Consolidation release.

## Authority

This map derives from repository inspection at SHA `35cf577` (branch `release/platform-consolidation`), the Master Spec, and the Platform Consolidation contract. It is binding on all specialist workstreams.

## Ownership domains

### 1. Principal Release Integrator (cross-cutting)

**Owns:**
- `docs/PLATFORM-OWNERSHIP-MAP.md` (this file)
- `docs/PLATFORM-PACKET-PLAN.md`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/PLATFORM-CONSOLIDATION-RELEASE.md` (clarifications only)
- `AGENTS.md`
- `.opencode/agents/` (all agent definitions)
- `opencode.json`
- `prompts/` (all packet prompts)
- `scripts/create-release-worktrees.sh`
- Release gate orchestration (`scripts/release_gate.py`, `scripts/production_preflight.py`)
- Integration/merge decisions for all specialist branches
- Final release acceptance

**Shared contracts owned by principal (frozen before parallel work):**
- `apps/web/src/lib/platform.ts` — navigation groups, readiness labels
- `apps/web/src/lib/workspace.ts` — `InsightsSummary`, `ProductReadiness`, `PRODUCT_KEYS`, `PRODUCT_LABELS` types
- `apps/web/src/lib/dashboard-logic.ts` — `summarizeReadiness`, `selectDefaultOrganization`
- `apps/web/src/lib/operating-dashboard.ts` — `dashboardMetrics`, `requiresAttention`, `todaysWork`
- `apps/web/src/components/AppShell.astro` — layout shell, navigation rendering
- `apps/web/src/components/MetricCard.astro` — shared metric card component
- `apps/web/src/components/StatusBadge.astro` — shared status badge component
- `apps/web/src/components/Card.astro` — shared card component
- `apps/web/src/components/EmptyState.astro` — shared empty state component
- `apps/web/src/components/PageHeader.astro` — shared page header component
- `apps/web/src/lib/ui/` — all shared UI primitives (badge, boot, errors, forms, table, tabs, regions, states, components)
- `apps/web/src/lib/api-client.ts` — base API client
- `apps/web/src/lib/session.ts` — auth session management
- `apps/web/src/lib/supabase-client.ts` — Supabase client initialization
- `apps/web/src/lib/config.ts` — frontend config
- `apps/api/app/administration/service.py` — readiness engine (lines 1661-1880)
- `apps/api/app/administration/contracts.py` — `ProductReadiness`, `ReadinessFinding`
- `apps/api/app/onboarding/service.py` — onboarding orchestration
- `apps/api/app/onboarding/contracts.py` — `OnboardingState`, `OnboardingStep`
- `apps/api/app/insights/aggregation_service.py` — cross-product aggregation
- `apps/api/app/execution/workflow_catalog.py` — `WORKFLOW_TYPES` registry
- `apps/api/app/access_control/catalog.py` — role/permission catalog
- `apps/api/app/authorization/dependencies.py` — `require_authorization`
- `apps/api/app/authorization/service.py` — `AuthorizationService`
- `apps/api/app/routes/api_v1.py` — main authenticated API router
- `apps/api/app/main.py` — FastAPI app assembly, router registration
- `apps/api/app/config.py` — environment configuration
- `apps/api/app/database/` — database foundation (base, session, runtime, health)
- `apps/api/app/schemas.py` — shared API contracts
- `apps/api/app/errors.py` — error handling
- `apps/api/app/middleware.py` — correlation ID middleware
- `apps/api/app/context.py` — request context
- `migrations/env.py` — Alembic environment
- `infrastructure/` — Docker, Render blueprints, release contract
- `scripts/check_secrets.py`, `scripts/validate_render_blueprint.py`, `scripts/verify_runtime_heartbeats.py`
- `scripts/provision_gbp_entitlement.py`, `scripts/provision_pilot_owner.py`, `scripts/provision_platform_administrator.py`
- `scripts/seed_access_catalog.py`, `scripts/seed_administration_catalog.py`, `scripts/seed_industries.py`
- `scripts/render_predeploy.sh`, `scripts/render_start_api.sh`, `scripts/render_start_scheduler.sh`, `scripts/render_start_worker.sh`
- `scripts/verify_restored_database.py`
- `package.json`, `pyproject.toml`, `alembic.ini` — root configuration
- `.github/workflows/ci.yml` — CI pipeline
- `apps/api/app/organizations/` — organization domain (models, service, repository, contracts, enums, errors)
- `apps/api/app/locations/` — location domain (models, service, repository, contracts, enums, errors)
- `apps/api/app/profiles/` — organization/location profiles (models, service, repository, contracts, errors, validation)
- `apps/api/app/location_groups/` — location groups (models, service, repository, contracts, enums, errors)
- `apps/api/app/domains/` — organization domains (models, service, repository, contracts, enums, errors)
- `apps/api/app/industries/` — industry catalog (models, service, repository, contracts, enums, errors, seed, policy_documents)
- `apps/api/app/business_identity/` — business identity service (contracts, service)
- `apps/api/app/platform_admin/` — platform administration (models, service, repository, contracts, dependencies)
- `apps/api/app/authentication/` — auth service (models, service, repository, contracts, enums, errors, verifier, dependencies)
- `apps/api/app/audit/` — audit service (models, service, repository, contracts, enums, metadata)
- `apps/api/app/notifications/` — notification service (models, service)
- `apps/api/app/observability/` — observability (models, telemetry, operations)
- `apps/api/app/ai/` — AI gateway (models, gateway)
- `apps/api/app/routes/health.py` — health endpoints
- `apps/api/app/routes/platform_administration.py` — platform admin routes
- `apps/api/app/routes/internal_*.py` — internal admin routes (all 8 files)
- `apps/web/src/pages/index.astro` — agency/client dashboard
- `apps/web/src/pages/settings.astro` — settings page
- `apps/web/src/pages/administration.astro` — administration page
- `apps/web/src/pages/onboarding.astro` — onboarding page
- `apps/web/src/pages/login.astro` — login page
- `apps/web/src/pages/mfa.astro` — MFA page
- `apps/web/src/lib/platform-admin.ts` — platform admin client
- `apps/web/src/lib/administration.ts` — administration client
- `apps/web/src/lib/product-entitlements.ts` — product entitlements client
- `apps/web/src/lib/boot-boundary.ts` — boot boundary
- `apps/web/src/lib/settings.ts` — settings client
- `tests/` — test infrastructure (conftest, fixtures); each specialist owns their domain tests

### 2. Integrations Specialist

**Owns:**
- `apps/api/app/integrations/` — all files (connection_service, contracts, errors, models, provider_seed, secrets, service)
- `apps/api/app/routes/integrations.py` — integration routes
- `apps/api/app/routes/github_app.py` — GitHub App routes
- `apps/api/app/products/gbp/discovery_service.py` — GBP discovery
- `apps/api/app/products/gbp/adapter.py` — GBP Google API adapter
- `apps/api/app/products/seo/search_console_adapter.py` — Search Console adapter
- `apps/api/app/products/seo/search_console_service.py` — Search Console service
- `apps/api/app/products/analytics/adapter.py` — GA4 adapter
- `apps/api/app/products/analytics/service.py` — GA4 service
- `apps/api/app/products/content/github_adapter.py` — GitHub adapter
- `apps/api/app/products/content/github_app_service.py` — GitHub App service
- `apps/api/app/synchronization/` — all files
- `apps/web/src/lib/gbp-connection.ts` — GBP connection client
- `apps/web/src/lib/github-app.ts` — GitHub App client
- `apps/web/src/lib/search-console.ts` — Search Console client
- `apps/web/src/lib/analytics.ts` — Analytics client
- `apps/web/src/pages/integrations.astro` — Integrations page
- `migrations/versions/20260803_0004_integrations.py`
- `migrations/versions/20260803_0005_synchronization.py`
- `migrations/versions/20260805_0001_provider_secrets.py`
- `scripts/seed_integration_providers.py`
- `tests/python/integrations/` — integration tests
- `tests/python/synchronization/` — synchronization tests
- `tests/python/gbp/test_adapter.py`, `tests/python/gbp/test_discovery_service.py` — GBP adapter/discovery tests
- `tests/python/seo/test_search_console.py` — Search Console tests
- `tests/python/content/test_github_adapter.py` — GitHub adapter tests

**Shared contracts consumed (read-only):**
- `apps/api/app/administration/service.py` — `_integration_connected()` (line 1882)
- `apps/api/app/execution/workflow_catalog.py` — `WORKFLOW_TYPES`
- `apps/api/app/authorization/dependencies.py` — `require_authorization`
- `apps/web/src/lib/api-client.ts` — base API client
- `apps/web/src/lib/workspace.ts` — types

**Must not modify:**
- Any product service outside `integrations/`, `synchronization/`, or product adapter files
- Navigation, dashboard, or readiness contracts
- `apps/web/src/components/` shared components

### 3. Automation & Agents Specialist

**Owns:**
- `apps/api/app/execution/` — all files (handlers, models, runtime, service, workflow_catalog)
- `apps/api/app/routes/workflows.py` — workflow routes
- `apps/worker/` — worker process
- `apps/scheduler/` — scheduler process
- `apps/web/src/lib/workflows.ts` — workflow client
- `migrations/versions/20260803_0002_workflow_execution.py`
- `tests/python/workflows/` — workflow execution tests

**Shared contracts consumed (read-only):**
- `apps/api/app/execution/workflow_catalog.py` — `WORKFLOW_TYPES` (principal-owned)
- `apps/api/app/administration/service.py` — readiness engine
- `apps/api/app/integrations/connection_service.py` — token resolution
- `apps/api/app/authorization/dependencies.py` — `require_authorization`
- Product services for handler implementations (GBP, Reviews, Content, SEO, Leads)

**Must not modify:**
- `WORKFLOW_TYPES` registry without principal approval
- Product service internals
- Navigation or dashboard contracts

### 4. Product UX Specialist

**Owns:**
- `apps/api/app/products/gbp/service.py` — GBP service
- `apps/api/app/products/gbp/operations_service.py` — GBP operations
- `apps/api/app/products/gbp/operations.py` — GBP operations helpers
- `apps/api/app/products/gbp/contracts.py` — GBP contracts
- `apps/api/app/products/gbp/operations_contracts.py` — GBP operations contracts
- `apps/api/app/products/gbp/models.py` — GBP models
- `apps/api/app/products/gbp/operations_models.py` — GBP operations models
- `apps/api/app/products/gbp/resource_names.py` — GBP resource names
- `apps/api/app/products/reviews/` — all files
- `apps/api/app/products/seo/service.py` — SEO service
- `apps/api/app/products/seo/contracts.py` — SEO contracts
- `apps/api/app/products/seo/models.py` — SEO models
- `apps/api/app/products/content/service.py` — Content service
- `apps/api/app/products/content/contracts.py` — Content contracts
- `apps/api/app/products/content/models.py` — Content models
- `apps/api/app/products/content/adapter.py` — Content adapter
- `apps/api/app/products/leads/` — all files
- `apps/api/app/routes/gbp.py` — GBP routes
- `apps/api/app/routes/gbp_operations.py` — GBP operations routes
- `apps/api/app/routes/reviews.py` — Reviews routes
- `apps/api/app/routes/seo.py` — SEO routes
- `apps/api/app/routes/content.py` — Content routes
- `apps/api/app/routes/leads.py` — Leads routes
- `apps/web/src/lib/gbp.ts` — GBP client
- `apps/web/src/lib/gbp-operations.ts` — GBP operations client
- `apps/web/src/lib/reviews.ts` — Reviews client
- `apps/web/src/lib/seo.ts` — SEO client
- `apps/web/src/lib/content.ts` — Content client
- `apps/web/src/lib/leads.ts` — Leads client
- `apps/web/src/pages/gbp.astro` — GBP page
- `apps/web/src/pages/reviews.astro` — Reviews page
- `apps/web/src/pages/seo.astro` — SEO page
- `apps/web/src/pages/content.astro` — Content page
- `apps/web/src/pages/leads.astro` — Leads page
- Product-specific migrations
- `tests/python/gbp/` — GBP tests (except adapter/discovery)
- `tests/python/reviews/` — Reviews tests
- `tests/python/seo/` — SEO tests (except search_console)
- `tests/python/content/` — Content tests (except github_adapter)
- `tests/python/leads/` — Leads tests

**Shared contracts consumed (read-only):**
- `apps/web/src/lib/platform.ts` — navigation, readiness labels
- `apps/web/src/lib/workspace.ts` — types
- `apps/web/src/lib/dashboard-logic.ts` — `summarizeReadiness`
- `apps/web/src/lib/operating-dashboard.ts` — dashboard functions
- `apps/web/src/components/` — shared components
- `apps/web/src/lib/ui/` — shared UI primitives
- `apps/api/app/administration/service.py` — readiness engine
- `apps/api/app/integrations/` — integration services
- `apps/api/app/execution/` — workflow infrastructure
- `apps/api/app/authorization/dependencies.py` — `require_authorization`

**Must not modify:**
- Navigation groups, readiness labels, or dashboard logic
- Shared components or UI primitives
- Integration, workflow, or authorization infrastructure
- `InsightsSummary` type or aggregation service

### 5. Insights & Reporting Specialist

**Owns:**
- `apps/api/app/insights/service.py` — Insights service
- `apps/api/app/insights/models.py` — Insights models
- `apps/api/app/routes/insights.py` — Insights routes
- `apps/web/src/pages/insights.astro` — Insights page
- `migrations/versions/20260803_0012_insights.py`
- `tests/python/insights/` — Insights tests

**Shared contracts consumed (read-only):**
- `apps/api/app/insights/aggregation_service.py` — cross-product aggregation (principal-owned)
- `apps/web/src/lib/workspace.ts` — `InsightsSummary` type (principal-owned)
- `apps/web/src/lib/operating-dashboard.ts` — dashboard functions (principal-owned)
- `apps/web/src/components/` — shared components
- `apps/web/src/lib/ui/` — shared UI primitives
- `apps/api/app/administration/service.py` — readiness engine
- `apps/api/app/authorization/dependencies.py` — `require_authorization`

**Must not modify:**
- Aggregation service or `InsightsSummary` type without principal approval
- Navigation, dashboard logic, or shared components
- Product service internals

## Concurrency rules

1. **Packet 1 (Platform IA) must complete before any parallel work begins.** This packet establishes the frozen shared contracts.

2. **After Packet 1, these workstreams may proceed in isolated worktrees:**
   - Integrations Control Plane (Packet 3)
   - Automation & Agents (Packet 5)
   - Product UX (Packet 4) — only against frozen shared contracts
   - Insights & Reporting (Packet 6) — after product/integration data contracts stabilize

3. **Unified Onboarding (Packet 2) may integrate with Integrations work or run as a bounded branch after shared state contracts are frozen.**

4. **No specialist may modify a file owned by another specialist or the principal without explicit principal approval.**

5. **If a specialist discovers a defect in a shared contract, they must report it to the principal. The principal owns the fix.**

## Shared contract freeze list (Packet 1 exit)

These files are frozen after Packet 1 acceptance. No specialist may modify them without principal approval:

### Frontend contracts (frozen)
- `apps/web/src/lib/platform.ts`
- `apps/web/src/lib/workspace.ts`
- `apps/web/src/lib/dashboard-logic.ts`
- `apps/web/src/lib/operating-dashboard.ts`
- `apps/web/src/components/AppShell.astro`
- `apps/web/src/components/MetricCard.astro`
- `apps/web/src/components/StatusBadge.astro`
- `apps/web/src/components/Card.astro`
- `apps/web/src/components/EmptyState.astro`
- `apps/web/src/components/PageHeader.astro`
- `apps/web/src/lib/ui/` (all files)
- `apps/web/src/lib/api-client.ts`
- `apps/web/src/lib/session.ts`
- `apps/web/src/lib/supabase-client.ts`
- `apps/web/src/lib/config.ts`

### Backend contracts (frozen)
- `apps/api/app/administration/service.py` (readiness engine)
- `apps/api/app/administration/contracts.py`
- `apps/api/app/onboarding/service.py`
- `apps/api/app/onboarding/contracts.py`
- `apps/api/app/insights/aggregation_service.py`
- `apps/api/app/execution/workflow_catalog.py`
- `apps/api/app/access_control/catalog.py`
- `apps/api/app/authorization/dependencies.py`
- `apps/api/app/authorization/service.py`
- `apps/api/app/routes/api_v1.py`
- `apps/api/app/main.py`
- `apps/api/app/config.py`
- `apps/api/app/database/` (all files)
- `apps/api/app/schemas.py`
- `apps/api/app/errors.py`
- `apps/api/app/middleware.py`
- `apps/api/app/context.py`

### Infrastructure contracts (frozen)
- `migrations/env.py`
- `infrastructure/` (all files)
- `package.json`
- `pyproject.toml`
- `alembic.ini`
- `.github/workflows/ci.yml`

## File collision risk matrix

| File | Principal | Integrations | Automation | Product UX | Insights |
|------|-----------|-------------|------------|------------|----------|
| `apps/web/src/lib/platform.ts` | **OWNS** | READ | READ | READ | READ |
| `apps/web/src/lib/workspace.ts` | **OWNS** | READ | READ | READ | READ |
| `apps/web/src/lib/dashboard-logic.ts` | **OWNS** | — | — | READ | READ |
| `apps/web/src/lib/operating-dashboard.ts` | **OWNS** | — | — | READ | READ |
| `apps/web/src/components/AppShell.astro` | **OWNS** | — | — | — | — |
| `apps/web/src/components/MetricCard.astro` | **OWNS** | — | — | READ | READ |
| `apps/web/src/components/StatusBadge.astro` | **OWNS** | READ | READ | READ | READ |
| `apps/web/src/lib/ui/` | **OWNS** | READ | READ | READ | READ |
| `apps/api/app/administration/service.py` | **OWNS** | READ | READ | READ | READ |
| `apps/api/app/insights/aggregation_service.py` | **OWNS** | — | — | — | READ |
| `apps/api/app/execution/workflow_catalog.py` | **OWNS** | READ | READ | READ | — |
| `apps/api/app/authorization/dependencies.py` | **OWNS** | READ | READ | READ | READ |
| `apps/api/app/integrations/connection_service.py` | — | **OWNS** | READ | READ | — |
| `apps/api/app/execution/handlers.py` | — | — | **OWNS** | — | — |
| `apps/api/app/products/gbp/service.py` | — | — | — | **OWNS** | — |
| `apps/api/app/products/reviews/service.py` | — | — | — | **OWNS** | — |
| `apps/api/app/insights/service.py` | — | — | — | — | **OWNS** |
| `apps/web/src/pages/gbp.astro` | — | — | — | **OWNS** | — |
| `apps/web/src/pages/integrations.astro` | — | **OWNS** | — | — | — |
| `apps/web/src/pages/insights.astro` | — | — | — | — | **OWNS** |
| `apps/web/src/pages/index.astro` | **OWNS** | — | — | READ | READ |
| `apps/web/src/pages/settings.astro` | **OWNS** | — | — | — | — |
| `apps/web/src/pages/administration.astro` | **OWNS** | — | — | — | — |
| `apps/web/src/pages/onboarding.astro` | **OWNS** | — | — | — | — |
| `apps/api/app/organizations/service.py` | **OWNS** | — | — | — | — |
| `apps/api/app/locations/service.py` | **OWNS** | — | — | — | — |
| `apps/api/app/authentication/service.py` | **OWNS** | — | — | — | — |
| `apps/api/app/audit/service.py` | **OWNS** | READ | READ | READ | READ |
| `apps/api/app/notifications/service.py` | **OWNS** | READ | READ | READ | — |
| `apps/api/app/ai/gateway.py` | **OWNS** | — | — | READ | — |

**Legend:** OWNS = may modify, READ = may consume but not modify, — = should not touch