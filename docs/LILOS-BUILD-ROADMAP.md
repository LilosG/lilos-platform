# LILOs Platform Build Roadmap

## Purpose
This roadmap defines the required implementation order for the LILOs Platform. It converts the stable requirements in `/docs/LILOS-MASTER-SPEC.md` into controlled build phases without restating the full specification.

## Source Authority
1. The Master Specification defines what the finished platform must contain and how it must behave.
2. This roadmap defines sequence, dependencies, deliverables, and phase exit criteria.
3. The Master Build Prompt defines how an implementation agent executes an assigned roadmap task.
4. When roadmap wording conflicts with the Master Specification, the Master Specification controls and the conflict must be reported before implementation.

## Execution Rules
- Complete phases in order unless an approved dependency analysis permits parallel work.
- A later phase may begin only when its required dependencies and exit criteria are satisfied or a documented, approved exception exists.
- Deliverables are production-quality increments, not placeholders.
- Do not pull deferred scope forward merely because it is technically adjacent.
- Update implementation status and acceptance evidence after every completed task.

Phase 0 — Specification and Repository Baseline
Objective
Prepare the repository and documentation so implementation begins from a controlled baseline.
Deliverables
	•	Final Master Spec assembled
	•	Specification terminology normalized
	•	Architecture conflicts resolved
	•	Repository initialized
	•	Frontend and backend workspace structure created
	•	Environment-variable conventions defined
	•	Local development instructions created
	•	Formatting and linting configured
	•	Type checking configured
	•	Test frameworks configured
	•	CI baseline created
	•	Architecture decision log created
	•	Implementation-status document created
Relevant Master Spec Sections
	•	Sections 1–4
	•	Sections 9–10
	•	Sections 21–27
Dependencies
None. This phase establishes the controlled baseline for all later work.

Exit Criteria
	•	Master Spec is internally consistent.
	•	Frontend and backend start locally.
	•	CI runs successfully.
	•	Empty test suites run successfully.
	•	Repository structure matches the architecture.

Phase 1 — Core Backend and Data Foundation
Objective
Create the backend foundation and shared persistence layer.
Deliverables
	•	FastAPI application foundation
	•	PostgreSQL connection management
	•	SQLAlchemy foundation
	•	Alembic migration foundation
	•	Base entity conventions
	•	UUID strategy
	•	Timestamp conventions
	•	Environment configuration
	•	Structured error model
	•	Request correlation IDs
	•	Basic health endpoints
	•	Database health checks
	•	Initial audit-event infrastructure
Relevant Master Spec Sections
	•	Section 4
	•	Section 5
	•	Section 7
	•	Section 9
	•	Section 10
	•	Section 21
	•	Section 23
Dependencies
Phase 0.

Exit Criteria
	•	Backend starts in local and test environments.
	•	Database migrations run forward successfully.
	•	Database connectivity is monitored.
	•	Error responses use the standard contract.
	•	Correlation IDs appear in logs and responses.
	•	Audit events can be persisted.

Phase 2 — Tenant, Organization and Location Model
Objective
Establish the platform’s ownership and isolation model.
Deliverables
	•	Platform tenant model
	•	Agency workspace model
	•	Client organization model
	•	Organization profile
	•	Organization lifecycle
	•	Location model
	•	Location lifecycle
	•	Location groups
	•	Business identity model
	•	Tenant-aware repositories
	•	Tenant-aware service layer
	•	Tenant-isolation tests
Relevant Master Spec Sections
	•	Section 5
	•	Section 9
	•	Section 20
Dependencies
Phases 0–1.

Exit Criteria
	•	Every tenant-scoped record belongs to the correct scope.
	•	Cross-tenant access fails.
	•	Organization and location states are validated.
	•	Business identity can be resolved by organization and location.

Phase 3 — Authentication, Memberships and Authorization
Objective
Implement secure identity and scoped access.
Deliverables
	•	Supabase Auth integration
	•	User identity records
	•	Session validation
	•	Memberships
	•	Invitations
	•	Roles
	•	Permissions
	•	Scoped role assignments
	•	Explicit deny rules
	•	Sensitive permissions
	•	MFA policy enforcement
	•	Session revocation
	•	User deactivation
	•	Authorization middleware and services
	•	Privilege-escalation tests
Relevant Master Spec Sections
	•	Section 9
	•	Section 20
	•	Section 22
Dependencies
Phases 0–2.

Exit Criteria
	•	Authentication and authorization are separate.
	•	Access is limited by membership, role, permission, and scope.
	•	Deactivated users lose access.
	•	Cross-organization access is blocked.
	•	Sensitive actions require separate permissions.

Phase 4 — Shared Administration and Configuration
Objective
Implement the shared operational configuration used by all products.
Deliverables
	•	Service catalog
	•	Service assignments
	•	Business facts
	•	Business-fact authority
	•	Business-fact approval
	•	Business-fact versioning
	•	Product registry
	•	Product entitlements
	•	Product readiness
	•	Configuration inheritance
	•	Effective-dated configuration
	•	Configuration validation
	•	Policy registry
	•	Policy versioning
	•	Approval-policy registry
	•	Notification-policy registry
	•	Feature flags
	•	Runtime controls
	•	Onboarding checklist
	•	Offboarding workflow
Relevant Master Spec Sections
	•	Section 12
	•	Section 20
Dependencies
Phases 0–3.

Exit Criteria
	•	Products can be enabled without being incorrectly marked ready.
	•	Business facts are approved and versioned.
	•	Effective configuration can be resolved and explained.
	•	Runtime controls override lower-level operations.
	•	Onboarding blockers are visible.

Phase 5 — Workflow and Background Job Foundation
Objective
Create the durable execution system for asynchronous platform work.
Deliverables
	•	Workflow definitions
	•	Workflow execution records
	•	Step execution records
	•	Job queue
	•	Worker process
	•	Scheduler
	•	Cron support
	•	Retry policies
	•	Timeouts
	•	Idempotency
	•	Cancellation
	•	Human approval steps
	•	Manual resume
	•	Dead-letter handling
	•	Job replay
	•	Workflow audit
	•	Workflow diagnostics
Relevant Master Spec Sections
	•	Section 6
	•	Section 9
	•	Section 21
	•	Section 22
Dependencies
Phases 0–4.

Exit Criteria
	•	Long-running work executes outside HTTP requests.
	•	Failed jobs are retryable according to policy.
	•	Ambiguous operations are not blindly replayed.
	•	Human approvals can pause and resume workflows.
	•	Operators can inspect and replay failed jobs safely.

Phase 6 — Notification Foundation
Objective
Create platform notifications for operational and administrative events.
Deliverables
	•	In-app notifications
	•	Resend integration
	•	Notification templates
	•	Notification preferences
	•	Mandatory notification rules
	•	Digest support
	•	Quiet-hour support
	•	Escalation support
	•	Delivery status
	•	Failure handling
	•	Notification audit
Relevant Master Spec Sections
	•	Section 6
	•	Section 17
	•	Section 19
	•	Section 20
Dependencies
Phases 0–5.

Exit Criteria
	•	Platform events can produce notifications.
	•	Mandatory notifications cannot be suppressed improperly.
	•	Notification deliveries are tracked.
	•	Failures are visible and retryable.

Phase 7 — Integration Framework Foundation
Objective
Implement the common external-system integration layer.
Deliverables
	•	Provider registry
	•	Connector registry
	•	Connector manifest
	•	Connector versioning
	•	Capability registry
	•	Integration connections
	•	OAuth framework
	•	API-key framework
	•	Secret references
	•	Token refresh
	•	Provider account discovery
	•	Provider resource discovery
	•	Entity mapping
	•	Connection health
	•	Standard provider errors
	•	Connector contract-test harness
Relevant Master Spec Sections
	•	Section 19
	•	Section 22
	•	Section 25
Dependencies
Phases 0–6.

Exit Criteria
	•	Providers can be registered consistently.
	•	Connections can authenticate securely.
	•	Provider resources can be mapped explicitly.
	•	Secrets never appear in frontend responses or logs.
	•	Connector contract tests pass.

Phase 8 — Synchronization, Webhooks and Outbound Actions
Objective
Complete the operational integration layer.
Deliverables
	•	Full synchronization
	•	Incremental synchronization
	•	Sync cursors
	•	Polling
	•	Webhook gateway
	•	Signature verification
	•	Replay protection
	•	Webhook deduplication
	•	Outbound-action records
	•	Outbound validation
	•	Idempotency
	•	Verification
	•	Reconciliation
	•	Rate-limit manager
	•	Provider circuit breakers
	•	Provider incidents
Relevant Master Spec Sections
	•	Section 6
	•	Section 19
	•	Section 21
Dependencies
Phases 0–7.

Exit Criteria
	•	Inbound synchronization is durable and idempotent.
	•	Webhooks are verified and deduplicated.
	•	Outbound writes require confirmed mappings.
	•	Provider writes are verified.
	•	Ambiguous results enter reconciliation.
	•	Provider degradation does not block unrelated tenants.

Phase 9 — First End-to-End Vertical Slice: Google Business Profile
Objective
Validate the shared architecture using one complete production workflow.
Deliverables
	•	Google OAuth connection
	•	GBP account discovery
	•	GBP location discovery
	•	LILOs location mapping
	•	GBP profile synchronization
	•	GBP profile display
	•	Profile-health evaluation
	•	Proposed profile change
	•	Approval workflow
	•	Provider write
	•	Write verification
	•	Reconciliation
	•	Audit
	•	Operational diagnostics
	•	Tenant-isolation tests
	•	Connector contract tests
	•	End-to-end tests
Relevant Master Spec Sections
	•	Section 6
	•	Section 12
	•	Section 14
	•	Section 19
	•	Section 20
	•	Section 21
	•	Section 22
Dependencies
Phases 0–8.

Exit Criteria
A user can:
	1	Connect Google.
	2	Select the correct GBP account.
	3	Map a GBP location.
	4	Sync profile data.
	5	Review a proposed change.
	6	Approve the change.
	7	Publish the change.
	8	Verify the provider state.
	9	Inspect the audit and workflow history.
This phase proves the platform architecture before all products are built.

Phase 10 — Reviews Product
Objective
Implement review monitoring and response operations.
Deliverables
	•	Review ingestion
	•	Review normalization
	•	Review source mapping
	•	Review filters
	•	Review status
	•	Response drafts
	•	AI-assisted response generation
	•	Business-fact grounding
	•	Approval workflow
	•	Response publication
	•	Verification
	•	Response history
	•	Restricted-review handling
	•	Review insights
	•	Review notifications
Relevant Master Spec Sections
	•	Section 8
	•	Section 15
	•	Section 19
Dependencies
Phase 9 and the shared AI, approval, notification, and integration foundations.

Exit Criteria
	•	Reviews sync without duplication.
	•	AI drafts are grounded and reviewable.
	•	Responses follow policy and approval requirements.
	•	Published responses are verified.
	•	Restricted cases cannot be auto-published.

Phase 11 — Leads Product
Objective
Implement lead intake, routing, response, follow-up, and lifecycle management.
Deliverables
	•	Lead model
	•	Lead sources
	•	Lead deduplication
	•	Consent model
	•	Service classification
	•	Urgency classification
	•	Routing
	•	Assignment
	•	Speed-to-lead tracking
	•	Email response
	•	SMS response when approved
	•	Follow-up sequences
	•	Communication history
	•	Lead status
	•	Conversion tracking
	•	CRM integration contract
	•	After-hours handling
	•	Escalation
	•	Suppression
Relevant Master Spec Sections
	•	Section 8
	•	Section 17
	•	Section 19
	•	Section 20
Dependencies
Phases 0–8, plus the administration, workflow, notification, and integration foundations. Phase 9 should be stable before production rollout.

Exit Criteria
	•	Leads enter from approved sources.
	•	Consent is explicit.
	•	Leads route to the correct organization, location, service, and user.
	•	Follow-up is durable and auditable.
	•	Opt-outs stop future communication.
	•	Client and agency users see only authorized leads.

Phase 12 — Content Product
Objective
Implement structured content planning, drafting, approval, publication, and revision.
Deliverables
	•	Content opportunities
	•	Content briefs
	•	Content drafts
	•	Revision history
	•	Business-fact grounding
	•	AI-assisted drafting
	•	Content validation
	•	Editorial approval
	•	Client approval
	•	Publishing targets
	•	Astro publishing adapter
	•	GitHub pull-request publication
	•	Build verification
	•	Deployment verification
	•	Rollback
	•	Content-performance linkage
Relevant Master Spec Sections
	•	Section 8
	•	Section 16
	•	Section 19
Dependencies
Phases 0–10, especially business facts, AI gateway, approvals, connector framework, GitHub, and deployment verification.

Exit Criteria
	•	Content can move from opportunity to published state.
	•	Drafts remain versioned.
	•	Claims use approved business facts.
	•	Publishing uses the integration framework.
	•	Astro publishing creates controlled repository changes.
	•	Publication is verified after deployment.

Phase 13 — SEO Product
Objective
Implement SEO data collection, analysis, recommendations, and execution tracking.
Deliverables
	•	Website entities
	•	Page inventory
	•	Search Console connection
	•	Search Console synchronization
	•	Query and page metrics
	•	Technical checks
	•	On-page checks
	•	Internal-link analysis
	•	Content-gap analysis
	•	Local landing-page analysis
	•	Recommendation model
	•	Recommendation prioritization
	•	Approval workflow
	•	Execution tracking
	•	Impact tracking
	•	SEO dashboards
Relevant Master Spec Sections
	•	Section 13
	•	Section 18
	•	Section 19
Dependencies
Phases 0–8 and stable Insights primitives required for metric normalization; Content integration is optional for initial recommendation execution.

Exit Criteria
	•	Search Console data syncs correctly.
	•	Recommendations preserve source evidence.
	•	Recommendations are prioritized deterministically.
	•	Execution and results can be tracked.
	•	Missing data is not represented as zero.

Phase 14 — Remaining Google Business Profile Capabilities
Objective
Complete the broader GBP product after the vertical slice proves the foundation.
Deliverables
	•	Categories
	•	Services
	•	Products
	•	Hours
	•	Special hours
	•	Attributes
	•	Description
	•	Photos
	•	Posts
	•	Q&A where supported
	•	Profile-completeness scoring
	•	Data-conflict detection
	•	Proposed-change sets
	•	Scheduled actions
	•	GBP reporting
	•	GBP operational alerts
Relevant Master Spec Sections
	•	Section 14
	•	Section 18
	•	Section 19
Dependencies
Phase 9 and stable connector, workflow, approval, and verification infrastructure.

Exit Criteria
	•	All supported GBP capabilities use explicit provider capabilities.
	•	High-risk changes require approval.
	•	Changes are verified.
	•	Unsupported capabilities are not presented as available.

Phase 15 — Insights and Reporting
Objective
Implement normalized analytics, insights, goals, dashboards, and reporting.
Deliverables
	•	KPI registry
	•	Metric observations
	•	Dimensions
	•	Aggregations
	•	Trends
	•	Anomalies
	•	Benchmarks
	•	Goals
	•	Attribution
	•	Insight generation
	•	AI summaries
	•	Dashboards
	•	Scheduled reports
	•	Report approval
	•	Report delivery
	•	Exports
	•	Data freshness
	•	Data-quality indicators
Relevant Master Spec Sections
	•	Section 18
	•	Section 21
	•	Section 24
Dependencies
Stable normalized data from the product phases included in the first release; Phases 9–14 as applicable.

Exit Criteria
	•	Metrics are definition-driven.
	•	Reports show freshness and missing-data states.
	•	AI summarizes validated metrics rather than calculating them.
	•	Reports are reproducible.
	•	Delivery is tracked.
	•	Historical reports remain immutable.

Phase 16 — Administrative and Client User Interfaces
Objective
Complete the operational frontend across platform, agency, client, and product scopes.
Deliverables
	•	Platform administration
	•	Agency workspace
	•	Client organization workspace
	•	Location administration
	•	User management
	•	Role management
	•	Product management
	•	Integration management
	•	Approval inbox
	•	Workflow status
	•	Notification center
	•	Runtime controls
	•	Audit views
	•	Product dashboards
	•	Responsive navigation
	•	Accessibility validation
	•	Empty, loading, error, and degraded states
Relevant Master Spec Sections
	•	Section 11
	•	Section 12
	•	Section 20
Dependencies
Phases 0–15. Product APIs and state models must be stable enough to support complete administrative and client workflows.

Exit Criteria
	•	Users see only authorized scopes and actions.
	•	Navigation reflects product entitlement and readiness.
	•	Administrative changes display their impact.
	•	All critical workflows can be completed without direct database access.

Phase 17 — Observability and Operational Hardening
Objective
Make the complete platform operable in production.
Deliverables
	•	Centralized logs
	•	Metrics
	•	Traces
	•	Operational dashboards
	•	Alert rules
	•	Incident lifecycle
	•	Runbooks
	•	Queue dashboards
	•	Worker dashboards
	•	Integration dashboards
	•	AI usage monitoring
	•	Cost monitoring
	•	Capacity monitoring
	•	Service-level objectives
	•	Error budgets
	•	Maintenance mode
	•	Emergency controls
	•	Operator diagnostics
Relevant Master Spec Sections
	•	Section 21
	•	Section 26
Dependencies
Phases 0–16. Foundational telemetry from earlier phases must already exist; this phase completes operational hardening.

Exit Criteria
	•	Critical failures generate actionable alerts.
	•	Operators can identify the affected tenant, product, workflow, and provider.
	•	Queues and workers are visible.
	•	Service-level objectives are measurable.
	•	Runbooks exist for critical incidents.

Phase 18 — Testing, Security and Reliability Hardening
Objective
Complete the production-quality validation required across the full platform.
Deliverables
	•	Full unit-test coverage for critical domains
	•	Integration tests
	•	End-to-end workflows
	•	Tenant-isolation test suite
	•	Authorization test suite
	•	Connector contract suite
	•	Migration test suite
	•	Load tests
	•	Stress tests
	•	Failure-injection tests
	•	Security testing
	•	Backup restore test
	•	Disaster-recovery test
	•	Accessibility test
	•	Browser test
	•	AI evaluation suite
	•	Regression suite
Relevant Master Spec Sections
	•	Section 9
	•	Section 22
	•	Section 24
	•	Section 26
	•	Section 27
Dependencies
Phases 0–17.

Exit Criteria
	•	All mandatory quality gates pass.
	•	Cross-tenant access attempts fail.
	•	Critical workflows survive documented provider failures.
	•	Backup restoration is proven.
	•	Production release blockers are resolved.

Phase 19 — Production Deployment and Launch
Objective
Deploy the first production-ready platform release.
Deliverables
	•	Production infrastructure
	•	Production database
	•	Production secrets
	•	Frontend deployment
	•	Backend deployment
	•	Worker deployment
	•	Scheduler deployment
	•	Migration execution
	•	Monitoring activation
	•	Alert activation
	•	Backup activation
	•	Domain and TLS configuration
	•	Release checklist
	•	Rollback plan
	•	Pilot organization migration
	•	Pilot validation
	•	Production launch approval
Relevant Master Spec Sections
	•	Section 10
	•	Section 21
	•	Section 23
	•	Section 24
	•	Section 27
Dependencies
Phases 0–18 and formal completion of the Section 27 acceptance package.

Exit Criteria
	•	Production deployment passes smoke tests.
	•	Monitoring and alerts are active.
	•	Backups are verified.
	•	Rollback procedures are tested.
	•	Pilot organization workflows complete successfully.
	•	Formal acceptance criteria are signed off.

Phase 20 — Post-Launch Expansion
Objective
Expand only after the first production version is stable.
Deliverables
	•	Additional CRM connectors
	•	Additional CMS connectors
	•	Toast integration
	•	Booqable integration
	•	Jobber integration
	•	Housecall Pro integration
	•	FieldworkHQ integration
	•	Slack integration
	•	Additional AI providers
	•	Additional product capabilities
	•	Usage-based controls
	•	White-label preparation
	•	Partner-extension preparation
Relevant Master Spec Sections
	•	Product-specific sections
	•	Section 19
	•	Section 25
Dependencies
Phase 19 production stability and separately approved expansion scope.

Exit Criteria
Defined separately for each approved expansion project.
