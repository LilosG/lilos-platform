Section 1 — Product Vision
1.1 Purpose
LILOs is a modular business operating platform designed to help local businesses improve visibility, generate qualified leads, automate repetitive work, and measure business performance through a unified ecosystem of products.
The platform combines software, automation, integrations, and artificial intelligence into a single operating environment.
Artificial intelligence is an enhancement to the platform—not the platform itself.

1.2 Mission
Our mission is to give local businesses access to enterprise-grade technology through software that is simple to operate, measurable in its impact, and flexible enough to grow alongside the business.
The platform should reduce manual work, improve consistency, increase operational efficiency, and produce measurable business outcomes.

1.3 Vision
LILOs aims to become the operating system for local business growth.
Instead of relying on disconnected tools for SEO, Google Business Profile management, content creation, reviews, reporting, automation, and lead management, businesses should be able to operate from a single connected platform.
Every product should contribute to one unified ecosystem while remaining independently valuable.

1.4 Target Customers
The initial focus is on industries where local search visibility directly influences revenue.
Primary industries include:
	•	Restaurants
	•	Bars
	•	Home Service Businesses
	•	Professional Service Businesses
Future expansion should build upon this foundation without compromising the platform architecture.

1.5 Problems We Solve
Most local businesses operate using disconnected software that creates duplicated work, inconsistent processes, and poor visibility into performance.
Common examples include:
	•	Website management
	•	Google Business Profile
	•	Google Search Console
	•	Analytics
	•	Reviews
	•	Lead management
	•	Email marketing
	•	SMS communication
	•	Reporting
	•	Content creation
LILOs exists to unify these systems into one platform with shared data, shared workflows, and shared intelligence.

1.6 Product Philosophy
Platform First
The platform is the product.
AI models, APIs, cloud providers, and third-party services are implementation details.
No architectural decision should permanently depend on a single vendor.

Vendor Agnostic
The platform should always be capable of using whichever technology is best suited for a given task.
Model providers, APIs, infrastructure, and integrations should remain replaceable whenever practical.

Configuration Before Customization
Client behavior should be controlled primarily through configuration rather than custom software.
Adding a new client should involve enabling products, connecting integrations, and defining settings—not writing code.

AI Supports Software
Artificial intelligence enhances decision-making, content generation, analysis, and workflow efficiency.
Critical business rules, permissions, validation, security, billing, and auditing remain deterministic software.

Measurable Outcomes
Every feature should improve one or more measurable business metrics.
Examples include:
	•	Organic visibility
	•	Local rankings
	•	Qualified leads
	•	Review velocity
	•	Response time
	•	Conversion rate
	•	Revenue
	•	Operational efficiency
If a feature cannot demonstrate measurable value, it should be reconsidered.

Human Oversight
Automation should reduce repetitive work without removing accountability.
High-impact customer interactions should support approval workflows when appropriate.
Users should always understand why the platform made a recommendation or performed an action.

Simplicity Wins
Simple systems that are maintainable are preferred over complex systems with marginal improvements.
Complexity should only be introduced when it creates meaningful business value.

1.7 Product Objectives
The platform should eventually allow businesses to:
	•	Improve local search visibility
	•	Manage Google Business Profile
	•	Generate SEO opportunities
	•	Create and optimize content
	•	Manage customer reviews
	•	Capture and qualify leads
	•	Automate repetitive workflows
	•	Measure business performance
	•	Expand functionality by enabling additional products

1.8 What LILOs Is Not
LILOs is not intended to become:
	•	A website builder
	•	A general CRM
	•	A bookkeeping system
	•	A payroll application
	•	A project management platform
	•	A generic AI chatbot
The platform should integrate with specialized software rather than replace products that already solve those problems well.

1.9 Definition of Success
The platform succeeds when it enables one operator to manage significantly more businesses while maintaining or improving service quality.
Success is measured through:
	•	Client outcomes
	•	Operational efficiency
	•	Reliability
	•	Product adoption
	•	Long-term maintainability

---

Section 2 — Product Constitution
The following principles are permanent architectural rules.
Every future product, feature, automation, or integration should align with these principles.

Principle 1 — Platform Before Products
LILOs is a platform.
Products exist because the platform exists—not the other way around.
The Core Platform should continue operating regardless of which products are enabled.

Principle 2 — Independent Products
Every major capability should function as an independent product.
Examples include:
	•	SEO Intelligence
	•	Google Business Profile
	•	Content Intelligence
	•	Review Management
	•	Lead Management
	•	Speed-to-Lead
	•	Reporting
	•	Automations
Every product should provide value independently while becoming more valuable when combined with other products.

Principle 3 — Progressive Adoption
Businesses should never be forced into an all-or-nothing platform.
A customer should be able to purchase one product today and enable additional products later without migration projects or architectural changes.
Adding functionality should primarily require:
	•	Enabling the product
	•	Connecting integrations
	•	Configuring settings
	•	Assigning permissions

Principle 4 — Shared Foundation
Every product should rely on the same core platform services.
These include:
	•	Authentication
	•	Organizations
	•	Users
	•	Permissions
	•	Billing
	•	Notifications
	•	Integrations
	•	Audit Logging
	•	AI Gateway
	•	Reporting
	•	Settings
These capabilities should not be duplicated inside individual products.

Principle 5 — AI Is Replaceable
No AI provider should become a permanent dependency.
The platform should support selecting the best model for each task.
Changing AI providers should require configuration—not architectural redesign.

Principle 6 — Configuration Over Code
Business behavior should be defined through settings, policies, and configuration whenever practical.
Custom development should be the exception—not the standard onboarding process.

Principle 7 — Observable Systems
Every meaningful action performed by the platform should be traceable.
The platform should record:
	•	Who initiated the action
	•	What occurred
	•	When it occurred
	•	Why it occurred
	•	Which product performed the action
	•	Which AI model or automation participated, when applicable
Observability should be built into the platform rather than added later.

Principle 8 — Security by Default
Security is a platform responsibility.
Every product should inherit authentication, authorization, encryption, audit logging, and permission management from the Core Platform.

Principle 9 — Business Value Over Technology
Technology choices should be driven by measurable customer value rather than novelty.
New technologies should be adopted only when they improve outcomes, reduce operational cost, or simplify the platform.

Principle 10 — Long-Term Maintainability
Every architectural decision should optimize for the next three to five years rather than the next release.
Avoid unnecessary complexity, duplicated functionality, vendor lock-in, and tightly coupled systems.
Maintainability is a core product feature.

Closing Statement
LILOs is designed as a platform with independent products, not a collection of disconnected tools or automations.
Every product should deliver value on its own while benefiting from a shared platform that provides authentication, integrations, intelligence, reporting, billing, security, and automation.
The architecture should remain vendor-agnostic, modular, measurable, and maintainable, allowing new products and technologies to be introduced without fundamental redesign.
---

Section 3 — Platform Structure and Product Scope
3.1 Purpose of This Section
This section defines the functional structure of the LILOs platform.
It establishes:
	•	The distinction between the Core Platform and individual products
	•	The products planned for the platform
	•	The responsibilities and boundaries of each product
	•	Which capabilities belong in the initial build
	•	Which capabilities are intentionally deferred
	•	How products may be purchased, enabled, and combined
	•	How shared services prevent duplicated functionality
	•	How the agency-facing and client-facing experiences differ
This section defines product scope. It does not prescribe the detailed technical implementation. Technical architecture, database design, APIs, infrastructure, and implementation standards are defined in later sections.
 
⸻
 
3.2 Platform Model
LILOs is one platform composed of a shared Core Platform and multiple independently enabled products.
The platform is not sold or deployed as an all-or-nothing system.
A customer may use one product, several products, or the complete product suite. Products share foundational services but maintain clear functional boundaries.
The platform structure is:
LILOs Platform

├── Core Platform
│   ├── Organizations and locations
│   ├── Users and permissions
│   ├── Product entitlements
│   ├── Integrations and credentials
│   ├── Workflow execution
│   ├── Notifications
│   ├── AI gateway
│   ├── Audit logging
│   ├── Usage metering
│   ├── Billing support
│   └── Shared reporting infrastructure
│
├── LILOs SEO
├── LILOs GBP
├── LILOs Reviews
├── LILOs Content
├── LILOs Leads
├── LILOs Automations
└── LILOs Insights
The Core Platform is required infrastructure. It is not necessarily presented or sold as a standalone customer product.
The products above the Core Platform may be enabled independently.
 
⸻
 
3.3 Core Platform
3.3.1 Purpose
The Core Platform provides the common services required by every LILOs product.
Its purpose is to prevent each product from implementing separate authentication, client records, permissions, integrations, notifications, billing logic, audit trails, AI connections, or workflow infrastructure.
The Core Platform is the system of record for platform-level configuration.
3.3.2 Core Responsibilities
The Core Platform is responsible for:
	•	Organizations and client accounts
	•	Business locations
	•	Users and team membership
	•	Roles and permissions
	•	Product activation and entitlements
	•	Client-specific settings
	•	Integration connections
	•	Credential references and secret management
	•	Workflow execution records
	•	Notifications
	•	Audit history
	•	Usage tracking
	•	Subscription and billing references
	•	AI model access and routing
	•	Prompt version references
	•	Shared reporting data
	•	System health and operational status
3.3.3 Organization and Location Model
The platform must distinguish between an organization and a business location.
An organization represents the customer account.
A location represents an individual physical business location, service area, or operating unit.
Examples:
Organization: Restaurant Group A
├── Location: Little Italy
├── Location: Oceanside
└── Location: Carlsbad
Organization: Home Service Company B
└── Location: San Diego County Service Area
Products may be enabled:
	•	Across the entire organization
	•	For selected locations only
	•	With different configurations by location
A multi-location restaurant group must not require a separate disconnected client account for every location.
3.3.4 Product Entitlements
The Core Platform must maintain a record of which products and capabilities are enabled for each organization or location.
An entitlement defines access to a product or product capability.
Example:
Client: Example Restaurant

LILOs SEO              Enabled
LILOs GBP              Enabled
LILOs Reviews          Enabled
LILOs Content          Enabled
LILOs Leads            Disabled
LILOs Automations      Disabled
LILOs Insights         Enabled
Entitlements must be controlled independently from user permissions.
A client may pay for a product but restrict access to only certain users. Likewise, LILOs agency staff may have administrative access without being a customer user.
3.3.5 Configuration Hierarchy
Settings should follow a predictable hierarchy:
Platform defaults
    ↓
Industry defaults
    ↓
Organization settings
    ↓
Location settings
    ↓
Product settings
    ↓
Workflow-specific settings
More specific settings override broader defaults.
Example:
	•	Platform default: Review responses require approval.
	•	Restaurant industry default: Four- and five-star reviews may qualify for automatic responses.
	•	Client setting: All responses require approval.
	•	Location setting: One location permits approved automatic responses.
	•	Workflow setting: Responses mentioning injury, discrimination, payment disputes, or legal issues always require escalation.
This hierarchy allows standardized products without eliminating client-specific control.
3.3.6 Shared Integration Layer
The Core Platform manages connections to external services.
Expected integrations include:
	•	Google Business Profile
	•	Google Search Console
	•	Google Analytics 4
	•	Google Ads, when required
	•	Google Places and Maps APIs
	•	Website and content repositories
	•	GitHub
	•	Vercel
	•	Resend
	•	Email providers
	•	SMS and phone providers
	•	CRM systems
	•	Scheduling systems
	•	Form providers
	•	Stripe
	•	Third-party reporting or SEO data providers
Products should request access to an integration through the Core Platform rather than maintaining separate credentials.
A Google connection may support multiple products. For example:
	•	LILOs SEO uses Search Console and Analytics.
	•	LILOs GBP uses Business Profile.
	•	LILOs Reviews uses Business Profile reviews.
	•	LILOs Insights uses data from all connected Google services.
3.3.7 Shared Workflow Layer
The platform must support deterministic workflows that can:
	•	Run on a schedule
	•	Run in response to an event
	•	Run manually
	•	Require approval
	•	Pause for human input
	•	Retry after a transient failure
	•	Escalate after a permanent failure
	•	Record each execution
	•	Produce structured outputs
	•	Notify designated users
Individual products define their own workflow logic, but the Core Platform provides the execution framework and execution history.
The initial implementation may use the existing Hetzner environment and Python services. The architecture must not require a dedicated third-party workflow platform unless the operational need later justifies one.
3.3.8 Shared AI Layer
The Core Platform provides a vendor-agnostic interface to AI providers.
Products should not call Claude, ChatGPT, Gemini, Hermes, or another model directly from product-specific business logic.
The AI layer is responsible for:
	•	Provider connections
	•	Model registration
	•	Model routing
	•	Structured output validation
	•	Prompt version selection
	•	Usage and cost tracking
	•	Fallback models
	•	Retry behavior
	•	Evaluation records
	•	Safety and approval policies
The detailed AI architecture is defined in a later section.
3.3.9 Shared Audit Layer
Every significant action must generate an audit record.
This includes:
	•	Configuration changes
	•	Product activation
	•	Integration connection changes
	•	User and permission changes
	•	Automated content generation
	•	Review-response generation
	•	Customer communication
	•	GBP publication
	•	Website publication
	•	AI model usage
	•	Approval or rejection
	•	Workflow failure
	•	Manual override
An audit record should identify:
	•	Organization
	•	Location, when applicable
	•	Product
	•	Action
	•	Initiating user or system process
	•	Time
	•	Input reference
	•	Output reference
	•	Status
	•	Approval state
	•	AI provider and model, when applicable
	•	Error details, when applicable
 
⸻
 
3.4 User Surfaces
LILOs serves two distinct operating audiences.
3.4.1 Agency Operations Surface
The agency operations surface is used by LILOs staff.
It must support:
	•	Viewing all managed organizations
	•	Viewing all locations
	•	Enabling and configuring products
	•	Managing integrations
	•	Reviewing cross-client workflow status
	•	Approving generated work
	•	Investigating failures
	•	Comparing performance across clients
	•	Monitoring AI usage and costs
	•	Viewing client-level audit history
	•	Managing subscriptions and entitlements
	•	Assuming a controlled support view of a client account
	•	Applying templates and industry defaults
This is the primary operational control plane for LILOs Growth.
It should be optimized for managing multiple clients efficiently rather than mirroring the client interface.
3.4.2 Client-Facing Surface
The client-facing surface is used by business owners, managers, and authorized client employees.
It should expose only the products, locations, data, and actions included in their permissions and subscription.
It may support:
	•	Performance dashboards
	•	Recommendations
	•	Approval queues
	•	Review-response approval
	•	Content approval
	•	Lead status
	•	Integration status
	•	Product configuration
	•	Reports
	•	Notification preferences
	•	User management, when authorized
The client-facing interface should not expose internal LILOs operating notes, internal costs, platform-wide analytics, model experimentation, or other clients’ information.
3.4.3 Internal and External Data Separation
The platform must distinguish among:
	•	Client-visible information
	•	LILOs internal operational information
	•	System-only information
	•	Sensitive credentials
For example, a client may see that a GBP post is awaiting approval but should not automatically see internal prompt diagnostics, model comparisons, raw provider errors, or LILOs margin data.
This separation must be enforced through the data model and permissions, not merely hidden in the interface.
 
⸻
 
3.5 Product Catalog
The following products define the planned LILOs product suite.
The product names are working names and may change. Their functional boundaries should remain stable unless the platform scope is deliberately revised.
 
⸻
 
3.6 LILOs SEO
3.6.1 Purpose
LILOs SEO identifies, prioritizes, and tracks opportunities to improve organic and local search visibility.
It converts raw search data into actionable recommendations and measurable work.
3.6.2 Core Capabilities
LILOs SEO should support:
	•	Google Search Console data ingestion
	•	Google Analytics performance context
	•	Query and landing-page analysis
	•	Ranking and visibility imports
	•	Opportunity scoring
	•	Page decline detection
	•	Query-to-page mapping
	•	Cannibalization detection
	•	content-gap identification
	•	Local keyword tracking
	•	Technical issue monitoring
	•	Internal-linking recommendations
	•	Client and location segmentation
	•	Recommendation tracking
	•	Before-and-after measurement
3.6.3 Expected Outputs
Outputs may include:
	•	High-impression, low-click opportunities
	•	Queries ranking near page-one thresholds
	•	Pages losing clicks or impressions
	•	Pages with weakening click-through rates
	•	Missing service and location coverage
	•	Content refresh recommendations
	•	Internal-link opportunities
	•	Technical remediation tasks
	•	Prioritized SEO work queues
	•	Monthly or weekly performance summaries
3.6.4 AI Usage
AI may assist with:
	•	Interpreting patterns
	•	Grouping related queries
	•	Classifying search intent
	•	Drafting recommendations
	•	Identifying likely content gaps
	•	Summarizing performance changes
	•	Producing briefs for approved opportunities
Deterministic systems remain responsible for:
	•	Data collection
	•	Date comparisons
	•	Calculations
	•	Threshold evaluation
	•	Deduplication
	•	Record creation
	•	Status tracking
3.6.5 Product Boundary
LILOs SEO identifies and manages SEO opportunities.
It does not own full content production or publication. Those functions belong to LILOs Content.
LILOs SEO may create a content recommendation that is passed to LILOs Content when that product is enabled.
If LILOs Content is not enabled, the recommendation remains usable as an SEO task or export.
 
⸻
 
3.7 LILOs GBP
3.7.1 Purpose
LILOs GBP manages and improves the accuracy, relevance, activity, and measurable performance of Google Business Profiles.
3.7.2 Core Capabilities
LILOs GBP should support:
	•	Profile and location synchronization
	•	Primary and secondary category tracking
	•	Hours and special-hours monitoring
	•	Business information auditing
	•	Attribute tracking
	•	Service and menu data review
	•	Profile completeness checks
	•	GBP post planning
	•	GBP post generation
	•	Approval and publishing workflows
	•	Photo planning and publication tracking
	•	Q&A monitoring and drafting
	•	Local performance data ingestion
	•	Change detection
	•	Issue and suspension-status tracking
	•	Location-level recommendations
3.7.3 Industry-Specific Behavior
The product must support industry-specific configuration.
Restaurant and bar workflows may emphasize:
	•	Menus
	•	Reservations
	•	Brunch, happy hour, and event relevance
	•	Cuisine and venue categories
	•	Photos
	•	Posts
	•	Ordering links
	•	Business hours
	•	Seasonal offerings
Home-service workflows may emphasize:
	•	Service categories
	•	Service areas
	•	Emergency availability
	•	Appointment links
	•	Service descriptions
	•	Licensing and trust signals
	•	Lead actions
	•	Location and coverage consistency
The underlying product remains shared. Industry-specific behavior is implemented through configuration, templates, policies, and data mappings.
3.7.4 Product Boundary
LILOs GBP owns profile optimization and GBP publication workflows.
Review ingestion may originate through the same Google integration, but review-response workflows belong to LILOs Reviews.
This separation allows a customer to purchase GBP management without purchasing automated review management, or vice versa.
 
⸻
 
3.8 LILOs Reviews
3.8.1 Purpose
LILOs Reviews helps businesses monitor, respond to, learn from, and improve customer reviews.
3.8.2 Core Capabilities
LILOs Reviews should support:
	•	Review ingestion
	•	Review-status tracking
	•	Response drafting
	•	Approval workflows
	•	Authorized automatic responses
	•	Response publication
	•	Sentiment and topic classification
	•	Risk detection
	•	Escalation
	•	Response-time measurement
	•	Review-volume reporting
	•	Review-request workflow support
	•	Repeated-issue detection
	•	Location and employee context, where provided
	•	Brand and industry response policies
3.8.3 Guardrails
The product must not:
	•	Invent details about the customer’s experience
	•	Admit legal liability
	•	Promise compensation without explicit authority
	•	Disclose private customer information
	•	Argue with reviewers
	•	Publish responses to high-risk reviews without the required approval
	•	Treat all ratings as equivalent
	•	Use identical repetitive responses at scale
	•	Claim an issue was resolved unless verified
Reviews involving legal threats, injury, discrimination, harassment, fraud, charge disputes, food safety, threats, or other defined risk topics must be escalated according to client policy.
3.8.4 Product Boundary
LILOs Reviews owns review monitoring and response workflows.
It may send aggregated review topics to LILOs Insights.
It may create operational recommendations, but it is not intended to become a full reputation-management CRM.
 
⸻
 
3.9 LILOs Content
3.9.1 Purpose
LILOs Content turns approved business and SEO opportunities into structured, brand-consistent, publishable content.
3.9.2 Core Capabilities
LILOs Content should support:
	•	Content opportunity intake
	•	Topic and duplication checks
	•	Brief generation
	•	Outline generation
	•	Draft generation
	•	Content optimization
	•	Brand-rule enforcement
	•	Local relevance requirements
	•	Fact and claim controls
	•	Internal-link recommendations
	•	Metadata generation
	•	Approval workflows
	•	Revision history
	•	Repository-based publication
	•	CMS publication, where supported
	•	Performance feedback after publication
3.9.3 Content Types
The initial system may support:
	•	Service pages
	•	Location pages
	•	Blog articles
	•	Existing-page updates
	•	FAQ content
	•	GBP post copy
	•	Review-response language
	•	Selected email or lead-follow-up copy
GBP posts and review responses use shared content infrastructure where appropriate, but ownership of those workflows remains with their respective products.
3.9.4 Existing LILOs Guardrails
The initial content system should preserve proven operating rules already used by LILOs Growth, including:
	•	Do not overwrite an existing published slug unintentionally.
	•	Do not create duplicate H1 elements.
	•	Avoid duplicate or substantially overlapping topics.
	•	Use editorial, readable URLs.
	•	Support defined city-to-service mappings.
	•	Preserve approved claims.
	•	Do not introduce unverified business claims.
	•	Include relevant local references when required.
	•	Ensure calls to action are functional and appropriate.
	•	Follow product- and client-specific content length requirements.
	•	Keep website structure and schema consistent.
	•	Require approval before publication unless the workflow is explicitly authorized.
Content standards must be configurable because requirements differ between restaurants, home services, and other industries.
3.9.5 Product Boundary
LILOs Content owns content creation, editing, approval, and publication.
LILOs SEO may supply the opportunity and performance context.
LILOs GBP may request GBP-specific content.
LILOs Reviews may use shared brand guidance but retains responsibility for review workflows.
 
⸻
 
3.10 LILOs Leads
3.10.1 Purpose
LILOs Leads captures, normalizes, qualifies, routes, and tracks leads from supported sources.
It is not intended to replace a full CRM.
3.10.2 Core Capabilities
LILOs Leads should support:
	•	Form lead ingestion
	•	Phone and missed-call event ingestion
	•	Email lead ingestion
	•	Supported third-party lead-source ingestion
	•	Duplicate detection
	•	Lead normalization
	•	Source attribution
	•	Basic qualification
	•	Assignment and routing
	•	Lead-status tracking
	•	Contact-attempt tracking
	•	Response-time tracking
	•	CRM handoff
	•	Lead outcome feedback
	•	Consent and communication-policy tracking
3.10.3 Speed-to-Lead Capability
Speed-to-Lead is a capability within LILOs Leads that may be packaged and sold independently.
It should support:
	•	Immediate lead acknowledgment
	•	Email and SMS follow-up
	•	Business-hours rules
	•	After-hours handling
	•	Qualification questions
	•	Routing by service, location, urgency, or other defined criteria
	•	Escalation when no staff response occurs
	•	Appointment or booking handoff
	•	Conversation-state tracking
	•	Stop and opt-out handling
	•	Human takeover
	•	Outcome measurement
3.10.4 Deterministic and AI Responsibilities
Deterministic software is responsible for:
	•	Consent validation
	•	Communication timing
	•	Sending limits
	•	Business-hours rules
	•	Contact routing
	•	Opt-out enforcement
	•	Retry behavior
	•	Record creation
	•	State transitions
	•	Escalation timing
AI may assist with:
	•	Intent classification
	•	Service classification
	•	Urgency classification
	•	Response drafting
	•	Qualification
	•	Conversation summarization
AI must not independently ignore consent rules, invent availability, guarantee service, provide unapproved pricing, or make commitments beyond configured authority.
3.10.5 Product Boundary
LILOs Leads manages lead activity until handoff or defined closure.
It does not replace the customer’s complete sales pipeline, dispatch software, field-service management system, or long-term CRM unless scope is deliberately expanded later.
 
⸻
 
3.11 LILOs Automations
3.11.1 Purpose
LILOs Automations provides reusable business workflows that extend beyond the fixed workflows included in other products.
3.11.2 Core Capabilities
The product may support:
	•	Scheduled workflows
	•	Event-triggered workflows
	•	Conditional logic
	•	Approval steps
	•	Notifications
	•	Data transformation
	•	Integration actions
	•	Delayed follow-up
	•	Escalation
	•	Retry and failure handling
	•	Workflow templates
	•	Execution history
	•	Client-specific configuration
3.11.3 Example Automations
Examples may include:
	•	Estimate follow-up
	•	Missed-call follow-up
	•	Appointment reminders
	•	Review requests
	•	Unanswered-lead escalation
	•	Customer re-engagement
	•	Expiring-offer reminders
	•	Internal task creation
	•	Failed-publication alerts
	•	Weekly operating summaries
	•	Data-quality alerts
	•	Integration-health alerts
3.11.4 Product Boundary
Other products contain their required native workflows.
LILOs Automations is used when a customer needs reusable cross-product workflows or business processes beyond the standard product behavior.
The product should not become an unrestricted no-code automation builder in the initial release.
The initial focus is a controlled library of supported, configurable automation templates.
 
⸻
 
3.12 LILOs Insights
3.12.1 Purpose
LILOs Insights provides cross-product reporting, dashboards, performance measurement, and operational summaries.
3.12.2 Core Capabilities
LILOs Insights should support:
	•	Organization dashboards
	•	Location dashboards
	•	Product-specific dashboards
	•	Cross-product KPI views
	•	Scheduled reports
	•	Period comparisons
	•	Goal tracking
	•	Data freshness indicators
	•	Annotation of significant events
	•	Recommendation summaries
	•	Workflow-performance reporting
	•	Lead-response reporting
	•	AI usage and cost reporting for internal users
	•	Client-facing report generation
	•	Agency portfolio reporting
3.12.3 Reporting Principles
Reports must clearly distinguish among:
	•	Observed facts
	•	Calculated metrics
	•	AI-generated interpretations
	•	Recommendations
	•	Missing or delayed data
The platform must not present incomplete data as complete.
Every significant metric should identify:
	•	Source
	•	Date range
	•	Last successful synchronization
	•	Scope
	•	Applicable location or organization
	•	Comparison period, where relevant
3.12.4 Product Boundary
Each product may contain basic operational reporting required to use that product.
LILOs Insights provides advanced reporting, consolidated dashboards, historical comparisons, and cross-product analysis.
A customer should not be forced to purchase LILOs Insights merely to see whether a purchased product is functioning.
 
⸻
 
3.13 Product Dependencies
Products should remain independently valuable, but some capabilities may improve when another product is present.
Dependencies must be classified as either required or optional.
Required Dependency
A required dependency is a Core Platform service without which the product cannot operate.
Examples:
	•	LILOs GBP requires the Core Platform integration layer.
	•	LILOs Leads requires the Core Platform organization and workflow records.
Optional Enhancement
An optional enhancement provides additional value but is not required.
Examples:
	•	LILOs SEO can pass approved opportunities to LILOs Content.
	•	LILOs Reviews can pass review themes to LILOs Insights.
	•	LILOs Leads can trigger workflows in LILOs Automations.
	•	LILOs GBP can use LILOs Content for expanded production workflows.
Products must not create hidden subscription dependencies.
If a workflow requires another paid product, that dependency must be explicit in product configuration and commercial packaging.
 
⸻
 
3.14 Product Packaging Rules
The commercial packaging may change over time, but the architecture must support:
	•	Standalone products
	•	Product bundles
	•	Organization-wide products
	•	Location-specific products
	•	Usage-based capabilities
	•	Agency-managed service tiers
	•	Client self-service tiers
	•	Trial entitlements
	•	Internal test entitlements
	•	Feature-level restrictions
Billing logic should reference entitlements rather than determine application behavior directly.
A failed payment may affect entitlements according to policy, but product code should not contain provider-specific Stripe logic.
 
⸻
 
3.15 Product Activation
Enabling a product should follow a standard lifecycle:
	1.	Assign the product entitlement.
	2.	Select the applicable organization and locations.
	3.	Verify user permissions.
	4.	Connect required integrations.
	5.	Validate data access.
	6.	Apply industry defaults.
	7.	Configure client-specific policies.
	8.	Configure approval requirements.
	9.	Run a readiness check.
	10.	Activate the product.
	11.	Record the activation in the audit log.
	12.	Begin synchronization or workflow execution.
A product must not be considered active merely because a database flag has been changed.
Activation should confirm that required integrations and configuration are operational.
 
⸻
 
3.16 Product States
Every enabled product should have an explicit state.
Recommended states include:
	•	not_enabled
	•	setup_required
	•	connection_required
	•	configuration_required
	•	ready
	•	active
	•	paused
	•	degraded
	•	suspended
	•	archived
The interface must show why a product is not fully operational.
Example:
LILOs GBP
Status: Degraded
Reason: Google Business Profile authorization expired
Last successful synchronization: July 26, 2026 at 4:18 PM PT
Required action: Reconnect Google account
This is preferable to showing a generic error or silently stopping workflows.
 
⸻
 
3.17 Initial Build Scope
The complete product vision is broader than the first release.
The initial build should prioritize the shared foundation and the products closest to LILOs Growth’s existing operations.
Phase 1 Core Scope
The initial Core Platform should include:
	•	Organizations
	•	Locations
	•	Users
	•	Basic roles and permissions
	•	Product entitlements
	•	Client configuration
	•	Integration records
	•	Workflow execution records
	•	Audit logs
	•	Notifications
	•	AI provider abstraction
	•	Prompt records
	•	Basic usage records
	•	Agency operations dashboard
	•	Basic client access structure
Phase 1 Product Scope
The first product implementations should focus on:
	1.	LILOs SEO
	2.	LILOs GBP
	3.	LILOs Reviews
	4.	LILOs Content
	5.	LILOs Insights
These products most directly consolidate and improve existing LILOs workflows.
Phase 1.5 Scope
After the first product group is stable:
	1.	LILOs Leads
	2.	Speed-to-Lead
	3.	Communication integrations
	4.	Lead routing
	5.	CRM handoff
	6.	Lead-response reporting
Phase 2 Scope
After repeatable client deployment is proven:
	1.	LILOs Automations
	2.	Reusable workflow templates
	3.	Expanded cross-product orchestration
	4.	More client self-service configuration
	5.	More advanced billing and usage controls
	6.	Expanded industry templates
The phase labels define sequencing, not rigid release names.
 
⸻
 
3.18 Initial Product Priorities
The initial build order should follow these priorities:
Priority 1 — Establish the Shared Platform
Do not begin by rewriting every existing script.
First establish:
	•	Client and location identity
	•	Product entitlements
	•	Configuration
	•	Integrations
	•	Execution tracking
	•	Audit logging
	•	AI abstraction
	•	Agency visibility
Existing scripts may initially operate behind standardized interfaces while being gradually refactored.
Priority 2 — Consolidate Existing SEO and GBP Operations
Existing LILOs processes already provide a working foundation for:
	•	GSC opportunity analysis
	•	Blog strategy
	•	Blog production
	•	GBP post generation
	•	GBP publication
	•	GBP photo workflows
The initial platform should standardize, expose, configure, and monitor these capabilities rather than discarding them without cause.
Priority 3 — Add Approval and Quality Control
The platform must improve control before increasing autonomy.
Priority controls include:
	•	Review queues
	•	Approval states
	•	Prompt versions
	•	Model records
	•	Structured validation
	•	Failure visibility
	•	Client-specific rules
	•	Publication history
Priority 4 — Measure Results
The platform should connect recommendations and generated work to outcomes.
Examples:
	•	SEO recommendation to page update to performance change
	•	GBP post to publication to engagement data
	•	Review received to response time
	•	Content brief to published page to search performance
	•	Lead received to first response to outcome
Priority 5 — Expand Automation Only After Reliability
More automation should be added only after the underlying workflow is observable, repeatable, and measurable.
The objective is not maximum autonomy.
The objective is reliable operational leverage.
 
⸻
 
3.19 Explicitly Deferred Capabilities
The following are not part of the initial build unless required by a validated customer need:
	•	Full general-purpose CRM
	•	Drag-and-drop automation builder
	•	Website page builder
	•	Full social-media management suite
	•	General accounting
	•	Payroll
	•	Field-service dispatch
	•	Full call-center platform
	•	General-purpose chatbot builder
	•	Unrestricted autonomous agent execution
	•	Custom enterprise data warehouse
	•	Kubernetes
	•	Complex microservice architecture
	•	A dedicated event-streaming platform
	•	A proprietary foundation model
	•	A complete replacement for GitHub, Vercel, Supabase, Stripe, or existing specialist tools
Deferral does not mean these capabilities can never be added.
It means they should not distract from building the shared platform and initial products.
 
⸻
 
3.20 Hermes or Similar Operator Compatibility
The platform must work without Hermes or any similar AI operator.
A future operator may be added as an optional interface over the platform.
The operator may:
	•	Interpret natural-language requests
	•	Select authorized platform actions
	•	Run approved workflows
	•	Summarize workflow results
	•	Investigate failures
	•	Retrieve operational status
	•	Coordinate multiple product actions
	•	Deliver internal summaries
	•	Create proposed configurations or tasks
The operator must not become:
	•	The platform database
	•	The workflow system of record
	•	The permissions system
	•	The integration credential store
	•	The billing system
	•	The audit system
	•	The sole way to operate a product
The same product services must remain accessible through standard application interfaces and APIs.
This requirement allows LILOs to add Hermes, an alternative operator, or a future internally developed operator without redesigning the platform.
A separate operator-enabled version of the build roadmap will define:
	•	Operator permissions
	•	Tool interfaces
	•	Read and write boundaries
	•	Approval requirements
	•	Memory boundaries
	•	Sandboxing
	•	Audit requirements
	•	Failure containment
 
⸻
 
3.21 Product Acceptance Rules
A product is not complete merely because its primary feature works.
Before a product can be considered production-ready, it must have:
	•	Defined scope
	•	Defined ownership
	•	Organization and location awareness
	•	Entitlement enforcement
	•	Permission enforcement
	•	Required integrations
	•	Configuration validation
	•	Explicit operational states
	•	Audit logging
	•	Error handling
	•	Retry behavior where appropriate
	•	Approval behavior where appropriate
	•	Basic reporting
	•	Data freshness visibility
	•	Test coverage
	•	Documentation
	•	Onboarding steps
	•	Suspension and disconnection behavior
	•	Export or handoff behavior where required
	•	Defined success metrics
These requirements apply to every product regardless of whether it uses AI.
 
⸻
 
3.22 Section Decisions
The following decisions are established by this section:
	1.	LILOs consists of a shared Core Platform and independently enabled products.
	2.	Organizations and locations are separate platform entities.
	3.	Products may be enabled by organization or by location.
	4.	Product entitlements and user permissions are separate concepts.
	5.	LILOs will support both agency-facing and client-facing operating surfaces.
	6.	Shared platform services must not be reimplemented inside individual products.
	7.	Products may enhance one another but should avoid unnecessary required dependencies.
	8.	The initial product focus is SEO, GBP, Reviews, Content, and Insights.
	9.	Leads and Speed-to-Lead follow after the initial shared foundation is stable.
	10.	LILOs Automations initially provides controlled workflow templates rather than an unrestricted automation builder.
	11.	Existing LILOs scripts should be standardized and integrated where viable rather than automatically replaced.
	12.	Hermes or a similar operator is optional and must not become a foundational dependency.
	13.	The platform must remain fully operable without an AI operator.
	14.	Product activation requires validated readiness, not merely an enabled flag.
	15.	Every product must expose clear operational status, failures, and data freshness.

---

Section 4 — Technical Architecture
4.1 Purpose of This Section
This section defines the technical architecture of the LILOs platform.
It establishes:
	•	The approved technology stack
	•	The responsibilities of each infrastructure component
	•	The system boundaries between frontend, backend, workflows, data, integrations, and AI
	•	The deployment model
	•	The multi-tenant architecture
	•	The communication patterns between platform components
	•	The standards for background jobs, APIs, events, and approvals
	•	The architectural differences between the platform with and without an AI operator
	•	The implementation constraints that future developers and AI coding systems must follow
This section does not define every database table or API endpoint. Those are addressed in later sections.
 
⸻
 
4.2 Architecture Goals
The architecture must support the following goals:
	1.	Build one reusable platform rather than separate systems for each client.
	2.	Allow products to be enabled independently.
	3.	Support both agency-operated and client-operated workflows.
	4.	Preserve existing LILOs infrastructure where it remains appropriate.
	5.	Minimize new vendors and unnecessary recurring costs.
	6.	Keep AI providers replaceable.
	7.	Keep workflow execution observable and auditable.
	8.	Support both scheduled and event-driven processes.
	9.	Support human approval before high-impact actions.
	10.	Scale from current agency operations to a larger multi-client product.
	11.	Avoid infrastructure complexity that is not yet justified.
	12.	Allow future replacement of individual components without redesigning the full platform.
 
⸻
 
4.3 Approved Initial Technology Stack
The initial architecture should use the following stack.
Application Frontend
	•	Astro
	•	TypeScript
	•	Tailwind CSS
	•	Vercel
Core Application and Data
	•	Supabase PostgreSQL
	•	Supabase Authentication
	•	Supabase Row Level Security
	•	Supabase Storage when appropriate
	•	Supabase Realtime only where operationally useful
Backend and Workflow Execution
	•	Python
	•	FastAPI for long-running or integration-facing backend services
	•	Scheduled Python workers
	•	Hetzner VPS
	•	Docker Compose where containerization improves repeatability
	•	Systemd or Docker restart policies for production processes
	•	Cron only for simple stable schedules
Source Control and Deployment
	•	GitHub
	•	GitHub Actions where useful
	•	Vercel deployment for the Astro application
	•	Controlled deployment to Hetzner for backend workers and services
Messaging and Communications
	•	Resend for transactional email
	•	An SMS or phone provider only when lead or communication products require it
	•	Email provider integrations where client inbox access is required
Payments and Billing
	•	Stripe
	•	Stripe Checkout, Billing, and webhooks as required
	•	Product access controlled through platform entitlements rather than direct Stripe checks throughout the application
External Data Sources
	•	Google Search Console API
	•	Google Analytics Data API
	•	Google Business Profile APIs
	•	Google Places and Maps APIs
	•	GitHub APIs
	•	Vercel APIs
	•	Supported CRM, scheduling, phone, and form systems as required
AI Providers
The platform may support:
	•	Anthropic
	•	OpenAI
	•	Google
	•	OpenRouter
	•	Specialized models
	•	Self-hosted or local models where justified
	•	Future providers through the same internal interface
No product should depend directly on one provider.
 
⸻
 
4.4 Components Not Required Initially
The initial platform does not require:
	•	Kubernetes
	•	A large microservice architecture
	•	Apache Kafka
	•	A dedicated event-streaming platform
	•	Redis unless a specific validated need exists
	•	Trigger.dev
	•	Temporal
	•	Airflow
	•	A separate vector database
	•	A dedicated API gateway product
	•	A service mesh
	•	Multiple cloud providers
	•	A proprietary model-hosting environment
	•	A dedicated enterprise data warehouse
	•	A general-purpose no-code automation platform
These tools may be introduced later when a defined operational limitation justifies them.
They should not be added merely because they are common in larger systems.
 
⸻
 
4.5 High-Level System Architecture
The initial architecture is divided into six layers.
Users
    ↓
Application Layer
    ↓
Core Platform Services
    ↓
Product Services
    ↓
Workflow and Integration Layer
    ↓
Data, Providers, and External Systems
A more detailed view is:
┌─────────────────────────────────────────────┐
│                  Users                      │
│                                             │
│  LILOs Staff        Client Users            │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│          Astro Application on Vercel        │
│                                             │
│  Agency Console      Client Portal          │
│  Approval Queues     Dashboards             │
│  Product Settings    Reports                │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│            Core Platform Services           │
│                                             │
│  Auth               Organizations           │
│  Locations          Permissions             │
│  Entitlements       Configuration           │
│  Integrations       Audit Logs              │
│  Notifications      AI Gateway              │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│              Product Services               │
│                                             │
│  SEO      GBP      Reviews      Content     │
│  Leads    Automations          Insights     │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│        Workflow and Execution Layer         │
│                                             │
│  Schedules          Event Handlers          │
│  Job Workers        Approvals               │
│  Retries            Publishing              │
│  Notifications      External Actions        │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│       Data and External Integrations        │
│                                             │
│ Supabase       Google APIs      GitHub       │
│ Vercel         Resend           Stripe       │
│ CRMs           SMS              AI Models    │
└─────────────────────────────────────────────┘
 
⸻
 
4.6 Architectural Style
The initial system should be implemented as a modular monolith with external workers.
This means:
	•	One primary application codebase may contain the shared platform and product modules.
	•	Product boundaries must remain explicit inside the codebase.
	•	Background and integration-heavy work may run as separate worker processes.
	•	The platform should not begin as dozens of independently deployed services.
	•	Modules should be separable later if scale or operational requirements justify it.
This approach provides:
	•	Lower operational complexity
	•	Faster development
	•	Easier local testing
	•	Shared typing and validation
	•	Simpler deployment
	•	Clearer debugging
	•	Lower infrastructure cost
The system must still preserve internal module boundaries so it does not become a tightly coupled monolith.
 
⸻
 
4.7 Recommended Repository Structure
The preferred initial structure is a monorepo.
lilos-platform/
│
├── apps/
│   ├── web/
│   │   ├── src/
│   │   ├── public/
│   │   └── astro.config.mjs
│   │
│   └── api/
│       ├── app/
│       ├── routes/
│       ├── services/
│       └── main.py
│
├── workers/
│   ├── scheduler/
│   ├── seo/
│   ├── gbp/
│   ├── reviews/
│   ├── content/
│   ├── leads/
│   ├── reporting/
│   └── notifications/
│
├── packages/
│   ├── contracts/
│   ├── configuration/
│   ├── database/
│   ├── permissions/
│   ├── integrations/
│   ├── ai/
│   ├── audit/
│   └── shared/
│
├── products/
│   ├── seo/
│   ├── gbp/
│   ├── reviews/
│   ├── content/
│   ├── leads/
│   ├── automations/
│   └── insights/
│
├── infrastructure/
│   ├── docker/
│   ├── systemd/
│   ├── scripts/
│   └── deployment/
│
├── supabase/
│   ├── migrations/
│   ├── seed/
│   └── functions/
│
├── prompts/
│   ├── seo/
│   ├── gbp/
│   ├── reviews/
│   ├── content/
│   └── leads/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── workflows/
│   └── acceptance/
│
└── docs/
    ├── product/
    ├── architecture/
    ├── products/
    ├── workflows/
    ├── api/
    └── decisions/
This exact structure may be refined during implementation, but the separation of responsibilities must be preserved.
 
⸻
 
4.8 Frontend Architecture
4.8.1 Application Responsibilities
The Astro application is responsible for:
	•	Agency operations interface
	•	Client portal
	•	Authentication flows
	•	Product navigation
	•	Configuration forms
	•	Approval queues
	•	Workflow status
	•	Dashboards
	•	Reports
	•	Integration connection flows
	•	User and permission management
	•	Billing and subscription interfaces
	•	Operational alerts
The frontend must not contain sensitive provider credentials or trusted business logic.
4.8.2 Server Rendering and API Access
Astro server-side rendering may be used where appropriate.
The frontend should access data through:
	•	Supabase with Row Level Security for approved direct access patterns
	•	Server-side application endpoints
	•	The FastAPI backend for privileged operations, integrations, or complex workflows
The application must not rely on frontend-only authorization.
Every protected operation must be validated server-side.
4.8.3 Agency and Client Interfaces
The application may use one shared codebase with separate route groups.
Example:
/app/agency/
/app/client/
/app/admin/
Agency users may access cross-client functions according to their role.
Client users must be restricted to authorized organizations, locations, and products.
4.8.4 Frontend State
Persistent business state belongs in Supabase.
Temporary interface state may remain in the browser.
The frontend must not become the source of truth for:
	•	Workflow status
	•	Approval state
	•	Permissions
	•	Product access
	•	Integration health
	•	Publication history
	•	AI execution records
 
⸻
 
4.9 Backend API Architecture
4.9.1 Purpose
The backend API manages operations that should not execute directly in the browser or through unrestricted database access.
These include:
	•	Privileged business operations
	•	Integration calls
	•	Credential access
	•	Workflow creation
	•	Publishing actions
	•	AI requests
	•	Webhook processing
	•	Complex validation
	•	File processing
	•	Cross-product orchestration
4.9.2 Recommended Framework
FastAPI is the preferred initial backend framework because the existing automation environment is Python-based.
It should provide:
	•	Typed request models
	•	Typed response models
	•	Automatic API documentation
	•	Dependency injection
	•	Authentication middleware
	•	Structured error handling
	•	Clear separation between routes and business services
4.9.3 API Responsibility Rule
API route handlers should remain thin.
A route handler should:
	1.	Authenticate the caller.
	2.	Validate permissions.
	3.	Validate the request.
	4.	Call the appropriate application service.
	5.	Return a structured response.
Business logic should not be embedded directly in route files.
4.9.4 Internal Service Contracts
Product services should expose stable internal interfaces.
Example:
class ReviewResponseService:
    def generate_response(...)
    def submit_for_approval(...)
    def approve_response(...)
    def publish_response(...)
    def escalate_review(...)
The exact implementation may change while the interface remains stable.
 
⸻
 
4.10 Multi-Tenant Architecture
4.10.1 Tenant Model
The platform is multi-tenant.
The primary tenant boundary is the organization.
Data may also be scoped to:
	•	Location
	•	Product
	•	User
	•	Workflow
	•	Integration
Every tenant-owned record must include an organization reference.
Location-specific records must also include a location reference.
4.10.2 Data Isolation
Tenant isolation must be enforced through:
	•	Database foreign keys
	•	Row Level Security
	•	Application authorization
	•	Service-level permission checks
	•	Integration scoping
	•	Test coverage
The interface alone is not a security boundary.
4.10.3 Agency Access
LILOs staff may have cross-tenant access based on internal roles.
Cross-tenant access must be:
	•	Explicitly granted
	•	Logged
	•	Limited to business need
	•	Revocable
	•	Distinguishable from client access
4.10.4 No Client-Specific Tables
The system must not create separate tables or schemas for ordinary clients.
Client-specific behavior belongs in:
	•	Configuration
	•	Policies
	•	Templates
	•	Product entitlements
	•	Workflow settings
	•	Industry presets
 
⸻
 
4.11 Authentication and Authorization Architecture
4.11.1 Authentication
Supabase Authentication should manage:
	•	User accounts
	•	Login
	•	Password reset
	•	Session management
	•	Supported OAuth providers
	•	Email verification
	•	Multi-factor authentication when introduced
4.11.2 Authorization Layers
Authorization should be evaluated through four separate questions:
	1.	Is the user authenticated?
	2.	Does the user belong to the organization?
	3.	Does the user have permission for the action?
	4.	Does the organization or location have the required product entitlement?
All four conditions may be required.
4.11.3 Role Categories
Initial roles may include:
Internal Roles
	•	Platform owner
	•	Platform administrator
	•	Agency administrator
	•	Account manager
	•	SEO operator
	•	Content operator
	•	Support user
	•	Read-only internal user
Client Roles
	•	Client owner
	•	Client administrator
	•	Location manager
	•	Marketing manager
	•	Approver
	•	Reporting-only user
Roles should map to explicit permissions rather than relying only on role names.
4.11.4 Permission Format
Permissions should be action-based.
Examples:
organizations.read
organizations.manage

products.enable
products.configure

seo.read
seo.run_analysis
seo.approve_recommendation

gbp.read
gbp.generate_post
gbp.approve_post
gbp.publish_post

reviews.read
reviews.generate_response
reviews.approve_response
reviews.publish_response

content.read
content.create
content.approve
content.publish

leads.read
leads.respond
leads.assign

integrations.read
integrations.manage

billing.read
billing.manage
This allows role definitions to evolve without rewriting product logic.
 
⸻
 
4.12 Data Architecture
4.12.1 Primary Database
Supabase PostgreSQL is the primary system of record.
It stores:
	•	Organizations
	•	Locations
	•	Users
	•	Memberships
	•	Permissions
	•	Entitlements
	•	Product configuration
	•	Workflow definitions
	•	Workflow executions
	•	Approvals
	•	Integration metadata
	•	Sync status
	•	Audit records
	•	AI execution metadata
	•	Reports
	•	Leads
	•	Reviews
	•	Content records
	•	SEO recommendations
	•	GBP records
4.12.2 External Data Storage
Large or raw external datasets should not automatically be duplicated in full.
The platform should store:
	•	Data needed for operation
	•	Data needed for reporting
	•	Data needed for historical comparison
	•	Provider identifiers
	•	Synchronization metadata
	•	Relevant normalized metrics
Raw payloads may be retained temporarily for debugging or compliance according to a retention policy.
4.12.3 File Storage
Supabase Storage or another approved object store may contain:
	•	Report exports
	•	Generated assets
	•	Content attachments
	•	Client uploads
	•	Workflow artifacts
	•	Temporary import files
Files must be scoped by organization and protected by access policies.
4.12.4 Database Change Management
All database changes must use version-controlled migrations.
Direct undocumented production schema changes are prohibited.
Every migration should include:
	•	Purpose
	•	Forward change
	•	Rollback or recovery approach
	•	Data migration requirements
	•	Index impact
	•	Security-policy impact
 
⸻
 
4.13 Integration Architecture
4.13.1 Integration Adapter Pattern
Every external provider must be accessed through an internal adapter.
Example:
GBP Product
    ↓
BusinessProfileProvider Interface
    ↓
Google Business Profile Adapter
Product logic must not directly depend on provider-specific response formats.
4.13.2 Adapter Responsibilities
Adapters should handle:
	•	Authentication
	•	Provider request formatting
	•	Provider response normalization
	•	Pagination
	•	Rate limits
	•	Provider-specific retries
	•	Error translation
	•	Data mapping
	•	Health status
4.13.3 Credential Handling
Credentials and refresh tokens must not be stored:
	•	In source code
	•	In client-visible database fields
	•	In prompts
	•	In logs
	•	In frontend bundles
The platform should store encrypted credentials or secure references to credentials.
Access must be restricted to approved backend services.
4.13.4 Integration Health
Every integration should have an explicit status.
Recommended statuses:
	•	Connected
	•	Authorization required
	•	Expired
	•	Permission denied
	•	Rate limited
	•	Degraded
	•	Provider unavailable
	•	Disconnected
The platform should record:
	•	Last successful connection
	•	Last successful synchronization
	•	Last failure
	•	Required remediation
	•	Available account scopes
 
⸻
 
4.14 Workflow Architecture
4.14.1 Workflow Types
The platform must support four workflow types:
Scheduled
Runs at a defined interval.
Examples:
	•	Weekly GSC opportunity analysis
	•	Daily GBP performance synchronization
	•	Monthly report generation
Event-Driven
Runs in response to a platform or provider event.
Examples:
	•	New review received
	•	New lead submitted
	•	Stripe subscription updated
	•	Content approved
Manual
Started by an authorized user.
Examples:
	•	Run an SEO analysis
	•	Regenerate a response
	•	Republish content
Approval-Dependent
Pauses until an authorized user approves, rejects, or requests revision.
Examples:
	•	GBP post publication
	•	Review response publication
	•	Website content publication
4.14.2 Workflow Record
Every workflow execution should record:
	•	Workflow type
	•	Organization
	•	Location
	•	Product
	•	Trigger
	•	Input references
	•	Start time
	•	Completion time
	•	Current status
	•	Attempt count
	•	Approval state
	•	Output references
	•	Errors
	•	Cost where relevant
	•	AI model where relevant
4.14.3 Workflow Statuses
Recommended statuses:
queued
running
waiting_for_approval
approved
rejected
retry_scheduled
completed
partially_completed
failed
cancelled
expired
4.14.4 Retry Policy
Retries should depend on failure type.
Retryable failures may include:
	•	Temporary provider outage
	•	Timeout
	•	Network failure
	•	Rate limit
	•	Temporary database conflict
Non-retryable failures may include:
	•	Invalid permissions
	•	Missing configuration
	•	Revoked authorization
	•	Invalid content
	•	Policy rejection
	•	Unsupported request
The platform must not retry indefinitely.
4.14.5 Idempotency
External actions must be idempotent where possible.
The system must prevent accidental duplicate:
	•	GBP posts
	•	Review responses
	•	Customer messages
	•	Content publication
	•	Billing actions
	•	Lead acknowledgments
Every external action should use an idempotency key or an equivalent duplicate-prevention strategy.
 
⸻
 
4.15 Event Architecture
The initial platform does not require a dedicated event broker.
Internal events may be stored in PostgreSQL and processed by workers.
Example events:
organization.created
product.enabled
integration.connected
integration.failed
seo.opportunity_created
content.brief_approved
content.published
gbp.post_approved
gbp.post_published
review.received
review.response_approved
review.response_published
lead.created
lead.assigned
lead.responded
workflow.failed
subscription.updated
Events should contain:
	•	Event ID
	•	Event type
	•	Organization ID
	•	Location ID where applicable
	•	Product
	•	Actor
	•	Timestamp
	•	Payload reference
	•	Processing status
The architecture should allow migration to a dedicated message system later without rewriting product logic.
 
⸻
 
4.16 AI Architecture Boundary
4.16.1 Product Access
Products access AI through one internal AI service.
They must not import provider SDKs directly into product business logic.
Correct:
Product Service
    ↓
AI Gateway
    ↓
Selected Provider
Incorrect:
GBP Product
    ↓
Anthropic SDK
4.16.2 AI Request Structure
Every AI request should identify:
	•	Task type
	•	Organization
	•	Product
	•	Prompt version
	•	Required output schema
	•	Candidate model policy
	•	Cost limit
	•	Timeout
	•	Approval requirement
	•	Input sensitivity
	•	Fallback behavior
4.16.3 Structured Output
AI outputs should use validated structured formats whenever they are consumed by software.
Freeform text should not directly control:
	•	Permissions
	•	Publication state
	•	Billing
	•	Customer consent
	•	Workflow state
	•	Security decisions
	•	Database mutations
4.16.4 Model Selection
Model selection should be task-based.
Examples:
	•	Classification may use a low-cost model.
	•	Long-form SEO reasoning may use a stronger reasoning model.
	•	Review responses may use a model optimized for concise writing.
	•	Code generation may use a coding-specialized model.
	•	Image analysis may use a multimodal model.
The model name should be configuration, not code.
 
⸻
 
4.17 Approval Architecture
4.17.1 Approval as a Shared Service
Approval workflows should use one shared platform service.
Approval records should include:
	•	Organization
	•	Location
	•	Product
	•	Item type
	•	Item ID
	•	Requested action
	•	Requested by
	•	Required approver role
	•	Status
	•	Reviewer
	•	Review time
	•	Comments
	•	Revision request
	•	Expiration
4.17.2 Approval Policies
Approval policies may be configured by:
	•	Product
	•	Organization
	•	Location
	•	Action type
	•	Risk level
	•	AI confidence
	•	User role
Examples:
	•	All website publications require LILOs approval.
	•	Four- and five-star review responses may publish automatically.
	•	One- and two-star reviews always require manual approval.
	•	GBP posts require client approval for one organization but not another.
	•	Lead acknowledgments may send automatically, but quotes may not.
4.17.3 Approval Integrity
The content approved must match the content published.
Any material modification after approval must invalidate the approval or create a new revision.
 
⸻
 
4.18 Notification Architecture
The platform should support:
	•	In-app notifications
	•	Email notifications
	•	Optional SMS notifications
	•	Internal operational alerts
	•	Client approval reminders
	•	Failure alerts
	•	Integration-expiration alerts
	•	Scheduled summaries
Notification behavior should be configurable by:
	•	User
	•	Organization
	•	Product
	•	Event type
	•	Severity
	•	Delivery channel
Notifications must avoid exposing sensitive client information in unsecured channels.
 
⸻
 
4.19 Reporting Architecture
Operational product data should be written to normalized application tables.
Reporting views may be created for:
	•	SEO performance
	•	GBP performance
	•	Review performance
	•	Content production
	•	Lead performance
	•	Workflow reliability
	•	Product usage
	•	AI cost and quality
	•	Agency portfolio health
The initial platform should use PostgreSQL views and materialized views where appropriate.
A separate warehouse should only be introduced when:
	•	Query performance becomes inadequate
	•	Data volume materially exceeds transactional use
	•	Cross-source historical analysis requires it
	•	Reporting workloads interfere with application workloads
 
⸻
 
4.20 Deployment Architecture
4.20.1 Vercel
Vercel should host:
	•	Astro frontend
	•	Server-rendered application routes where appropriate
	•	Lightweight application endpoints
	•	Preview deployments
Vercel should not be relied upon for:
	•	Persistent background workers
	•	Long-running jobs
	•	Continuous polling
	•	Heavy data processing
	•	Long external publishing workflows
4.20.2 Supabase
Supabase should host:
	•	PostgreSQL
	•	Authentication
	•	Row Level Security
	•	Storage
	•	Database functions where appropriate
	•	Webhooks or database-triggered actions where appropriate
Complex business workflows should not be embedded entirely in database triggers.
4.20.3 Hetzner
Hetzner should host:
	•	FastAPI backend
	•	Scheduled workers
	•	Integration workers
	•	Long-running jobs
	•	Data synchronization
	•	AI orchestration
	•	Publication workers
	•	Operational scripts
The initial deployment may use one appropriately sized VPS with clear process separation.
4.20.4 Process Layout
Example:
Hetzner VPS

├── lilos-api
├── scheduler-worker
├── seo-worker
├── gbp-worker
├── review-worker
├── content-worker
├── notification-worker
└── monitoring
These may initially run in Docker Compose or as managed systemd processes.
They do not need separate servers.
 
⸻
 
4.21 Environment Separation
The platform must use separate environments.
At minimum:
	•	Local
	•	Staging
	•	Production
Each environment should have separate:
	•	Database
	•	Authentication configuration
	•	Secrets
	•	External provider credentials where possible
	•	Webhook endpoints
	•	Storage
	•	AI usage configuration
	•	Deployment settings
Production client data must not be copied into local development environments without an approved sanitization process.
 
⸻
 
4.22 Secret Management
Secrets include:
	•	API keys
	•	OAuth client secrets
	•	Refresh tokens
	•	Database service keys
	•	Stripe secrets
	•	Resend keys
	•	SMS provider credentials
	•	AI provider credentials
	•	Encryption keys
Secrets should be stored through:
	•	Vercel environment variables
	•	Hetzner server environment or approved secret storage
	•	Supabase secrets where applicable
	•	GitHub repository secrets for deployment
Secrets must never be committed to Git.
Secret rotation procedures must be documented.
 
⸻
 
4.23 Logging and Observability Architecture
4.23.1 Structured Logs
Application and worker logs should be structured.
Each log should include where applicable:
	•	Timestamp
	•	Environment
	•	Service
	•	Organization
	•	Location
	•	Product
	•	Workflow ID
	•	Request ID
	•	Severity
	•	Event
	•	Error code
4.23.2 Correlation IDs
Every workflow and API request should have a correlation ID.
The same ID should follow the operation across:
	•	Frontend request
	•	Backend service
	•	Worker
	•	Integration call
	•	AI request
	•	Audit record
4.23.3 Monitoring Priorities
Initial monitoring should focus on:
	•	API availability
	•	Worker availability
	•	Failed workflows
	•	Queue age
	•	Database connectivity
	•	Integration errors
	•	Credential expiration
	•	AI provider failures
	•	Cost anomalies
	•	Failed publications
	•	Data synchronization delays
4.23.4 Error Visibility
A failed workflow should never disappear only into a server log.
Operational failures must appear in the agency console with:
	•	Affected client
	•	Affected product
	•	Failure time
	•	Failure reason
	•	Retry state
	•	Required action
 
⸻
 
4.24 Security Architecture
Security requirements include:
	•	Row Level Security
	•	Server-side permission enforcement
	•	Encrypted transport
	•	Protected secrets
	•	Minimal provider scopes
	•	Audit logging
	•	Session expiration
	•	Controlled internal access
	•	Input validation
	•	Output encoding
	•	Rate limiting
	•	Webhook signature validation
	•	File validation
	•	Dependency maintenance
	•	Backup and recovery
The architecture must assume that client data is sensitive even where it is not legally classified as protected data.
 
⸻
 
4.25 Backup and Recovery
The platform must maintain:
	•	Database backups
	•	Migration history
	•	Source control history
	•	Configuration export capability
	•	Integration reconnection procedures
	•	Worker deployment rollback procedures
	•	Incident documentation
Recovery objectives should initially prioritize:
	1.	Prevent permanent client-data loss.
	2.	Restore platform access.
	3.	Restore workflow execution.
	4.	Reconcile missed or partially completed external actions.
	5.	Confirm that duplicate external actions were not created.
 
⸻
 
4.26 Existing Script Migration Strategy
The platform should not begin by discarding existing working scripts.
Existing scripts should be evaluated and categorized.
Category A — Reusable With Minimal Change
The script already performs a valid product function and can be wrapped with:
	•	Standard configuration
	•	Structured inputs
	•	Structured outputs
	•	Logging
	•	Execution records
	•	Error handling
Category B — Requires Refactoring
The script provides useful logic but contains:
	•	Hardcoded client data
	•	Direct credentials
	•	Embedded prompts
	•	Weak error handling
	•	No structured output
	•	No audit trail
Category C — Replace
The script should be replaced when it is:
	•	Fundamentally unreliable
	•	Duplicative
	•	Unsafe
	•	Too tightly coupled
	•	Based on deprecated APIs
	•	Incompatible with the platform model
The migration goal is not code preservation for its own sake.
The goal is to retain proven behavior while moving execution into a standardized platform.
 
⸻
 
4.27 Architecture Without Hermes or Similar Operator
In the standard architecture, users operate the platform through:
	•	Agency console
	•	Client portal
	•	API
	•	Scheduled workflows
	•	Event-driven workflows
	•	Notifications
	•	Approval queues
The system does not require a conversational operator.
User
    ↓
Application or API
    ↓
Product Service
    ↓
Workflow
    ↓
Integration or AI Gateway
All platform functionality must be available through these standard interfaces.
 
⸻
 
4.28 Architecture With Hermes or Similar Operator
An operator-enabled architecture adds a conversational control layer.
User
    ↓
Hermes or Similar Operator
    ↓
Authorized Platform Tools
    ↓
Product Service
    ↓
Workflow
    ↓
Integration or AI Gateway
The operator may be given tools such as:
	•	Read client status
	•	Read workflow failures
	•	Run an approved analysis
	•	Create a draft
	•	Submit an item for approval
	•	Retrieve a report
	•	Summarize system health
	•	Propose configuration changes
The operator should not receive unrestricted:
	•	Database access
	•	Shell access to all infrastructure
	•	Production credential access
	•	Direct billing authority
	•	Permission-management authority
	•	Unlogged publication authority
	•	Unrestricted client communication authority
Every operator action must pass through the same:
	•	Authentication
	•	Permissions
	•	Entitlements
	•	Validation
	•	Approval policies
	•	Audit logging
The operator is an optional interface, not a privileged bypass.
 
⸻
 
4.29 Architecture Decision Rules
When making future technical decisions, use the following order:
	1.	Can the requirement be solved within the existing approved stack?
	2.	Can it be implemented through configuration?
	3.	Can it be implemented as part of an existing product service?
	4.	Can it reuse a shared platform capability?
	5.	Does it require a new persistent service?
	6.	Does the operational value justify the added cost and complexity?
	7.	Can the new component be replaced later?
	8.	Does it introduce a new security or reliability burden?
	9.	Does it preserve multi-tenant isolation?
	10.	Does it remain operable without one AI provider or operator?
A new vendor or infrastructure component should not be added unless these questions have been answered.
 
⸻
 
4.30 Initial Architecture Build Order
The recommended build order is:
Stage 1 — Foundation
	•	Create monorepo
	•	Establish local, staging, and production environments
	•	Configure Supabase
	•	Configure authentication
	•	Create organizations and locations
	•	Create memberships and permissions
	•	Create product entitlements
	•	Create audit framework
	•	Create configuration framework
Stage 2 — Backend and Workflows
	•	Establish FastAPI backend
	•	Establish worker execution pattern
	•	Create workflow records
	•	Create event records
	•	Create retry and error handling
	•	Add integration-status tracking
	•	Add notification framework
Stage 3 — AI Gateway
	•	Create provider interface
	•	Add model registry
	•	Add prompt registry
	•	Add structured-output validation
	•	Add cost and execution tracking
	•	Add fallback handling
Stage 4 — First Product Integration
	•	Integrate one existing SEO workflow
	•	Add client configuration
	•	Add execution history
	•	Add approval or recommendation state
	•	Add agency interface
	•	Validate multi-client operation
Stage 5 — Expand Products
	•	GBP
	•	Reviews
	•	Content
	•	Insights
	•	Leads
	•	Automations
The architecture should be validated with one end-to-end workflow before every existing script is migrated.
 
⸻
 
4.31 Architectural Guardrails
The following are prohibited unless the architecture is formally revised:
	1.	Hardcoding client IDs or business rules in product code
	2.	Calling AI providers directly from product modules
	3.	Embedding production prompts in application logic
	4.	Storing secrets in the database without protection
	5.	Using frontend visibility as the only permission control
	6.	Creating separate application deployments for ordinary clients
	7.	Creating duplicate integration connections for every product
	8.	Publishing external content without an audit record
	9.	Allowing one failed job to halt unrelated workflows
	10.	Adding infrastructure without a documented need
	11.	Allowing an AI operator to bypass platform permissions
	12.	Treating Stripe as the source of application authorization
	13.	Running untracked cron jobs outside the workflow system
	14.	Allowing silent workflow failure
	15.	Building client-specific core-product forks
 
⸻
 
4.32 Section Decisions
This section establishes the following decisions:
	1.	The initial architecture uses Astro, Vercel, Supabase, Python, FastAPI, Hetzner, GitHub, Resend, Stripe, and provider APIs.
	2.	The initial implementation is a modular monolith with external workers.
	3.	The project should use a monorepo.
	4.	Supabase PostgreSQL is the primary system of record.
	5.	Hetzner runs long-lived backend processes and workflows.
	6.	Vercel hosts the user-facing Astro application.
	7.	Product services must use shared platform services.
	8.	Product logic must not directly depend on third-party AI providers.
	9.	External integrations must use internal adapters.
	10.	All important workflows must be tracked, retryable where appropriate, and auditable.
	11.	Product entitlements and user permissions are independent.
	12.	Tenant isolation must be enforced in both the database and application.
	13.	Existing LILOs scripts should be migrated selectively rather than discarded automatically.
	14.	A dedicated workflow platform is not required initially.
	15.	Hermes or a similar operator is optional and may only access the platform through authorized, audited tools.
	16.	The platform must remain fully functional without an AI operator.
	17.	Infrastructure complexity must be justified by a demonstrated operational requirement.
	18.	The architecture should be validated through one complete end-to-end product workflow before broad migration.


---

Section 5 — Data Model and Database Design
5.1 Purpose of This Section
This section defines the logical data model for the LILOs platform.
It establishes:
	•	Core entities
	•	Tenant ownership
	•	Organization and location relationships
	•	User membership and permissions
	•	Product entitlements
	•	Client and product configuration
	•	Integration records
	•	Workflow execution
	•	Approval records
	•	AI providers, models, prompts, and executions
	•	Audit logging
	•	Product-specific records
	•	Data retention and deletion rules
	•	Database constraints and indexing expectations
This section is a logical specification.
Exact SQL, migration files, generated types, and Row Level Security policies should be produced during implementation from this specification.
 
⸻
 
5.2 Database Principles
The database must follow these principles.
5.2.1 PostgreSQL Is the System of Record
Supabase PostgreSQL is the authoritative source for:
	•	Organizations
	•	Locations
	•	Users and memberships
	•	Product access
	•	Configuration
	•	Integration status
	•	Workflow state
	•	Approvals
	•	Audit records
	•	AI execution metadata
	•	Product records
	•	Operational reporting data
Third-party providers remain authoritative for data they own, but LILOs stores the normalized data required to operate and report on the platform.
 
⸻
 
5.2.2 Every Tenant-Owned Record Has an Organization
Every client-owned record must include:
organization_id
Records tied to a specific location must also include:
location_id
A record must not rely on an indirect relationship alone to establish tenant ownership when a direct organization reference materially improves security and query safety.
 
⸻
 
5.2.3 Use Stable Internal Identifiers
Primary keys should use UUIDs unless there is a documented reason to use another type.
External provider identifiers must be stored separately.
Example:
id                         Internal LILOs UUID
google_location_id         External Google identifier
stripe_customer_id         External Stripe identifier
github_repository_id       External GitHub identifier
External identifiers must not serve as primary keys.
 
⸻
 
5.2.4 Configuration Must Not Become Unstructured Storage
JSONB may be used for:
	•	Flexible provider metadata
	•	Product settings that vary materially by integration
	•	Versioned workflow inputs and outputs
	•	Raw provider payload references
	•	Non-critical extensible fields
JSONB should not replace well-defined columns for fields that are:
	•	Frequently queried
	•	Used for permissions
	•	Used for billing
	•	Used for state transitions
	•	Used for joins
	•	Required for reporting
	•	Required for integrity
 
⸻
 
5.2.5 States Must Be Explicit
Important records must use defined state fields rather than infer state from missing values.
Examples:
	•	Product status
	•	Integration status
	•	Workflow status
	•	Approval status
	•	Publication status
	•	Lead status
	•	Content status
	•	Review-response status
State values should be enforced through database enums, check constraints, or validated reference tables.
 
⸻
 
5.2.6 Records Should Be Preserved for Auditability
Operational records should normally be archived rather than physically deleted.
Examples include:
	•	Workflow executions
	•	Approvals
	•	Publications
	•	AI executions
	•	Audit events
	•	Lead communications
	•	Review responses
	•	Product configuration history
Hard deletion should be limited to:
	•	Legally required deletion
	•	Duplicate test data
	•	Ephemeral records past retention
	•	Records explicitly approved for permanent removal
 
⸻
 
5.3 Naming Standards
Database identifiers should use:
	•	snake_case
	•	Singular field names
	•	Plural table names
	•	Clear foreign-key suffixes
	•	UTC timestamps
Examples:
organizations
organization_id
created_at
updated_at
archived_at
external_account_id
Every major table should generally include:
id
created_at
updated_at
Tenant-owned tables should generally include:
organization_id
Location-owned tables should generally include:
location_id
Records that support archival should include:
archived_at
Records created or changed by a user may include:
created_by_user_id
updated_by_user_id
 
⸻
 
5.4 Core Entity Relationship Overview
Organization
├── Locations
├── Memberships
│   └── Users
├── Product Entitlements
├── Product Configurations
├── Integration Connections
├── Workflows
│   └── Workflow Executions
├── Approvals
├── Notifications
├── Audit Events
├── AI Executions
├── SEO Records
├── GBP Records
├── Review Records
├── Content Records
├── Lead Records
└── Reporting Records
The organization is the primary tenant boundary.
A location is an operating unit within the organization.
Products, integrations, users, workflows, and data may apply at either organization or location scope.
 
⸻
 
5.5 Core Platform Tables
5.5.1 
organizations
Purpose
Represents a customer account, internal test account, partner account, or LILOs-owned operating account.
Required Fields
id
name
slug
organization_type
status
timezone
default_currency
industry_id
created_at
updated_at
archived_at
Recommended Fields
legal_name
website_url
primary_contact_name
primary_contact_email
primary_contact_phone
billing_email
external_reference
onboarding_status
account_manager_user_id
metadata
Organization Types
Recommended values:
client
internal
partner
demo
test
Organization Statuses
Recommended values:
prospect
onboarding
active
paused
suspended
offboarding
archived
Rules
	•	slug must be unique.
	•	The organization timezone is the default for schedules and reporting.
	•	A location may override the organization timezone.
	•	An archived organization must not execute active workflows.
	•	Suspension must not delete data.
	•	Internal and test organizations must be clearly distinguishable from production clients.
 
⸻
 
5.5.2 
industries
Purpose
Defines reusable industry profiles.
Required Fields
id
key
name
status
created_at
updated_at
Initial Industry Values
restaurant
bar
home_services
professional_services
general_local_business
Recommended Fields
description
default_configuration
default_risk_policy
default_content_policy
Industry records provide defaults.
They must not contain client-specific settings.
 
⸻
 
5.5.3 
locations
Purpose
Represents a physical location, service-area operation, branch, venue, or other independently configurable business unit.
Required Fields
id
organization_id
name
slug
location_type
status
timezone
created_at
updated_at
archived_at
Recommended Fields
business_name
address_line_1
address_line_2
city
region
postal_code
country_code
latitude
longitude
phone
website_url
public_email
service_area_description
is_primary
metadata
Location Types
Recommended values:
physical
service_area
hybrid
virtual
department
Location Statuses
Recommended values:
setup_required
active
paused
closed_temporarily
closed_permanently
archived
Rules
	•	A location belongs to exactly one organization.
	•	Location slugs must be unique within an organization.
	•	A multi-location organization may designate one primary location.
	•	A service-area business may have a location record without publishing a street address.
	•	Closed locations retain historical reporting data.
	•	Location deletion must not cascade-delete historical operational records.
 
⸻
 
5.5.4 
organization_profiles
Purpose
Stores business context that may be shared across products.
Fields
id
organization_id
brand_name
brand_summary
business_description
value_proposition
target_customer
primary_services
approved_claims
prohibited_claims
tone_guidelines
legal_disclaimers
default_call_to_action
created_at
updated_at
Rules
	•	Approved claims must be treated as controlled business data.
	•	AI prompts may reference this record but must not modify it automatically.
	•	Changes should create an audit event.
	•	Location-specific overrides belong in a separate location profile.
 
⸻
 
5.5.5 
location_profiles
Purpose
Stores location-specific business context.
Fields
id
organization_id
location_id
local_description
primary_services
service_area
local_landmarks
local_references
approved_claims
prohibited_claims
tone_overrides
call_to_action_override
created_at
updated_at
Rules
	•	Location values override organization profile values where defined.
	•	Local references should be factual and manually approved when used as persistent context.
	•	AI-generated location information must not be written here without approval.
 
⸻
 
5.6 User and Membership Tables
5.6.1 
user_profiles
Purpose
Extends the Supabase authentication user record with platform-specific profile data.
Fields
id
auth_user_id
display_name
first_name
last_name
email
phone
status
is_internal
created_at
updated_at
last_active_at
Rules
	•	auth_user_id must uniquely reference the Supabase Auth user.
	•	Authentication credentials remain managed by Supabase Auth.
	•	The profile must not store passwords or authentication secrets.
	•	Internal status does not itself grant cross-tenant access.
 
⸻
 
5.6.2 
organization_memberships
Purpose
Connects users to organizations.
Fields
id
organization_id
user_id
membership_type
status
invited_at
accepted_at
created_at
updated_at
Membership Types
internal
client
partner
support
Membership Statuses
invited
active
suspended
revoked
expired
Rules
	•	A user may belong to multiple organizations.
	•	Membership does not automatically grant every product permission.
	•	Revoking membership must terminate organization access.
	•	Historical actions by revoked users must remain attributable.
 
⸻
 
5.6.3 
roles
Purpose
Defines named permission bundles.
Fields
id
key
name
scope_type
description
is_system_role
created_at
updated_at
Scope Types
platform
organization
location
Rules
	•	System roles may not be edited casually in production.
	•	Custom roles may be added later.
	•	Product logic must evaluate permissions, not role names alone.
 
⸻
 
5.6.4 
permissions
Purpose
Defines individual authorized actions.
Fields
id
key
product_key
resource
action
description
created_at
Example keys:
seo.read
seo.run_analysis
gbp.approve_post
reviews.publish_response
integrations.manage
billing.read
 
⸻
 
5.6.5 
role_permissions
Purpose
Maps roles to permissions.
Fields
role_id
permission_id
created_at
The pair must be unique.
 
⸻
 
5.6.6 
membership_roles
Purpose
Assigns roles to organization memberships.
Fields
id
membership_id
role_id
location_id
created_at
expires_at
Rules
	•	A role may apply organization-wide or to a single location.
	•	Location-scoped assignments must not grant access to sibling locations.
	•	Expired assignments must not authorize actions.
	•	Permission evaluation must account for both membership and role status.
 
⸻
 
5.7 Product Catalog and Entitlement Tables
5.7.1 
products
Purpose
Defines products available on the platform.
Initial Records
core
seo
gbp
reviews
content
leads
automations
insights
Fields
id
key
name
description
status
version
created_at
updated_at
Product Statuses
planned
internal
beta
active
deprecated
retired
 
⸻
 
5.7.2 
product_features
Purpose
Defines optional capabilities within a product.
Examples:
gbp.posts
gbp.photo_tracking
reviews.auto_response
content.website_publishing
leads.speed_to_lead
insights.scheduled_reports
Fields
id
product_id
key
name
description
status
created_at
updated_at
This supports feature-level packaging without duplicating products.
 
⸻
 
5.7.3 
product_entitlements
Purpose
Defines which products an organization or location is authorized to use.
Fields
id
organization_id
location_id
product_id
status
source
starts_at
ends_at
created_at
updated_at
Entitlement Statuses
pending
trial
active
paused
suspended
expired
cancelled
Entitlement Sources
manual
stripe
contract
internal
trial
promotion
Rules
	•	location_id may be null for organization-wide access.
	•	A location entitlement may refine an organization-wide entitlement.
	•	Product code checks entitlement state through a shared service.
	•	Stripe must not be queried directly for every authorization decision.
	•	Entitlement history must be retained.
 
⸻
 
5.7.4 
feature_entitlements
Purpose
Controls optional product features.
Fields
id
organization_id
location_id
product_feature_id
status
usage_limit
starts_at
ends_at
created_at
updated_at
Rules
Feature entitlements must not conflict silently with product entitlements.
A feature cannot be active when its parent product is unavailable.
 
⸻
 
5.8 Configuration Tables
5.8.1 
configuration_definitions
Purpose
Defines valid configurable settings.
Fields
id
key
product_id
value_type
default_value
validation_schema
description
is_sensitive
status
created_at
updated_at
Value Types
string
integer
decimal
boolean
date
time
datetime
enum
json
secret_reference
Examples
reviews.auto_publish_min_rating
gbp.posts.require_approval
seo.analysis.lookback_days
content.default_word_count_min
leads.business_hours_response_enabled
 
⸻
 
5.8.2 
configuration_values
Purpose
Stores scoped configuration values.
Fields
id
configuration_definition_id
organization_id
location_id
product_id
workflow_definition_id
value
source
effective_from
effective_to
created_by_user_id
created_at
updated_at
Configuration Sources
platform_default
industry_default
organization
location
product
workflow
Resolution Order
workflow
location
organization
industry
platform
The most specific active value wins.
Rules
	•	Sensitive values should reference secure storage rather than contain plaintext.
	•	Invalid values must be rejected before activation.
	•	Configuration changes must be audited.
	•	Previous values should remain recoverable through history or versioning.
 
⸻
 
5.8.3 
configuration_versions
Purpose
Preserves configuration snapshots.
Fields
id
organization_id
location_id
product_id
version_number
configuration_snapshot
created_by_user_id
created_at
change_summary
This allows rollback and reconstruction of workflow behavior.
 
⸻
 
5.9 Integration Tables
5.9.1 
integration_providers
Purpose
Defines supported external provider types.
Initial Examples
google_search_console
google_analytics
google_business_profile
google_places
github
vercel
resend
stripe
sms_provider
crm
scheduling
form_provider
Fields
id
key
name
category
status
auth_type
created_at
updated_at
 
⸻
 
5.9.2 
integration_connections
Purpose
Represents a connected provider account.
Fields
id
organization_id
location_id
provider_id
name
status
credential_reference
external_account_id
connected_by_user_id
connected_at
last_verified_at
last_success_at
last_failure_at
error_code
error_message
metadata
created_at
updated_at
archived_at
Integration Statuses
setup_required
connected
degraded
authorization_required
expired
permission_denied
rate_limited
provider_unavailable
disconnected
archived
Rules
	•	Credentials must be stored through a secure reference.
	•	A connection may apply to the organization or one location.
	•	Products reuse shared connections where scopes permit.
	•	Error messages shown to clients may differ from internal diagnostic details.
	•	Integration state must be visible in the agency console.
 
⸻
 
5.9.3 
integration_resources
Purpose
Maps external provider resources into LILOs.
Examples:
	•	GSC property
	•	GA4 property
	•	GBP account
	•	GBP location
	•	GitHub repository
	•	Vercel project
	•	Stripe customer
	•	CRM pipeline
Fields
id
organization_id
location_id
integration_connection_id
resource_type
external_resource_id
name
status
metadata
last_synced_at
created_at
updated_at
Rules
	•	External identifiers should be unique within the provider connection and resource type.
	•	A resource may be mapped to one or more product workflows.
	•	Disconnected resources must not be silently replaced.
 
⸻
 
5.9.4 
integration_syncs
Purpose
Tracks synchronization operations.
Fields
id
organization_id
location_id
integration_connection_id
integration_resource_id
sync_type
status
started_at
completed_at
records_read
records_created
records_updated
records_failed
cursor
error_code
error_message
workflow_execution_id
created_at
Sync Statuses
queued
running
completed
partially_completed
failed
cancelled
 
⸻
 
5.10 Workflow Tables
5.10.1 
workflow_definitions
Purpose
Defines reusable workflow templates.
Fields
id
key
name
product_id
version
trigger_type
status
input_schema
output_schema
default_retry_policy
requires_approval
created_at
updated_at
Trigger Types
scheduled
event
manual
webhook
approval_continuation
Examples
seo.weekly_opportunity_analysis
gbp.generate_post
gbp.publish_post
reviews.generate_response
content.publish_to_github
leads.speed_to_lead
insights.monthly_report
 
⸻
 
5.10.2 
workflow_schedules
Purpose
Stores client-specific schedules.
Fields
id
organization_id
location_id
workflow_definition_id
status
timezone
schedule_expression
next_run_at
last_run_at
configuration
created_by_user_id
created_at
updated_at
Schedule Statuses
active
paused
invalid
expired
archived
Rules
	•	Schedule expressions must be validated.
	•	Timezone must be explicit.
	•	A paused product entitlement must prevent scheduled execution.
	•	Schedules must be visible and editable by authorized users.
 
⸻
 
5.10.3 
workflow_executions
Purpose
Tracks each workflow run.
Fields
id
organization_id
location_id
product_id
workflow_definition_id
workflow_version
trigger_type
trigger_reference
status
priority
correlation_id
idempotency_key
input_data
output_data
started_at
completed_at
attempt_count
max_attempts
next_retry_at
error_code
error_message
initiated_by_user_id
parent_execution_id
created_at
updated_at
Workflow Statuses
queued
running
waiting_for_approval
approved
rejected
retry_scheduled
completed
partially_completed
failed
cancelled
expired
Rules
	•	idempotency_key should be unique within the relevant workflow scope.
	•	Input and output data should contain references where payloads are large.
	•	Provider errors must be normalized into internal error codes.
	•	Parent-child relationships may represent multi-step workflows.
	•	Failed executions must remain queryable.
	•	Completed executions must not be modified except for approved metadata correction.
 
⸻
 
5.10.4 
workflow_steps
Purpose
Tracks individual steps inside a workflow execution.
Fields
id
workflow_execution_id
step_key
step_order
status
started_at
completed_at
attempt_count
input_reference
output_reference
error_code
error_message
created_at
updated_at
Step Statuses
pending
running
waiting
completed
skipped
failed
cancelled
This enables precise failure diagnosis without requiring separate microservices.
 
⸻
 
5.10.5 
platform_events
Purpose
Stores event records used by event-driven workflows.
Fields
id
event_type
organization_id
location_id
product_id
actor_type
actor_id
payload
correlation_id
status
occurred_at
processed_at
created_at
Event Statuses
pending
processing
processed
partially_processed
failed
ignored
Rules
	•	Events should be immutable after creation except for processing metadata.
	•	Consumers must be idempotent.
	•	Event payloads should contain stable references rather than unnecessary duplicated data.
 
⸻
 
5.11 Approval Tables
5.11.1 
approval_requests
Purpose
Tracks requests requiring human authorization.
Fields
id
organization_id
location_id
product_id
workflow_execution_id
item_type
item_id
action_type
status
risk_level
required_permission
requested_by_user_id
requested_at
expires_at
resolved_by_user_id
resolved_at
decision_notes
revision_number
content_hash
created_at
updated_at
Approval Statuses
pending
approved
rejected
revision_requested
expired
cancelled
superseded
Risk Levels
low
medium
high
critical
Rules
	•	Approval must be tied to a specific revision or content hash.
	•	Material changes invalidate prior approval.
	•	An approver must possess the required permission.
	•	A user should not approve their own action when separation of duties is configured.
	•	Expired approvals cannot authorize publication.
	•	Rejections and revision requests should retain notes.
 
⸻
 
5.11.2 
approval_history
Purpose
Preserves every transition for an approval request.
Fields
id
approval_request_id
from_status
to_status
acted_by_user_id
notes
created_at
The history must be append-only.
 
⸻
 
5.12 Notification Tables
5.12.1 
notification_preferences
Purpose
Stores user notification settings.
Fields
id
user_id
organization_id
product_id
event_type
channel
enabled
severity_threshold
created_at
updated_at
Channels
in_app
email
sms
webhook
 
⸻
 
5.12.2 
notifications
Purpose
Stores generated user notifications.
Fields
id
organization_id
user_id
product_id
event_type
severity
title
message
action_url
status
created_at
read_at
dismissed_at
expires_at
Notification Statuses
pending
delivered
read
dismissed
failed
expired
 
⸻
 
5.12.3 
notification_deliveries
Purpose
Tracks individual channel delivery attempts.
Fields
id
notification_id
channel
provider
status
provider_message_id
attempt_count
sent_at
delivered_at
failed_at
error_code
error_message
created_at
 
⸻
 
5.13 AI Architecture Tables
5.13.1 
ai_providers
Purpose
Defines available AI providers.
Fields
id
key
name
status
credential_reference
base_url
metadata
created_at
updated_at
Provider Statuses
active
degraded
disabled
testing
retired
 
⸻
 
5.13.2 
ai_models
Purpose
Registers models available through providers.
Fields
id
provider_id
model_key
display_name
model_type
status
context_window
supports_structured_output
supports_vision
supports_tools
supports_embeddings
input_cost_reference
output_cost_reference
capabilities
created_at
updated_at
Model Types
general
reasoning
writing
coding
vision
classification
embedding
image_generation
audio
Cost fields should be treated as versioned reference data because provider pricing changes.
 
⸻
 
5.13.3 
ai_task_types
Purpose
Defines platform AI tasks independently from models.
Examples
seo_opportunity_analysis
keyword_clustering
gbp_post_generation
review_response_generation
content_brief_generation
long_form_content_generation
lead_intent_classification
report_summary
code_assistance
Fields
id
key
name
product_id
risk_level
required_output_schema
default_timeout_seconds
default_cost_limit
status
created_at
updated_at
 
⸻
 
5.13.4 
ai_routing_policies
Purpose
Determines which models may be used for a task.
Fields
id
ai_task_type_id
organization_id
primary_model_id
fallback_model_id
secondary_fallback_model_id
max_cost
max_latency_ms
minimum_quality_score
policy
status
created_at
updated_at
Rules
	•	Organization-specific policies may override platform defaults.
	•	Product code references the task type, not a model name.
	•	A model change should not require product-code modification.
	•	Fallback behavior must be explicit.
 
⸻
 
5.13.5 
prompt_definitions
Purpose
Defines reusable prompt identities.
Fields
id
key
name
product_id
ai_task_type_id
description
status
created_at
updated_at
 
⸻
 
5.13.6 
prompt_versions
Purpose
Stores immutable prompt versions.
Fields
id
prompt_definition_id
version_number
system_prompt
instruction_template
input_schema
output_schema
change_summary
status
created_by_user_id
created_at
approved_by_user_id
approved_at
Prompt Statuses
draft
testing
approved
deprecated
retired
Rules
	•	Approved prompt versions must be immutable.
	•	Editing an approved prompt creates a new version.
	•	Production workflows may only use approved versions unless explicitly operating in test mode.
	•	Prompt templates must not contain plaintext credentials.
	•	Client-specific business context should be passed as structured input, not permanently copied into prompt text.
 
⸻
 
5.13.7 
ai_executions
Purpose
Tracks each model invocation.
Fields
id
organization_id
location_id
product_id
workflow_execution_id
ai_task_type_id
provider_id
model_id
prompt_version_id
status
request_reference
response_reference
structured_output
input_tokens
output_tokens
estimated_cost
latency_ms
attempt_number
fallback_from_execution_id
error_code
error_message
created_at
completed_at
AI Execution Statuses
queued
running
completed
validation_failed
provider_failed
timed_out
cancelled
blocked
Rules
	•	Sensitive raw prompts and responses should be retained only according to policy.
	•	Structured output should be retained when necessary for workflow reproducibility.
	•	Provider and model must always be recorded.
	•	Cost may be estimated if exact billing data is unavailable.
	•	Failed structured-output validation must not be treated as success.
	•	Fallback executions should link to the original attempt.
 
⸻
 
5.13.8 
ai_evaluations
Purpose
Captures quality and outcome measurements.
Fields
id
ai_execution_id
evaluation_type
score
result
reviewed_by_user_id
human_edit_distance
accepted_without_edit
rejection_reason
business_outcome_reference
created_at
Evaluation Types
human_review
schema_validation
automated_rule
comparison_test
production_outcome
Use Cases
The platform should eventually support questions such as:
	•	Which model produces the highest approval rate?
	•	Which prompt requires the least editing?
	•	Which model performs best for restaurant GBP posts?
	•	Which model is cheapest while meeting quality thresholds?
	•	Which fallback is most reliable?
	•	Which content outputs produce measurable search gains?
 
⸻
 
5.14 Audit Tables
5.14.1 
audit_events
Purpose
Records significant platform actions.
Fields
id
organization_id
location_id
product_id
actor_type
actor_user_id
actor_service
action
resource_type
resource_id
workflow_execution_id
ai_execution_id
correlation_id
summary
before_state
after_state
ip_address
user_agent
created_at
Actor Types
user
system
workflow
integration
ai_operator
support
Rules
	•	Audit events are append-only.
	•	Secrets must never be stored in audit state.
	•	Sensitive fields should be redacted.
	•	Cross-tenant support access must generate an event.
	•	AI-operator actions must identify the operator and human initiator where applicable.
 
⸻
 
5.15 Billing and Usage Tables
5.15.1 
billing_accounts
Purpose
Links organizations to billing systems.
Fields
id
organization_id
provider
external_customer_id
status
billing_email
created_at
updated_at
 
⸻
 
5.15.2 
subscriptions
Purpose
Tracks the platform’s normalized subscription state.
Fields
id
organization_id
billing_account_id
external_subscription_id
status
starts_at
current_period_start
current_period_end
cancel_at
cancelled_at
created_at
updated_at
Subscription Statuses
trialing
active
past_due
paused
cancelled
expired
Rule
Subscriptions influence entitlements through a billing synchronization service.
Product code should not inspect Stripe directly.
 
⸻
 
5.15.3 
subscription_items
Purpose
Maps billing items to products and features.
Fields
id
subscription_id
product_id
product_feature_id
external_price_id
quantity
usage_type
created_at
updated_at
 
⸻
 
5.15.4 
usage_records
Purpose
Tracks billable or operational usage.
Fields
id
organization_id
location_id
product_id
feature_key
quantity
unit
source_type
source_id
occurred_at
created_at
Example Units
ai_tokens
ai_execution
workflow_run
location
lead
sms
email
published_post
report
Usage tracking must not automatically imply usage-based billing.
 
⸻
 
5.16 Product-Specific Tables
The following tables define the initial domain records.
They may be expanded during detailed product design.
 
⸻
 
5.17 LILOs SEO Data Model
5.17.1 
seo_properties
Purpose
Represents an SEO data source associated with a location or organization.
Fields
id
organization_id
location_id
integration_resource_id
property_type
property_url
status
created_at
updated_at
Property Types
gsc_domain
gsc_url_prefix
website
local_rank_tracker
analytics_property
 
⸻
 
5.17.2 
seo_query_metrics
Purpose
Stores normalized search-query performance.
Fields
id
organization_id
location_id
seo_property_id
query
page_url
metric_date
country
device
search_type
clicks
impressions
ctr
average_position
created_at
Constraints
A uniqueness constraint should prevent duplicate records for the same:
property
query
page
date
country
device
search_type
Retention and aggregation rules should be defined to control data volume.
 
⸻
 
5.17.3 
seo_page_metrics
Purpose
Stores page-level search performance.
Fields
id
organization_id
location_id
seo_property_id
page_url
metric_date
clicks
impressions
ctr
average_position
sessions
conversions
created_at
 
⸻
 
5.17.4 
seo_opportunities
Purpose
Stores actionable SEO opportunities.
Fields
id
organization_id
location_id
seo_property_id
opportunity_type
title
summary
status
priority
confidence_score
impact_score
effort_score
source_period_start
source_period_end
target_page_url
target_query
recommended_action
workflow_execution_id
assigned_to_user_id
created_at
updated_at
completed_at
Opportunity Types
high_impression_low_ctr
near_page_one
traffic_decline
query_decline
content_gap
cannibalization
internal_link
technical_issue
local_relevance
refresh
new_page
Opportunity Statuses
new
reviewing
approved
rejected
planned
in_progress
completed
measuring
validated
closed
Rules
	•	Opportunities should be deduplicated.
	•	Automated recommendations must identify their source period.
	•	Completion does not imply performance improvement.
	•	Performance validation should be tracked separately.
 
⸻
 
5.17.5 
seo_opportunity_measurements
Purpose
Measures outcomes after implementation.
Fields
id
seo_opportunity_id
measurement_period_start
measurement_period_end
baseline_metrics
result_metrics
result_status
notes
created_at
Result Statuses
improved
neutral
declined
insufficient_data
measurement_pending
 
⸻
 
5.18 LILOs GBP Data Model
5.18.1 
gbp_locations
Purpose
Stores normalized Google Business Profile location data.
Fields
id
organization_id
location_id
integration_resource_id
external_location_id
business_name
primary_category
secondary_categories
status
profile_data
last_synced_at
created_at
updated_at
 
⸻
 
5.18.2 
gbp_profile_snapshots
Purpose
Stores profile state over time.
Fields
id
gbp_location_id
snapshot_date
business_information
categories
hours
special_hours
attributes
services
menu_links
booking_links
profile_completeness
created_at
Snapshots support change detection and historical review.
 
⸻
 
5.18.3 
gbp_recommendations
Purpose
Stores GBP optimization recommendations.
Fields
id
organization_id
location_id
gbp_location_id
recommendation_type
title
description
priority
status
source
created_at
updated_at
completed_at
 
⸻
 
5.18.4 
gbp_posts
Purpose
Stores GBP post drafts and publication records.
Fields
id
organization_id
location_id
gbp_location_id
post_type
title
body
call_to_action_type
call_to_action_url
media_reference
status
prompt_version_id
ai_execution_id
approval_request_id
scheduled_for
published_at
external_post_id
expires_at
created_by_user_id
created_at
updated_at
Post Statuses
draft
generated
validation_failed
awaiting_approval
approved
scheduled
publishing
published
failed
rejected
expired
archived
Rules
	•	Published text must match the approved revision.
	•	Duplicate publication must be prevented.
	•	External post IDs must be stored after successful publication.
	•	Failed publication must retain the approved content and provider error.
 
⸻
 
5.18.5 
gbp_performance_metrics
Purpose
Stores normalized GBP performance data.
Fields
id
organization_id
location_id
gbp_location_id
metric_date
metric_key
metric_value
source
created_at
Metric definitions should be versioned because Google may change available GBP metrics.
 
⸻
 
5.19 LILOs Reviews Data Model
5.19.1 
reviews
Purpose
Stores normalized customer reviews.
Fields
id
organization_id
location_id
integration_resource_id
external_review_id
provider
reviewer_name
rating
review_text
review_created_at
review_updated_at
language
status
risk_level
sentiment
topics
last_synced_at
created_at
updated_at
Review Statuses
new
analyzed
response_drafted
awaiting_approval
responded
escalated
ignored
removed
Rules
	•	Provider review IDs must be unique within the provider resource.
	•	Reviewer data should be limited to information supplied by the provider.
	•	Removed reviews should retain a tombstone record when operationally useful.
	•	Original review text must not be rewritten.
 
⸻
 
5.19.2 
review_risk_flags
Purpose
Stores review-risk classifications.
Fields
id
review_id
risk_type
severity
confidence_score
source
notes
created_at
Initial Risk Types
legal
injury
discrimination
harassment
fraud
charge_dispute
food_safety
threat
privacy
employee_misconduct
media_risk
 
⸻
 
5.19.3 
review_responses
Purpose
Stores response drafts, revisions, and publication state.
Fields
id
organization_id
location_id
review_id
revision_number
response_text
status
generated_by_type
generated_by_user_id
ai_execution_id
prompt_version_id
approval_request_id
published_at
external_response_id
created_at
updated_at
Generated By Types
user
ai
template
imported
Response Statuses
draft
generated
awaiting_approval
approved
publishing
published
failed
rejected
superseded
Rules
	•	Revisions must be preserved.
	•	Only one response revision may be the active approved revision.
	•	A published response cannot be silently overwritten.
	•	A new edit after publication creates a new revision and publication action.
 
⸻
 
5.20 LILOs Content Data Model
5.20.1 
content_items
Purpose
Represents a content asset through its lifecycle.
Fields
id
organization_id
location_id
content_type
title
slug
target_url
status
source_type
source_id
primary_keyword
search_intent
assigned_to_user_id
created_at
updated_at
published_at
archived_at
Content Types
service_page
location_page
blog_post
page_update
faq
gbp_post
email
lead_message
other
Content Statuses
idea
briefing
brief_ready
drafting
draft_ready
reviewing
revision_requested
approved
publishing
published
failed
archived
 
⸻
 
5.20.2 
content_briefs
Purpose
Stores structured content specifications.
Fields
id
content_item_id
revision_number
objective
target_audience
primary_keyword
secondary_keywords
search_intent
required_topics
local_references
approved_claims
prohibited_claims
internal_link_targets
competitor_context
minimum_word_count
maximum_word_count
outline
status
prompt_version_id
ai_execution_id
created_at
updated_at
 
⸻
 
5.20.3 
content_revisions
Purpose
Stores immutable content versions.
Fields
id
content_item_id
revision_number
content_body
metadata
content_hash
created_by_type
created_by_user_id
ai_execution_id
created_at
Rules
	•	Published revisions must remain immutable.
	•	Approval must reference a revision and hash.
	•	AI-generated and human-authored revisions must be distinguishable.
	•	Large binary files should be stored externally and referenced.
 
⸻
 
5.20.4 
content_publications
Purpose
Tracks publication attempts and destinations.
Fields
id
content_item_id
content_revision_id
destination_type
integration_resource_id
target_reference
status
workflow_execution_id
external_revision_id
published_url
published_at
error_code
error_message
created_at
updated_at
Destination Types
github
cms
website_api
gbp
email
manual_export
 
⸻
 
5.20.5 
content_performance
Purpose
Connects published content to measurable outcomes.
Fields
id
content_item_id
measurement_date
clicks
impressions
ctr
average_position
sessions
conversions
engagement_metrics
created_at
 
⸻
 
5.21 LILOs Leads Data Model
5.21.1 
leads
Purpose
Stores normalized lead records.
Fields
id
organization_id
location_id
external_lead_id
source_type
source_name
status
first_name
last_name
email
phone
service_requested
message
urgency
lead_score
consent_email
consent_sms
consent_recorded_at
assigned_to_user_id
received_at
first_response_at
qualified_at
closed_at
created_at
updated_at
Lead Statuses
new
acknowledged
attempting_contact
contacted
qualifying
qualified
unqualified
assigned
appointment_set
converted
lost
spam
closed
Rules
	•	Consent state must be explicit.
	•	Phone and email values should be normalized.
	•	Duplicates should be linked rather than silently discarded.
	•	Lead status history must be retained.
	•	Sensitive lead data must be protected through RLS and permissions.
 
⸻
 
5.21.2 
lead_sources
Purpose
Defines configured lead channels.
Fields
id
organization_id
location_id
source_type
name
integration_connection_id
status
configuration
created_at
updated_at
Source Types
website_form
phone
missed_call
email
google
advertising
marketplace
crm
manual
api
 
⸻
 
5.21.3 
lead_status_history
Purpose
Preserves lead state transitions.
Fields
id
lead_id
from_status
to_status
changed_by_type
changed_by_user_id
workflow_execution_id
notes
created_at
 
⸻
 
5.21.4 
lead_communications
Purpose
Tracks inbound and outbound communications.
Fields
id
organization_id
location_id
lead_id
direction
channel
status
message_body
template_reference
provider
provider_message_id
sent_by_type
sent_by_user_id
ai_execution_id
workflow_execution_id
sent_at
delivered_at
failed_at
created_at
Channels
email
sms
phone
voicemail
chat
internal_note
Rules
	•	Automated communication must reference the workflow execution.
	•	Opt-out events must immediately affect future eligibility.
	•	Failed delivery must not be recorded as successful contact.
	•	Message content retention must follow policy.
 
⸻
 
5.21.5 
lead_conversations
Purpose
Tracks conversation state for Speed-to-Lead and follow-up workflows.
Fields
id
lead_id
status
current_stage
human_takeover_required
last_inbound_at
last_outbound_at
next_action_at
summary
created_at
updated_at
Conversation Statuses
active
waiting_for_lead
waiting_for_staff
human_takeover
completed
opted_out
expired
 
⸻
 
5.22 LILOs Insights Data Model
5.22.1 
metric_definitions
Purpose
Defines standardized platform metrics.
Fields
id
key
name
product_id
description
unit
aggregation_type
source
status
created_at
updated_at
 
⸻
 
5.22.2 
metric_values
Purpose
Stores normalized KPI values.
Fields
id
organization_id
location_id
metric_definition_id
period_start
period_end
value
dimensions
source_reference
data_freshness_at
created_at
 
⸻
 
5.22.3 
report_definitions
Purpose
Defines reusable report templates.
Fields
id
key
name
report_type
configuration
status
created_at
updated_at
 
⸻
 
5.22.4 
report_runs
Purpose
Tracks generated reports.
Fields
id
organization_id
location_id
report_definition_id
period_start
period_end
status
workflow_execution_id
generated_output_reference
generated_at
delivered_at
created_at
Report Statuses
queued
generating
generated
delivering
delivered
failed
expired
 
⸻
 
5.22.5 
report_annotations
Purpose
Adds human or system context to reporting periods.
Fields
id
organization_id
location_id
annotation_date
annotation_type
title
description
source_type
source_id
created_by_user_id
created_at
Examples:
	•	Website launch
	•	GBP category change
	•	Menu update
	•	Major algorithm update
	•	New campaign
	•	Business closure
	•	Tracking outage
 
⸻
 
5.23 Data Access and Row Level Security
5.23.1 Default Rule
Access is denied unless explicitly allowed.
5.23.2 Client User Access
A client user may access a record only when:
	1.	The user has an active membership in the record’s organization.
	2.	The user has the required permission.
	3.	The relevant product entitlement is active where applicable.
	4.	The user has access to the record’s location where location scope applies.
	5.	The record is client-visible.
5.23.3 Internal User Access
Internal users may access cross-tenant data only through assigned roles and permissions.
Internal access must not rely on a universal frontend flag.
Administrative service-role access must be limited to backend services.
5.23.4 Service Access
Workers and backend services may use elevated database access only when:
	•	The service is authenticated.
	•	The action is authorized by platform logic.
	•	The organization scope is explicit.
	•	The action is logged.
	•	User-originated actions retain the initiating user reference.
5.23.5 Sensitive Tables
The following should not generally be directly readable from the browser:
	•	Credential references
	•	Raw AI requests and responses
	•	Internal cost records
	•	Internal audit diagnostics
	•	Provider error payloads
	•	Support-only notes
	•	Sensitive lead communication metadata
	•	Secret-bearing configuration
 
⸻
 
5.24 Indexing Requirements
Indexes should be created for common access patterns.
At minimum, tenant-owned tables should consider indexes on:
organization_id
location_id
status
created_at
updated_at
Common composite indexes may include:
organization_id, status
organization_id, location_id
organization_id, product_id, status
workflow_definition_id, status, next_retry_at
organization_id, occurred_at
location_id, metric_date
content_item_id, revision_number
review_id, revision_number
lead_id, created_at
Unique indexes should enforce:
	•	Organization slug
	•	Location slug within organization
	•	External resource identity
	•	Provider review identity
	•	Workflow idempotency where applicable
	•	Prompt version number within prompt definition
	•	Content revision number within content item
	•	One active entitlement per defined scope and product
	•	One active connection mapping where required
Indexing must be based on real query patterns and reviewed for write overhead.
 
⸻
 
5.25 Data Validation and Constraints
The database should enforce critical integrity rules.
Examples:
	•	Ratings must fall within the provider-supported range.
	•	Dates must be logically ordered.
	•	Organization references cannot be null for tenant records.
	•	Location records must belong to the same organization as their parent record.
	•	Approved content must reference an existing revision.
	•	Published content must reference an approved revision unless an authorized exception exists.
	•	Feature entitlements require a valid product entitlement.
	•	Location-scoped records cannot reference a location from another organization.
	•	Workflow attempt count cannot be negative.
	•	Usage quantity cannot be negative.
	•	AI token counts cannot be negative.
	•	Approval resolution requires a resolving user and timestamp.
	•	Active schedules require a valid schedule expression.
	•	Consent-dependent messages cannot be marked eligible without consent evidence.
Application validation supplements these constraints but does not replace them.
 
⸻
 
5.26 Data Freshness
Records derived from external systems must expose freshness.
Relevant tables should include one or more of:
source_updated_at
last_synced_at
data_freshness_at
sync_status
The interface must distinguish:
	•	Current data
	•	Delayed data
	•	Partially synchronized data
	•	Failed synchronization
	•	Unknown freshness
Reports must not imply current performance when source data has not updated.
 
⸻
 
5.27 Data Retention
Retention should be defined by data category.
Permanent or Long-Term
	•	Organizations
	•	Locations
	•	Entitlements
	•	Audit events
	•	Approval history
	•	Published content revisions
	•	Published review responses
	•	Workflow execution summaries
	•	Billing records
	•	Lead consent records
Configurable Retention
	•	Raw provider payloads
	•	Detailed workflow step payloads
	•	AI raw prompts and responses
	•	Notification delivery payloads
	•	Integration debugging records
	•	Temporary files
	•	Fine-grained metrics
Short-Term or Ephemeral
	•	Temporary imports
	•	Processing files
	•	Expired authentication states
	•	Incomplete uploads
	•	Duplicate webhook payloads after reconciliation
Retention policies must consider:
	•	Operational needs
	•	Security risk
	•	Provider terms
	•	Client agreements
	•	Legal obligations
	•	Cost
 
⸻
 
5.28 Data Deletion and Offboarding
Offboarding must be controlled.
Recommended process:
	1.	Disable new workflow execution.
	2.	Revoke or disconnect external integrations.
	3.	Disable user access.
	4.	Export agreed client data.
	5.	Preserve billing and audit records as required.
	6.	Apply retention policy.
	7.	Delete or anonymize eligible personal data.
	8.	Record the offboarding action.
	9.	Prevent orphaned scheduled jobs.
	10.	Confirm external publications and communications are no longer active.
Deleting an organization must not be implemented as an unrestricted cascading delete.
 
⸻
 
5.29 Data Migration Standards
Every schema change must use a migration.
A migration must document:
	•	Reason for change
	•	Tables affected
	•	New constraints
	•	Data backfill requirements
	•	RLS changes
	•	Index changes
	•	Application compatibility
	•	Rollback or recovery plan
Breaking migrations should be deployed in stages:
	1.	Add backward-compatible schema.
	2.	Deploy compatible application code.
	3.	Backfill data.
	4.	Validate.
	5.	Remove deprecated fields in a later migration.
 
⸻
 
5.30 Seed and Test Data
The repository should include controlled seed data for:
	•	Internal test organization
	•	Sample locations
	•	User roles
	•	Permissions
	•	Products
	•	Product features
	•	Industry defaults
	•	Workflow definitions
	•	AI task types
	•	Prompt definitions
	•	Metric definitions
Seed data must not contain real client credentials or private client data.
Tests should use fabricated business and customer information.
 
⸻
 
5.31 Generated Types and Contracts
Database types should be generated and shared with application code where practical.
The system should maintain consistent contracts across:
	•	Supabase
	•	FastAPI
	•	Astro
	•	Workers
	•	Integration adapters
	•	AI structured outputs
Generated types do not replace domain models.
External provider payloads should be normalized before entering product services.
 
⸻
 
5.32 Initial Database Build Order
Stage 1 — Tenant Foundation
Create:
	•	organizations
	•	industries
	•	locations
	•	organization_profiles
	•	location_profiles
	•	user_profiles
	•	organization_memberships
	•	roles
	•	permissions
	•	role_permissions
	•	membership_roles
Stage 2 — Product Access
Create:
	•	products
	•	product_features
	•	product_entitlements
	•	feature_entitlements
	•	configuration_definitions
	•	configuration_values
	•	configuration_versions
Stage 3 — Platform Operations
Create:
	•	integration_providers
	•	integration_connections
	•	integration_resources
	•	integration_syncs
	•	workflow_definitions
	•	workflow_schedules
	•	workflow_executions
	•	workflow_steps
	•	platform_events
	•	approval_requests
	•	approval_history
	•	audit_events
Stage 4 — AI Foundation
Create:
	•	ai_providers
	•	ai_models
	•	ai_task_types
	•	ai_routing_policies
	•	prompt_definitions
	•	prompt_versions
	•	ai_executions
	•	ai_evaluations
Stage 5 — First Product Tables
Create the minimum required tables for the first end-to-end SEO workflow:
	•	seo_properties
	•	seo_query_metrics
	•	seo_page_metrics
	•	seo_opportunities
	•	seo_opportunity_measurements
Stage 6 — Remaining Product Tables
Add GBP, Reviews, Content, Insights, Leads, and Automations as each product enters implementation.
Do not create every speculative product table before the related workflow is defined.
 
⸻
 
5.33 Database Guardrails
The following are prohibited unless formally approved:
	1.	Tenant-owned records without organization_id
	2.	Client-specific database schemas
	3.	Provider credentials stored in plaintext
	4.	Hard deletion of audit records
	5.	Direct production schema edits outside migrations
	6.	Product authorization based only on Stripe state
	7.	Permissions enforced only in the frontend
	8.	Large raw provider payloads stored indefinitely without policy
	9.	Approved prompt versions modified in place
	10.	Published content revisions modified in place
	11.	Workflow failures overwritten or discarded
	12.	Cross-organization joins without explicit tenant constraints
	13.	AI-generated configuration written directly into active settings without validation
	14.	Location records linked across organizations
	15.	JSONB used in place of essential relational structure
	16.	Silent cascade deletion of historical client activity
	17.	Production client data used as general development seed data
	18.	A Hermes-style operator receiving unrestricted database access
 
⸻
 
5.34 Section Decisions
This section establishes the following decisions:
	1.	Supabase PostgreSQL is the authoritative platform database.
	2.	The organization is the primary tenant boundary.
	3.	Locations exist beneath organizations and may carry independent product configuration.
	4.	Every tenant-owned record includes an organization reference.
	5.	User membership, permissions, and product entitlements are separate authorization concepts.
	6.	Product and feature access are represented through entitlement records.
	7.	Configuration uses a layered hierarchy with version history.
	8.	External providers are represented through shared connections and mapped resources.
	9.	Every workflow execution and significant workflow step is recorded.
	10.	Approval records reference specific revisions or content hashes.
	11.	Prompt versions and published content revisions are immutable.
	12.	AI providers, models, task types, routing policies, executions, costs, and evaluations are tracked independently.
	13.	Audit events are append-only.
	14.	Product-specific data remains tenant-scoped and follows common platform conventions.
	15.	Raw data retention is limited according to operational need and policy.
	16.	Tenant isolation is enforced through PostgreSQL constraints, RLS, and application authorization.
	17.	Database changes require version-controlled migrations.
	18.	Existing and future AI operators interact through platform services and do not receive unrestricted database access.
	19.	Product tables should be created as workflows are implemented rather than through speculative overbuilding.
	20.	The first end-to-end database implementation should support the SEO opportunity workflow before broader product expansion.


---

Section 6 — Workflow Architecture and Execution Model
6.1 Purpose of This Section
This section defines how work moves through the LILOs platform.
It establishes:
	•	The lifecycle of work
	•	Workflow standards
	•	Execution patterns
	•	Human approval requirements
	•	AI participation
	•	Retry behavior
	•	Error handling
	•	State transitions
	•	Workflow composition
	•	Cross-product communication
	•	Operational reliability standards
Every product introduced into the platform must conform to these workflow rules.
The objective is consistency, observability, and predictable execution.
 
⸻
 
6.2 Platform Workflow Philosophy
Every meaningful business action should exist as a workflow.
Examples include:
	•	Running an SEO analysis
	•	Creating a GBP post
	•	Publishing content
	•	Responding to a review
	•	Sending a lead acknowledgment
	•	Generating a report
	•	Synchronizing Google data
A workflow is not simply code execution.
A workflow represents:
	•	a business objective
	•	a defined sequence of steps
	•	measurable inputs
	•	measurable outputs
	•	observable execution
	•	recoverable failures
	•	an auditable history
 
⸻
 
6.3 Workflow Principles
Principle 1 — Work Must Be Observable
Every workflow execution must answer:
	•	What started it?
	•	What was supposed to happen?
	•	What actually happened?
	•	What failed?
	•	What succeeded?
	•	What still needs attention?
No workflow should disappear into a cron job or server log.
 
⸻
 
Principle 2 — Human Approval Is First-Class
Approval is not an afterthought.
Approval is part of the workflow.
The workflow engine must understand states such as:
Running

↓

Waiting for Approval

↓

Approved

↓

Continue Execution
Approval is never simulated by pausing code.
It is an explicit workflow state.
 
⸻
 
Principle 3 — AI Performs Tasks
AI performs individual tasks.
AI does not own workflows.
Example:
Workflow:
Create GBP Post
↓
Gather business context
↓
Determine event
↓
Generate draft ← AI
↓
Validate
↓
Approval
↓
Publish
Only one step uses AI.
The workflow itself remains deterministic.
 
⸻
 
Principle 4 — Failure Is Expected
Every workflow must define:
	•	retryable failures
	•	permanent failures
	•	escalation rules
	•	cancellation behavior
Failure handling is designed before implementation.
 
⸻
 
Principle 5 — Every Workflow Produces Records
A completed workflow always produces:
	•	execution record
	•	duration
	•	status
	•	audit trail
	•	outputs
	•	errors
	•	related entities
Nothing important exists only in memory.
 
⸻
 
6.4 Standard Workflow Lifecycle
Every workflow follows the same lifecycle.
Created

↓

Queued

↓

Running

↓

Validation

↓

AI (optional)

↓

Validation

↓

Approval (optional)

↓

External Actions

↓

Completed
Alternative paths include:
Running

↓

Retry

↓

Running
or
Running

↓

Failed

↓

Escalated
or
Running

↓

Cancelled
 
⸻
 
6.5 Workflow Types
The platform supports four workflow categories.
Scheduled
Example:
Weekly SEO opportunity generation.
 
⸻
 
Event Driven
Example:
New Google review.
 
⸻
 
Manual
Example:
Operator clicks:
Generate New GBP Post
 
⸻
 
Chained
One workflow starts another.
Example:
SEO Opportunity
↓
Content Brief
↓
Article Draft
↓
Publish
↓
Performance Monitoring
 
⸻
 
6.6 Workflow Composition
Large workflows should be composed of smaller reusable workflows.
Poor design:
Mega Workflow

4000 lines
Preferred:
Generate Draft

↓

Validate Draft

↓

Approval

↓

Publish

↓

Notify
Each component should be reusable.
 
⸻
 
6.7 Workflow Step Categories
Every workflow step belongs to one category.
Examples:
Input
Validation
Transformation
AI Generation
Classification
Decision
Approval
Integration
Publication
Notification
Measurement
Cleanup
Audit
 
⸻
 
6.8 Standard Step Contract
Every step receives:
Input
↓
Context
↓
Configuration
↓
Dependencies
↓
Execution Metadata
Every step returns:
Success
or
Failure
plus
Structured Output
A step never returns arbitrary text that later code attempts to interpret.
 
⸻
 
6.9 Context Object
Every workflow receives a shared context.
Example contents:
Organization
Location
User
Permissions
Configuration
Timezone
Current Workflow
Current Product
Correlation ID
Prompt Versions
Model Policies
Logging
Everything required for execution exists inside the context.
No step should fetch unrelated global state unnecessarily.
 
⸻
 
6.10 AI Workflow Pattern
Correct pattern:
Business Rules
↓
Collect Data
↓
Validate Inputs
↓
AI Task
↓
Validate AI Output
↓
Continue Workflow
Incorrect:
Collect Data
↓
AI decides everything
↓
Publish
AI always operates inside defined boundaries.
 
⸻
 
6.11 AI Output Validation
Every AI output must be validated.
Possible validators include:
JSON schema
Length
Required fields
Brand rules
Grammar
Toxicity
Policy compliance
Location relevance
Approved claims
Duplicate detection
Only validated outputs proceed.
 
⸻
 
6.12 Workflow States
Every workflow supports:
Created
Queued
Running
Waiting
Waiting Approval
Retry Scheduled
Completed
Partially Completed
Cancelled
Expired
Failed
Escalated
These states are shared platform-wide.
 
⸻
 
6.13 Retry Strategy
Retryable examples:
Timeout
Network interruption
429 rate limit
Temporary provider outage
Non-retryable:
Invalid credentials
Permission denied
Deleted resource
Policy rejection
Validation failure
Retries should use exponential backoff.
Repeated failures escalate.
 
⸻
 
6.14 Idempotency
A workflow must safely retry.
Examples:
GBP posts
Review responses
Emails
SMS
Invoices
Lead acknowledgements
Retrying must never duplicate the external action.
 
⸻
 
6.15 Human Tasks
Some workflow steps require humans.
Examples:
Approve
Reject
Edit
Assign
Escalate
Request Revision
Human tasks suspend workflow execution until resolved.
 
⸻
 
6.16 Cross Product Workflows
Products communicate through workflows.
Example:
SEO
↓
Opportunity
↓
Content
↓
Draft
↓
Approval
↓
Publication
↓
Insights
↓
Measure Results
Products do not call one another’s internal logic directly.
They exchange structured workflow events.
 
⸻
 
6.17 Example Workflow — SEO Opportunity
	1.	Scheduled execution starts.
	2.	Retrieve Search Console metrics.
	3.	Normalize data.
	4.	Detect opportunities.
	5.	Score opportunities.
	6.	AI summarizes findings.
	7.	Validate recommendations.
	8.	Store opportunities.
	9.	Notify operator.
	10.	Complete.
 
⸻
 
6.18 Example Workflow — GBP Post
	1.	Schedule begins.
	2.	Retrieve latest business context.
	3.	Determine eligible topic.
	4.	Build structured prompt.
	5.	Generate draft.
	6.	Validate.
	7.	Check duplicate content.
	8.	Submit approval.
	9.	Publish.
	10.	Store publication.
	11.	Retrieve publication identifier.
	12.	Complete.
 
⸻
 
6.19 Example Workflow — Review Response
	1.	Review arrives.
	2.	Risk classification.
	3.	Sentiment classification.
	4.	Policy evaluation.
	5.	Draft response.
	6.	Validate.
	7.	Determine approval requirement.
	8.	Publish or wait.
	9.	Record publication.
	10.	Measure response time.
 
⸻
 
6.20 Example Workflow — Speed to Lead
	1.	Lead arrives.
	2.	Normalize.
	3.	Check consent.
	4.	Determine urgency.
	5.	Business hours evaluation.
	6.	AI drafts response.
	7.	Send communication.
	8.	Wait for reply.
	9.	Route to staff.
	10.	Measure response time.
	11.	Continue conversation.
	12.	Close.
 
⸻
 
6.21 Long Running Workflows
Long-running workflows must survive:
Application restarts
Server restarts
Worker restarts
Provider outages
Deployments
Waiting periods
A workflow should resume rather than restart.
 
⸻
 
6.22 Scheduled Workflows
Schedules belong to data.
Not code.
Changing execution time must not require deployment.
 
⸻
 
6.23 Event Driven Workflows
Events should initiate workflows.
Examples:
New review
New booking
Subscription renewed
Content approved
GBP connected
Lead received
Events are durable records.
 
⸻
 
6.24 Notifications
Notifications are outcomes.
Not workflow logic.
A workflow requests:
Notify User
The notification system determines:
Email
SMS
In App
Push
 
⸻
 
6.25 Escalation
Escalation is a workflow.
Example:
Three retries
↓
Escalate
↓
Notify Account Manager
↓
Pause dependent workflows
↓
Wait Resolution
 
⸻
 
6.26 Metrics
Every workflow records:
Duration
Success
Failure
Retries
Approvals
Average execution time
Average wait time
Average AI latency
Cost
Provider
Outcome
 
⸻
 
6.27 Workflow Versioning
Workflow definitions are versioned.
A running workflow completes using its original version.
New executions use the latest approved version.
Historical executions remain reproducible.
 
⸻
 
6.28 Workflow Testing
Every workflow requires:
Unit tests
Integration tests
Happy path
Failure path
Retry path
Approval path
Cancellation path
Provider failure simulation
AI output validation
Duplicate prevention
 
⸻
 
6.29 Workflow Security
Every workflow enforces:
Permissions
Product entitlement
Organization scope
Location scope
Approval policy
Audit logging
No workflow bypasses platform security.
 
⸻
 
6.30 Workflow Observability
Operations staff should answer in under one minute:
Why did this fail?
What is waiting?
Who approved this?
Which AI model ran?
How much did it cost?
When did it publish?
What changed?
Without searching logs.
 
⸻
 
6.31 Workflow Design Standards
Every new workflow must define:
Business objective
Owner
Trigger
Inputs
Outputs
Dependencies
States
Retries
Escalations
Approval policy
External actions
Metrics
Security
Audit events
Success criteria
No workflow should be implemented before these items are documented.
 
⸻
 
6.32 Section Decisions
This section establishes:
	1.	Every meaningful business action is represented as a workflow.
	2.	AI performs workflow tasks but never owns workflow execution.
	3.	Human approval is a native workflow state.
	4.	Workflows are deterministic outside AI task boundaries.
	5.	All workflows are observable, auditable, retryable, and measurable.
	6.	Cross-product communication occurs through workflow events rather than direct coupling.
	7.	Workflow definitions are versioned and reproducible.
	8.	Retry behavior, escalation, idempotency, and validation are mandatory design elements.
	9.	Long-running workflows must survive restarts and deployments.
	10.	No workflow may bypass authentication, authorization, approval, or audit requirements.


---

Section 7 — API and Service Architecture
7.1 Purpose of This Section
This section defines how LILOs application components communicate.
It establishes:
	•	API boundaries
	•	Internal service contracts
	•	Public and private endpoints
	•	Authentication and authorization requirements
	•	Request and response standards
	•	Error handling
	•	API versioning
	•	Webhook design
	•	Idempotency
	•	Pagination
	•	Rate limiting
	•	File handling
	•	Cross-product communication
	•	Integration adapter interfaces
	•	AI service interfaces
	•	Observability requirements
	•	API testing and documentation standards
The goal is to ensure that the frontend, backend, workers, products, integrations, and future AI operators communicate through stable, predictable interfaces.
This section does not require that every internal function become a network API.
The platform should use network boundaries only where they provide operational value.
 
⸻
 
7.2 API Architecture Principles
Principle 1 — Services Own Business Logic
Business logic belongs in application and domain services.
It does not belong in:
	•	Frontend components
	•	API route handlers
	•	Database triggers
	•	Integration adapters
	•	Prompt templates
	•	Workflow scheduler code
API routes receive requests and delegate to services.
 
⸻
 
Principle 2 — APIs Express Business Actions
Endpoints should represent platform resources and meaningful actions.
Preferred:
POST /v1/gbp/posts/{post_id}/submit-for-approval
POST /v1/reviews/{review_id}/generate-response
POST /v1/content/{content_id}/publish
Avoid vague command endpoints such as:
POST /run-action
POST /do-task
POST /process
 
⸻
 
Principle 3 — Every Request Has Explicit Scope
Every protected request must resolve:
	•	User or service identity
	•	Organization
	•	Location, when applicable
	•	Product
	•	Permission
	•	Product entitlement
Scope must never be inferred solely from client-supplied identifiers.
 
⸻
 
Principle 4 — External Providers Are Hidden Behind Adapters
Product services should not expose Google, Stripe, GitHub, Vercel, Resend, or AI provider payloads directly to the rest of the platform.
Provider-specific data must be normalized.
 
⸻
 
Principle 5 — Contracts Are Versioned
Interfaces that are consumed across deployment boundaries must be versioned.
These include:
	•	Public APIs
	•	Webhooks
	•	Worker job payloads
	•	Integration adapter outputs
	•	AI structured-output schemas
	•	Cross-product events
 
⸻
 
Principle 6 — Errors Are Structured
Every API error must provide a stable machine-readable error code.
Consumers should not have to interpret arbitrary error text.
 
⸻
 
Principle 7 — Writes Are Safe to Retry
Write operations that may be repeated because of network or worker failure must support idempotency.
 
⸻
 
Principle 8 — Long-Running Work Is Asynchronous
An API request should not remain open while a long-running workflow:
	•	Synchronizes external data
	•	Generates a full article
	•	Publishes multiple items
	•	Processes a large import
	•	Waits for approval
	•	Performs multi-step AI analysis
The request should create a workflow execution and return its identifier.
 
⸻
 
7.3 API Surfaces
The platform contains several distinct API surfaces.
7.3.1 Application API
Used by:
	•	Agency console
	•	Client portal
	•	Internal administrative interfaces
Responsibilities include:
	•	Reading product data
	•	Updating configuration
	•	Creating workflows
	•	Managing approvals
	•	Viewing reports
	•	Managing integrations
	•	Managing users and permissions
 
⸻
 
7.3.2 Worker API
Used by trusted background services.
Responsibilities include:
	•	Claiming queued jobs
	•	Updating workflow status
	•	Recording step results
	•	Requesting secure integration access
	•	Recording provider actions
	•	Creating follow-up events
	•	Reporting heartbeat and health
Where possible, workers may communicate directly with PostgreSQL through controlled service interfaces. Sensitive or high-impact operations should still pass through backend service methods.
 
⸻
 
7.3.3 Webhook API
Receives provider-originated events.
Examples:
	•	Stripe billing events
	•	Google notifications, where supported
	•	GitHub events
	•	Vercel deployment events
	•	CRM lead events
	•	Form submissions
	•	SMS delivery receipts
	•	Email delivery events
Webhook endpoints must be isolated from ordinary user-facing routes.
 
⸻
 
7.3.4 Integration API
Used when an external customer system communicates directly with LILOs.
Potential examples:
	•	Submit a lead
	•	Retrieve lead status
	•	Trigger a report
	•	Create a content request
	•	Retrieve a product status
	•	Send an approved business event
This API should be introduced only for validated integration needs.
 
⸻
 
7.3.5 Operator Tool API
Used by Hermes or another authorized AI operator.
It exposes narrow, permissioned business tools such as:
	•	Read organization status
	•	List failed workflows
	•	Create a draft
	•	Run an SEO analysis
	•	Submit content for approval
	•	Retrieve a report
It must not expose unrestricted database, server, or credential access.
 
⸻
 
7.4 Recommended API Base Structure
The primary application API should use:
/api/v1/
Example resource layout:
/api/v1/organizations
/api/v1/locations
/api/v1/users
/api/v1/memberships
/api/v1/products
/api/v1/entitlements
/api/v1/configuration
/api/v1/integrations
/api/v1/workflows
/api/v1/approvals
/api/v1/notifications
/api/v1/reports
/api/v1/seo
/api/v1/gbp
/api/v1/reviews
/api/v1/content
/api/v1/leads
Webhook routes should use a separate namespace:
/api/webhooks/v1/stripe
/api/webhooks/v1/github
/api/webhooks/v1/vercel
/api/webhooks/v1/resend
/api/webhooks/v1/sms
Internal service routes, if required, should use:
/api/internal/v1/
Internal routes must not be accessible using normal client credentials.
 
⸻
 
7.5 Resource and Action Design
7.5.1 Standard Resource Operations
Typical resource endpoints may include:
GET    /api/v1/organizations
POST   /api/v1/organizations
GET    /api/v1/organizations/{organization_id}
PATCH  /api/v1/organizations/{organization_id}
Physical deletion should be uncommon.
Archive actions are preferred:
POST /api/v1/organizations/{organization_id}/archive
 
⸻
 
7.5.2 Business Actions
Business actions should be explicit.
Examples:
POST /api/v1/products/{product_key}/enable
POST /api/v1/integrations/{connection_id}/verify
POST /api/v1/workflows/{workflow_key}/run
POST /api/v1/approvals/{approval_id}/approve
POST /api/v1/approvals/{approval_id}/reject
POST /api/v1/content/{content_id}/submit-for-approval
POST /api/v1/content/{content_id}/publish
Business action endpoints should be used when a state transition has rules beyond a basic field update.
A client must not change:
status = published
through a generic update endpoint.
It must call the publication action.
 
⸻
 
7.6 Request Context
Every protected request should build a server-side request context.
Recommended context fields:
request_id
correlation_id
authenticated_user_id
organization_id
location_id
membership_id
permissions
product_entitlements
environment
client_ip
user_agent
request_started_at
The context should be passed into application services.
Services must not rely on global mutable request state.
 
⸻
 
7.7 Organization and Location Resolution
7.7.1 Organization Scope
Organization scope may be provided through:
	•	Route parameter
	•	Trusted session context
	•	Internal service payload
	•	API credential mapping
Example:
GET /api/v1/organizations/{organization_id}/locations
The server must verify that the caller has access to the provided organization.
 
⸻
 
7.7.2 Location Scope
Location scope should be explicit when a resource is location-specific.
Example:
POST /api/v1/organizations/{organization_id}/locations/{location_id}/gbp/posts
The service must verify:
	•	The location belongs to the organization.
	•	The caller has access to the location.
	•	The relevant product is enabled.
	•	The required integration exists.
 
⸻
 
7.7.3 Internal Cross-Tenant Requests
Internal staff may operate across organizations only through authorized roles.
Cross-tenant actions must create an audit event.
Support impersonation, if introduced, should use an explicit support-session mechanism rather than substituting identities invisibly.
 
⸻
 
7.8 Authentication
7.8.1 User Authentication
The application API should use Supabase-authenticated sessions.
The backend must validate:
	•	Token signature
	•	Token expiration
	•	User status
	•	Membership status
	•	Session requirements
Frontend possession of a session is not sufficient authorization.
 
⸻
 
7.8.2 Service Authentication
Trusted services should use dedicated service identities.
Examples:
	•	Scheduler worker
	•	SEO worker
	•	GBP worker
	•	Review worker
	•	Content worker
	•	Notification worker
Service identities should have:
	•	Unique credentials
	•	Minimal permissions
	•	Environment separation
	•	Rotation procedures
	•	Audit identity
Workers should not share one unrestricted credential when separate privileges are practical.
 
⸻
 
7.8.3 External API Authentication
External integrations may use:
	•	Scoped API keys
	•	OAuth
	•	Signed requests
	•	Mutual authentication where justified
External API credentials should map to:
	•	Organization
	•	Allowed locations
	•	Allowed products
	•	Allowed actions
	•	Expiration
	•	Rate limit
 
⸻
 
7.8.4 Webhook Authentication
Webhook requests must be authenticated using provider-supported verification.
Examples:
	•	Signature validation
	•	Shared signing secret
	•	Timestamp tolerance
	•	Provider certificate validation
	•	Event ID deduplication
A webhook request must not be trusted based solely on source IP.
 
⸻
 
7.9 Authorization
Every protected action must check:
	1.	Authentication
	2.	Active user or service status
	3.	Organization access
	4.	Location access
	5.	Required permission
	6.	Product entitlement
	7.	Feature entitlement, when applicable
	8.	Resource ownership
	9.	Action-specific policy
	10.	Approval state, when applicable
Example:
Publishing a GBP post may require:
authenticated
+
organization membership
+
location access
+
gbp.publish_post
+
active GBP entitlement
+
connected GBP resource
+
approved post revision
Authorization failures should not reveal information about resources the caller cannot access.
 
⸻
 
7.10 Request Standards
7.10.1 Content Type
JSON APIs should use:
Content-Type: application/json
File uploads should use:
multipart/form-data
 
⸻
 
7.10.2 Field Naming
API fields should use:
snake_case
This aligns with PostgreSQL and Python.
If frontend conventions differ, conversion should happen in a shared client layer rather than inconsistently across components.
 
⸻
 
7.10.3 Timestamps
Timestamps must use ISO 8601 with timezone information.
Example:
2026-07-27T19:45:12Z
The database stores UTC.
The interface renders according to organization, location, or user timezone.
 
⸻
 
7.10.4 Dates
Dates without time should use:
YYYY-MM-DD
 
⸻
 
7.10.5 Null and Missing Values
The API must distinguish between:
	•	Field omitted
	•	Field explicitly set to null
	•	Field set to an empty string
	•	Field set to an empty array
PATCH operations must not treat these as equivalent.
 
⸻
 
7.10.6 Identifiers
Internal identifiers should be represented as UUID strings.
External provider identifiers should have clearly named fields.
Avoid ambiguous fields such as:
account_id
when the intended value is:
google_account_id
stripe_customer_id
 
⸻
 
7.11 Standard Response Structure
Successful single-resource response:
{
  "data": {
    "id": "uuid",
    "status": "active"
  },
  "meta": {
    "request_id": "uuid"
  }
}
Successful collection response:
{
  "data": [],
  "pagination": {
    "next_cursor": null,
    "has_more": false
  },
  "meta": {
    "request_id": "uuid"
  }
}
Asynchronous workflow response:
{
  "data": {
    "workflow_execution_id": "uuid",
    "status": "queued"
  },
  "meta": {
    "request_id": "uuid"
  }
}
 
⸻
 
7.12 Error Model
7.12.1 Standard Error Response
{
  "error": {
    "code": "GBP_CONNECTION_REQUIRED",
    "message": "The Google Business Profile connection must be restored before publishing.",
    "category": "integration",
    "retryable": false,
    "details": {
      "integration_connection_id": "uuid"
    }
  },
  "meta": {
    "request_id": "uuid"
  }
}
 
⸻
 
7.12.2 Error Categories
Recommended categories:
authentication
authorization
validation
not_found
conflict
rate_limit
integration
workflow
approval
ai
billing
configuration
system
 
⸻
 
7.12.3 Stable Error Codes
Examples:
AUTHENTICATION_REQUIRED
SESSION_EXPIRED
PERMISSION_DENIED
ORGANIZATION_ACCESS_DENIED
LOCATION_ACCESS_DENIED
PRODUCT_NOT_ENABLED
FEATURE_NOT_ENABLED
RESOURCE_NOT_FOUND
VALIDATION_FAILED
CONFIGURATION_REQUIRED
INTEGRATION_CONNECTION_REQUIRED
INTEGRATION_AUTHORIZATION_EXPIRED
APPROVAL_REQUIRED
APPROVAL_EXPIRED
REVISION_MISMATCH
DUPLICATE_ACTION
WORKFLOW_ALREADY_RUNNING
WORKFLOW_FAILED
AI_OUTPUT_INVALID
PROVIDER_RATE_LIMITED
PROVIDER_UNAVAILABLE
IDEMPOTENCY_CONFLICT
Error codes must remain stable even when human-readable messages change.
 
⸻
 
7.12.4 HTTP Status Mapping
Recommended mappings:
200 OK
201 Created
202 Accepted
204 No Content
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Entity
429 Too Many Requests
500 Internal Server Error
502 Bad Gateway
503 Service Unavailable
Use 202 Accepted when a long-running workflow has been queued.
Use 409 Conflict for invalid state transitions or idempotency conflicts.
Use 422 Unprocessable Entity for structurally valid requests that fail domain validation.
 
⸻
 
7.12.5 Error Disclosure
Client-visible errors should provide actionable guidance without exposing:
	•	Secrets
	•	Raw provider tokens
	•	Database queries
	•	Stack traces
	•	Internal network information
	•	Other tenant identifiers
Detailed diagnostics belong in internal logs and agency-facing operational records.
 
⸻
 
7.13 Validation
Validation should occur at multiple levels.
Transport Validation
Checks:
	•	Required fields
	•	Field types
	•	Date formats
	•	Enum values
	•	Length limits
Domain Validation
Checks:
	•	Valid state transition
	•	Organization ownership
	•	Active entitlement
	•	Valid business policy
	•	Required integration
	•	Approval requirement
	•	Content revision match
Provider Validation
Checks:
	•	Provider-specific limits
	•	Supported media format
	•	Required external account scope
	•	Provider field restrictions
Output Validation
Checks:
	•	Response contract
	•	AI schema
	•	Publication result
	•	Provider identifier presence
Transport validation must not be mistaken for business validation.
 
⸻
 
7.14 Pagination
Cursor-based pagination is preferred for large or frequently changing collections.
Example request:
GET /api/v1/workflows?limit=50&cursor=encoded_cursor
Example response:
{
  "data": [],
  "pagination": {
    "next_cursor": "encoded_cursor",
    "has_more": true
  }
}
Offset pagination may be used for small administrative lists where consistency risk is low.
Maximum page sizes should be enforced.
 
⸻
 
7.15 Filtering, Sorting, and Search
Collection endpoints should use consistent query conventions.
Example:
GET /api/v1/workflows
    ?organization_id=uuid
    &location_id=uuid
    &product=gbp
    &status=failed
    &created_after=2026-07-01T00:00:00Z
    &sort=-created_at
Recommended conventions:
	•	Comma-separated values for multi-value filters
	•	Minus prefix for descending sort
	•	Explicit date-range fields
	•	Search limited to supported resources
	•	Server-side allowlists for sortable fields
Arbitrary SQL-like filters must not be exposed.
 
⸻
 
7.16 Partial Updates
PATCH requests should update only supplied fields.
Example:
PATCH /api/v1/locations/{location_id}
The service must validate:
	•	Which fields are editable
	•	Whether the user may edit them
	•	Whether changing them affects integrations
	•	Whether the change requires approval
	•	Whether the change creates a new version
Sensitive state changes should use explicit action endpoints rather than PATCH.
 
⸻
 
7.17 Idempotency
7.17.1 Idempotency Header
Retryable write endpoints should accept:
Idempotency-Key: unique-value
Examples:
	•	Publish GBP post
	•	Publish review response
	•	Send lead acknowledgment
	•	Create payment action
	•	Submit external lead
	•	Publish website content
 
⸻
 
7.17.2 Idempotency Scope
The stored idempotency record should include:
	•	Organization
	•	Endpoint or action
	•	Requesting identity
	•	Idempotency key
	•	Request hash
	•	Result reference
	•	Status
	•	Expiration
 
⸻
 
7.17.3 Conflicts
Reusing a key with the same request should return the original result where possible.
Reusing a key with a materially different request should return:
IDEMPOTENCY_CONFLICT
 
⸻
 
7.18 Concurrency Control
Concurrent edits must not silently overwrite one another.
Recommended techniques include:
	•	updated_at preconditions
	•	Version numbers
	•	Content hashes
	•	Optimistic locking
	•	Unique active-state constraints
Example request header:
If-Match: revision-hash
A stale update should return a conflict rather than overwrite newer work.
This is especially important for:
	•	Content revisions
	•	Review responses
	•	Product configuration
	•	Approval decisions
	•	Lead assignment
	•	Integration reconnection
 
⸻
 
7.19 Asynchronous Operations
7.19.1 Start Operation
Example:
POST /api/v1/seo/analyses
Response:
{
  "data": {
    "workflow_execution_id": "uuid",
    "status": "queued"
  }
}
 
⸻
 
7.19.2 Check Status
GET /api/v1/workflows/{workflow_execution_id}
Response may include:
	•	Status
	•	Current step
	•	Start time
	•	Last update
	•	Progress summary
	•	Retry state
	•	Approval state
	•	Result reference
	•	Error
 
⸻
 
7.19.3 Cancellation
POST /api/v1/workflows/{workflow_execution_id}/cancel
Cancellation must be best-effort.
An external action that has already completed may not be reversible.
The result must state whether:
	•	Execution was cancelled before action
	•	Partial work completed
	•	External action already occurred
	•	Manual reconciliation is required
 
⸻
 
7.20 Service Layer Structure
The backend should separate services into layers.
API Route
    ↓
Application Service
    ↓
Domain Service
    ↓
Repository or Adapter
API Route
Handles:
	•	Authentication
	•	Request parsing
	•	Context creation
	•	Response formatting
Application Service
Coordinates a business use case.
Example:
PublishApprovedGBPPost
Domain Service
Implements business rules.
Example:
GBPPostPolicy
ApprovalPolicy
PublicationEligibility
Repository
Reads and writes platform data.
Adapter
Communicates with an external provider.
 
⸻
 
7.21 Service Contract Standards
Every service method should define:
	•	Name
	•	Purpose
	•	Inputs
	•	Output
	•	Required context
	•	Permissions
	•	Entitlements
	•	State preconditions
	•	Side effects
	•	Errors
	•	Audit events
	•	Idempotency behavior
Example:
Service:
PublishGBPPost

Input:
organization_id
location_id
gbp_post_id
idempotency_key

Requires:
gbp.publish_post
active GBP entitlement
connected GBP location
approved active post revision

Output:
publication status
external post identifier
published timestamp

Side effects:
provider publication
post state transition
audit event
notification
workflow completion

Errors:
APPROVAL_REQUIRED
REVISION_MISMATCH
INTEGRATION_CONNECTION_REQUIRED
DUPLICATE_ACTION
PROVIDER_UNAVAILABLE
 
⸻
 
7.22 Repository Pattern
Repositories provide controlled data access.
Examples:
OrganizationRepository
LocationRepository
WorkflowRepository
ApprovalRepository
GBPPostRepository
ReviewRepository
ContentRepository
LeadRepository
Repositories should:
	•	Enforce organization scope
	•	Return domain-oriented records
	•	Centralize common queries
	•	Support transactions
	•	Avoid leaking raw database behavior into product services
Repositories should not contain:
	•	User-interface formatting
	•	AI prompts
	•	Provider calls
	•	Complex business decisions
 
⸻
 
7.23 Transaction Boundaries
Database transactions should protect operations that must succeed or fail together.
Examples:
	•	Create approval request and move item to awaiting approval
	•	Approve revision and update approval history
	•	Create lead and initial status history
	•	Enable product and apply initial configuration
	•	Record publication and mark content published
	•	Create workflow execution and enqueue first step
External provider calls should not remain inside long-held database transactions.
Preferred pattern:
	1.	Validate state.
	2.	Reserve or mark action pending.
	3.	Commit transaction.
	4.	Call external provider.
	5.	Record success or failure in a new transaction.
 
⸻
 
7.24 Product Service Boundaries
Each product owns its domain logic.
SEO Service
Owns:
	•	SEO properties
	•	Metric analysis
	•	Opportunity generation
	•	Opportunity status
	•	Outcome measurement
GBP Service
Owns:
	•	GBP profile records
	•	Recommendations
	•	Posts
	•	Publication eligibility
	•	GBP-specific provider actions
Reviews Service
Owns:
	•	Review normalization
	•	Risk flags
	•	Response drafts
	•	Response publication policy
Content Service
Owns:
	•	Content items
	•	Briefs
	•	Revisions
	•	Approval readiness
	•	Publication destinations
Leads Service
Owns:
	•	Lead normalization
	•	Lead state
	•	Assignment
	•	Communication eligibility
	•	Conversation state
Insights Service
Owns:
	•	Metric definitions
	•	Aggregation
	•	Report generation
	•	Report delivery
Products must not directly modify another product’s tables.
Cross-product actions should use:
	•	Application service contracts
	•	Events
	•	Workflow requests
 
⸻
 
7.25 Cross-Product Service Calls
Direct synchronous service calls may be used for small, reliable internal reads.
Example:
Content Service requests approved SEO opportunity context.
Events or workflows should be used when:
	•	The action may take time.
	•	The action may fail independently.
	•	Human approval may be required.
	•	The initiating product should not wait.
	•	Multiple products may consume the result.
Example:
seo.opportunity_approved
may initiate:
content.create_brief
 
⸻
 
7.26 Event Contract
Every event should have a standard envelope.
{
  "event_id": "uuid",
  "event_type": "review.received",
  "event_version": 1,
  "occurred_at": "2026-07-27T19:45:12Z",
  "organization_id": "uuid",
  "location_id": "uuid",
  "product": "reviews",
  "actor": {
    "type": "integration",
    "id": "uuid"
  },
  "correlation_id": "uuid",
  "data": {
    "review_id": "uuid"
  }
}
Event payloads should be concise.
Consumers should retrieve full records through services when needed.
 
⸻
 
7.27 Event Versioning
Event types require independent versions.
Example:
review.received v1
review.received v2
Consumers must declare supported versions.
Breaking payload changes require a new event version.
Adding optional fields may remain backward-compatible.
 
⸻
 
7.28 Webhook Processing Model
Webhook processing should follow:
Receive
↓
Authenticate
↓
Check timestamp
↓
Deduplicate
↓
Store original event reference
↓
Acknowledge provider
↓
Process asynchronously
↓
Normalize
↓
Create platform event
↓
Record result
The provider should receive a timely acknowledgment.
Complex processing must not occur before acknowledgment unless required for validation.
 
⸻
 
7.29 Webhook Event Storage
Webhook records should include:
provider
provider_event_id
event_type
received_at
signature_valid
processing_status
organization_id
integration_connection_id
payload_reference
attempt_count
processed_at
error_code
error_message
Sensitive payloads should be retained only according to policy.
Duplicate events should be acknowledged without repeating side effects.
 
⸻
 
7.30 Webhook Replay
Authorized internal users should be able to replay failed webhook processing.
Replay must:
	•	Retain the original provider event ID
	•	Create a new processing attempt
	•	Preserve audit history
	•	Reuse idempotency protections
	•	Avoid duplicating completed external actions
 
⸻
 
7.31 Integration Adapter Contract
Each provider adapter should implement a defined interface.
Example categories:
authenticate
verify_connection
list_resources
fetch_resource
sync_data
create_resource
update_resource
delete_resource
publish
get_status
normalize_error
Not every provider supports every action.
Unsupported operations should return a defined capability error.
 
⸻
 
7.32 Provider Capability Discovery
Integration providers should declare capabilities.
Example:
{
  "provider": "google_business_profile",
  "capabilities": [
    "locations.read",
    "posts.create",
    "reviews.read",
    "reviews.respond"
  ]
}
Product activation should validate required capabilities before marking the product ready.
 
⸻
 
7.33 Integration Error Normalization
Provider-specific errors should be converted to internal categories.
Example:
Google 401
↓
INTEGRATION_AUTHORIZATION_EXPIRED
Provider 429
↓
PROVIDER_RATE_LIMITED
Missing OAuth scope
↓
INTEGRATION_PERMISSION_DENIED
The original provider error may be retained internally for diagnosis.
Product logic should respond to normalized errors.
 
⸻
 
7.34 AI Gateway Service Contract
Products should invoke AI through a shared contract.
Example request:
{
  "task_type": "review_response_generation",
  "organization_id": "uuid",
  "location_id": "uuid",
  "workflow_execution_id": "uuid",
  "input": {
    "review_id": "uuid",
    "business_context": {},
    "policy_context": {}
  },
  "requirements": {
    "output_schema": "review_response_v1",
    "maximum_cost": 0.10,
    "timeout_seconds": 30
  }
}
Example response:
{
  "execution_id": "uuid",
  "status": "completed",
  "provider": "provider_key",
  "model": "model_key",
  "prompt_version": 4,
  "output": {
    "response_text": "..."
  },
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 120,
    "estimated_cost": 0.01
  }
}
Product services must not supply arbitrary unversioned prompts.
They should provide structured task inputs.
 
⸻
 
7.35 Approval Service Contract
Recommended actions:
create_approval_request
approve
reject
request_revision
cancel
expire
get_active_approval
list_pending_approvals
Approval service responsibilities include:
	•	Permission validation
	•	Revision or hash verification
	•	Separation-of-duties rules
	•	Expiration
	•	History
	•	Workflow continuation
	•	Notifications
	•	Audit events
Product services determine what requires approval.
The shared service manages the approval process.
 
⸻
 
7.36 Notification Service Contract
Products should request notifications through a standard message.
Example:
{
  "organization_id": "uuid",
  "event_type": "approval.requested",
  "severity": "normal",
  "audience": {
    "required_permission": "gbp.approve_post"
  },
  "content": {
    "title": "GBP post awaiting approval",
    "message": "A post is ready for review.",
    "action_url": "/app/client/approvals/uuid"
  }
}
The notification service determines:
	•	Eligible users
	•	User preferences
	•	Delivery channel
	•	Retry behavior
	•	Delivery provider
 
⸻
 
7.37 File Upload API
File uploads should use a controlled process.
Recommended pattern:
	1.	Request upload authorization.
	2.	Receive a signed upload URL or upload session.
	3.	Upload directly to approved object storage.
	4.	Complete upload registration.
	5.	Validate file.
	6.	Attach file reference to product record.
The platform must validate:
	•	File type
	•	File size
	•	Extension
	•	Content signature
	•	Organization ownership
	•	Malware risk where appropriate
	•	Image dimensions where required
	•	Retention category
The original filename must not determine the storage path.
 
⸻
 
7.38 File Download API
Protected files should use:
	•	Signed temporary URLs
	•	Authorization checks
	•	Short expiration
	•	Audit logging for sensitive exports
Direct public object URLs should be limited to intentionally public assets.
 
⸻
 
7.39 Bulk Operations
Bulk endpoints may be introduced for validated use cases.
Examples:
	•	Approve multiple low-risk GBP posts
	•	Assign multiple SEO opportunities
	•	Export multiple leads
	•	Update multiple location settings
Bulk operations must return per-item results.
Example:
{
  "data": {
    "completed": 18,
    "failed": 2,
    "results": [
      {
        "id": "uuid",
        "status": "completed"
      },
      {
        "id": "uuid",
        "status": "failed",
        "error_code": "APPROVAL_EXPIRED"
      }
    ]
  }
}
A partial failure must not be represented as complete success.
 
⸻
 
7.40 Rate Limiting
Rate limits should be applied by:
	•	User
	•	Organization
	•	API credential
	•	Endpoint
	•	Provider dependency
	•	Operation risk
Higher-risk endpoints should have stricter limits.
Examples:
	•	Login attempts
	•	AI generation
	•	Lead submissions
	•	Customer messaging
	•	Publication
	•	Report exports
	•	Integration verification
Internal services should also respect provider rate limits.
 
⸻
 
7.41 Abuse and Spam Controls
Public or externally accessible endpoints should support:
	•	Rate limiting
	•	CAPTCHA where justified
	•	Honeypot fields
	•	Payload-size limits
	•	Duplicate detection
	•	IP and reputation controls
	•	Input sanitization
	•	Email and phone normalization
	•	Quarantine states
	•	Manual review
Lead ingestion must not automatically trigger unrestricted communication without consent and spam evaluation.
 
⸻
 
7.42 API Versioning
7.42.1 URL Versioning
The initial public API should use URL versioning:
/api/v1/
7.42.2 Breaking Changes
Breaking changes require a new major API version.
Examples:
	•	Removing a required field
	•	Changing field meaning
	•	Changing response shape
	•	Changing authentication
	•	Changing an action’s side effects
7.42.3 Non-Breaking Changes
Generally non-breaking:
	•	Adding optional fields
	•	Adding new endpoints
	•	Adding new enum values when consumers are designed to tolerate them
	•	Adding new error details
Enum expansion should be treated cautiously because some clients may implement exhaustive matching.
 
⸻
 
7.43 API Deprecation
Deprecation should include:
	•	Deprecation notice
	•	Replacement endpoint
	•	Migration guidance
	•	Defined removal date
	•	Usage monitoring
	•	Internal owner
Production consumers should not discover breaking removal without notice.
 
⸻
 
7.44 API Documentation
FastAPI should generate OpenAPI documentation.
Documentation must include:
	•	Purpose
	•	Authentication
	•	Permissions
	•	Entitlements
	•	Request schema
	•	Response schema
	•	Error codes
	•	Idempotency behavior
	•	Example requests
	•	Example responses
	•	Side effects
	•	Rate limits
	•	Version
Generated documentation should be supplemented with business-context documentation for complex workflows.
 
⸻
 
7.45 Client SDKs
The web application should use a shared typed API client.
The client should provide:
	•	Authentication headers
	•	Request IDs
	•	Typed requests
	•	Typed responses
	•	Error normalization
	•	Retry rules for safe reads
	•	Idempotency-key generation where appropriate
	•	Pagination helpers
Product components should not construct inconsistent raw fetch requests throughout the frontend.
External SDKs should only be created after stable external demand exists.
 
⸻
 
7.46 API Observability
Every API request should record:
request_id
correlation_id
route
method
status_code
duration_ms
user_id or service_id
organization_id
location_id
product
error_code
Sensitive request and response bodies must not be logged by default.
Operational dashboards should identify:
	•	Slow endpoints
	•	Error rates
	•	Authorization failures
	•	Provider failures
	•	Queue-creation failures
	•	Repeated validation errors
	•	Rate-limit activity
 
⸻
 
7.47 Health Endpoints
Recommended health endpoints:
GET /health/live
GET /health/ready
GET /health/dependencies
Live
Confirms the process is running.
Ready
Confirms the service can accept work.
Dependencies
Checks approved dependencies such as:
	•	Database
	•	Queue or workflow store
	•	Required internal services
Public health responses must not expose sensitive infrastructure details.
Detailed dependency diagnostics should be restricted to internal users.
 
⸻
 
7.48 API Performance Standards
Initial performance objectives should distinguish between synchronous and asynchronous work.
Synchronous read and configuration endpoints should generally:
	•	Avoid unnecessary provider calls
	•	Use indexed queries
	•	Return bounded data
	•	Complete predictably
Provider synchronization and AI work should be asynchronous.
The API should not promise immediate completion when external systems control latency.
Performance targets should be established after baseline measurements rather than invented without evidence.
 
⸻
 
7.49 Caching
Caching may be used for:
	•	Stable product definitions
	•	Permission definitions
	•	Industry defaults
	•	Recently generated reports
	•	Provider metadata
	•	Expensive read-only aggregations
Caching must not bypass:
	•	Tenant isolation
	•	Entitlement changes
	•	Permission revocation
	•	Approval state
	•	Integration status
Cache keys must include tenant and relevant scope.
Redis is not required initially.
PostgreSQL, application memory, and platform caching may be sufficient until measured limitations appear.
 
⸻
 
7.50 API Testing
Each endpoint should have tests for:
	•	Authentication
	•	Authorization
	•	Tenant isolation
	•	Validation
	•	Successful response
	•	Not-found behavior
	•	Invalid state transition
	•	Entitlement failure
	•	Provider failure
	•	Idempotency
	•	Concurrency conflict
	•	Audit creation
	•	Error response format
High-impact actions additionally require tests for:
	•	Approval enforcement
	•	Duplicate prevention
	•	External action reconciliation
	•	Partial failure
	•	Retry behavior
 
⸻
 
7.51 Contract Testing
Contract tests should verify communication between:
	•	Frontend and application API
	•	API and workers
	•	Product services and repositories
	•	Product services and integration adapters
	•	Product services and AI gateway
	•	Webhook handlers and provider event schemas
	•	Event producers and consumers
Provider adapters should use fixtures based on sanitized provider responses.
Tests must not rely solely on live third-party systems.
 
⸻
 
7.52 API Security Standards
The API must protect against:
	•	Broken object-level authorization
	•	Broken function-level authorization
	•	Injection
	•	Cross-tenant access
	•	Excessive data exposure
	•	Mass assignment
	•	Replay attacks
	•	Unsigned webhooks
	•	Unrestricted file upload
	•	Rate-limit bypass
	•	Secret leakage
	•	Insecure error output
Request models should explicitly declare writable fields.
Database models must not be accepted directly as public write schemas.
 
⸻
 
7.53 Operator Tool Architecture
An AI operator should receive a curated tool catalog.
Example tools:
organizations.get_status
workflows.list_failures
workflows.retry
seo.run_analysis
gbp.create_post_draft
reviews.generate_response
content.create_brief
approvals.submit
reports.retrieve
Each tool must define:
	•	Input schema
	•	Output schema
	•	Required permission
	•	Product entitlement
	•	Risk level
	•	Approval requirements
	•	Side effects
	•	Idempotency behavior
	•	Audit behavior
Operator tools should generally call application services rather than public HTTP endpoints internally.
 
⸻
 
7.54 Operator Confirmation Rules
An operator may perform low-risk read operations directly when authorized.
Write operations should follow configured risk policies.
Examples that may require explicit human confirmation:
	•	Publishing content
	•	Sending customer communications
	•	Changing business hours
	•	Changing GBP categories
	•	Updating billing
	•	Disabling a product
	•	Deleting or archiving data
	•	Retrying a workflow that may repeat an external action
The operator must not reinterpret confirmation policy on its own.
 
⸻
 
7.55 Initial API Implementation Order
Stage 1 — Shared API Foundation
Implement:
	•	Request context
	•	Authentication middleware
	•	Permission checks
	•	Entitlement checks
	•	Standard response format
	•	Standard error format
	•	Request and correlation IDs
	•	Audit integration
	•	OpenAPI generation
Stage 2 — Tenant and Access APIs
Implement:
	•	Organizations
	•	Locations
	•	Memberships
	•	Roles
	•	Entitlements
	•	Configuration
Stage 3 — Integration and Workflow APIs
Implement:
	•	Integration connections
	•	Integration resources
	•	Connection verification
	•	Workflow creation
	•	Workflow status
	•	Retry
	•	Cancellation
	•	Approval actions
Stage 4 — AI Gateway Contract
Implement:
	•	Task execution
	•	Structured output
	•	Model-routing response
	•	Cost tracking
	•	Failure and fallback records
Stage 5 — First Product API
Implement SEO:
	•	Properties
	•	Analyses
	•	Opportunities
	•	Opportunity status
	•	Measurement
Stage 6 — Additional Product APIs
Add:
	•	GBP
	•	Reviews
	•	Content
	•	Insights
	•	Leads
	•	Automations
Each product API should be added only when its domain workflow is ready.
 
⸻
 
7.56 API Guardrails
The following are prohibited unless formally approved:
	1.	Business logic embedded in route handlers
	2.	Product modules calling provider SDKs directly
	3.	Client-supplied organization scope trusted without verification
	4.	Generic status updates used to bypass business transitions
	5.	Long-running work performed synchronously in user requests
	6.	Arbitrary unstructured error responses
	7.	Public exposure of provider payloads
	8.	Unauthenticated webhook processing
	9.	Write endpoints without idempotency where duplicate action is possible
	10.	Frontend components constructing inconsistent authorization logic
	11.	Direct table mutation by an AI operator
	12.	Direct provider credential access by product code
	13.	Public APIs returning internal diagnostic or cost data without permission
	14.	Breaking API changes without versioning
	15.	Database models reused directly as public write schemas
	16.	Cross-product table modification
	17.	Silent partial success
	18.	Unbounded collection endpoints
	19.	API keys with unrestricted tenant access
	20.	Sensitive request or response bodies logged by default
 
⸻
 
7.57 Section Decisions
This section establishes the following decisions:
	1.	The platform uses versioned resource-oriented APIs with explicit business-action endpoints.
	2.	Business logic belongs in services, not route handlers.
	3.	Every protected request resolves organization, location, permission, and entitlement scope.
	4.	Long-running work returns a workflow execution rather than blocking the request.
	5.	Errors use stable machine-readable codes.
	6.	Write operations that may be retried use idempotency protections.
	7.	Concurrent updates use version, hash, or optimistic-lock checks.
	8.	Product services own their domain and do not directly modify other product tables.
	9.	Cross-product asynchronous behavior uses versioned events and workflows.
	10.	External providers are accessed through normalized adapters.
	11.	Webhooks are authenticated, deduplicated, stored, and processed asynchronously.
	12.	AI access occurs through a shared task-based gateway.
	13.	Approval, notification, and workflow capabilities are shared platform services.
	14.	Public, internal, webhook, and operator APIs are separate surfaces.
	15.	APIs use generated and validated contracts.
	16.	API documentation is generated through OpenAPI and supplemented for complex business behavior.
	17.	Every endpoint must be tested for tenant isolation and authorization.
	18.	AI operators receive narrow business tools rather than unrestricted infrastructure access.
	19.	New APIs should be implemented product by product after the shared foundation is stable.
	20.	API design must preserve the ability to replace providers, workers, and operator interfaces without rewriting product logic.


---

Section 8 — AI Architecture, Model Governance, and Evaluation
8.1 Purpose of This Section
This section defines how artificial intelligence is used inside the LILOs platform.
It establishes:
	•	The role of AI within the platform
	•	The shared AI gateway
	•	Provider and model abstraction
	•	Task-based model routing
	•	Prompt management
	•	Structured input and output contracts
	•	Context assembly
	•	Retrieval and grounding
	•	Validation
	•	Human approval
	•	Cost and latency controls
	•	Fallback behavior
	•	Quality evaluation
	•	Experimentation
	•	Security and privacy controls
	•	AI operator architecture
	•	Prohibited AI behavior
The purpose of this architecture is not to maximize AI usage.
The purpose is to use AI selectively where it creates measurable operational value while keeping the platform reliable, replaceable, auditable, and understandable.
 
⸻
 
8.2 AI Position Within the Platform
AI is a shared platform capability.
It is not:
	•	The platform database
	•	The workflow engine
	•	The permissions system
	•	The billing system
	•	The integration layer
	•	The audit system
	•	The source of truth for client configuration
	•	The sole interface for platform operation
AI operates within product workflows.
Example:
Product Workflow
    ↓
Prepare Structured Context
    ↓
Invoke AI Task
    ↓
Validate Structured Output
    ↓
Apply Business Rules
    ↓
Human Approval, if required
    ↓
Continue Workflow
The workflow exists independently from the model.
A model may be replaced without redesigning the workflow.
 
⸻
 
8.3 AI Architecture Principles
Principle 1 — Task First, Model Second
Product code requests an AI task.
It does not request a specific vendor model.
Correct:
Generate Review Response
Incorrect:
Call Claude Model X
The routing layer determines which approved model should perform the task.
 
⸻
 
Principle 2 — AI Is Replaceable
No product should depend on:
	•	One provider
	•	One model
	•	One prompt format
	•	One response format
	•	One operator
	•	One proprietary agent framework
The platform must support replacing a provider through configuration and adapters.
 
⸻
 
Principle 3 — Structured Inputs and Outputs
AI tasks should use structured inputs and validated outputs wherever the result is consumed by software.
Unstructured model text must not directly control:
	•	Permissions
	•	Product entitlements
	•	Billing
	•	Workflow status
	•	Consent
	•	Publication
	•	Security policy
	•	Data deletion
	•	External commitments
 
⸻
 
Principle 4 — Deterministic Rules Override AI
AI may recommend, classify, summarize, or draft.
Deterministic systems decide:
	•	Whether the user has permission
	•	Whether a product is enabled
	•	Whether consent exists
	•	Whether approval is required
	•	Whether a schedule is active
	•	Whether a record belongs to an organization
	•	Whether publication may proceed
	•	Whether a communication is legally or operationally eligible
 
⸻
 
Principle 5 — Every AI Action Is Traceable
The platform must record:
	•	Task type
	•	Provider
	•	Model
	•	Prompt version
	•	Structured input reference
	•	Structured output
	•	Token usage
	•	Cost
	•	Latency
	•	Validation result
	•	Fallback usage
	•	Approval result
	•	Human edits
	•	Business outcome where measurable
 
⸻
 
Principle 6 — AI Quality Must Be Measured
A response that looks acceptable is not sufficient evidence of system quality.
The platform should measure:
	•	Approval rate
	•	Rejection rate
	•	Revision rate
	•	Human editing required
	•	Factual error rate
	•	Policy violation rate
	•	Cost
	•	Latency
	•	Workflow success
	•	Business outcome
 
⸻
 
Principle 7 — More Capable Models Are Not Always Better
The strongest or most expensive model should not automatically handle every task.
A lower-cost model may be appropriate for:
	•	Classification
	•	Extraction
	•	Tagging
	•	Simple summarization
	•	Format normalization
A stronger model may be appropriate for:
	•	Complex SEO analysis
	•	Long-form content
	•	Nuanced risk review
	•	Difficult reasoning
	•	Multi-document synthesis
 
⸻
 
Principle 8 — AI Must Fail Safely
When AI fails, the system should:
	•	Preserve the workflow record
	•	Record the failure
	•	Retry only when appropriate
	•	Use an approved fallback when configured
	•	Escalate when necessary
	•	Avoid unauthorized publication or communication
	•	Allow manual completion
A model failure must not create an uncontrolled system failure.
 
⸻
 
8.4 AI System Components
The AI architecture contains the following components:
Product Service
    ↓
AI Task Service
    ↓
Context Builder
    ↓
Prompt Registry
    ↓
Routing Policy
    ↓
Provider Adapter
    ↓
Model
    ↓
Output Validator
    ↓
Evaluation and Usage Records
The main components are:
	1.	AI task registry
	2.	Model registry
	3.	Provider adapters
	4.	Routing policies
	5.	Prompt registry
	6.	Context assembly
	7.	Structured output schemas
	8.	Validation pipeline
	9.	Evaluation framework
	10.	Cost and usage controls
	11.	Experimentation system
	12.	Operator tool layer
 
⸻
 
8.5 AI Gateway
8.5.1 Purpose
The AI gateway is the single approved platform interface for model execution.
It is responsible for:
	•	Accepting task-based requests
	•	Resolving approved prompt versions
	•	Selecting a model
	•	Building provider requests
	•	Enforcing limits
	•	Calling the provider
	•	Validating output
	•	Handling retries
	•	Applying fallbacks
	•	Recording usage
	•	Returning normalized results
Products must not call provider SDKs directly.
 
⸻
 
8.5.2 Gateway Request
A normalized request should include:
task_type
organization_id
location_id
product_id
workflow_execution_id
input
context_references
output_schema
routing_policy
maximum_cost
maximum_latency
approval_policy
sensitivity_classification
Example:
{
  "task_type": "gbp_post_generation",
  "organization_id": "uuid",
  "location_id": "uuid",
  "product_id": "gbp",
  "workflow_execution_id": "uuid",
  "input": {
    "topic": "weekend brunch",
    "offer": null,
    "call_to_action": {
      "type": "learn_more",
      "url": "https://example.com/brunch"
    }
  },
  "context_references": {
    "organization_profile_id": "uuid",
    "location_profile_id": "uuid",
    "content_policy_version": 4
  },
  "requirements": {
    "output_schema": "gbp_post_v1",
    "maximum_cost": 0.08,
    "maximum_latency_ms": 30000
  }
}
 
⸻
 
8.5.3 Gateway Response
A normalized result should include:
{
  "ai_execution_id": "uuid",
  "status": "completed",
  "task_type": "gbp_post_generation",
  "provider": "provider_key",
  "model": "model_key",
  "prompt_version": 7,
  "output": {
    "post_body": "...",
    "call_to_action_type": "learn_more"
  },
  "validation": {
    "schema_valid": true,
    "policy_valid": true,
    "requires_human_review": true
  },
  "usage": {
    "input_tokens": 1800,
    "output_tokens": 140,
    "estimated_cost": 0.02,
    "latency_ms": 4200
  }
}
 
⸻
 
8.6 AI Task Registry
8.6.1 Purpose
The task registry defines the approved AI functions available to the platform.
Each task is independent from a provider or model.
Examples:
seo.opportunity_summary
seo.query_clustering
seo.search_intent_classification
seo.content_gap_analysis

gbp.post_generation
gbp.profile_recommendation_summary
gbp.category_relevance_analysis

reviews.risk_classification
reviews.sentiment_classification
reviews.topic_classification
reviews.response_generation

content.brief_generation
content.outline_generation
content.draft_generation
content.revision
content.metadata_generation

leads.intent_classification
leads.urgency_classification
leads.response_generation
leads.conversation_summary

insights.performance_summary
insights.anomaly_explanation
 
⸻
 
8.6.2 Task Definition Requirements
Every AI task must define:
	•	Task key
	•	Business purpose
	•	Owning product
	•	Input schema
	•	Output schema
	•	Risk level
	•	Approved use cases
	•	Prohibited use cases
	•	Default routing policy
	•	Maximum cost
	•	Maximum latency
	•	Required validators
	•	Approval requirements
	•	Retention policy
	•	Evaluation criteria
	•	Fallback behavior
No production task should exist only as an informal prompt.
 
⸻
 
8.7 Provider Abstraction
8.7.1 Provider Interface
Every provider adapter should implement a normalized interface.
Recommended capabilities:
generate_text
generate_structured_output
classify
embed
analyze_image
use_tools
stream
estimate_tokens
normalize_error
check_health
Not every provider or model must support every capability.
The adapter must expose supported features.
 
⸻
 
8.7.2 Initial Provider Support
The platform may support adapters for:
	•	OpenAI
	•	Anthropic
	•	Google
	•	OpenRouter
	•	xAI
	•	DeepSeek
	•	Self-hosted models
	•	Local models
	•	Specialized third-party models
Provider support should be added based on validated task needs, not for completeness.
 
⸻
 
8.7.3 Provider-Specific Logic
Provider-specific behavior belongs inside the adapter.
Examples:
	•	Authentication
	•	Message formatting
	•	Tool format
	•	Structured-output configuration
	•	Token counting
	•	Retry headers
	•	Rate limits
	•	Safety settings
	•	Provider error mapping
Product services must receive a normalized result.
 
⸻
 
8.8 Model Registry
8.8.1 Purpose
The model registry stores the operational characteristics of available models.
Each model record should include:
	•	Provider
	•	Model identifier
	•	Model family
	•	Status
	•	Supported modalities
	•	Context limit
	•	Structured-output support
	•	Tool support
	•	Input price
	•	Output price
	•	Expected latency
	•	Approved data classifications
	•	Approved task types
	•	Known limitations
	•	Effective date of pricing and capabilities
 
⸻
 
8.8.2 Model Status
Recommended model states:
testing
approved
preferred
degraded
disabled
deprecated
retired
A deprecated model may continue serving existing experiments but should not receive new production routing.
A retired model must not receive production traffic.
 
⸻
 
8.8.3 Model Capability Records
Capabilities should be represented explicitly.
Examples:
text_generation
structured_output
long_context
vision
tool_use
reasoning
low_latency
high_volume_classification
code_generation
embedding
Product code should not infer capability from model names.
 
⸻
 
8.9 Model Routing
8.9.1 Routing Inputs
Model selection may consider:
	•	Task type
	•	Product
	•	Organization policy
	•	Industry
	•	Input size
	•	Output size
	•	Risk level
	•	Required modality
	•	Required structured-output support
	•	Quality threshold
	•	Cost ceiling
	•	Latency ceiling
	•	Provider health
	•	Current rate limits
	•	Experiment assignment
	•	Data sensitivity
 
⸻
 
8.9.2 Default Routing Pattern
Example:
Task Request
    ↓
Check Required Capabilities
    ↓
Apply Organization Restrictions
    ↓
Filter Approved Models
    ↓
Apply Quality Requirement
    ↓
Apply Cost and Latency Limits
    ↓
Select Primary Model
    ↓
Execute
    ↓
Validate
    ↓
Fallback if Eligible
 
⸻
 
8.9.3 Routing Policies
A routing policy may define:
primary_model
fallback_models
maximum_cost
maximum_latency
minimum_quality_score
maximum_attempts
provider_exclusions
data_residency_requirements
Routing policies should be versioned.
 
⸻
 
8.9.4 Organization Overrides
An organization may require:
	•	A specific provider
	•	Provider exclusion
	•	No external AI processing
	•	Reduced data retention
	•	Human approval for every output
	•	Lower cost limits
	•	Specific model class
	•	No model training usage where provider controls support it
Organization policy may restrict platform defaults but should not silently weaken platform safety controls.
 
⸻
 
8.10 Prompt Architecture
8.10.1 Prompts Are Versioned Assets
Prompts are part of the software system.
They must be:
	•	Stored outside product business logic
	•	Versioned
	•	Reviewed
	•	Tested
	•	Approved
	•	Auditable
	•	Reversible
Production workflows must reference an approved prompt version.
 
⸻
 
8.10.2 Prompt Components
A prompt may contain:
	1.	System instructions
	2.	Task instructions
	3.	Structured business context
	4.	Input data
	5.	Rules and constraints
	6.	Output schema
	7.	Examples, when justified
	8.	Validation reminders
Business facts should be supplied as structured context rather than embedded permanently in the prompt.
 
⸻
 
8.10.3 Prompt Separation
Prompts should separate:
	•	Platform-level rules
	•	Product-level rules
	•	Industry defaults
	•	Organization policies
	•	Location context
	•	Task input
Example:
Platform Safety Rules
    +
Review Product Policy
    +
Restaurant Industry Policy
    +
Client Brand Guidance
    +
Location Details
    +
Specific Review
This avoids maintaining separate full prompts for every client.
 
⸻
 
8.10.4 Prompt Immutability
Approved prompt versions are immutable.
Changes create a new version.
The platform must record which version generated each result.
 
⸻
 
8.10.5 Prompt Injection Protection
External content must be treated as untrusted input.
Examples include:
	•	Customer reviews
	•	Lead messages
	•	Website content
	•	Uploaded files
	•	Search results
	•	Emails
	•	CRM notes
The system must not allow untrusted text to override platform instructions.
Controls should include:
	•	Clear separation of instructions and data
	•	Structured delimiters
	•	Restricted tool access
	•	Output validation
	•	Data minimization
	•	Explicit task scope
	•	No provider secrets in model context
 
⸻
 
8.11 Context Assembly
8.11.1 Purpose
The context builder gathers only the information required for the task.
Potential context sources include:
	•	Organization profile
	•	Location profile
	•	Product configuration
	•	Industry defaults
	•	Approved claims
	•	Prohibited claims
	•	Recent related outputs
	•	Source metrics
	•	Review text
	•	Lead record
	•	Content brief
	•	Publication history
 
⸻
 
8.11.2 Context Hierarchy
Context should follow this precedence:
Platform Rules
    ↓
Product Rules
    ↓
Industry Rules
    ↓
Organization Rules
    ↓
Location Rules
    ↓
Workflow Rules
    ↓
Task Input
More specific context may override stylistic defaults.
It must not override platform security or legal restrictions.
 
⸻
 
8.11.3 Context Minimization
The model should receive only necessary data.
Do not send:
	•	Entire client databases
	•	Unrelated leads
	•	Unrelated reviews
	•	All historical content
	•	Provider credentials
	•	Internal billing information
	•	Other organizations’ data
	•	Sensitive operational notes without need
Context minimization reduces:
	•	Privacy risk
	•	Prompt cost
	•	Latency
	•	Confusion
	•	Cross-client leakage risk
 
⸻
 
8.12 Retrieval and Grounding
8.12.1 Grounding Sources
AI output may be grounded in:
	•	Platform database records
	•	Approved business profiles
	•	Product configuration
	•	Google data
	•	Website content
	•	Approved source documents
	•	Integration data
	•	Version-controlled content
	•	Explicitly approved external research
The source of important claims should be traceable.
 
⸻
 
8.12.2 Retrieval Pattern
Recommended pattern:
Task
    ↓
Determine Required Sources
    ↓
Retrieve Authorized Records
    ↓
Normalize and Rank
    ↓
Build Context
    ↓
Generate
    ↓
Validate Against Sources
 
⸻
 
8.12.3 Vector Search
A dedicated vector database is not required initially.
PostgreSQL with an approved vector extension may be used when semantic retrieval is justified.
Vector retrieval should not be introduced merely because the platform uses AI.
Valid use cases may include:
	•	Finding similar previously approved content
	•	Retrieving relevant brand rules
	•	Matching a lead to service descriptions
	•	Identifying duplicate content themes
	•	Retrieving relevant operational knowledge
Relational queries remain preferable for exact structured facts.
 
⸻
 
8.12.4 Source Authority
Sources should have an authority order.
Example:
Approved Client Configuration
    ↓
Verified Integration Data
    ↓
Published Client Website
    ↓
Approved Internal Records
    ↓
External Research
    ↓
Model General Knowledge
The model must not override verified client data with general knowledge.
 
⸻
 
8.13 Structured Output
8.13.1 Requirement
AI output consumed by software should use a versioned schema.
Example review-response output:
{
  "response_text": "Thank you for the feedback...",
  "risk_flags": [],
  "requires_human_review": false,
  "reasoning_summary": "Positive four-star review with no risk indicators."
}
 
⸻
 
8.13.2 Schema Versioning
Schemas should be named and versioned.
Examples:
review_response_v1
gbp_post_v2
seo_opportunity_summary_v1
content_brief_v3
lead_classification_v1
Breaking changes require a new version.
 
⸻
 
8.13.3 Validation Failure
When output fails schema validation:
	1.	Record the invalid execution.
	2.	Retry using a constrained repair attempt if allowed.
	3.	Use a fallback model if configured.
	4.	Escalate when attempts are exhausted.
	5.	Do not continue the workflow with partially interpreted output.
 
⸻
 
8.14 Validation Pipeline
AI outputs may pass through multiple validators.
Schema Validation
    ↓
Required Field Validation
    ↓
Business Rule Validation
    ↓
Claim Validation
    ↓
Brand Validation
    ↓
Risk Validation
    ↓
Duplicate Validation
    ↓
Approval Policy
 
⸻
 
8.14.1 Schema Validation
Confirms:
	•	Correct structure
	•	Correct types
	•	Required fields
	•	Allowed enum values
	•	Length constraints
 
⸻
 
8.14.2 Business Validation
Confirms:
	•	Active product context
	•	Valid call to action
	•	Allowed offer
	•	Valid service
	•	Correct location
	•	Appropriate workflow state
 
⸻
 
8.14.3 Claim Validation
Checks generated claims against:
	•	Approved claims
	•	Source data
	•	Product records
	•	Business configuration
Unverified claims should be removed or escalated.
 
⸻
 
8.14.4 Brand Validation
Checks:
	•	Tone
	•	Prohibited phrases
	•	Required terminology
	•	Length
	•	Formatting
	•	Industry style
	•	Client-specific restrictions
 
⸻
 
8.14.5 Duplicate Validation
Checks against:
	•	Recent GBP posts
	•	Existing review responses
	•	Existing content
	•	Repeated titles
	•	Similar metadata
	•	Previously rejected outputs
The platform should avoid producing repetitive content at scale.
 
⸻
 
8.14.6 Risk Validation
Checks for:
	•	Legal admissions
	•	Unsafe claims
	•	Discriminatory content
	•	Personal data exposure
	•	Unapproved guarantees
	•	Pricing commitments
	•	Harassment
	•	Aggressive review responses
	•	Misleading statements
 
⸻
 
8.15 Human Approval
8.15.1 Approval Triggers
Human review may be required based on:
	•	Product
	•	Action
	•	Risk
	•	Rating
	•	Client policy
	•	Model confidence
	•	Validation result
	•	Publication destination
	•	User role
	•	Cost
	•	Novelty
 
⸻
 
8.15.2 Examples
Automatic approval may be allowed for:
	•	Low-risk classification
	•	Internal summaries
	•	Draft-only SEO recommendations
	•	Four- or five-star review responses under approved policy
	•	Routine internal tagging
Human approval should normally be required for:
	•	Website publication
	•	One- or two-star review responses
	•	Legal-risk communications
	•	GBP category changes
	•	Business-hours changes
	•	Public claims
	•	Pricing statements
	•	Customer compensation
	•	External commitments
 
⸻
 
8.15.3 Approval Integrity
Approval references:
	•	Output revision
	•	Content hash
	•	Prompt version
	•	Model execution
	•	Relevant policy version
Editing the output after approval invalidates the approval when the edit is material.
 
⸻
 
8.16 AI Confidence
8.16.1 Confidence Use
A model-provided confidence score must not be treated as objective truth.
Confidence may be informed by:
	•	Model output
	•	Validator results
	•	Source completeness
	•	Retrieval quality
	•	Rule conflicts
	•	Historical task performance
	•	Agreement between classifiers
 
⸻
 
8.16.2 Confidence Categories
Recommended categories:
high
medium
low
unknown
Confidence should influence:
	•	Approval requirements
	•	Escalation
	•	Fallback behavior
	•	Whether output is shown as recommendation or action
Confidence must not override deterministic safety rules.
 
⸻
 
8.17 Fallback Strategy
8.17.1 Fallback Triggers
Fallback may occur after:
	•	Provider outage
	•	Timeout
	•	Rate limit
	•	Invalid structured output
	•	Model refusal
	•	Context-length failure
	•	Temporary capacity failure
 
⸻
 
8.17.2 Fallback Restrictions
Fallback must not:
	•	Use a provider prohibited by the organization
	•	Exceed the cost limit without authorization
	•	Use a model lacking required capabilities
	•	Reduce safety or privacy requirements
	•	change the task schema
	•	Publish an unvalidated result
 
⸻
 
8.17.3 Fallback Sequence
Example:
Primary Model
    ↓ failure
Repair Attempt
    ↓ failure
Approved Fallback Model
    ↓ failure
Manual Review
Fallback history must be recorded.
 
⸻
 
8.18 Retry Behavior
AI retries must distinguish among:
Retryable
	•	Timeout
	•	Temporary provider failure
	•	Rate limit
	•	Invalid JSON that may be repaired
	•	Temporary network error
Non-Retryable
	•	Missing required business context
	•	Prohibited request
	•	Invalid permissions
	•	Organization policy restriction
	•	Unsupported modality
	•	Input exceeding allowed policy
	•	Repeated claim validation failure
Retries must be limited.
Repeated retries should not create uncontrolled cost.
 
⸻
 
8.19 Cost Management
8.19.1 Cost Records
Every execution should record:
	•	Input tokens
	•	Output tokens
	•	Cached tokens where applicable
	•	Provider
	•	Model
	•	Estimated cost
	•	Actual cost when available
	•	Organization
	•	Product
	•	Task
	•	Workflow
	•	Date
 
⸻
 
8.19.2 Cost Controls
Controls may include:
	•	Per-execution limits
	•	Per-task limits
	•	Daily organization limits
	•	Monthly organization limits
	•	Product limits
	•	Workflow limits
	•	User limits
	•	Alert thresholds
	•	Hard stops
	•	Approval for unusually expensive tasks
 
⸻
 
8.19.3 Cost Allocation
AI usage should be attributable to:
Organization
Location
Product
Task
Workflow
User or System
This allows LILOs to evaluate:
	•	Client profitability
	•	Product margin
	•	Task efficiency
	•	Model efficiency
	•	Cost anomalies
 
⸻
 
8.19.4 Cost Optimization
Optimization methods may include:
	•	Smaller models for simple tasks
	•	Prompt reduction
	•	Context reduction
	•	Cached reusable context
	•	Batch classification
	•	Deterministic preprocessing
	•	Avoiding repeated generation
	•	Reusing approved outputs
	•	Limiting unnecessary reasoning depth
Cost optimization must not reduce required quality below the defined acceptance threshold.
 
⸻
 
8.20 Latency Management
Tasks should be classified by latency sensitivity.
Low-Latency
Examples:
	•	Lead intent classification
	•	Review risk classification
	•	User-facing draft generation
Moderate-Latency
Examples:
	•	GBP post generation
	•	Report summary
	•	Content outline
Long-Running
Examples:
	•	Full SEO analysis
	•	Long-form article generation
	•	Multi-document synthesis
	•	Large batch classification
Long-running tasks must execute asynchronously.
The interface should show workflow status rather than hold a request open.
 
⸻
 
8.21 Evaluation Framework
8.21.1 Evaluation Levels
AI quality should be evaluated at several levels:
	1.	Schema validity
	2.	Rule compliance
	3.	Human review
	4.	Comparative model testing
	5.	Workflow outcome
	6.	Business outcome
 
⸻
 
8.21.2 Automatic Evaluation
Automated checks may measure:
	•	Required field presence
	•	Length
	•	Prohibited phrases
	•	Duplicate similarity
	•	Claim support
	•	Style compliance
	•	Sentiment consistency
	•	Classification agreement
	•	Link validity
	•	Formatting
Automated evaluation should not claim to measure subjective quality completely.
 
⸻
 
8.21.3 Human Evaluation
Human reviewers may rate:
	•	Accuracy
	•	Relevance
	•	Usefulness
	•	Tone
	•	Brand fit
	•	Local relevance
	•	Completeness
	•	Required editing
	•	Approval decision
A consistent review rubric should be used by task type.
 
⸻
 
8.21.4 Outcome Evaluation
Where possible, outputs should be connected to business results.
Examples:
	•	SEO recommendation accepted and implemented
	•	Content performance after publication
	•	GBP post engagement
	•	Review response time
	•	Lead contact rate
	•	Lead conversion
	•	Approval turnaround time
Correlation must not be presented as causation without evidence.
 
⸻
 
8.22 Evaluation Datasets
8.22.1 Test Sets
The platform should maintain approved evaluation datasets for important tasks.
Examples:
	•	Restaurant review responses
	•	Home-service review responses
	•	GBP posts
	•	SEO opportunity summaries
	•	Content briefs
	•	Lead classifications
 
⸻
 
8.22.2 Dataset Requirements
Evaluation data should be:
	•	Representative
	•	De-identified where appropriate
	•	Versioned
	•	Balanced across risk levels
	•	Approved for use
	•	Separated from production credentials
	•	Protected from unauthorized access
 
⸻
 
8.22.3 Golden Examples
Golden examples are approved reference outputs.
They should be used to evaluate:
	•	Regression
	•	Prompt changes
	•	Model changes
	•	Provider changes
	•	Schema changes
Golden examples are standards, not text to be copied repeatedly.
 
⸻
 
8.23 Model and Prompt Experiments
8.23.1 Experiment Purpose
Experiments may compare:
	•	Models
	•	Prompts
	•	Context structures
	•	Validators
	•	Routing policies
	•	Temperature or reasoning settings
	•	Retrieval strategies
 
⸻
 
8.23.2 Experiment Requirements
Every experiment should define:
	•	Hypothesis
	•	Task
	•	Population
	•	Variants
	•	Success metrics
	•	Cost limits
	•	Duration or sample size
	•	Stopping rules
	•	Approval status
	•	Owner
 
⸻
 
8.23.3 Production Experiments
Production experiments must not weaken:
	•	Security
	•	Client policy
	•	Approval requirements
	•	Data privacy
	•	Consent
	•	Publication safeguards
High-risk tasks should not be experimented on without explicit controls.
 
⸻
 
8.23.4 Experiment Assignment
An execution should record:
	•	Experiment ID
	•	Variant
	•	Routing decision
	•	Prompt version
	•	Model
	•	Outcome
This allows results to be compared accurately.
 
⸻
 
8.24 Prompt and Model Promotion
Changes should progress through:
Draft
    ↓
Internal Testing
    ↓
Evaluation Dataset
    ↓
Limited Production
    ↓
Approved
    ↓
Preferred
Promotion criteria may include:
	•	Minimum schema-valid rate
	•	Minimum approval rate
	•	Maximum edit rate
	•	Maximum policy violation rate
	•	Maximum cost
	•	Maximum latency
	•	Minimum sample size
A model should not become preferred based on a small number of favorable examples.
 
⸻
 
8.25 Regression Testing
Prompt, model, schema, and context changes must be tested against prior accepted cases.
Regression tests should identify:
	•	Reduced approval rate
	•	Increased hallucinations
	•	Increased prohibited language
	•	Lost local relevance
	•	Increased cost
	•	Increased latency
	•	New formatting failures
	•	More repetitive output
A provider model update should be treated as a potential behavioral change even when the model identifier remains stable.
 
⸻
 
8.26 AI Security and Privacy
8.26.1 Data Classification
Inputs should be classified before model execution.
Suggested classes:
public
business_internal
client_confidential
personal_data
restricted
Routing policies may limit which providers can receive each class.
 
⸻
 
8.26.2 Sensitive Data
AI requests should minimize:
	•	Personal lead information
	•	Customer contact information
	•	Private review metadata
	•	Internal financial data
	•	Credentials
	•	Authentication tokens
	•	Legal records
	•	Private employee information
Where possible, use references, redaction, or pseudonymization.
 
⸻
 
8.26.3 Secret Exclusion
The following must never be placed into model context:
	•	API keys
	•	OAuth refresh tokens
	•	Database passwords
	•	Stripe secret keys
	•	Supabase service keys
	•	Private signing keys
	•	Server credentials
 
⸻
 
8.26.4 Provider Retention Policy
The platform should record provider settings related to:
	•	Data retention
	•	Model training usage
	•	Regional processing
	•	Enterprise privacy controls
	•	Logging
Organization restrictions must be enforced through routing.
 
⸻
 
8.26.5 Cross-Tenant Isolation
Context assembly must explicitly scope all data by organization.
The model must never receive mixed-client context unless an authorized internal aggregate workflow uses properly anonymized data.
 
⸻
 
8.27 AI Safety Policies
The platform must define product-specific safety policies.
Reviews
AI must not:
	•	Admit liability
	•	Threaten reviewers
	•	Reveal personal information
	•	Invent remediation
	•	Promise compensation without authority
	•	Accuse the reviewer of dishonesty without approved evidence
Leads
AI must not:
	•	Ignore opt-outs
	•	Misstate service availability
	•	Guarantee arrival times
	•	Invent pricing
	•	Claim a person has reviewed the lead when they have not
	•	Continue messaging after consent is withdrawn
Content
AI must not:
	•	Invent licenses
	•	Invent awards
	•	Invent business history
	•	Invent staff credentials
	•	Create unsupported health, legal, or financial claims
	•	Fabricate local references
GBP
AI must not:
	•	Publish unsupported offers
	•	Invent events
	•	Misstate business hours
	•	Create misleading urgency
	•	Use prohibited or repetitive language
	•	Change profile facts without authorization
 
⸻
 
8.28 AI-Generated Claims
Claims should be classified as:
source_verified
client_approved
derived
general
unverified
prohibited
Public-facing output should normally use only:
	•	Source-verified claims
	•	Client-approved claims
	•	Clearly safe general statements
Derived claims require supporting logic and may require review.
Unverified or prohibited claims must not publish.
 
⸻
 
8.29 Hallucination Controls
Controls should include:
	•	Structured source context
	•	Claim allowlists
	•	Prohibited-claim lists
	•	Retrieval grounding
	•	Required citations for internal analytical tasks
	•	Validation against platform records
	•	Human approval
	•	Conservative fallback language
	•	Refusal to fill missing facts
The system should prefer:
Information unavailable
over inventing a business fact.
 
⸻
 
8.30 AI Memory
8.30.1 Platform Memory
Persistent business memory belongs in structured platform records.
Examples:
	•	Brand guidance
	•	Approved claims
	•	Services
	•	Location facts
	•	Workflow history
	•	User preferences
It should not exist only in a model conversation history.
 
⸻
 
8.30.2 Operator Memory
A future AI operator may maintain limited memory for:
	•	User preferences
	•	Common operating patterns
	•	Ongoing tasks
	•	Recent platform context
Operator memory must:
	•	Be scoped by user and organization
	•	Be reviewable
	•	Be editable
	•	Be deletable
	•	Not replace platform records
	•	Not contain unrestricted secrets
	•	Not create cross-client leakage
 
⸻
 
8.30.3 Conversation History
Conversation history should not automatically become trusted business configuration.
A user statement may be used for the current task.
Persistent platform changes require an explicit action and validation.
 
⸻
 
8.31 Tool-Using Models
8.31.1 Tool Access
Models may use approved platform tools.
Examples:
	•	Retrieve organization profile
	•	Read product status
	•	List pending approvals
	•	Create a draft
	•	Run analysis
	•	Submit for approval
Tools must be defined through structured contracts.
 
⸻
 
8.31.2 Tool Permission
Every tool call must enforce:
	•	User or service identity
	•	Organization
	•	Location
	•	Permission
	•	Entitlement
	•	Risk policy
	•	Approval policy
	•	Audit logging
The model cannot grant itself access.
 
⸻
 
8.31.3 Tool Result Validation
Tool outputs should be structured.
The model should not parse unrestricted server logs or raw database output when a narrower result can be provided.
 
⸻
 
8.31.4 Write Tool Restrictions
High-impact tools should require:
	•	Explicit confirmation
	•	Approval
	•	Idempotency key
	•	Current resource version
	•	Clear action summary
Examples:
	•	Publish content
	•	Send customer communication
	•	Change business hours
	•	Modify billing
	•	Disable products
	•	Archive client data
 
⸻
 
8.32 AI Operator Architecture
8.32.1 Purpose
An AI operator may provide a conversational interface for authorized platform work.
Potential capabilities:
	•	Summarize account status
	•	Identify failed workflows
	•	Explain recent performance
	•	Create drafts
	•	Run approved analyses
	•	Prepare reports
	•	Submit work for approval
	•	Recommend next actions
 
⸻
 
8.32.2 Operator Boundaries
The operator must use approved platform tools.
It must not receive:
	•	Unrestricted SQL
	•	Root server access
	•	Unrestricted shell access
	•	Raw provider credentials
	•	Universal cross-client access
	•	Unlogged publication access
	•	Permission to change its own controls
 
⸻
 
8.32.3 Operator Modes
Recommended modes:
Read Mode
May retrieve and summarize authorized data.
Draft Mode
May create drafts and recommendations.
Action Mode
May initiate approved workflows.
Restricted Action Mode
Requires confirmation or approval before external effect.
The current mode should be explicit.
 
⸻
 
8.32.4 Operator Action Plan
Before a multi-step action, the operator should produce a structured internal plan containing:
	•	Objective
	•	Organization
	•	Location
	•	Tools required
	•	Expected side effects
	•	Approval requirements
	•	Stop conditions
The plan should be recorded when the action materially affects external systems.
 
⸻
 
8.32.5 Operator Audit
Every operator action should record:
	•	Human initiator
	•	Operator identity
	•	Model
	•	Prompt or policy version
	•	Tools called
	•	Inputs
	•	Outputs
	•	Permissions evaluated
	•	Result
	•	External side effects
	•	Approval references
 
⸻
 
8.33 AI Development Assistant
AI may also support platform engineering.
Potential uses:
	•	Code generation
	•	Test generation
	•	Migration drafting
	•	Documentation
	•	Debugging
	•	Repository analysis
	•	Pull-request review
	•	Incident summarization
Engineering AI must follow the same principles:
	•	Repository context is scoped.
	•	Secrets are excluded.
	•	Changes are reviewed.
	•	Tests are required.
	•	Generated code is not automatically trusted.
	•	Production deployment requires existing controls.
The development assistant is not part of the customer product unless explicitly productized later.
 
⸻
 
8.34 AI Failure Modes
The platform should explicitly handle:
	•	Invalid structured output
	•	Hallucinated fact
	•	Provider outage
	•	Rate limit
	•	Timeout
	•	Context overflow
	•	Refusal
	•	Unsafe output
	•	Repetitive output
	•	Wrong language
	•	Wrong client context
	•	Tool failure
	•	Partial tool completion
	•	Excessive cost
	•	Unexpected latency
	•	Prompt injection
	•	Model behavioral drift
Each task definition should specify relevant failure handling.
 
⸻
 
8.35 Manual Completion
Every important AI-assisted workflow should have a manual path.
Examples:
	•	Human writes review response
	•	Human drafts GBP post
	•	Human creates content brief
	•	Human classifies lead
	•	Human completes SEO recommendation
	•	Human produces report summary
AI failure must not make the product unusable.
 
⸻
 
8.36 AI Observability
The agency console should expose:
	•	Executions by task
	•	Success rate
	•	Validation failure rate
	•	Fallback rate
	•	Approval rate
	•	Edit rate
	•	Cost
	•	Latency
	•	Provider health
	•	Model health
	•	Prompt-version performance
	•	Organization usage
	•	Product usage
Operators should be able to answer:
	•	Which model generated this?
	•	Which prompt version was used?
	•	Why was fallback used?
	•	Why was the output blocked?
	•	How much did it cost?
	•	Was it edited?
	•	Did it produce the intended business result?
 
⸻
 
8.37 AI Alerts
Alerts may be created for:
	•	Sudden cost increase
	•	High failure rate
	•	Provider outage
	•	High schema-invalid rate
	•	Increased rejection rate
	•	Increased fallback use
	•	Model deprecation
	•	Prompt regression
	•	Cross-client context anomaly
	•	Unexpected restricted-data use
	•	Task latency degradation
Alerts should use measured baselines where possible.
 
⸻
 
8.38 Initial AI Task Priorities
The initial implementation should prioritize tasks closest to current LILOs operations.
Priority 1 — Classification and Summarization
	•	SEO opportunity summaries
	•	Review risk classification
	•	Review sentiment and topics
	•	Lead intent classification
	•	Report summaries
These tasks are easier to validate and lower risk.
Priority 2 — Controlled Draft Generation
	•	GBP post drafts
	•	Review response drafts
	•	Content briefs
	•	Content outlines
	•	Metadata
These should use approval workflows.
Priority 3 — Long-Form Generation
	•	Blog articles
	•	Service pages
	•	Location pages
	•	Major page revisions
These require stronger source controls, duplication checks, and human review.
Priority 4 — Operator Tools
	•	Read status
	•	List failures
	•	Run approved analysis
	•	Create drafts
	•	Submit for approval
Write-heavy autonomous operation should come later.
 
⸻
 
8.39 Initial AI Implementation Order
Stage 1 — Shared Gateway
Implement:
	•	Task registry
	•	Provider interface
	•	Model registry
	•	Routing policy
	•	Normalized execution records
	•	Structured-output validation
	•	Basic cost tracking
	•	Basic retry and fallback
Stage 2 — Prompt System
Implement:
	•	Prompt definitions
	•	Prompt versions
	•	Approval states
	•	Context assembly
	•	Organization and location context
	•	Output schemas
Stage 3 — First Production Task
Implement one low-risk end-to-end task.
Recommended:
SEO opportunity summary
This task should prove:
	•	Routing
	•	Prompt versioning
	•	Structured output
	•	Validation
	•	Cost recording
	•	Workflow integration
	•	Human review
Stage 4 — GBP and Reviews
Implement:
	•	GBP post generation
	•	Review risk classification
	•	Review response generation
Stage 5 — Content
Implement:
	•	Brief generation
	•	Outline generation
	•	Draft generation
	•	Revision
	•	Metadata
Stage 6 — Evaluation
Implement:
	•	Human ratings
	•	Approval rate
	•	Edit tracking
	•	Model comparison
	•	Prompt comparison
	•	Cost and latency dashboards
Stage 7 — Operator
Implement read-only tools first.
Add draft and action tools only after permission and audit controls are proven.
 
⸻
 
8.40 AI Acceptance Requirements
An AI task is not production-ready until it has:
	•	Defined business purpose
	•	Defined owner
	•	Input schema
	•	Output schema
	•	Approved prompt version
	•	Approved routing policy
	•	Cost limit
	•	Latency limit
	•	Validation rules
	•	Failure behavior
	•	Fallback behavior
	•	Approval policy
	•	Data-retention policy
	•	Security classification
	•	Evaluation dataset
	•	Minimum quality criteria
	•	Audit records
	•	Manual alternative
	•	Monitoring
	•	Documentation
 
⸻
 
8.41 AI Guardrails
The following are prohibited unless the architecture is formally revised:
	1.	Product code calling AI providers directly
	2.	Hardcoded model names in product workflows
	3.	Unversioned production prompts
	4.	AI output directly changing permissions or entitlements
	5.	AI output directly authorizing billing actions
	6.	AI output bypassing approval
	7.	Secrets included in model context
	8.	Mixed-client context
	9.	Raw unvalidated output controlling software actions
	10.	Unlimited retries
	11.	Unlimited AI spending
	12.	Silent fallback to an unapproved provider
	13.	Unlogged AI execution
	14.	Approved prompts modified in place
	15.	Model confidence treated as definitive evidence
	16.	Public claims generated without source or approved basis
	17.	Operator access to unrestricted SQL or production shell
	18.	Conversation memory treated as authoritative configuration
	19.	Production experiments without evaluation and stopping criteria
	20.	AI dependence without a manual completion path
	21.	Automated customer communication after opt-out
	22.	Autonomous publication of high-risk content
	23.	Provider selection that violates organization privacy restrictions
	24.	AI-generated code deployed without normal review and testing
	25.	AI explanations presented as measured facts without evidence
 
⸻
 
8.42 Section Decisions
This section establishes the following decisions:
	1.	AI is a shared platform service, not the platform foundation.
	2.	Products request task types rather than specific models.
	3.	All providers are accessed through normalized adapters.
	4.	Models are selected through versioned routing policies.
	5.	Prompts are versioned, approved, auditable assets.
	6.	Business context is assembled dynamically from structured platform records.
	7.	AI outputs consumed by software must use validated schemas.
	8.	Deterministic business rules override model output.
	9.	Every execution records provider, model, prompt, usage, cost, latency, validation, and result.
	10.	AI quality is measured through automatic checks, human review, workflow outcomes, and business outcomes.
	11.	Model and prompt changes require controlled evaluation and regression testing.
	12.	Fallbacks must remain within approved provider, cost, security, and capability constraints.
	13.	AI context must be minimized and tenant-isolated.
	14.	Sensitive credentials must never enter model context.
	15.	Public-facing claims must be source-verified or client-approved.
	16.	High-risk actions require human approval.
	17.	Every major AI workflow requires a manual alternative.
	18.	A future AI operator uses narrow permissioned tools and cannot bypass platform services.
	19.	Operator actions are authenticated, authorized, auditable, and subject to confirmation rules.
	20.	The initial AI rollout should begin with low-risk structured tasks before long-form generation or autonomous actions.


---

Section 9 — Security, Privacy, and Risk Management
9.1 Purpose of This Section
This section defines the security and privacy requirements for the LILOs platform.
It establishes:
	•	Security ownership
	•	Tenant isolation
	•	Identity and access control
	•	Authentication requirements
	•	Authorization enforcement
	•	Secret management
	•	Data classification
	•	Encryption
	•	Infrastructure security
	•	Application security
	•	API and webhook protection
	•	Integration security
	•	AI-specific security
	•	Logging and monitoring
	•	Vulnerability management
	•	Backup and recovery
	•	Incident response
	•	Privacy requirements
	•	Data retention and deletion
	•	Vendor risk management
	•	Security testing
	•	Operational guardrails
The goal is to protect client data, platform integrity, connected accounts, external communication channels, and LILOs operations without introducing security processes that are disconnected from the actual risk of the platform.
Security must be designed into the platform architecture.
It must not be treated as a final checklist added after product development.
 
⸻
 
9.2 Security Objectives
The platform must protect five primary areas.
Confidentiality
Only authorized users and services may access client or platform data.
Integrity
Data, configuration, approvals, publications, and workflow state must not be altered without authorization.
Availability
The platform must remain usable and recoverable during failures, outages, attacks, or operator mistakes.
Accountability
Important actions must be attributable to a user, service, integration, workflow, or operator.
Tenant Isolation
One organization must not access or influence another organization’s data or operations.
 
⸻
 
9.3 Security Principles
Principle 1 — Deny by Default
Access is denied unless explicitly granted.
This applies to:
	•	Database records
	•	API routes
	•	Product features
	•	Files
	•	Integrations
	•	Workflows
	•	AI tools
	•	Internal operations
 
⸻
 
Principle 2 — Least Privilege
Users, services, integrations, and workers receive only the permissions required for their function.
A service that sends notifications should not receive unrestricted access to billing, user administration, or unrelated client data.
 
⸻
 
Principle 3 — Multiple Enforcement Layers
Security must be enforced through several layers:
Authentication
    ↓
Authorization
    ↓
Product Entitlement
    ↓
Organization Scope
    ↓
Location Scope
    ↓
Resource Ownership
    ↓
Action Policy
    ↓
Audit Logging
No single frontend check, database policy, or API middleware is sufficient by itself.
 
⸻
 
Principle 4 — Explicit Trust Boundaries
The platform must treat the following as separate trust zones:
	•	Public internet
	•	Client browser
	•	Agency browser
	•	Application backend
	•	Background workers
	•	Database
	•	Object storage
	•	External providers
	•	AI providers
	•	Administrative infrastructure
Data crossing a boundary must be authenticated, validated, and minimized.
 
⸻
 
Principle 5 — Security Events Must Be Visible
Security-relevant failures must not remain only in raw logs.
Examples:
	•	Repeated failed login
	•	Cross-tenant access attempt
	•	Expired integration credentials
	•	Invalid webhook signature
	•	Unusual bulk export
	•	Permission escalation
	•	Disabled security control
	•	Secret exposure
	•	Unexpected AI data access
 
⸻
 
Principle 6 — Human Error Is Expected
The architecture must assume:
	•	Users click the wrong action.
	•	Operators choose the wrong client.
	•	Credentials expire.
	•	Configuration is entered incorrectly.
	•	Deployments introduce regressions.
	•	External providers behave unexpectedly.
Controls should reduce the impact of mistakes.
 
⸻
 
Principle 7 — Security Must Remain Operable
Controls must be understandable and maintainable by the actual LILOs operating team.
Security architecture that cannot be monitored, tested, or consistently followed creates false confidence.
 
⸻
 
9.4 Security Ownership
Security responsibilities must be explicit.
Recommended ownership categories:
Platform Owner
Responsible for:
	•	Security policy
	•	Administrative access
	•	Incident authority
	•	Vendor approval
	•	Risk acceptance
	•	Production access decisions
Engineering Owner
Responsible for:
	•	Secure implementation
	•	Dependency management
	•	Access controls
	•	Secrets
	•	Infrastructure
	•	Vulnerability remediation
	•	Backup testing
Product Owner
Responsible for:
	•	Product-specific risks
	•	Approval policies
	•	Data minimization
	•	External action safeguards
	•	User-visible security behavior
Account Manager or Operator
Responsible for:
	•	Correct organization selection
	•	Client access management
	•	Escalating suspicious activity
	•	Following approval procedures
	•	Avoiding unauthorized data exports
Client Administrator
Responsible for:
	•	Managing client users
	•	Reviewing permissions
	•	Protecting login credentials
	•	Reporting unauthorized activity
	•	Maintaining connected-provider access
Security ownership does not remove the need for technical enforcement.
 
⸻
 
9.5 Data Classification
All platform data should be assigned a security classification.
Recommended classes:
public
internal
client_confidential
personal_data
restricted
secret
 
⸻
 
9.5.1 Public
Information intentionally available publicly.
Examples:
	•	Published website content
	•	Public GBP data
	•	Public business hours
	•	Public review text
	•	Published business contact information
Public information still requires integrity protection.
 
⸻
 
9.5.2 Internal
LILOs operational information not intended for clients or the public.
Examples:
	•	Internal documentation
	•	Workflow diagnostics
	•	Product roadmaps
	•	Internal annotations
	•	Non-sensitive cost summaries
 
⸻
 
9.5.3 Client Confidential
Private business information belonging to an organization.
Examples:
	•	Unpublished content
	•	Performance reports
	•	Product configuration
	•	Lead-routing rules
	•	Account notes
	•	Internal review escalations
	•	Connected resource metadata
 
⸻
 
9.5.4 Personal Data
Information relating to an identifiable individual.
Examples:
	•	Lead name
	•	Email address
	•	Phone number
	•	User account information
	•	Reviewer identity supplied by a provider
	•	Communication history
 
⸻
 
9.5.5 Restricted
High-risk data that requires additional controls.
Examples:
	•	Legal complaints
	•	Employee allegations
	•	Payment dispute details
	•	Sensitive customer communications
	•	Internal security investigations
	•	Highly privileged audit information
 
⸻
 
9.5.6 Secret
Credentials or values that grant access.
Examples:
	•	API keys
	•	OAuth refresh tokens
	•	Database service credentials
	•	Signing secrets
	•	Private keys
	•	Session-signing material
	•	Encryption keys
Secret data must not appear in ordinary platform records, logs, prompts, or client responses.
 
⸻
 
9.6 Data Handling Requirements
Data handling should depend on classification.
Classification
Browser Access
Logging
AI Processing
Export
Encryption
Public
Allowed
Limited
Allowed
Allowed
In transit
Internal
Authorized users
Redacted
Approved tasks
Restricted
In transit and at rest
Client confidential
Tenant-scoped
Redacted
Policy-controlled
Permission required
In transit and at rest
Personal data
Need-based
Minimized
Minimized and approved
Permission and purpose required
In transit and at rest
Restricted
Highly restricted
Metadata only
Normally prohibited or specifically approved
Exceptional
Enhanced controls
Secret
Never exposed
Never logged
Prohibited
Prohibited
Secure secret storage
This table defines minimum expectations.
Product-specific policy may be stricter.
 
⸻
 
9.7 Identity Security
9.7.1 User Identity
Each human user must have an individual account.
Shared user accounts are prohibited for routine platform access.
Actions must be attributable to a specific user.
 
⸻
 
9.7.2 Service Identity
Every trusted backend service should have a distinct identity where practical.
Examples:
	•	API service
	•	Scheduler
	•	SEO worker
	•	GBP worker
	•	Review worker
	•	Content worker
	•	Notification worker
	•	Deployment service
A service identity should not be reused across unrelated environments.
 
⸻
 
9.7.3 Operator Identity
An AI operator must have its own service identity.
Operator actions must also retain the human initiator where applicable.
The audit record should distinguish:
Human requester
AI operator
Underlying model
Executed platform tool
 
⸻
 
9.7.4 Identity Lifecycle
Identity management must support:
	•	Invitation
	•	Activation
	•	Suspension
	•	Password reset
	•	Session revocation
	•	Role change
	•	Organization removal
	•	Offboarding
	•	Account deletion
	•	Service credential rotation
Revoked identities must lose access promptly.
 
⸻
 
9.8 Authentication Requirements
9.8.1 User Authentication
Supabase Authentication should provide user authentication.
Requirements include:
	•	Secure session tokens
	•	Token expiration
	•	Email verification where appropriate
	•	Password-reset controls
	•	Session revocation
	•	Protection against brute-force login attempts
	•	Multi-factor authentication for privileged accounts when supported
 
⸻
 
9.8.2 Multi-Factor Authentication
Multi-factor authentication should be required for:
	•	Platform owners
	•	Production administrators
	•	Users with billing authority
	•	Users with broad cross-client access
	•	Users with secret-management access
	•	Users with deployment authority
Client administrators should be encouraged or required to use MFA based on plan and risk.
 
⸻
 
9.8.3 Session Security
Sessions should support:
	•	Secure cookies where browser sessions are used
	•	HTTP-only cookies
	•	SameSite protection
	•	TLS-only transmission
	•	Reasonable expiration
	•	Refresh-token protection
	•	Revocation
	•	Detection of disabled users
Highly privileged actions may require recent authentication.
 
⸻
 
9.8.4 Login Protection
Login endpoints should use:
	•	Rate limiting
	•	Generic failure messages
	•	Suspicious-attempt monitoring
	•	Temporary lock or escalating delay
	•	Bot protection where justified
The platform must not reveal whether a specific email address exists through ordinary login errors.
 
⸻
 
9.9 Authorization Requirements
9.9.1 Authorization Inputs
Every sensitive action must evaluate:
	•	User or service identity
	•	Organization membership
	•	Membership status
	•	Location access
	•	Role assignments
	•	Required permissions
	•	Product entitlement
	•	Feature entitlement
	•	Resource ownership
	•	Workflow state
	•	Approval requirements
 
⸻
 
9.9.2 Server-Side Enforcement
Authorization must be enforced in:
	•	Application services
	•	Database Row Level Security
	•	Worker execution
	•	Operator tools
	•	File access
	•	Export generation
Frontend access controls improve usability but do not provide security.
 
⸻
 
9.9.3 Privilege Escalation Protection
A user must not be able to:
	•	Assign themselves a higher role
	•	Enable their own product entitlement
	•	Add themselves to another organization
	•	Approve an action without the required permission
	•	Change internal user status
	•	Modify protected system roles
	•	Alter billing access through a general profile update
Privilege-changing operations require dedicated services and audit events.
 
⸻
 
9.9.4 Separation of Duties
The platform should support policies where:
	•	The creator cannot approve the same item.
	•	The approver cannot alter the content after approval.
	•	Billing administration is separate from product operation.
	•	Support access is separate from platform administration.
	•	Production deployment authority is separate from ordinary development access.
This may be applied based on organization size and risk.
 
⸻
 
9.10 Tenant Isolation
9.10.1 Organization Boundary
Every client-owned record must include an organization reference.
Every query must explicitly enforce organization scope.
Location scope supplements but does not replace organization scope.
 
⸻
 
9.10.2 Database Isolation
Supabase Row Level Security policies should validate:
	•	Active user identity
	•	Active organization membership
	•	Location access
	•	Resource ownership
	•	Client visibility
	•	Required operation
Backend service-role access must not bypass application-level scope checks merely because it can bypass RLS.
 
⸻
 
9.10.3 Object Storage Isolation
Storage paths should include non-guessable tenant scope.
Example:
organizations/{organization_uuid}/locations/{location_uuid}/content/{file_uuid}
Access must still be enforced through policy or signed URLs.
Path naming alone is not authorization.
 
⸻
 
9.10.4 Cache Isolation
Cache keys must include:
	•	Environment
	•	Organization
	•	Location where applicable
	•	Resource
	•	Version or permission context where needed
Cross-tenant cached responses are a critical failure.
 
⸻
 
9.10.5 Search and Retrieval Isolation
Search, reporting, semantic retrieval, and AI context assembly must preserve tenant boundaries.
A query for one organization must not return:
	•	Another organization’s content
	•	Another organization’s prompts
	•	Another organization’s leads
	•	Another organization’s reports
	•	Another organization’s model context
 
⸻
 
9.10.6 Testing Tenant Isolation
Automated tests must attempt:
	•	Direct record-ID access across organizations
	•	Location-ID substitution
	•	Pagination across tenant boundaries
	•	Export of unauthorized records
	•	File URL reuse
	•	Search leakage
	•	Worker payload manipulation
	•	Operator tool misuse
Tenant isolation tests are mandatory for every tenant-owned resource.
 
⸻
 
9.11 Administrative and Internal Access
9.11.1 Cross-Client Access
Internal users may receive cross-client access only where required.
Access should be:
	•	Role-based
	•	Time-limited where practical
	•	Logged
	•	Reviewable
	•	Revocable
 
⸻
 
9.11.2 Support Access
Support access should distinguish between:
	•	Reading account status
	•	Reading client data
	•	Modifying configuration
	•	Acting as the client
	•	Exporting data
	•	Accessing restricted records
Support users should not receive platform-owner permissions by default.
 
⸻
 
9.11.3 Impersonation
If impersonation is introduced, it must:
	•	Require explicit permission
	•	Display a visible impersonation state
	•	Record the internal user
	•	Record the impersonated user or organization
	•	Prevent hidden identity substitution
	•	Restrict high-risk actions
	•	Support immediate termination
 
⸻
 
9.11.4 Production Infrastructure Access
Production shell, database, and deployment access should be limited.
Requirements include:
	•	Named individual accounts
	•	SSH keys rather than passwords
	•	Key rotation
	•	Minimal sudo access
	•	Removal during offboarding
	•	Auditability
	•	Separate production and development credentials
 
⸻
 
9.12 Secret Management
9.12.1 Approved Secret Locations
Secrets may be stored in:
	•	Vercel environment variables
	•	Supabase-managed secrets
	•	GitHub Actions secrets
	•	Secured Hetzner environment configuration
	•	An approved secrets manager when introduced
	•	Encrypted provider-credential storage
 
⸻
 
9.12.2 Prohibited Secret Locations
Secrets must not be stored in:
	•	Git repositories
	•	Prompt files
	•	Public environment variables
	•	Client-side bundles
	•	Documentation examples
	•	General database JSON fields
	•	Logs
	•	Issue descriptions
	•	Chat transcripts used as permanent documentation
	•	Screenshots
	•	Test fixtures
 
⸻
 
9.12.3 Secret Scope
Secrets should be scoped by:
	•	Environment
	•	Service
	•	Provider
	•	Organization where applicable
	•	Permission
A production service key should not be used in development.
 
⸻
 
9.12.4 Rotation
Rotation procedures must exist for:
	•	Database credentials
	•	API keys
	•	OAuth client secrets
	•	Signing secrets
	•	Deployment tokens
	•	Service credentials
	•	Encryption keys
Rotation must include validation that old credentials no longer work.
 
⸻
 
9.12.5 Exposure Response
If a secret may have been exposed:
	1.	Revoke or rotate it immediately.
	2.	Identify affected systems.
	3.	Review logs.
	4.	Determine the exposure window.
	5.	Check for unauthorized use.
	6.	Replace dependent credentials where necessary.
	7.	Document the incident.
	8.	Prevent recurrence.
A secret must not remain active merely because confirmed misuse has not yet been observed.
 
⸻
 
9.13 Encryption
9.13.1 Data in Transit
All platform traffic must use TLS.
This includes:
	•	Browser to application
	•	Application to API
	•	API to database
	•	Worker to provider
	•	Webhook delivery
	•	Internal service communication
Unencrypted production HTTP must redirect or be blocked.
 
⸻
 
9.13.2 Data at Rest
Data should be encrypted at rest through the hosting and database platforms.
Additional application-layer encryption should be considered for:
	•	OAuth refresh tokens
	•	Sensitive integration credentials
	•	Restricted personal data
	•	Private signing material
 
⸻
 
9.13.3 Encryption Keys
Encryption keys must:
	•	Be stored separately from encrypted values
	•	Be environment-specific
	•	Be access-controlled
	•	Support rotation
	•	Never be logged
	•	Never enter AI context
 
⸻
 
9.14 Application Security
9.14.1 Input Validation
All external input must be validated.
Sources include:
	•	Forms
	•	API requests
	•	Webhooks
	•	File uploads
	•	Provider data
	•	AI output
	•	Query parameters
	•	User-generated content
Validation should enforce:
	•	Type
	•	Format
	•	Length
	•	Allowed values
	•	Organization scope
	•	Business rules
	•	File limits
	•	Encoding
 
⸻
 
9.14.2 Output Encoding
User-controlled content must be safely encoded before display.
The platform must protect against:
	•	Cross-site scripting
	•	HTML injection
	•	Script URLs
	•	Unsafe markdown rendering
	•	Embedded malicious content
 
⸻
 
9.14.3 Mass Assignment
Public request schemas must explicitly define writable fields.
The platform must not bind request bodies directly to database models.
Users must not be able to set protected fields such as:
organization_id
is_internal
role_id
entitlement_status
approved_at
published_at
billing_status
through ordinary update requests.
 
⸻
 
9.14.4 Injection Prevention
The platform must use:
	•	Parameterized queries
	•	ORM or query-builder safety
	•	Allowlisted sorting
	•	Validated filters
	•	Safe command invocation
	•	No direct shell interpolation
	•	No dynamic SQL from AI output
 
⸻
 
9.14.5 Cross-Site Request Forgery
Cookie-authenticated state-changing requests should use appropriate CSRF protections.
SameSite cookies alone should not be assumed sufficient for every flow.
 
⸻
 
9.14.6 Redirect Safety
User-controlled redirect destinations must be validated.
The platform must prevent open redirects after:
	•	Login
	•	OAuth
	•	Invitation acceptance
	•	Password reset
	•	Billing return
	•	Integration connection
 
⸻
 
9.15 API Security
API security requirements include:
	•	Authentication
	•	Authorization
	•	Rate limiting
	•	Request-size limits
	•	Input validation
	•	Idempotency
	•	Replay protection
	•	Safe error messages
	•	Correlation IDs
	•	Audit events
	•	Sensitive-field filtering
High-risk endpoints require stricter controls.
Examples:
	•	Billing changes
	•	User administration
	•	Bulk export
	•	External publication
	•	Lead messaging
	•	Integration reconnection
	•	Product suspension
	•	Data deletion
 
⸻
 
9.16 Webhook Security
Every webhook must:
	1.	Validate the provider signature.
	2.	Validate any timestamp or replay window.
	3.	Deduplicate provider event IDs.
	4.	Apply request-size limits.
	5.	Store processing status.
	6.	Process asynchronously where possible.
	7.	Avoid trusting payload organization IDs without mapping them to a known connection.
	8.	Record signature failure.
	9.	Return an appropriate response without leaking internal information.
Invalid webhook payloads must not create platform events.
 
⸻
 
9.17 Integration Security
9.17.1 OAuth Scope
The platform should request the minimum provider scopes required.
A product must not request write permission when read-only access is sufficient.
 
⸻
 
9.17.2 Credential Access
Provider credentials should be accessible only to:
	•	Approved backend services
	•	Approved integration adapters
	•	Limited administrative recovery operations
Product frontend code must never receive provider tokens.
 
⸻
 
9.17.3 Connection Ownership
Every integration connection must map to:
	•	An organization
	•	A location where applicable
	•	A provider
	•	The external account
	•	Authorized resources
	•	Granted scopes
The platform must verify that a selected provider resource belongs to the connected account.
 
⸻
 
9.17.4 Reauthorization
When credentials expire or scopes change:
	•	Mark the connection degraded or authorization required.
	•	Stop dependent external actions.
	•	Notify an authorized user.
	•	Preserve historical data.
	•	Resume only after verified reconnection.
 
⸻
 
9.17.5 Provider Revocation
Disconnecting an integration should:
	•	Revoke the token where supported.
	•	Disable dependent workflows.
	•	Remove scheduled external actions.
	•	Retain audit and historical records.
	•	Remove stored credentials according to policy.
 
⸻
 
9.18 External Action Security
External actions include:
	•	Publishing a GBP post
	•	Responding to a review
	•	Sending email
	•	Sending SMS
	•	Publishing website content
	•	Updating business information
	•	Creating billing changes
Every external action must verify:
	•	Organization scope
	•	Permission
	•	Entitlement
	•	Integration status
	•	Approved content or configuration
	•	Current revision
	•	Idempotency
	•	Action-specific policy
	•	Audit creation
The platform must not infer approval from the existence of a draft.
 
⸻
 
9.19 File Security
9.19.1 Upload Validation
File uploads must validate:
	•	File size
	•	Allowed extension
	•	MIME type
	•	File signature
	•	Organization ownership
	•	Intended product use
	•	Image dimensions where relevant
	•	Malware risk where justified
 
⸻
 
9.19.2 Storage
Uploaded files should use generated storage names.
Original filenames may be stored as metadata but should not define storage paths.
 
⸻
 
9.19.3 File Access
Private files should use:
	•	Authorization checks
	•	Short-lived signed URLs
	•	Tenant-scoped paths
	•	Expiration
	•	Download logging where appropriate
 
⸻
 
9.19.4 Dangerous Files
Executable files and unsupported archives should be rejected unless a defined product use case requires them.
User-supplied HTML, SVG, scripts, or office macros require additional controls.
 
⸻
 
9.19.5 File Retention
Temporary uploads should expire.
Abandoned uploads must be cleaned up.
Published assets and client records follow product retention policies.
 
⸻
 
9.20 AI Security
9.20.1 Context Isolation
Every AI request must identify:
	•	Organization
	•	Location
	•	Product
	•	Task
	•	Data classification
Context assembly must query only authorized records within that scope.
 
⸻
 
9.20.2 Prompt Injection
Untrusted content must be treated as data, not instructions.
Examples:
	•	Reviews
	•	Lead messages
	•	Website pages
	•	Uploaded documents
	•	Emails
	•	Search results
AI tools must not follow instructions found inside untrusted content unless those instructions are part of the approved task.
 
⸻
 
9.20.3 Tool Restriction
AI models may call only allowlisted tools.
Each tool must enforce:
	•	Authentication
	•	Authorization
	•	Tenant scope
	•	Input schema
	•	Output schema
	•	Risk policy
	•	Audit logging
The model must not receive a general shell, SQL console, or unrestricted provider client.
 
⸻
 
9.20.4 Data Leakage Prevention
AI requests must not include:
	•	Other client data
	•	Provider credentials
	•	Secret configuration
	•	Unnecessary personal data
	•	Internal restricted notes
	•	Full database exports
	•	Unrelated historical records
 
⸻
 
9.20.5 AI Output as Untrusted Input
AI output must be validated like any other external input.
It must not directly become:
	•	SQL
	•	Shell commands
	•	Billing instructions
	•	Authorization decisions
	•	Published content
	•	Customer communication
	•	Configuration changes
without the applicable validation and approval.
 
⸻
 
9.20.6 Provider Policy
AI routing must consider:
	•	Provider data retention
	•	Training use
	•	Regional processing
	•	Security terms
	•	Organization restrictions
	•	Data classification
Restricted data must not be sent to a provider without explicit approval and suitable controls.
 
⸻
 
9.21 Infrastructure Security
9.21.1 Vercel
Vercel security requirements include:
	•	Environment separation
	•	Restricted project access
	•	Protected production variables
	•	Controlled domain configuration
	•	Deployment auditability
	•	Preview deployment review
	•	No sensitive data in build logs
 
⸻
 
9.21.2 Supabase
Supabase security requirements include:
	•	Row Level Security
	•	Separate production project
	•	Limited service-role usage
	•	Secure database credentials
	•	Backup configuration
	•	Migration-controlled schema
	•	Restricted dashboard access
	•	Audited policy changes
 
⸻
 
9.21.3 Hetzner
Hetzner security requirements include:
	•	SSH key authentication
	•	Password login disabled where practical
	•	Firewall configuration
	•	Limited open ports
	•	Regular operating-system updates
	•	Non-root service processes
	•	Process supervision
	•	Log protection
	•	Backup configuration
	•	Offboarding of old keys
 
⸻
 
9.21.4 GitHub
GitHub security requirements include:
	•	Protected primary branches
	•	Pull-request review
	•	Required tests where appropriate
	•	Secret scanning
	•	Dependency alerts
	•	Limited repository administration
	•	Fine-grained deployment credentials
	•	No production secrets in repository content
 
⸻
 
9.21.5 Development Machines
Developer workstations should use:
	•	Device passcode
	•	Full-disk encryption
	•	Current operating-system updates
	•	Secure SSH keys
	•	Screen locking
	•	No shared accounts
	•	Controlled local production data
	•	Prompt removal of access after loss or replacement
 
⸻
 
9.22 Network Security
The initial architecture should minimize public network exposure.
Publicly accessible services should be limited to:
	•	Web application
	•	Public API routes
	•	Webhook endpoints
	•	Required authentication endpoints
Database ports and internal worker interfaces should not be exposed publicly unless strictly required and secured.
Firewall rules should allow only necessary traffic.
Administrative interfaces should use restricted access where possible.
 
⸻
 
9.23 Environment Isolation
Local, staging, and production environments must use separate:
	•	Databases
	•	Secrets
	•	Provider credentials where possible
	•	Webhook URLs
	•	Storage
	•	Authentication projects
	•	AI policies
	•	Billing configuration
Production data must not be copied into staging or local environments without sanitization and approval.
A staging test must not publish to a production client account.
 
⸻
 
9.24 Secure Development Lifecycle
Security must be included throughout development.
Planning
Define:
	•	Data classification
	•	Permissions
	•	Threats
	•	External actions
	•	Approval needs
	•	Retention
Implementation
Use:
	•	Typed contracts
	•	Secure defaults
	•	Input validation
	•	Tenant scope
	•	Audit events
	•	Secret controls
Review
Check:
	•	Authorization
	•	Cross-tenant risk
	•	Data exposure
	•	Failure handling
	•	Provider scopes
	•	AI tool access
Testing
Test:
	•	Unauthorized access
	•	Role restrictions
	•	Tenant isolation
	•	Injection
	•	Replay
	•	Duplicate actions
	•	Secret leakage
	•	File abuse
	•	Webhook forgery
Release
Confirm:
	•	Migrations
	•	Environment configuration
	•	Monitoring
	•	Rollback
	•	Incident ownership
	•	Security-sensitive changes
 
⸻
 
9.25 Threat Modeling
New products and major features should include a practical threat review.
The review should identify:
	•	Assets
	•	Actors
	•	Entry points
	•	Trust boundaries
	•	Abuse cases
	•	Failure impact
	•	Existing controls
	•	Additional controls
	•	Residual risk
Example threats for review management:
	•	Unauthorized response publication
	•	Cross-client review access
	•	Prompt injection through review text
	•	False legal admission
	•	Provider-token theft
	•	Duplicate response publication
	•	Malicious internal user action
Threat modeling should focus on plausible platform risks rather than produce documentation with no implementation effect.
 
⸻
 
9.26 Dependency Security
The platform must maintain an inventory of application dependencies.
Requirements include:
	•	Version-controlled lock files
	•	Dependency alerts
	•	Removal of unused packages
	•	Review of high-risk updates
	•	Prompt patching of critical vulnerabilities
	•	Avoidance of abandoned libraries for core security functions
	•	Verification of package names to reduce dependency-confusion risk
Automated updates should not merge security-sensitive changes without testing.
 
⸻
 
9.27 Vulnerability Management
Vulnerabilities should be classified by severity and actual exposure.
Recommended response categories:
Critical
Examples:
	•	Active secret exposure
	•	Cross-tenant data access
	•	Remote code execution
	•	Authentication bypass
	•	Unrestricted external publication
Action:
	•	Immediate containment
	•	Emergency remediation
	•	Incident process
High
Examples:
	•	Privilege escalation
	•	Stored cross-site scripting
	•	Significant personal-data exposure
	•	Webhook authentication bypass
Action:
	•	Rapid remediation
	•	Release priority
	•	Exposure review
Medium
Examples:
	•	Limited information disclosure
	•	Rate-limit weakness
	•	Non-critical dependency issue
Action:
	•	Scheduled remediation
Low
Examples:
	•	Minor hardening gap
	•	Limited metadata exposure
Action:
	•	Backlog with owner and review date
Severity alone should not replace analysis of exploitability and business impact.
 
⸻
 
9.28 Security Logging
Security logs should include:
	•	Authentication success and failure
	•	Session revocation
	•	Password reset
	•	MFA changes
	•	Membership changes
	•	Role changes
	•	Permission changes
	•	Entitlement changes
	•	Integration connection and revocation
	•	Failed webhook verification
	•	Cross-tenant access denial
	•	Data export
	•	Sensitive file access
	•	Operator write actions
	•	Administrative configuration changes
	•	Secret rotation events
	•	Incident actions
Logs must not contain secrets.
 
⸻
 
9.29 Security Monitoring
Initial monitoring should detect:
	•	Repeated login failure
	•	Sudden access from unusual contexts
	•	Large or repeated exports
	•	High authorization-failure rate
	•	Repeated invalid webhooks
	•	Unexpected worker identity use
	•	Cross-tenant query failures
	•	Unusual AI usage
	•	Elevated error rate after deployment
	•	Disabled integration verification
	•	Excessive publication attempts
	•	Failed backup jobs
Monitoring should produce actionable alerts rather than excessive undifferentiated noise.
 
⸻
 
9.30 Audit Log Protection
Audit logs should be append-only through ordinary application operations.
Users must not be able to:
	•	Edit audit records
	•	Delete audit records
	•	Change actor identity
	•	Remove failed-action history
Corrections should create a new explanatory record.
Audit access should be permission-controlled because logs may contain sensitive operational metadata.
 
⸻
 
9.31 Backup Security
Backups must be:
	•	Encrypted
	•	Access-controlled
	•	Environment-specific
	•	Monitored
	•	Retained according to policy
	•	Periodically tested
Backup credentials must be separate from ordinary application access where practical.
A backup that has never been restored in testing should not be assumed usable.
 
⸻
 
9.32 Recovery Requirements
Recovery planning should define:
	•	Recovery point objective
	•	Recovery time objective
	•	Responsible operator
	•	Database restoration steps
	•	File restoration steps
	•	Credential restoration or rotation
	•	Workflow reconciliation
	•	External action reconciliation
	•	Client communication process
Recovery must account for actions completed in external systems during the outage.
Examples:
	•	A GBP post published before the database update failed
	•	An email sent but delivery status was not recorded
	•	A review response published during retry
The system must reconcile rather than blindly repeat such actions.
 
⸻
 
9.33 Business Continuity
The platform should retain manual operating paths for critical services.
Examples:
	•	Manual review response
	•	Manual GBP publication
	•	Manual lead follow-up
	•	Manual report export
	•	Manual content publication
	•	Manual integration reconnection
The platform should degrade safely rather than make essential client work impossible.
 
⸻
 
9.34 Incident Response
9.34.1 Incident Categories
Potential incidents include:
	•	Unauthorized access
	•	Tenant-data exposure
	•	Secret leakage
	•	Malware
	•	Service outage
	•	Data loss
	•	Unauthorized publication
	•	Unintended customer communication
	•	Provider compromise
	•	AI cross-client leakage
	•	Billing error
	•	Backup failure
 
⸻
 
9.34.2 Incident Lifecycle
Recommended lifecycle:
Detect
    ↓
Triage
    ↓
Contain
    ↓
Preserve Evidence
    ↓
Remediate
    ↓
Recover
    ↓
Notify
    ↓
Review
 
⸻
 
9.34.3 Incident Record
Each material incident should record:
	•	Incident ID
	•	Start time
	•	Detection time
	•	Reporter
	•	Severity
	•	Affected organizations
	•	Affected systems
	•	Data involved
	•	Containment actions
	•	Root cause
	•	Recovery actions
	•	Notifications
	•	Corrective actions
	•	Closure approval
 
⸻
 
9.34.4 Containment Priorities
Containment may include:
	•	Revoke credentials
	•	Disable affected workflows
	•	Suspend integrations
	•	Disable publication
	•	Block a compromised user
	•	Remove public endpoint access
	•	Roll back deployment
	•	Isolate server
	•	Stop AI routing to a provider
Containment takes priority over preserving normal platform operation.
 
⸻
 
9.34.5 Evidence Preservation
During an incident, preserve:
	•	Audit logs
	•	Access logs
	•	Workflow records
	•	Provider event IDs
	•	Deployment history
	•	Relevant database snapshots
	•	Affected configuration
	•	Timeline notes
Do not overwrite evidence through informal troubleshooting.
 
⸻
 
9.34.6 Post-Incident Review
A review should determine:
	•	What happened?
	•	Why did controls fail?
	•	What was affected?
	•	How was it detected?
	•	How was it contained?
	•	What delayed response?
	•	Which controls should change?
	•	Who owns each corrective action?
The objective is operational improvement, not blame.
 
⸻
 
9.35 Privacy Principles
The platform should follow these privacy principles:
	•	Collect only data required for a defined purpose.
	•	Use data only for approved platform functions.
	•	Restrict access by role and tenant.
	•	Retain data only as long as needed.
	•	Provide deletion or export where applicable.
	•	Avoid unnecessary personal-data use in AI.
	•	Document external data processors.
	•	Do not silently repurpose client data.
 
⸻
 
9.36 Personal Data Inventory
The platform should maintain an inventory of personal-data categories.
Potential records include:
	•	Platform users
	•	Client contacts
	•	Leads
	•	Reviewers
	•	Email recipients
	•	SMS recipients
	•	Support communications
	•	Approval history
	•	Audit actors
The inventory should identify:
	•	Purpose
	•	Source
	•	Storage location
	•	Retention
	•	Access
	•	Processors
	•	Deletion behavior
 
⸻
 
9.37 Consent and Communication Privacy
Lead and communication products must record:
	•	Communication channel
	•	Consent status
	•	Consent source
	•	Consent timestamp
	•	Opt-out status
	•	Opt-out timestamp
	•	Applicable organization and location
	•	Message history
An opt-out must prevent future automated communication through the affected channel unless a lawful and documented exception applies.
AI must not override consent state.
 
⸻
 
9.38 Data Subject and Client Requests
The platform should support controlled handling of requests such as:
	•	Access to stored data
	•	Correction
	•	Export
	•	Deletion
	•	Communication opt-out
	•	Account closure
The platform should verify the requester before fulfilling a sensitive request.
Deletion requests may be limited by legitimate retention requirements such as:
	•	Billing records
	•	Security logs
	•	Contractual obligations
	•	Legal requirements
Where deletion is not possible, data may need to be restricted or anonymized.
 
⸻
 
9.39 Data Export
Exports must be:
	•	Permission-controlled
	•	Tenant-scoped
	•	Logged
	•	Time-limited
	•	Stored securely
	•	Deleted after expiration
Sensitive exports should use:
	•	Short-lived download links
	•	Strong authorization
	•	Explicit organization labeling
	•	Minimal included fields
Bulk cross-client export should require elevated internal permission.
 
⸻
 
9.40 Retention and Deletion
Retention policies should define:
	•	Record category
	•	Retention duration
	•	Business purpose
	•	Deletion method
	•	Archival behavior
	•	Legal exceptions
	•	Owner
Deletion should account for:
	•	Primary database
	•	Object storage
	•	Search indexes
	•	Vector indexes
	•	Temporary files
	•	AI execution payloads
	•	Backups
	•	Third-party providers
Backups may follow delayed deletion based on the backup cycle.
 
⸻
 
9.41 Client Offboarding Security
Offboarding should include:
	1.	Confirm authorized request.
	2.	Disable user access.
	3.	Pause workflows.
	4.	Revoke integration credentials.
	5.	Remove scheduled communications.
	6.	Export agreed data.
	7.	Resolve pending approvals.
	8.	Preserve required billing and audit records.
	9.	Delete or anonymize eligible data.
	10.	Remove internal access no longer required.
	11.	Record completion.
No scheduled automation should remain active after offboarding unless explicitly agreed.
 
⸻
 
9.42 Vendor and Provider Risk
External providers may process or store platform data.
Providers should be reviewed for:
	•	Security controls
	•	Data retention
	•	Subprocessors
	•	Breach-notification terms
	•	Availability
	•	Access controls
	•	Encryption
	•	API security
	•	Data deletion
	•	Contract terms
	•	Operational dependency
Provider risk review should be proportional to the sensitivity and volume of data involved.
 
⸻
 
9.43 Provider Failure and Compromise
The architecture must support:
	•	Disabling a provider
	•	Revoking credentials
	•	Routing AI tasks elsewhere
	•	Pausing external publication
	•	Preserving queued work
	•	Reconnecting affected accounts
	•	Identifying affected organizations
	•	Reviewing actions during the incident window
No single provider should have unnecessary access to unrelated platform functions.
 
⸻
 
9.44 Security Testing
Required security testing includes:
	•	Authentication tests
	•	Authorization tests
	•	Tenant-isolation tests
	•	RLS tests
	•	API schema tests
	•	Webhook-signature tests
	•	Replay tests
	•	File-upload tests
	•	Injection tests
	•	Cross-site scripting tests
	•	CSRF tests where applicable
	•	Rate-limit tests
	•	Secret-scanning tests
	•	AI prompt-injection tests
	•	Operator-tool permission tests
	•	External-action duplicate tests
 
⸻
 
9.45 Pre-Release Security Review
A feature should not enter production until the team can answer:
	•	What data does it access?
	•	What data does it create?
	•	Which organization owns the data?
	•	Who may read it?
	•	Who may change it?
	•	Does it produce an external action?
	•	Does it require approval?
	•	Which credentials does it use?
	•	What happens if it is retried?
	•	What happens if it fails halfway?
	•	What is logged?
	•	What is retained?
	•	Can it expose another client?
	•	Can AI access the data?
	•	Is there a manual recovery path?
 
⸻
 
9.46 Security Acceptance Requirements
A product is not production-ready until it has:
	•	Defined data classification
	•	Tenant-scoped records
	•	RLS policies
	•	Server-side authorization
	•	Permission definitions
	•	Entitlement enforcement
	•	Audit events
	•	Secure integration handling
	•	Secret-management plan
	•	Input validation
	•	Output protection
	•	Rate limiting where required
	•	File controls where applicable
	•	External-action idempotency
	•	Incident visibility
	•	Backup and recovery considerations
	•	Retention policy
	•	Security tests
	•	Offboarding behavior
	•	Documentation
 
⸻
 
9.47 Initial Security Implementation Order
Stage 1 — Identity and Tenant Isolation
Implement:
	•	Supabase authentication
	•	Organization memberships
	•	Roles and permissions
	•	Product entitlements
	•	Row Level Security
	•	Server-side authorization
	•	Tenant-isolation tests
Stage 2 — Secrets and Infrastructure
Implement:
	•	Environment separation
	•	Secret inventory
	•	Secure credential references
	•	Server firewall
	•	SSH-key controls
	•	GitHub branch protection
	•	Secret scanning
Stage 3 — Audit and Monitoring
Implement:
	•	Audit events
	•	Authentication logs
	•	Permission-change logs
	•	Integration logs
	•	External-action logs
	•	Failed-authorization monitoring
	•	Operational alerts
Stage 4 — Integration and Webhook Security
Implement:
	•	OAuth scope controls
	•	Webhook signatures
	•	Replay protection
	•	Event deduplication
	•	Credential rotation
	•	Connection revocation
Stage 5 — Product Security
Implement security requirements for the first SEO workflow, followed by:
	•	GBP publication
	•	Review responses
	•	Content publication
	•	Leads and communication
	•	Reporting exports
Stage 6 — AI and Operator Security
Implement:
	•	Context classification
	•	Prompt-injection controls
	•	Tool permissions
	•	Provider restrictions
	•	Data minimization
	•	Operator audit
	•	Confirmation policies
Stage 7 — Incident and Recovery
Implement:
	•	Backup verification
	•	Restore testing
	•	Incident templates
	•	Credential-exposure procedure
	•	Client offboarding checklist
	•	Provider-disable procedures
 
⸻
 
9.48 Security Guardrails
The following are prohibited unless formally approved:
	1.	Shared routine user accounts
	2.	Production access without an individual identity
	3.	Tenant-owned records without organization scope
	4.	Frontend-only authorization
	5.	Service-role database access used without application scope checks
	6.	Provider credentials exposed to the browser
	7.	Secrets committed to source control
	8.	Production secrets reused in development
	9.	Unsigned webhook processing
	10.	Public storage URLs for private files
	11.	Cross-client caching
	12.	Production client data used as ordinary test data
	13.	Unrestricted support impersonation
	14.	AI access to secrets
	15.	AI tools with unrestricted SQL or shell access
	16.	External publication without permission and entitlement checks
	17.	Bulk export without authorization and audit
	18.	Audit-log deletion through ordinary application functions
	19.	Hardcoded credentials in scripts
	20.	Public error responses containing stack traces or internal queries
	21.	Unbounded login attempts
	22.	Indefinite retention of sensitive raw payloads without purpose
	23.	Disabled RLS on tenant-owned client tables without a documented exception
	24.	Automatic communication after opt-out
	25.	Silent privilege escalation
	26.	Silent cross-tenant administrative access
	27.	Backup assumptions without restore testing
	28.	Continued use of a potentially exposed secret
	29.	Production deployment of a feature without tenant-isolation tests
	30.	Security controls that can be bypassed by an AI operator
 
⸻
 
9.49 Section Decisions
This section establishes the following decisions:
	1.	Security is a core platform architecture requirement.
	2.	The platform uses deny-by-default and least-privilege access.
	3.	Security is enforced through authentication, authorization, entitlements, tenant scope, business policy, and audit logging.
	4.	The organization is the primary tenant-security boundary.
	5.	Row Level Security and server-side authorization are both required.
	6.	Human users and backend services use identifiable, auditable identities.
	7.	Privileged users should use multi-factor authentication.
	8.	Secrets are stored only in approved protected systems.
	9.	Secrets must never enter source control, logs, frontend code, or AI context.
	10.	All production traffic uses encrypted transport.
	11.	External integrations use minimal scopes and protected credential references.
	12.	Webhooks are authenticated, deduplicated, and replay-protected.
	13.	External actions require authorization, entitlement, state validation, and idempotency.
	14.	AI input and output are treated as security-sensitive, untrusted processing boundaries.
	15.	AI tools cannot bypass platform permissions or tenant isolation.
	16.	Security-relevant activity is logged and monitored.
	17.	Audit records are append-only through ordinary platform operations.
	18.	Backups must be encrypted, monitored, and periodically restored in testing.
	19.	Incident response must support containment, evidence preservation, recovery, notification, and corrective action.
	20.	Personal data is collected, processed, retained, exported, and deleted only for defined purposes.
	21.	Communication consent and opt-out status are deterministic platform data.
	22.	Client offboarding includes access removal, integration revocation, workflow shutdown, export, and controlled deletion.
	23.	Vendor and provider risk is reviewed according to the data and operational access involved.
	24.	Tenant-isolation and authorization tests are mandatory for every product.
	25.	No product is production-ready without defined security, privacy, recovery, and offboarding behavior.

---

Section 10 — Infrastructure, Deployment, Observability, and Platform Operations
10.1 Purpose of This Section
This section defines how the LILOs platform is deployed, operated, monitored, maintained, and recovered in production.
It establishes:
	•	Environment architecture
	•	Hosting responsibilities
	•	Deployment topology
	•	Continuous integration
	•	Continuous delivery
	•	Release controls
	•	Database migration procedures
	•	Worker deployment
	•	Configuration management
	•	Infrastructure ownership
	•	Logging
	•	Metrics
	•	Tracing
	•	Health monitoring
	•	Alerting
	•	Operational dashboards
	•	Incident operations
	•	Capacity management
	•	Cost monitoring
	•	Backup verification
	•	Disaster recovery
	•	Maintenance procedures
	•	Production access
	•	Service-level objectives
	•	Operational acceptance requirements
The goal is to create an operating model that is reliable and visible without introducing unnecessary infrastructure complexity.
The platform should remain manageable by a small engineering and operations team.
 
⸻
 
10.2 Operational Philosophy
The platform must be designed to answer four questions at all times:
	1.	Is the platform available?
	2.	Is it functioning correctly?
	3.	Are client workflows completing?
	4.	Can failures be diagnosed and recovered safely?
A successful deployment is not one where code reaches production.
A successful deployment is one where:
	•	The new version is healthy.
	•	Existing workflows continue.
	•	Database state is valid.
	•	External actions remain controlled.
	•	Failures are visible.
	•	Rollback or recovery is possible.
 
⸻
 
10.3 Operational Principles
Principle 1 — Prefer Simple Infrastructure
The initial platform should use the minimum infrastructure required to meet reliability and product needs.
Approved initial components include:
	•	Vercel
	•	Supabase
	•	Hetzner
	•	GitHub Actions
	•	Docker Compose where useful
	•	systemd
	•	PostgreSQL-backed workflow state
	•	Structured application logging
The platform should not introduce Kubernetes, Kafka, service mesh infrastructure, or dedicated orchestration systems without measured need.
 
⸻
 
Principle 2 — Infrastructure Is Reproducible
Production services must not depend on undocumented manual server changes.
Infrastructure configuration should be:
	•	Version-controlled
	•	Documented
	•	Repeatable
	•	Reviewable
	•	Recoverable
Manual setup steps that remain necessary must be captured in an operating procedure.
 
⸻
 
Principle 3 — Every Deployment Is Observable
A deployment must record:
	•	Version
	•	Commit
	•	Environment
	•	Initiator
	•	Start time
	•	Completion time
	•	Migration status
	•	Health result
	•	Rollback status
	•	Related incident, if applicable
 
⸻
 
Principle 4 — Production Changes Are Controlled
No production change should occur without:
	•	Identified scope
	•	Known owner
	•	Validation
	•	Expected result
	•	Recovery path
	•	Auditability
Emergency changes may use an accelerated process but must still be documented afterward.
 
⸻
 
Principle 5 — Failures Must Be Actionable
Alerts should indicate:
	•	What failed
	•	Which service is affected
	•	Which organizations may be affected
	•	Whether the issue is continuing
	•	Whether external actions are at risk
	•	What the operator should inspect next
An alert that only says “error rate high” is insufficient for critical workflows.
 
⸻
 
Principle 6 — Client Workflows Matter More Than Process Uptime Alone
A worker process may be alive while workflows are stuck.
The platform must monitor business execution, not only infrastructure availability.
Examples:
	•	Reviews are syncing.
	•	GBP posts are publishing.
	•	SEO data is current.
	•	Approvals are progressing.
	•	Lead messages are being sent.
	•	Reports are generated on schedule.
 
⸻
 
10.4 Environment Model
The platform should maintain three primary environments.
Local
    ↓
Staging
    ↓
Production
Optional preview environments may exist for frontend pull requests.
 
⸻
 
10.4.1 Local Environment
Used for:
	•	Development
	•	Unit tests
	•	Local integration tests
	•	Database migration development
	•	Workflow simulation
	•	Prompt testing
	•	Provider mocks
Local development should use:
	•	Local or isolated Supabase instance where practical
	•	Test credentials
	•	Mock external providers
	•	Non-production storage
	•	Development AI routing policies
	•	Fabricated data
Local development must not publish to production client accounts.
 
⸻
 
10.4.2 Staging Environment
Used for:
	•	End-to-end validation
	•	Migration rehearsal
	•	Integration testing
	•	Workflow execution testing
	•	Approval testing
	•	Deployment verification
	•	Release-candidate testing
Staging must use separate:
	•	Database
	•	Authentication project
	•	Storage
	•	API credentials
	•	Webhook endpoints
	•	Worker services
	•	AI configuration
	•	Billing configuration
Staging data should be fabricated or sanitized.
 
⸻
 
10.4.3 Production Environment
Used only for live platform operation.
Production requires:
	•	Restricted access
	•	Protected secrets
	•	Controlled migrations
	•	Monitoring
	•	Backups
	•	Incident procedures
	•	Deployment history
	•	Rollback capability
Production systems must not be used as general development or testing environments.
 
⸻
 
10.4.4 Preview Environments
Vercel preview deployments may be used for:
	•	Frontend review
	•	User-interface testing
	•	Pull-request validation
Preview environments must not automatically receive:
	•	Production secrets
	•	Production service-role keys
	•	Production provider credentials
	•	Production database access
	•	Live client data
Preview environments should use mocked or staging APIs.
 
⸻
 
10.5 Initial Deployment Topology
The initial deployment topology should be:
Users
    ↓
Vercel
    ├── Astro Web Application
    └── Lightweight Server Routes
            ↓
FastAPI Application on Hetzner
            ↓
Supabase PostgreSQL
            ↓
Supabase Auth and Storage

Hetzner Worker Services
    ├── Scheduler
    ├── Workflow Worker
    ├── Integration Sync Workers
    ├── AI Task Worker
    ├── Publication Worker
    └── Notification Worker
External providers connect through the API and worker layers.
 
⸻
 
10.6 Vercel Responsibilities
Vercel should initially host:
	•	Astro application
	•	Agency console
	•	Client portal
	•	Marketing or public application pages
	•	Lightweight server-rendered routes
	•	Authentication callback routes
	•	Request proxying where appropriate
	•	Static assets
	•	Preview deployments
Vercel should not initially own:
	•	Long-running workflows
	•	Large integration syncs
	•	Persistent worker processes
	•	Long AI jobs
	•	Durable scheduling
	•	Multi-step publication operations
	•	High-volume background processing
Serverless execution limits must not define workflow architecture.
 
⸻
 
10.7 Supabase Responsibilities
Supabase should provide:
	•	PostgreSQL database
	•	Authentication
	•	Row Level Security
	•	Object storage
	•	Database backups
	•	Database connection management
	•	Realtime features only where justified
Supabase is the platform’s source of truth.
Supabase Edge Functions are not required for core architecture unless a specific use case benefits from them.
 
⸻
 
10.8 Hetzner Responsibilities
Hetzner should initially host:
	•	FastAPI backend
	•	Long-running workers
	•	Scheduler
	•	Integration synchronization
	•	AI gateway execution
	•	Publication workflows
	•	Notification processing
	•	Operational utilities
	•	Reconciliation jobs
Services may run through:
	•	Docker Compose
	•	systemd
	•	Separate process identities
	•	Internal networking
The implementation should favor operational clarity over excessive container fragmentation.
 
⸻
 
10.9 Service Deployment Model
The initial backend may use a small number of deployable services.
Recommended deployment units:
api
worker
scheduler
The worker deployment may process multiple workflow categories through separate queues or process groups.
Additional deployable services should be created only when needed for:
	•	Independent scaling
	•	Security isolation
	•	Failure isolation
	•	Different runtime requirements
	•	Operational ownership
A code module does not automatically require a separate deployed service.
 
⸻
 
10.10 Backend Process Structure
A practical initial process layout may include:
lilos-api
lilos-worker-default
lilos-worker-ai
lilos-worker-integrations
lilos-scheduler
Possible later separation:
lilos-worker-leads
lilos-worker-publication
lilos-worker-reporting
Separation should be driven by measurable workload or risk.
 
⸻
 
10.11 Container Strategy
Docker may be used to standardize:
	•	Runtime versions
	•	Dependencies
	•	Service startup
	•	Local parity
	•	Deployment packaging
Docker Compose is sufficient for the initial Hetzner deployment.
Each container should define:
	•	Image version
	•	Environment variables
	•	Health check
	•	Resource limits where practical
	•	Restart policy
	•	Log handling
	•	Network exposure
	•	Persistent volume requirements
Containers should not run as root unless technically unavoidable and documented.
 
⸻
 
10.12 Process Supervision
Services must restart automatically after:
	•	Process crash
	•	Server restart
	•	Deployment
	•	Temporary failure
systemd or Docker restart policies may provide supervision.
Supervision must not create infinite failure loops without alerting.
Repeated restart behavior should trigger an operational alert.
 
⸻
 
10.13 Repository and Branch Strategy
The platform should use GitHub as the source of truth for application code and infrastructure configuration.
Recommended branches:
main
feature/*
fix/*
release/* when necessary
main should represent deployable production code.
Direct pushes to main should be restricted.
 
⸻
 
10.13.1 Pull Request Requirements
Production-impacting changes should use pull requests.
A pull request should include:
	•	Purpose
	•	Scope
	•	Risks
	•	Tests
	•	Migration impact
	•	Configuration impact
	•	Rollback considerations
	•	Screenshots where interface changes are involved
 
⸻
 
10.13.2 Required Checks
Initial required checks may include:
	•	Formatting
	•	Linting
	•	Type checks
	•	Unit tests
	•	Integration tests
	•	Database migration validation
	•	Build verification
	•	Security scans
	•	Secret scanning
Not every repository needs every check, but failures must not be ignored without explanation.
 
⸻
 
10.14 Continuous Integration
The CI pipeline should validate changes before merge.
Recommended stages:
Checkout
    ↓
Install Dependencies
    ↓
Static Analysis
    ↓
Unit Tests
    ↓
Integration Tests
    ↓
Build
    ↓
Migration Validation
    ↓
Security Checks
    ↓
Artifact Creation
CI should fail clearly and identify the failing stage.
 
⸻
 
10.15 Continuous Delivery
Deployment should occur through a controlled automated process.
Recommended production deployment sequence:
Merge to main
    ↓
Build versioned artifact
    ↓
Run pre-deployment validation
    ↓
Apply backward-compatible migration
    ↓
Deploy backend
    ↓
Deploy workers
    ↓
Deploy frontend
    ↓
Run health checks
    ↓
Run smoke tests
    ↓
Mark deployment successful
The exact order may differ depending on compatibility requirements.
 
⸻
 
10.16 Deployment Versioning
Every deployment should have a stable version identifier.
Recommended format:
Git commit SHA
Optional human-readable release version:
2026.07.1
Each running service should expose:
	•	Application version
	•	Commit SHA
	•	Build timestamp
	•	Environment
This information should be visible through an internal health or version endpoint.
 
⸻
 
10.17 Release Types
Recommended release categories:
Standard Release
Normal reviewed deployment during an ordinary release window.
Low-Risk Configuration Release
Changes only approved configuration or prompt routing without application-code deployment.
Database Migration Release
Includes schema or data changes requiring additional validation.
High-Risk Release
Affects:
	•	Authentication
	•	Authorization
	•	Billing
	•	External publication
	•	Lead communication
	•	Tenant isolation
	•	Data deletion
	•	AI operator write access
Emergency Release
Used to contain or remediate an urgent production issue.
Release type should influence required review and validation.
 
⸻
 
10.18 Deployment Approval
The initial team may use lightweight approvals, but high-risk production changes should require a second qualified reviewer.
At minimum, high-risk deployments should verify:
	•	Scope understood
	•	Tests passed
	•	Migration safe
	•	Rollback or recovery available
	•	Monitoring ready
	•	External side effects controlled
An AI-generated change does not qualify as independent human review.
 
⸻
 
10.19 Feature Flags
Feature flags may be used for:
	•	Gradual rollout
	•	Internal-only features
	•	Beta products
	•	High-risk capabilities
	•	Organization-specific activation
	•	Emergency disabling
Feature flags must not replace product entitlements.
A flag controls deployment behavior.
An entitlement controls contractual or authorized product access.
 
⸻
 
10.19.1 Feature Flag Requirements
A feature flag should define:
	•	Key
	•	Owner
	•	Purpose
	•	Default state
	•	Eligible environments
	•	Eligible organizations
	•	Expiration or review date
	•	Removal plan
Permanent forgotten flags create operational debt.
 
⸻
 
10.20 Database Migration Process
Every production schema change must use a reviewed migration.
Migration process:
	1.	Create migration locally.
	2.	Test against representative schema.
	3.	Validate data impact.
	4.	Test rollback or recovery approach.
	5.	Rehearse in staging.
	6.	Deploy compatible application code where required.
	7.	Apply migration.
	8.	Verify database health.
	9.	Run product smoke tests.
	10.	Monitor.
 
⸻
 
10.20.1 Migration Categories
Additive
Examples:
	•	New table
	•	Nullable column
	•	New index
	•	New optional enum value
Usually lowest risk.
Transformational
Examples:
	•	Backfill
	•	Data normalization
	•	Relationship migration
	•	Large index build
Requires measured execution planning.
Destructive
Examples:
	•	Drop column
	•	Drop table
	•	Change incompatible type
	•	Remove enum value
Destructive changes should be delayed until all code and data dependencies are removed.
 
⸻
 
10.20.2 Expand-and-Contract Pattern
Breaking schema changes should use:
Expand schema
    ↓
Deploy compatible code
    ↓
Backfill data
    ↓
Switch reads and writes
    ↓
Validate
    ↓
Remove old schema later
This reduces deployment coupling.
 
⸻
 
10.20.3 Migration Locks and Performance
Migrations must consider:
	•	Table size
	•	Lock duration
	•	Index creation
	•	Backfill size
	•	Worker activity
	•	API traffic
	•	Timeout behavior
Large production backfills should run as controlled jobs rather than one unbounded migration transaction.
 
⸻
 
10.21 Data Backfills
Backfills should define:
	•	Source records
	•	Target records
	•	Batch size
	•	Idempotency
	•	Progress tracking
	•	Failure handling
	•	Retry behavior
	•	Validation
	•	Rollback or correction approach
Backfills must be observable.
A backfill must not exist only as an undocumented one-time terminal command.
 
⸻
 
10.22 Worker Deployment Safety
Workers must support graceful shutdown.
During deployment, workers should:
	1.	Stop claiming new work.
	2.	Complete or safely checkpoint current work.
	3.	Record unfinished state.
	4.	Shut down.
	5.	Restart with the new version.
	6.	Resume eligible work.
Workers must not abandon workflows in ambiguous states.
 
⸻
 
10.23 Workflow Compatibility During Deployment
A workflow execution should retain its definition version.
New deployments must consider:
	•	Existing queued workflows
	•	Running workflows
	•	Waiting approvals
	•	Retry-scheduled workflows
	•	Old payload schemas
	•	Old prompt versions
	•	Old integration adapter behavior
A deployment must not assume every workflow started under the newest code version.
 
⸻
 
10.24 Scheduler Operation
The scheduler should:
	•	Query durable schedules
	•	Respect timezone
	•	Prevent duplicate dispatch
	•	Verify entitlement
	•	Verify workflow status
	•	Create execution records
	•	Update next-run time
	•	Record failures
	•	Support pause and resume
The scheduler should not execute the full business workflow directly.
It should dispatch work to workers.
 
⸻
 
10.25 Queue and Job Dispatch
The initial platform may use PostgreSQL-backed job dispatch.
Required behavior includes:
	•	Atomic job claiming
	•	Visibility or lock timeout
	•	Retry count
	•	Scheduled availability
	•	Priority
	•	Dead-letter or terminal failure state
	•	Worker identity
	•	Heartbeat where required
	•	Idempotency
A dedicated queue system may be introduced later if PostgreSQL becomes a measured bottleneck.
 
⸻
 
10.26 Dead-Letter and Failed Work
Terminally failed work must remain visible.
A failed job should include:
	•	Workflow
	•	Step
	•	Organization
	•	Location
	•	Error code
	•	Attempt count
	•	Last attempt
	•	Provider
	•	Retry eligibility
	•	Reconciliation requirement
	•	Assigned owner
	•	Resolution status
Operators should be able to:
	•	Retry safely
	•	Cancel
	•	Mark resolved
	•	Create a follow-up
	•	Escalate
	•	Inspect related records
 
⸻
 
10.27 Configuration Management
Configuration must be separated into categories.
Code Configuration
Version-controlled behavior.
Examples:
	•	Supported products
	•	Permission definitions
	•	Workflow definitions
	•	Schema definitions
Environment Configuration
Deployment-specific values.
Examples:
	•	Database URL
	•	API base URL
	•	Provider credentials
	•	Log destination
	•	Environment name
Tenant Configuration
Database-managed organization or location settings.
Examples:
	•	Approval requirements
	•	Post cadence
	•	Business timezone
	•	Notification preferences
Runtime Operational Controls
Examples:
	•	Pause provider
	•	Disable publishing
	•	Reduce concurrency
	•	Stop a workflow type
	•	Activate incident mode
 
⸻
 
10.28 Runtime Kill Switches
The platform should support emergency controls for:
	•	All external publication
	•	GBP publication
	•	Review responses
	•	Lead messaging
	•	Content publication
	•	AI execution
	•	Specific provider
	•	Specific organization
	•	Specific workflow type
Kill switches must be:
	•	Permission-controlled
	•	Audited
	•	Visible
	•	Reversible
	•	Tested
A kill switch should stop new actions without corrupting workflow history.
 
⸻
 
10.29 Logging Architecture
All services should produce structured logs.
Recommended log fields:
timestamp
level
environment
service
version
request_id
correlation_id
workflow_execution_id
organization_id
location_id
product
event
status
error_code
duration_ms
Logs should use machine-readable JSON where practical.
 
⸻
 
10.29.1 Log Levels
Recommended levels:
debug
info
warning
error
critical
Production debug logging should be disabled by default or narrowly enabled.
 
⸻
 
10.29.2 Logging Rules
Logs must not contain:
	•	Passwords
	•	API keys
	•	OAuth tokens
	•	Session tokens
	•	Database credentials
	•	Full sensitive lead records
	•	Entire AI prompts containing personal data
	•	Raw payment details
	•	Unredacted restricted data
 
⸻
 
10.29.3 Business Event Logging
Important business events should also exist as database records, not only logs.
Examples:
	•	Content published
	•	Review response sent
	•	Product enabled
	•	Workflow failed
	•	Approval granted
	•	Integration disconnected
Logs are for operations.
Database events are for durable platform history.
 
⸻
 
10.30 Metrics Architecture
Metrics should cover four layers.
Infrastructure Metrics
Examples:
	•	CPU
	•	Memory
	•	Disk
	•	Network
	•	Process restarts
	•	Database connections
Application Metrics
Examples:
	•	Request count
	•	Request latency
	•	Error rate
	•	Worker concurrency
	•	Queue depth
	•	Job age
Integration Metrics
Examples:
	•	Sync success
	•	Provider latency
	•	Rate limits
	•	Credential failures
	•	Data freshness
Business Workflow Metrics
Examples:
	•	Reviews processed
	•	GBP posts published
	•	Leads acknowledged
	•	Content approved
	•	Reports delivered
	•	SEO analyses completed
 
⸻
 
10.31 Tracing and Correlation
Every request, workflow, and external action should use correlation identifiers.
A single client action should be traceable across:
Frontend Request
    ↓
API Request
    ↓
Workflow Execution
    ↓
Worker Step
    ↓
AI Execution
    ↓
Provider Call
    ↓
Audit Event
Distributed tracing infrastructure may be introduced later.
Initially, consistent correlation IDs across structured logs and database records may be sufficient.
 
⸻
 
10.32 Health Checks
Each deployed service should expose health status.
Liveness
Confirms the process is running.
Readiness
Confirms the service can accept work.
Dependency Health
May verify:
	•	Database connectivity
	•	Required table availability
	•	Storage access
	•	Workflow queue access
	•	Critical configuration
Business Health
Confirms business workflows are progressing.
Examples:
	•	Oldest queued job age
	•	Last successful review sync
	•	Last successful GBP publication
	•	Last successful scheduler cycle
 
⸻
 
10.33 Service Health States
Recommended health states:
healthy
degraded
unavailable
maintenance
unknown
A service may be alive but degraded.
Example:
The API is reachable, but Google authentication failures prevent GBP operations.
The interface must distinguish infrastructure availability from product functionality.
 
⸻
 
10.34 Operational Dashboard
The agency console should provide a system-status area.
It should show:
	•	API health
	•	Worker health
	•	Scheduler health
	•	Database health
	•	Queue depth
	•	Oldest queued workflow
	•	Failed workflows
	•	Provider status
	•	Integration failures
	•	Data freshness issues
	•	Publication failures
	•	AI failure rate
	•	Notification failures
	•	Active incidents
	•	Recent deployments
The dashboard should support filtering by:
	•	Organization
	•	Location
	•	Product
	•	Provider
	•	Severity
	•	Time period
 
⸻
 
10.35 Client-Facing Status
Clients should see relevant operational status without unnecessary infrastructure detail.
Examples:
	•	Google connection requires attention
	•	Reporting data is delayed
	•	A publication failed
	•	A workflow is awaiting approval
	•	A provider is temporarily unavailable
Clients should not see:
	•	Stack traces
	•	Server names
	•	Credential details
	•	Other tenant impact
	•	Internal cost diagnostics
	•	Sensitive security information
 
⸻
 
10.36 Alerting
Alerts should be sent only for actionable conditions.
Recommended severity levels:
informational
warning
high
critical
 
⸻
 
10.36.1 Critical Alerts
Examples:
	•	Cross-tenant access detected
	•	Authentication outage
	•	Database unavailable
	•	Widespread external publication duplication
	•	Secret exposure
	•	Data-loss risk
	•	Production deployment causing severe outage
Critical alerts require immediate human attention.
 
⸻
 
10.36.2 High Alerts
Examples:
	•	Major workflow backlog
	•	Lead messaging unavailable
	•	GBP publication failing across multiple clients
	•	Worker service repeatedly crashing
	•	Backup failure
	•	AI provider failure without fallback
 
⸻
 
10.36.3 Warning Alerts
Examples:
	•	One integration needs reauthorization
	•	Data freshness delay
	•	Cost threshold approaching
	•	Elevated validation failures
	•	Queue age increasing
 
⸻
 
10.36.4 Informational Notifications
Examples:
	•	Deployment completed
	•	Provider recovered
	•	Backfill completed
	•	Scheduled maintenance started
	•	New model marked deprecated
 
⸻
 
10.37 Alert Routing
Alert routing should consider:
	•	Severity
	•	Product
	•	Organization impact
	•	Time of day
	•	Responsible owner
	•	Whether action is required
Potential delivery channels:
	•	Email
	•	In-app
	•	SMS for critical incidents
	•	Slack or another operational channel if introduced
Alerts should not be sent to clients unless the issue affects their required action or service expectations.
 
⸻
 
10.38 Alert Deduplication
Repeated occurrences of the same issue should be grouped.
An alert should track:
	•	First occurrence
	•	Latest occurrence
	•	Count
	•	Affected organizations
	•	Current state
	•	Acknowledgment
	•	Assigned owner
	•	Resolution
Alert storms reduce operational effectiveness.
 
⸻
 
10.39 Service-Level Indicators
Service-level indicators should measure actual platform behavior.
Examples:
	•	API successful request rate
	•	API latency
	•	Workflow completion rate
	•	Scheduled workflow timeliness
	•	Integration sync freshness
	•	External publication success
	•	Lead acknowledgment timeliness
	•	Report delivery timeliness
 
⸻
 
10.40 Initial Service-Level Objectives
Initial objectives should be realistic and refined after baseline measurement.
Potential starting objectives:
Platform API Availability
Target:
99.9% monthly successful availability
excluding approved maintenance where contractually permitted.
Workflow Dispatch
Target:
95% of scheduled workflows dispatched within 5 minutes of scheduled time
Standard Workflow Completion
Target:
95% of non-provider-blocked standard workflows complete without manual intervention
Critical Lead Workflow
Target:
95% of eligible automated lead acknowledgments initiated within 2 minutes
The exact lead objective must account for provider delivery latency and client configuration.
Reporting Freshness
Target:
95% of scheduled reports generated within the defined reporting window
These are initial engineering objectives, not contractual promises unless formally adopted.
 
⸻
 
10.41 Error Budgets
Once service-level objectives are measured reliably, the platform may use error budgets.
An error budget represents the acceptable amount of failure within an objective period.
If a service exceeds its error budget:
	•	Reliability work receives priority.
	•	High-risk feature releases may be paused.
	•	Root causes must be reviewed.
	•	Capacity or architecture changes may be justified.
Error budgets should not be implemented before metrics are trustworthy.
 
⸻
 
10.42 Incident Operations
Operational incidents should have an assigned incident owner.
The incident owner coordinates:
	•	Impact assessment
	•	Containment
	•	Communication
	•	Technical investigation
	•	Recovery
	•	Closure
	•	Follow-up actions
The person investigating a subsystem does not necessarily need to manage the overall incident.
 
⸻
 
10.43 Incident Severity
Recommended severity model:
SEV-1 — Critical
Examples:
	•	Cross-tenant data exposure
	•	Platform-wide outage
	•	Unauthorized production access
	•	Widespread unintended customer communication
	•	Irrecoverable data-loss risk
SEV-2 — High
Examples:
	•	Major product unavailable
	•	Many clients affected
	•	Critical workflow backlog
	•	Significant provider outage without mitigation
SEV-3 — Moderate
Examples:
	•	Single product degradation
	•	Limited client impact
	•	Manual workaround available
SEV-4 — Low
Examples:
	•	Minor defect
	•	Non-critical reporting discrepancy
	•	Cosmetic operational issue
 
⸻
 
10.44 Incident Communication
Internal incident communication should include:
	•	Severity
	•	Start time
	•	Current impact
	•	Affected services
	•	Affected clients
	•	Current action
	•	Next decision point
	•	Owner
Client communication should be:
	•	Accurate
	•	Scoped
	•	Timely
	•	Free from unsupported speculation
	•	Updated when material facts change
 
⸻
 
10.45 Maintenance Windows
Planned maintenance should be used when changes may materially affect availability.
Maintenance planning should include:
	•	Scope
	•	Expected impact
	•	Start and end window
	•	Responsible owner
	•	Rollback criteria
	•	Client communication where needed
	•	Workflow pause requirements
Most ordinary deployments should not require a full maintenance window.
 
⸻
 
10.46 Deployment Rollback
Rollback means returning application code to a prior compatible version.
Rollback is appropriate when:
	•	New code causes failure.
	•	Database remains backward-compatible.
	•	External actions are not corrupted.
	•	Previous version can safely process current data.
Rollback is not sufficient when:
	•	A destructive migration completed.
	•	External duplicate actions occurred.
	•	Data was incorrectly transformed.
	•	Credentials were exposed.
Those cases require recovery or reconciliation.
 
⸻
 
10.47 Reconciliation
Reconciliation compares internal platform state with external provider state.
It is required when an external action may have succeeded but internal recording failed.
Examples:
	•	GBP post exists externally but status is still publishing.
	•	Review response published but provider response timed out.
	•	Email sent but delivery record was not saved.
	•	GitHub commit succeeded but publication workflow failed afterward.
A reconciliation process should:
	1.	Query external state.
	2.	Match using stable identifiers or idempotency metadata.
	3.	Update internal state.
	4.	Avoid duplicate action.
	5.	Record the correction.
	6.	Escalate ambiguous cases.
 
⸻
 
10.48 Backup Operations
Backup operations must cover:
	•	PostgreSQL
	•	Object storage
	•	Infrastructure configuration
	•	Deployment configuration
	•	Critical prompt and workflow definitions
	•	Secret-recovery procedures
Application code remains protected through GitHub.
 
⸻
 
10.48.1 Database Backups
Database backup planning should define:
	•	Automated backup frequency
	•	Retention
	•	Point-in-time recovery availability
	•	Access permissions
	•	Restore procedure
	•	Restore test schedule
 
⸻
 
10.48.2 Object Storage Backups
Important private files should have:
	•	Versioning or backup where justified
	•	Retention policy
	•	Deletion policy
	•	Restore procedure
Not every generated temporary asset requires long-term backup.
 
⸻
 
10.48.3 Configuration Recovery
The platform must be able to reconstruct:
	•	Environment variables
	•	Server configuration
	•	Service definitions
	•	Domain configuration
	•	Webhook configuration
	•	Scheduler configuration
	•	Runtime controls
Secrets themselves should be backed up or recoverable through a secure process.
They must not be stored in ordinary infrastructure documentation.
 
⸻
 
10.49 Restore Testing
Restore testing should occur periodically.
A restore test should verify:
	•	Backup can be accessed.
	•	Database can be restored.
	•	Application can connect.
	•	Authentication works.
	•	Key records exist.
	•	Tenant isolation remains active.
	•	Workflows can resume or reconcile.
	•	Files are accessible.
	•	Required credentials can be restored or rotated.
Restore tests should produce a documented result.
 
⸻
 
10.50 Disaster Recovery
Disaster scenarios should include:
	•	Supabase project failure
	•	Hetzner server loss
	•	Vercel outage
	•	Accidental database deletion
	•	Credential compromise
	•	Object-storage loss
	•	GitHub repository compromise
	•	Provider outage
	•	Invalid migration
	•	Regional infrastructure issue
Recovery procedures should define:
	•	Responsible owner
	•	Replacement infrastructure
	•	Data restoration
	•	DNS changes
	•	Secret rotation
	•	Service validation
	•	Workflow reconciliation
	•	Client communication
 
⸻
 
10.51 Capacity Management
Capacity should be monitored before it becomes an outage.
Relevant indicators include:
	•	Database storage
	•	Database connections
	•	Query latency
	•	Worker concurrency
	•	Queue depth
	•	Oldest queued job
	•	Server CPU
	•	Server memory
	•	Disk capacity
	•	Network usage
	•	API rate limits
	•	Provider quotas
	•	AI usage
	•	Object storage
 
⸻
 
10.52 Scaling Strategy
Scaling should proceed in stages.
Stage 1 — Optimize
	•	Fix inefficient queries.
	•	Add indexes.
	•	Reduce unnecessary provider calls.
	•	Batch work.
	•	Adjust worker concurrency.
	•	Reduce excessive AI context.
Stage 2 — Increase Resources
	•	Larger Hetzner instance
	•	Higher Supabase plan
	•	Additional worker processes
	•	More provider quota
Stage 3 — Separate Workloads
	•	Dedicated AI workers
	•	Dedicated lead workers
	•	Dedicated integration workers
	•	Read replicas where justified
Stage 4 — Add Specialized Infrastructure
Only after measured need:
	•	Dedicated queue
	•	Redis
	•	Separate analytics storage
	•	Data warehouse
	•	Additional regions
	•	Container orchestration
Architecture changes should follow evidence.
 
⸻
 
10.53 Concurrency Controls
Concurrency must be controlled by:
	•	Worker type
	•	Provider
	•	Organization
	•	Location
	•	Workflow
	•	External resource
Examples:
	•	Avoid publishing two GBP posts to the same location simultaneously.
	•	Avoid running duplicate GSC syncs for the same property.
	•	Limit concurrent AI generation by organization.
	•	Prevent two workers from sending the same lead message.
Concurrency controls must work across multiple worker processes.
 
⸻
 
10.54 Provider Quota Management
Provider quotas should be tracked for:
	•	Google APIs
	•	AI providers
	•	Email
	•	SMS
	•	GitHub
	•	Vercel
	•	Stripe
	•	Other integrations
Quota handling should include:
	•	Usage measurement
	•	Warning threshold
	•	Rate-limit backoff
	•	Priority handling
	•	Queue delay
	•	Fallback where allowed
	•	Client-impact reporting
 
⸻
 
10.55 Cost Monitoring
Platform cost monitoring should include:
	•	Vercel
	•	Supabase
	•	Hetzner
	•	AI providers
	•	Email
	•	SMS
	•	Storage
	•	Monitoring services
	•	Third-party integrations
Costs should be attributable where practical to:
	•	Environment
	•	Organization
	•	Product
	•	Usage category
 
⸻
 
10.55.1 Cost Alerts
Potential alerts include:
	•	Daily AI cost spike
	•	Unexpected SMS increase
	•	Storage growth
	•	Database plan threshold
	•	Worker compute increase
	•	Provider overage risk
Cost alerts should distinguish expected client growth from abnormal behavior.
 
⸻
 
10.56 Operational Runbooks
Runbooks should exist for recurring operational tasks.
Initial runbooks should include:
	•	Deploy backend
	•	Deploy workers
	•	Roll back application
	•	Apply migration
	•	Reauthorize integration
	•	Retry failed workflow
	•	Reconcile external publication
	•	Pause lead messaging
	•	Rotate secret
	•	Restore database
	•	Restore server
	•	Respond to provider outage
	•	Offboard client
	•	Investigate cross-tenant alert
	•	Disable AI provider
	•	Recover failed scheduler
A runbook should include:
	•	Trigger
	•	Required access
	•	Steps
	•	Verification
	•	Escalation
	•	Recovery
	•	Audit requirements
 
⸻
 
10.57 Operational Ownership
Every production component should have an owner.
Examples:
Component: Scheduler
Owner: Platform Engineering
Backup Owner: Operations
Runbook: scheduler-recovery.md
Alerts: workflow dispatch delay
Ownership should be recorded for:
	•	API
	•	Database
	•	Authentication
	•	Workers
	•	Scheduler
	•	Integrations
	•	AI gateway
	•	Notifications
	•	Billing
	•	Reports
	•	Backups
 
⸻
 
10.58 Routine Maintenance
Routine maintenance should include:
	•	Dependency updates
	•	Operating-system patches
	•	Database review
	•	Index review
	•	Log-retention review
	•	Secret rotation
	•	Permission review
	•	Backup verification
	•	Alert review
	•	Provider deprecation review
	•	AI model and price review
	•	Feature-flag cleanup
	•	Dead workflow cleanup
Maintenance should be scheduled and tracked.
 
⸻
 
10.59 Access Reviews
Production access should be reviewed periodically.
Review:
	•	GitHub administrators
	•	Vercel access
	•	Supabase access
	•	Hetzner SSH keys
	•	Deployment credentials
	•	Service accounts
	•	Billing access
	•	Cross-client platform roles
	•	AI operator permissions
Unused or unnecessary access should be removed.
 
⸻
 
10.60 Data Freshness Operations
External data pipelines must define acceptable freshness.
Examples:
	•	GSC data
	•	GBP performance data
	•	Reviews
	•	Analytics
	•	Lead status
	•	Deployment status
Each integration should define:
	•	Expected provider delay
	•	Expected sync cadence
	•	Warning threshold
	•	Failure threshold
	•	Client-visible status
A provider that updates data slowly should not be treated as a platform failure until the provider-specific threshold is exceeded.
 
⸻
 
10.61 Operational Data Retention
Operational records require retention policies.
Examples:
Record
Suggested Initial Retention
Application logs
30–90 days
Security logs
12 months or policy-defined
Workflow executions
Long-term summary
Detailed workflow payloads
30–180 days
Provider debug payloads
Short-term
Deployment records
Long-term
Incident records
Long-term
Metrics
Aggregated long-term
Temporary files
Hours or days
Final retention must be based on security, cost, contractual, and operational requirements.
 
⸻
 
10.62 Operational Testing
The platform should test operational behavior, not only application logic.
Required test categories include:
	•	Service restart
	•	Worker shutdown and resume
	•	Scheduler duplicate prevention
	•	Queue lock expiration
	•	Provider timeout
	•	Provider rate limit
	•	Database temporary failure
	•	Migration failure
	•	Deployment rollback
	•	External-action reconciliation
	•	Backup restore
	•	Kill switch
	•	Alert generation
	•	Secret rotation
	•	Staging isolation
	•	Production-data protection
 
⸻
 
10.63 Chaos and Failure Simulation
Formal chaos engineering is not required initially.
Controlled failure simulation should still test:
	•	Worker crashes
	•	Provider outage
	•	Network timeout
	•	Database connection loss
	•	Invalid AI response
	•	Webhook duplication
	•	Server restart during workflow
	•	Deployment during queued work
Testing should be deliberate and performed outside production unless a safe production exercise is specifically approved.
 
⸻
 
10.64 Production Readiness Review
A service or product is not ready for production until the team can answer:
	•	Where is it deployed?
	•	Who owns it?
	•	How is it monitored?
	•	What are its dependencies?
	•	What happens when it fails?
	•	Can it be restarted safely?
	•	Can work be retried safely?
	•	Can external actions be reconciled?
	•	Are logs sufficient?
	•	Are alerts actionable?
	•	Is there a rollback or recovery path?
	•	Are backups relevant and tested?
	•	Is capacity sufficient?
	•	Are secrets protected?
	•	Is the runbook complete?
 
⸻
 
10.65 Initial Operations Implementation Order
Stage 1 — Environment Foundation
Implement:
	•	Local, staging, and production separation
	•	Versioned environment configuration
	•	Protected secrets
	•	Service identities
	•	GitHub branch controls
	•	Basic CI
Stage 2 — Deployment Foundation
Implement:
	•	Vercel deployment
	•	FastAPI deployment
	•	Worker deployment
	•	Scheduler deployment
	•	Version endpoint
	•	Health checks
	•	Automated restart
Stage 3 — Observability
Implement:
	•	Structured logs
	•	Request IDs
	•	Correlation IDs
	•	Workflow metrics
	•	Queue metrics
	•	Provider error metrics
	•	Operational dashboard
Stage 4 — Alerting
Implement:
	•	API unavailable
	•	Worker unavailable
	•	Scheduler delayed
	•	Queue backlog
	•	Workflow failure spike
	•	Integration authorization failure
	•	Backup failure
	•	Cost anomaly
Stage 5 — Safe Releases
Implement:
	•	Automated tests
	•	Migration checks
	•	Staging validation
	•	Production smoke tests
	•	Deployment records
	•	Rollback procedure
	•	Kill switches
Stage 6 — Recovery
Implement:
	•	Database restore procedure
	•	Server rebuild procedure
	•	Workflow reconciliation
	•	Provider-outage procedures
	•	Incident templates
	•	Restore testing
Stage 7 — Capacity and Optimization
Implement:
	•	Cost dashboards
	•	Quota monitoring
	•	Capacity thresholds
	•	Worker scaling controls
	•	Database query review
	•	Retention cleanup
 
⸻
 
10.66 Operational Guardrails
The following are prohibited unless formally approved:
	1.	Production changes made only through undocumented SSH commands
	2.	Direct pushes to the protected production branch
	3.	Deployments without a version identifier
	4.	Production and staging sharing the same database
	5.	Preview deployments receiving production secrets
	6.	Long-running workflows hosted in request-bound serverless functions
	7.	Untracked cron jobs
	8.	Workers without durable execution state
	9.	Infinite automatic retries
	10.	Deployments that abandon running workflows
	11.	Destructive migrations without a staged compatibility plan
	12.	Large untracked database backfills
	13.	Alerts without an assigned owner or response action
	14.	Logging secrets or sensitive raw payloads
	15.	Monitoring only process uptime while ignoring workflow health
	16.	Retrying external actions without idempotency or reconciliation
	17.	Client-facing errors exposing infrastructure details
	18.	Production shell access through shared accounts
	19.	Backups that are never restore-tested
	20.	Feature flags without an owner or removal plan
	21.	Permanent emergency kill switches left active without review
	22.	Scaling architecture based on speculation rather than measurements
	23.	Queue or provider limits ignored until failure
	24.	Production data copied to development without sanitization
	25.	Manual recovery that leaves workflow state inconsistent
	26.	AI provider cost increases remaining unmonitored
	27.	A deployment declared successful before health and smoke checks pass
	28.	Runtime configuration changes without audit history
	29.	Client offboarding that leaves scheduled workflows active
	30.	An AI operator receiving direct deployment or infrastructure access without dedicated controls
 
⸻
 
10.67 Section Decisions
This section establishes the following decisions:
	1.	The initial infrastructure uses Vercel, Supabase, Hetzner, GitHub Actions, Docker Compose where useful, and systemd.
	2.	The platform maintains separate local, staging, and production environments.
	3.	Vercel hosts the Astro application and lightweight server routes.
	4.	Supabase provides PostgreSQL, authentication, Row Level Security, and storage.
	5.	Hetzner hosts FastAPI, durable workers, the scheduler, integration processing, and AI execution.
	6.	The backend initially uses a small number of deployable services rather than many microservices.
	7.	Infrastructure and deployment configuration are version-controlled and reproducible.
	8.	Production code changes use protected branches, pull requests, tests, and deployment records.
	9.	Long-running work uses durable workers and must survive deployments and restarts.
	10.	Workflow definitions, payloads, and executions remain compatible across deployments.
	11.	Database migrations use staged, backward-compatible procedures wherever possible.
	12.	Large backfills are observable, batched, idempotent operations.
	13.	All services expose version and health information.
	14.	Platform operations are monitored through infrastructure, application, integration, and business-workflow metrics.
	15.	Correlation IDs connect user requests, workflows, AI calls, provider actions, and audit events.
	16.	The agency console includes an operational dashboard for platform and client workflow health.
	17.	Alerts are severity-based, actionable, deduplicated, and assigned to an owner.
	18.	Initial service-level objectives are engineering targets and must be refined using real measurements.
	19.	External-action failures require reconciliation rather than blind retry.
	20.	Emergency kill switches exist for high-impact products, providers, workflows, and organizations.
	21.	Backups cover the database, files, configuration, and recovery procedures.
	22.	Backups must be restored in testing before they are considered reliable.
	23.	Capacity and cost are monitored by environment, product, and organization where practical.
	24.	Scaling begins with optimization and vertical growth before introducing specialized infrastructure.
	25.	Every production component requires an owner, runbook, monitoring, and recovery path.
	26.	Operational testing includes restarts, provider failures, queue recovery, migration failure, rollback, reconciliation, and restore.
	27.	No product is production-ready until its deployment, monitoring, alerting, recovery, and operational ownership are defined.

---

Section 11 — User Experience, Agency Console, Client Portal, and Onboarding
11.1 Purpose of This Section
This section defines how users interact with the LILOs platform.
It establishes:
	•	User experience principles
	•	Agency and client interface boundaries
	•	Information architecture
	•	Navigation
	•	Organization and location switching
	•	Dashboard standards
	•	Product workspace structure
	•	Onboarding
	•	Integration connection flows
	•	Configuration interfaces
	•	Approval interfaces
	•	Workflow visibility
	•	Notifications
	•	Reporting interfaces
	•	Error and degraded-state handling
	•	Responsive behavior
	•	Accessibility
	•	Content and terminology standards
	•	Design system requirements
	•	Support and operational interfaces
	•	Interface acceptance requirements
The goal is to make a complex multi-product platform understandable without exposing unnecessary technical complexity.
The interface must help users answer:
	•	Where am I?
	•	Which organization and location am I viewing?
	•	What requires attention?
	•	What is working?
	•	What is blocked?
	•	What should happen next?
	•	What actions am I authorized to perform?
	•	What effect will an action have?
The platform should feel like one coherent system even though it contains multiple independent products.
 
⸻
 
11.2 User Experience Philosophy
The LILOs platform should reduce operational complexity rather than display all internal complexity to the user.
The interface should prioritize:
	•	Clarity
	•	Context
	•	Actionability
	•	Confidence
	•	Consistency
	•	Progressive disclosure
The platform should not require users to understand:
	•	Worker architecture
	•	Model routing
	•	Database structure
	•	Provider payloads
	•	Queue internals
	•	Infrastructure topology
Technical details should be available to authorized agency operators when required for diagnosis, but they should not dominate ordinary product use.
 
⸻
 
11.3 User Experience Principles
Principle 1 — Scope Is Always Visible
The interface must make the current scope clear.
At minimum, the user should be able to identify:
	•	Current organization
	•	Current location
	•	Current product
	•	Current environment for internal users where relevant
An action must never be ambiguous about which client or location it affects.
 
⸻
 
Principle 2 — Attention Before Exploration
The interface should first show what needs action.
Examples:
	•	Approval required
	•	Integration disconnected
	•	Workflow failed
	•	Report ready
	•	Data delayed
	•	Client input required
	•	Subscription issue
	•	Lead awaiting follow-up
The dashboard should not prioritize decorative metrics over operational needs.
 
⸻
 
Principle 3 — Products Feel Independent but Connected
Each product should have its own workspace and clear purpose.
Shared elements should remain consistent:
	•	Navigation
	•	Filters
	•	Approvals
	•	Status indicators
	•	Notifications
	•	Exports
	•	Audit history
	•	Help patterns
Users should not feel that every product is a separate application.
 
⸻
 
Principle 4 — Reveal Complexity Gradually
The initial interface should show the information needed for the current decision.
More detailed information should be available through:
	•	Expandable sections
	•	Detail panels
	•	Tabs
	•	Advanced settings
	•	Operational views
	•	Audit history
Do not place every setting and metric on the primary screen.
 
⸻
 
Principle 5 — Actions Must Explain Their Consequences
Before a high-impact action, the user should know:
	•	What will happen
	•	Which resource will change
	•	Whether the action is external
	•	Whether it can be reversed
	•	Whether approval is required
	•	Whether the action affects one or multiple locations
 
⸻
 
Principle 6 — Status Is Explicit
Do not rely only on color.
Status should include text such as:
Active
Awaiting Approval
Connection Required
Publishing
Failed
Paused
Data Delayed
Icons and color may supplement status but must not replace the label.
 
⸻
 
Principle 7 — The Interface Must Support Recovery
When something fails, the interface should provide the next valid action.
Examples:
	•	Reconnect Google account
	•	Retry workflow
	•	Review validation error
	•	Request revision
	•	Contact an administrator
	•	Complete missing configuration
A generic error message without a recovery path is insufficient.
 
⸻
 
Principle 8 — Agency and Client Needs Are Different
Agency users need:
	•	Cross-client visibility
	•	Operational controls
	•	Diagnostics
	•	Work queues
	•	Bulk actions
	•	Internal annotations
	•	Cost and usage visibility
Client users need:
	•	Simplified status
	•	Clear approvals
	•	Performance reporting
	•	Configuration relevant to their business
	•	Limited operational complexity
The client portal should not be a restricted copy of the agency console.
It should be designed for the client’s responsibilities.
 
⸻
 
11.4 User Types
The interface should support several user categories.
Platform Owner
Typical responsibilities:
	•	Platform administration
	•	Security
	•	Billing oversight
	•	Product configuration
	•	Provider configuration
	•	Incident control
	•	Cross-client access
 
⸻
 
Agency Administrator
Typical responsibilities:
	•	Manage organizations
	•	Manage users
	•	Enable products
	•	Configure integrations
	•	Review operations
	•	Approve sensitive actions
	•	Access reports
 
⸻
 
Agency Operator
Typical responsibilities:
	•	Manage product workflows
	•	Prepare drafts
	•	Review opportunities
	•	Resolve failures
	•	Submit work for approval
	•	Monitor client performance
 
⸻
 
Account Manager
Typical responsibilities:
	•	Review account health
	•	Communicate with clients
	•	Manage approvals
	•	Review reports
	•	Coordinate configuration
	•	Escalate operational issues
 
⸻
 
Client Administrator
Typical responsibilities:
	•	Manage client users
	•	Connect integrations
	•	Review configuration
	•	Approve work
	•	Access reports
	•	Manage notification preferences
 
⸻
 
Client Approver
Typical responsibilities:
	•	Review drafts
	•	Approve
	•	Reject
	•	Request revision
	•	Add comments
 
⸻
 
Client Viewer
Typical responsibilities:
	•	View reporting
	•	View product status
	•	View published work
	•	Download approved reports
 
⸻
 
Service Identity or AI Operator
Does not use the ordinary human interface unless a diagnostic representation is needed.
Actions should still appear in user-facing history where appropriate.
 
⸻
 
11.5 Experience Surfaces
The platform should contain three primary human-facing surfaces.
11.5.1 Agency Console
Used by LILOs internal users.
Provides:
	•	Cross-client portfolio management
	•	Work queues
	•	Operational status
	•	Product workspaces
	•	Integration management
	•	Approval management
	•	Reporting
	•	Billing visibility
	•	User and access management
	•	Internal configuration
	•	Diagnostics
	•	Audit history
 
⸻
 
11.5.2 Client Portal
Used by client users.
Provides:
	•	Account overview
	•	Location overview
	•	Product status
	•	Pending approvals
	•	Reports
	•	Integration actions
	•	Selected configuration
	•	Published work
	•	Notifications
	•	User management for authorized administrators
 
⸻
 
11.5.3 Platform Administration
Restricted to highly privileged internal users.
Provides:
	•	Product definitions
	•	Feature definitions
	•	System roles and permissions
	•	AI provider and model configuration
	•	Prompt management
	•	Workflow definitions
	•	Provider health
	•	Runtime controls
	•	Security events
	•	Platform-wide billing and usage
	•	Incident controls
Platform administration should not be accessible through ordinary agency roles.
 
⸻
 
11.6 Information Architecture
Recommended top-level agency navigation:
Home
Work Queue
Organizations
Products
Approvals
Reports
Operations
Billing
Administration
Recommended organization-level navigation:
Overview
Locations
Products
Approvals
Reports
Integrations
Users
Settings
Activity
Recommended location-level navigation:
Overview
SEO
GBP
Reviews
Content
Leads
Insights
Integrations
Settings
Activity
Only enabled products should appear as active navigation items.
Unavailable products may appear in a controlled product-discovery or activation area, but should not clutter routine navigation.
 
⸻
 
11.7 Navigation Model
The platform should use a stable navigation structure.
Recommended layout:
Global Navigation
    ↓
Organization Context
    ↓
Location Context
    ↓
Product Workspace
    ↓
Resource Detail
The interface should preserve context when the user moves between related views.
Example:
A user reviewing a GBP post for Location A should return to the GBP workspace for Location A rather than lose location scope.
 
⸻
 
11.8 Organization Switcher
Agency users with access to multiple organizations need a searchable organization switcher.
The switcher should show:
	•	Organization name
	•	Status
	•	Primary industry
	•	Number of locations
	•	Account health indicator where authorized
It should support:
	•	Search
	•	Recently viewed organizations
	•	Pinned organizations
	•	Clear current selection
Switching organizations must clear or revalidate any location-specific state.
 
⸻
 
11.9 Location Switcher
Organizations with multiple locations need a location switcher.
The switcher should show:
	•	Location name
	•	City or market
	•	Operational status
	•	Enabled product indicators where practical
The interface must distinguish:
	•	All locations
	•	A single location
	•	A selected group of locations
Actions affecting multiple locations must state that explicitly.
 
⸻
 
11.10 Global Context Header
The primary authenticated interface should display a context header containing:
	•	Organization
	•	Location or all-locations scope
	•	Product
	•	Current status
	•	Relevant primary action
Example:
Coco Maya
Little Italy
Google Business Profile
Active

[Create Post]
The interface should not depend on breadcrumb text alone to communicate scope.
 
⸻
 
11.11 Agency Home Dashboard
The agency home dashboard should prioritize portfolio-level operations.
Recommended sections:
Requires Attention
	•	Failed workflows
	•	Disconnected integrations
	•	Pending approvals
	•	Data freshness issues
	•	Billing problems
	•	Product setup incomplete
Today’s Work
	•	Scheduled publications
	•	Reports due
	•	Reviews awaiting response
	•	Content awaiting review
	•	Lead follow-up issues
Portfolio Health
	•	Active organizations
	•	Active locations
	•	Product health
	•	Provider degradation
	•	Workflow completion
Recent Activity
	•	Publications
	•	Approvals
	•	Integrations connected
	•	Product activations
	•	Incidents
	•	Deployments where authorized
The dashboard should allow users to move directly from the issue to the relevant resolution screen.
 
⸻
 
11.12 Client Home Dashboard
The client dashboard should be simpler.
Recommended sections:
Account Status
	•	Active products
	•	Connected integrations
	•	Current reporting period
	•	Important alerts
Requires Your Attention
	•	Pending approvals
	•	Connection requests
	•	Missing business information
	•	Payment issue where authorized
Recent Results
	•	Performance summary
	•	Completed work
	•	Published content
	•	Review activity
	•	Lead activity where enabled
Upcoming
	•	Scheduled posts
	•	Content in progress
	•	Reports
	•	Planned campaigns
Avoid exposing internal workflow terminology unless it helps the client act.
 
⸻
 
11.13 Organization Overview
The organization overview should provide:
	•	Organization identity
	•	Industry
	•	Locations
	•	Product subscriptions
	•	Account owner
	•	Client administrators
	•	Integration health
	•	Approval backlog
	•	Reporting status
	•	Recent activity
	•	Account-level alerts
It should also indicate whether configuration is:
Complete
Incomplete
Requires Review
 
⸻
 
11.14 Location Overview
The location overview should provide:
	•	Location name
	•	Address
	•	Timezone
	•	Website
	•	Phone
	•	Business status
	•	Product status
	•	Integration status
	•	Current alerts
	•	Recent work
	•	Key performance summary
	•	Pending approvals
The location overview should be the main operational entry point for single-location product work.
 
⸻
 
11.15 Product Workspace Standard
Every product workspace should follow a common structure.
Recommended tabs:
Overview
Work
Performance
Configuration
History
Not every product must use those exact labels, but the concepts should remain consistent.
 
⸻
 
11.15.1 Product Overview
Shows:
	•	Product status
	•	Connection status
	•	Current performance
	•	Current workload
	•	Pending approvals
	•	Recent outputs
	•	Primary next action
 
⸻
 
11.15.2 Work
Shows product-specific operational records.
Examples:
	•	SEO opportunities
	•	GBP posts
	•	Reviews
	•	Content items
	•	Leads
	•	Reports
 
⸻
 
11.15.3 Performance
Shows:
	•	Product metrics
	•	Trends
	•	Comparisons
	•	Annotations
	•	Outcome measurement
 
⸻
 
11.15.4 Configuration
Shows product-specific settings.
Examples:
	•	Cadence
	•	Approval policy
	•	Brand rules
	•	Notification settings
	•	Routing
	•	Publication destinations
 
⸻
 
11.15.5 History
Shows:
	•	Completed actions
	•	Workflow runs
	•	Approvals
	•	Changes
	•	Errors
	•	Publications
	•	Audit-relevant history
 
⸻
 
11.16 Product Status Presentation
Each product should have one primary lifecycle status:
Not Enabled
Setup Required
Connection Required
Ready
Active
Paused
Degraded
Suspended
Archived
Supplementary health states may indicate:
Healthy
Attention Required
Unavailable
Data Delayed
The interface must distinguish lifecycle from temporary health.
Example:
Product: Active
Health: Connection Required
 
⸻
 
11.17 Setup Progress
Products requiring onboarding should display setup progress.
Example:
3 of 5 setup steps completed
Potential steps:
	1.	Confirm business profile
	2.	Connect provider
	3.	Review configuration
	4.	Select approval policy
	5.	Activate product
The progress indicator should identify the next required action.
 
⸻
 
11.18 Onboarding Architecture
Onboarding should be modular.
A user may onboard:
	•	A new organization
	•	A new location
	•	A new product
	•	A new integration
	•	A new user
	•	An existing client adding another product
The platform must not require full organization setup to activate an unrelated product unless there is a genuine dependency.
 
⸻
 
11.19 Organization Onboarding
Recommended organization onboarding sequence:
Create Organization
    ↓
Select Industry
    ↓
Enter Core Business Information
    ↓
Add Locations
    ↓
Invite Client Users
    ↓
Select Products
    ↓
Connect Integrations
    ↓
Review Configuration
    ↓
Activate
Each step should be resumable.
Users should not lose progress if onboarding is interrupted.
 
⸻
 
11.20 Location Onboarding
Location onboarding should collect:
	•	Location name
	•	Address
	•	Timezone
	•	Phone
	•	Website
	•	Primary contact
	•	Business status
	•	Service area where relevant
	•	Connected external resources
	•	Product-specific facts
The platform should reuse verified provider data where appropriate, but users must be able to review and correct imported data.
 
⸻
 
11.21 Product Onboarding
Each product must define:
	•	Required information
	•	Required integration
	•	Optional integrations
	•	Default configuration
	•	Approval policy
	•	Initial workflow
	•	Success criteria
Product onboarding should end with a readiness review.
Example:
SEO Product Readiness

✓ Search Console connected
✓ Website verified
✓ Reporting timezone set
✓ Opportunity rules configured
✓ Notification recipients selected

[Activate SEO]
 
⸻
 
11.22 Integration Connection Experience
Integration connection should follow a standard pattern:
Choose Provider
    ↓
Explain Requested Access
    ↓
Authenticate
    ↓
Select External Account
    ↓
Select Resources
    ↓
Verify Capabilities
    ↓
Confirm Organization and Location Mapping
    ↓
Complete Initial Sync
    ↓
Show Connection Status
The interface should explain why each permission or scope is required.
 
⸻
 
11.23 Integration Status
Connection states should be presented consistently:
Not Connected
Connecting
Verifying
Connected
Syncing
Attention Required
Authorization Expired
Permission Missing
Provider Unavailable
Disconnected
The user should see:
	•	Provider
	•	Connected account
	•	Connected resource
	•	Last successful sync
	•	Current issue
	•	Required action
Do not expose raw OAuth or provider error messages to ordinary client users.
 
⸻
 
11.24 Reconnection Flow
When a connection fails, the interface should state:
	•	What stopped working
	•	What historical data remains available
	•	Which workflows are paused
	•	Who can reconnect
	•	The reconnection action
Example:
Google authorization expired.

New GBP posts and review responses are paused.
Existing reports and historical records remain available.

[Reconnect Google]
 
⸻
 
11.25 Configuration Experience
Configuration should be divided into:
	•	Essential settings
	•	Product settings
	•	Advanced settings
	•	Internal settings
Client users should only see settings they are permitted and expected to manage.
 
⸻
 
11.25.1 Configuration Inheritance
The interface should show when a setting is inherited.
Example:
Review approval policy:
Inherited from organization — Manual approval required
Authorized users may override inherited values when permitted.
The interface should identify:
	•	Current effective value
	•	Source level
	•	Whether an override exists
	•	Impact of removing the override
 
⸻
 
11.25.2 Configuration Changes
Before saving high-impact settings, the interface should explain effects.
Example:
Changing this setting will require approval for all future GBP posts at this location.
Existing approved posts will not be changed.
Configuration changes should create history records.
 
⸻
 
11.26 Work Queue
The agency work queue should consolidate actionable work across products.
Potential items:
	•	Approvals
	•	Failed workflows
	•	Drafts requiring review
	•	Integration issues
	•	SEO opportunities requiring assignment
	•	Reviews requiring escalation
	•	Content revisions
	•	Leads requiring human follow-up
	•	Reports requiring annotation
Recommended filters:
	•	Organization
	•	Location
	•	Product
	•	Work type
	•	Priority
	•	Status
	•	Assignee
	•	Due date
	•	Age
 
⸻
 
11.27 Work Item Standard
Each work item should display:
	•	Title
	•	Organization
	•	Location
	•	Product
	•	Work type
	•	Status
	•	Priority
	•	Assignee
	•	Created time
	•	Due time where applicable
	•	Required next action
A work item should link directly to the relevant resource.
 
⸻
 
11.28 Assignment
Work items may be assigned to:
	•	Internal user
	•	Client approver
	•	Team
	•	Unassigned queue
Assignment changes must be visible and auditable.
The system should avoid silently reassigning work when roles change.
 
⸻
 
11.29 Priority
Recommended priority levels:
Low
Normal
High
Urgent
Priority should be based on defined business rules rather than arbitrary visual emphasis.
Examples:
	•	One-star review with legal language: urgent
	•	Expired Google connection blocking publication: high
	•	Routine content approval: normal
	•	Optional optimization suggestion: low
 
⸻
 
11.30 Approval Inbox
The approval inbox should provide one place for authorized users to review pending approvals.
It should support filtering by:
	•	Organization
	•	Location
	•	Product
	•	Approval type
	•	Requester
	•	Due date
	•	Risk
	•	Status
Each approval should show:
	•	What is being approved
	•	Current revision
	•	Source or supporting context
	•	Expected external effect
	•	Requested by
	•	Approval deadline
	•	Relevant warnings
 
⸻
 
11.31 Approval Detail
An approval detail view should include:
	•	Draft or proposed action
	•	Organization and location
	•	Product
	•	Revision history
	•	Supporting context
	•	Validation results
	•	Risk flags
	•	AI involvement
	•	Requester
	•	Comments
	•	Approval actions
Available actions:
Approve
Reject
Request Revision
Edit and Resubmit
Cancel Request
Actions depend on permission and policy.
 
⸻
 
11.32 Approval Confirmation
Approval of a high-impact action should require explicit confirmation.
Example:
Approve and publish this response to Google?

This action will be visible publicly and cannot be edited through LILOs after publication unless Google supports an update.

[Cancel] [Approve and Publish]
Confirmation text should be specific to the action.
Avoid generic confirmation messages such as:
Are you sure?
 
⸻
 
11.33 Revision Handling
The interface must identify the revision being reviewed.
If content changes after the approval screen is opened:
	•	The approval action should fail safely.
	•	The user should be notified that a newer revision exists.
	•	The new revision should be loaded.
	•	Prior approval should not apply automatically.
 
⸻
 
11.34 Draft Editing
Draft editors should support:
	•	Autosave
	•	Revision history
	•	Character or word limits
	•	Validation feedback
	•	Preview
	•	Comments
	•	Source context
	•	Approval readiness
The editor should distinguish between:
	•	Generated draft
	•	Human-edited draft
	•	Approved revision
	•	Published version
 
⸻
 
11.35 AI Presentation
AI involvement should be visible where it affects user trust or review.
The interface may show:
AI-assisted draft
Model details available to authorized agency users
Client users generally do not need provider and token details.
Authorized agency users may inspect:
	•	Model
	•	Prompt version
	•	Generation time
	•	Validation result
	•	Fallback use
	•	Cost
	•	Human edits
The interface must not imply that AI output is verified merely because it was generated by the platform.
 
⸻
 
11.36 Recommendations
Recommendations should distinguish between:
	•	Observation
	•	Recommendation
	•	Required action
	•	Automated action
	•	Completed action
Example:
Observation:
The primary category does not match the strongest ranking opportunity.

Recommendation:
Review whether “Restaurant” should remain a secondary category.

No profile change has been made.
The interface must not make a recommendation look like an executed change.
 
⸻
 
11.37 Product-Specific Workspace: SEO
The SEO workspace should include:
	•	Data freshness
	•	Search properties
	•	Query trends
	•	Page trends
	•	Opportunities
	•	Opportunity scoring
	•	Assigned work
	•	Completed recommendations
	•	Outcome tracking
Opportunity records should show:
	•	Issue or opportunity
	•	Supporting metrics
	•	Affected page or query
	•	Priority
	•	Recommended action
	•	Status
	•	Owner
	•	Measurement period
 
⸻
 
11.38 Product-Specific Workspace: GBP
The GBP workspace should include:
	•	Profile connection
	•	Profile completeness
	•	Categories
	•	Business information
	•	Posts
	•	Reviews summary
	•	Performance metrics
	•	Recommendations
	•	Sync status
Profile recommendations must show:
	•	Current value
	•	Proposed change
	•	Reason
	•	Supporting evidence
	•	Risk
	•	Approval requirement
 
⸻
 
11.39 Product-Specific Workspace: Reviews
The reviews workspace should include:
	•	Incoming reviews
	•	Response status
	•	Rating
	•	Sentiment
	•	Risk
	•	Response draft
	•	Publication status
	•	Response time
	•	Filters
High-risk reviews should receive stronger visual and textual warnings.
Risk flags may include:
	•	Legal issue
	•	Safety issue
	•	Discrimination allegation
	•	Employee accusation
	•	Refund demand
	•	Threat
	•	Personal-data concern
 
⸻
 
11.40 Product-Specific Workspace: Content
The content workspace should include:
	•	Content calendar
	•	Ideas
	•	Briefs
	•	Drafts
	•	Revisions
	•	Approvals
	•	Publications
	•	Performance
Each content item should show its lifecycle:
Idea
Brief
Draft
Review
Approved
Scheduled
Published
Measuring
Archived
 
⸻
 
11.41 Product-Specific Workspace: Leads
The leads workspace should include:
	•	New leads
	•	Contacted leads
	•	Assigned leads
	•	Conversation status
	•	Urgency
	•	Source
	•	Consent
	•	Response time
	•	Conversion status
Personal data should be displayed only to authorized users.
The interface must clearly show when automated communication is:
	•	Enabled
	•	Disabled
	•	Paused
	•	Blocked by consent
	•	Awaiting human follow-up
 
⸻
 
11.42 Product-Specific Workspace: Insights
The Insights workspace should include:
	•	Executive summary
	•	Product metrics
	•	Location comparison
	•	Time-period comparison
	•	Annotations
	•	Report history
	•	Export
	•	Data freshness
Reports should distinguish:
	•	Measured result
	•	Platform interpretation
	•	Recommendation
	•	Missing data
 
⸻
 
11.43 Reporting Experience
Reporting should support:
	•	Organization view
	•	Location view
	•	Product view
	•	Date range
	•	Comparison period
	•	Export
	•	Scheduled delivery
	•	Commentary
	•	Data freshness
Users should not need to navigate each product separately to understand overall performance.
 
⸻
 
11.44 Metric Presentation
Every metric should define:
	•	Label
	•	Value
	•	Period
	•	Comparison period
	•	Data source
	•	Freshness
	•	Direction
	•	Interpretation where appropriate
Example:
Google Business Profile calls
184
Last 30 days
+12% versus previous 30 days
Updated July 27, 2026
Do not show percentage change without the comparison period.
 
⸻
 
11.45 Data Freshness
Data freshness should be visible for provider-derived data.
Recommended labels:
Updated 3 hours ago
Updated yesterday
Provider delay expected
Data delayed
Connection required
The interface should distinguish provider reporting delay from a failed platform sync.
 
⸻
 
11.46 Empty States
Every major view should define an intentional empty state.
Examples:
No Data Yet
Google Search Console is connected, but data has not completed its first sync.
Product Not Configured
Review response generation requires brand and approval settings.
No Work Required
No reviews currently require a response.
No Access
You do not have permission to view lead contact details.
Empty states should explain the situation and provide a valid next action where one exists.
 
⸻
 
11.47 Loading States
Loading indicators should reflect expected duration.
For short requests:
	•	Inline spinner
	•	Skeleton content
For long-running operations:
	•	Workflow status
	•	Progress steps
	•	Background processing notice
	•	Notification on completion
Do not display a permanent spinner for asynchronous work.
 
⸻
 
11.48 Success States
Success messages should identify what completed.
Example:
GBP post approved and queued for publication.
Avoid vague messages such as:
Success.
Where relevant, provide:
	•	Resource link
	•	Publication status
	•	Expected next step
	•	Undo option when supported
 
⸻
 
11.49 Error States
Error messages should contain:
	•	What failed
	•	What was not completed
	•	Whether anything succeeded
	•	Whether retry is safe
	•	Next action
	•	Support reference or request ID when relevant
Example:
The review response was saved, but Google publication failed because the connection has expired.

The draft remains available.

[Reconnect Google] [View Draft]
Reference: 8F31C2
 
⸻
 
11.50 Degraded States
The interface should support partial availability.
Example:
Reporting is available.
New GBP publications are paused because Google authorization expired.
A single integration failure should not make the entire product appear unavailable if other functions remain usable.
 
⸻
 
11.51 Notifications
The notification center should group notifications by:
	•	Action required
	•	Completed
	•	Warning
	•	Information
Each notification should include:
	•	Organization
	•	Location
	•	Product
	•	Time
	•	Message
	•	Action link
	•	Read state
 
⸻
 
11.52 Notification Preferences
Users should control:
	•	In-app notifications
	•	Email
	•	SMS where enabled
	•	Product categories
	•	Severity
	•	Digest frequency
Critical security and account notifications may not be fully suppressible.
 
⸻
 
11.53 Search
Global search may support:
	•	Organizations
	•	Locations
	•	Content
	•	Leads
	•	Reviews
	•	Workflows
	•	Reports
Search results must respect:
	•	Tenant scope
	•	Location access
	•	Product access
	•	Personal-data permissions
Search should not reveal the existence of unauthorized records.
 
⸻
 
11.54 Filters
Filters should use consistent placement and behavior.
Recommended filter patterns:
	•	Persistent within session where useful
	•	Clear active-filter indicators
	•	Reset action
	•	Shareable URL state for operational views
	•	Server-side validation
	•	Accessible labels
 
⸻
 
11.55 Tables
Data tables should support:
	•	Sorting
	•	Filtering
	•	Pagination
	•	Row selection where relevant
	•	Clear empty state
	•	Column visibility for advanced users
	•	Responsive fallback
	•	Export where authorized
Tables should not become the default for every screen.
Use cards, timelines, or summaries when they better support the decision.
 
⸻
 
11.56 Bulk Actions
Bulk actions should:
	•	Show selected count
	•	Describe the scope
	•	Validate each item
	•	Show partial failures
	•	Require confirmation for external effects
	•	Preserve per-item results
Example:
Approve 12 GBP posts across 6 locations?
The confirmation must identify the multi-location scope.
 
⸻
 
11.57 Activity History
Resource history should show:
	•	Time
	•	Actor
	•	Action
	•	Previous state
	•	New state
	•	Comments
	•	Related workflow
	•	External result
Client-facing history may omit internal-only diagnostics while preserving meaningful action history.
 
⸻
 
11.58 Audit Visibility
Audit logs and user activity are related but not identical.
User-facing activity should be readable and business-oriented.
Example:
Maria approved revision 4.
Internal audit may include:
actor_user_id
permission
request_id
resource_hash
ip_address
Sensitive audit detail should require elevated access.
 
⸻
 
11.59 Internal Notes
Agency users may need internal notes.
Internal notes must:
	•	Be clearly marked as internal
	•	Never appear in the client portal
	•	Be access-controlled
	•	Be auditable
	•	Avoid unnecessary restricted personal data
The interface must prevent accidental posting of an internal note as a client-visible comment.
 
⸻
 
11.60 Comments and Collaboration
Comments may be attached to:
	•	Approvals
	•	Content
	•	Recommendations
	•	Reports
	•	Work items
Comments should support:
	•	Author
	•	Timestamp
	•	Visibility
	•	Mentions
	•	Resolution status
	•	Editing history where necessary
Visibility should be explicit:
Internal
Client Visible
 
⸻
 
11.61 Responsive Design
The platform should be usable on:
	•	Desktop
	•	Tablet
	•	Mobile
Desktop remains the primary environment for complex agency workflows.
Mobile should fully support high-value actions such as:
	•	View alerts
	•	Approve or reject
	•	Review reports
	•	Reconnect where provider flow permits
	•	View lead status
	•	Receive notifications
Dense configuration and complex reporting may use simplified mobile layouts rather than reproducing desktop tables exactly.
 
⸻
 
11.62 Accessibility
The platform should target WCAG 2.2 AA conformance for core user flows.
Requirements include:
	•	Keyboard navigation
	•	Visible focus
	•	Semantic markup
	•	Proper labels
	•	Adequate contrast
	•	Screen-reader status announcements
	•	Error association
	•	Form instructions
	•	Non-color status indicators
	•	Accessible dialogs
	•	Accessible tables
	•	Reduced-motion support where appropriate
Accessibility applies to agency tools as well as the client portal.
 
⸻
 
11.63 Keyboard Interaction
Primary interactions should support keyboard use.
Examples:
	•	Navigation
	•	Search
	•	Filters
	•	Dialog confirmation
	•	Approval actions
	•	Form submission
	•	Tab switching
Keyboard shortcuts may be introduced for advanced agency users but must not conflict with accessibility.
 
⸻
 
11.64 Form Standards
Forms should:
	•	Use clear labels
	•	Show required fields
	•	Validate inline
	•	Preserve entered data after recoverable failure
	•	Use appropriate input types
	•	Explain constraints before submission
	•	Disable submission only when necessary
	•	Prevent duplicate submission
	•	Show save state
Forms should not use placeholder text as the only label.
 
⸻
 
11.65 Autosave
Autosave is appropriate for:
	•	Draft content
	•	Comments
	•	Long configuration forms
	•	Report annotations
The interface should display:
Saving…
Saved
Save failed
Autosave must not apply high-impact configuration or publish content without explicit user action.
 
⸻
 
11.66 Unsaved Changes
When autosave is not used, the interface should warn before leaving a page with unsaved changes.
The warning should not appear when no meaningful change exists.
 
⸻
 
11.67 Destructive Actions
Destructive actions include:
	•	Archive organization
	•	Remove location
	•	Disconnect integration
	•	Delete draft
	•	Disable product
	•	Remove user
	•	Cancel publication
	•	Delete export
Destructive actions should:
	•	Be visually distinct
	•	Explain impact
	•	Require confirmation
	•	Require typed confirmation only for exceptional high-risk actions
	•	State whether recovery is possible
	•	Create an audit event
 
⸻
 
11.68 Reversible Actions
Where safe, prefer reversible state changes.
Examples:
	•	Archive instead of delete
	•	Pause instead of disable
	•	Revoke access instead of erase membership history
	•	Unpublish where provider supports it
	•	Restore configuration version
The interface should explain the distinction between pause, disable, archive, and delete.
 
⸻
 
11.69 Design System
The platform should use a shared design system.
Core elements should include:
	•	Typography
	•	Spacing
	•	Layout grid
	•	Buttons
	•	Inputs
	•	Selects
	•	Tables
	•	Cards
	•	Badges
	•	Alerts
	•	Dialogs
	•	Drawers
	•	Tabs
	•	Tooltips
	•	Empty states
	•	Loading states
	•	Charts
	•	Pagination
	•	Breadcrumbs
	•	Navigation
	•	Command or search interface
Product teams should not recreate foundational components independently.
 
⸻
 
11.70 Visual Hierarchy
Visual hierarchy should prioritize:
	1.	Scope
	2.	Status
	3.	Required action
	4.	Primary metric or content
	5.	Supporting detail
	6.	Technical detail
The interface should avoid excessive decorative cards, gradients, and competing status colors.
 
⸻
 
11.71 Color Use
Color should communicate meaning consistently.
Suggested semantic uses:
	•	Success
	•	Warning
	•	Error
	•	Information
	•	Neutral
	•	Inactive
Product identities should not override semantic status colors.
All status meaning must also be available through text or icon labels.
 
⸻
 
11.72 Typography
Typography should prioritize readability.
Recommended rules:
	•	Clear heading hierarchy
	•	Readable body size
	•	Limited font families
	•	Consistent numerical display
	•	Monospace only for identifiers, code, or technical values
	•	Avoid all-uppercase body labels
 
⸻
 
11.73 Icons
Icons should supplement text.
Icon-only controls require:
	•	Accessible name
	•	Tooltip where needed
	•	Familiar meaning
	•	Adequate target size
Avoid using unfamiliar icons for critical actions without labels.
 
⸻
 
11.74 Charts
Charts should be used only when they clarify a trend or comparison.
Every chart should provide:
	•	Title
	•	Time period
	•	Units
	•	Data source
	•	Freshness
	•	Accessible summary
	•	Tooltip or detail behavior
	•	Empty and unavailable states
Charts should avoid:
	•	Misleading axes
	•	Unexplained percentage changes
	•	Excessive dimensions
	•	Decorative three-dimensional effects
	•	Color-only distinctions
 
⸻
 
11.75 Content and Terminology
The platform should maintain a terminology registry.
Preferred consistent terms include:
Organization
Location
Product
Integration
Workflow
Approval
Draft
Revision
Publication
Report
Lead
Notification
Do not interchange terms such as:
Client
Account
Company
Organization
within the same functional context without a defined reason.
“Organization” should remain the technical tenant term.
The interface may use “Client” in agency-facing language when that is clearer.
 
⸻
 
11.76 Technical Language
Client-facing language should translate technical conditions into operational meaning.
Internal:
OAuth refresh token invalid
Client-facing:
Google authorization expired. Reconnect the account to resume publishing.
Internal technical detail should remain accessible to authorized operators.
 
⸻
 
11.77 Dates and Times
The interface must show dates and times according to clear scope.
Possible timezone sources:
	•	User timezone
	•	Organization timezone
	•	Location timezone
	•	Reporting timezone
For scheduled external actions, the relevant location timezone should be explicit.
Example:
Scheduled for July 29, 2026 at 10:00 AM PDT
Location time: Little Italy
Relative time may supplement but not replace exact time for important actions.
 
⸻
 
11.78 Currency
Currency should follow the organization or billing account configuration.
Amounts must show:
	•	Currency symbol or code
	•	Billing period where relevant
	•	Whether tax is included
	•	Whether amount is estimated
	•	Usage period for variable charges
Example:
Estimated AI usage: $18.42 this month
Internal cost views must not automatically appear in client reporting.
 
⸻
 
11.79 Help and Guidance
Help should be contextual.
Potential forms:
	•	Inline explanation
	•	Tooltips
	•	Setup guidance
	•	Help drawer
	•	Documentation links
	•	Troubleshooting steps
The interface should not rely on tooltips for essential instructions.
 
⸻
 
11.80 Support Requests
Authorized users should be able to submit a support request from relevant context.
The support request should attach:
	•	Organization
	•	Location
	•	Product
	•	Current page
	•	Request ID
	•	Workflow ID where relevant
	•	User description
Secrets and sensitive payloads should not be attached automatically.
 
⸻
 
11.81 Operational Diagnostics
Agency operators may access a diagnostic panel for a resource.
It may show:
	•	Workflow status
	•	Integration status
	•	Last sync
	•	Error code
	•	Attempts
	•	Provider
	•	Correlation ID
	•	Data freshness
	•	Reconciliation status
The panel should prioritize interpreted information over raw logs.
 
⸻
 
11.82 Platform Administration Interface
The platform administration interface should support:
	•	Products
	•	Features
	•	Entitlement definitions
	•	Roles
	•	Permissions
	•	Integration providers
	•	AI providers
	•	Models
	•	Routing policies
	•	Prompt versions
	•	Workflow definitions
	•	Runtime controls
	•	Security events
	•	System health
Changes to platform-level definitions should require elevated permissions and audit history.
 
⸻
 
11.83 Prompt Administration Interface
Authorized users may manage:
	•	Prompt definitions
	•	Draft versions
	•	Test results
	•	Approval state
	•	Active version
	•	Rollback
	•	Task assignment
The interface should not allow direct editing of an approved version.
A change creates a draft version.
 
⸻
 
11.84 Workflow Administration Interface
Authorized users may view:
	•	Workflow definitions
	•	Versions
	•	Schedules
	•	Execution health
	•	Failure rate
	•	Average duration
	•	Active executions
	•	Paused workflows
Editing workflow definitions should follow versioning and release controls.
 
⸻
 
11.85 Runtime Controls Interface
Runtime controls may include:
	•	Pause AI provider
	•	Pause publication
	•	Pause workflow type
	•	Reduce worker concurrency
	•	Disable an integration provider
	•	Enable incident mode
Each control must show:
	•	Current state
	•	Scope
	•	Reason
	•	Activated by
	•	Activated at
	•	Expected effect
 
⸻
 
11.86 Onboarding Analytics
The platform should measure onboarding progress.
Potential metrics:
	•	Time to create organization
	•	Time to connect integration
	•	Time to first completed workflow
	•	Drop-off step
	•	Setup error rate
	•	Reconnection frequency
	•	Client invitation acceptance
	•	Time to first approval
	•	Time to product activation
These metrics should guide interface improvement.
 
⸻
 
11.87 Product Adoption Metrics
Useful adoption measures include:
	•	Active users
	•	Active organizations
	•	Active locations
	•	Product usage frequency
	•	Approval participation
	•	Report views
	•	Export use
	•	Workflow initiation
	•	Configuration completion
	•	Feature activation
Usage volume alone should not be treated as product success.
 
⸻
 
11.88 User Feedback
The platform may collect feedback on:
	•	Reports
	•	AI drafts
	•	Recommendations
	•	Product usability
	•	Onboarding
	•	Failed workflows
Feedback should attach to:
	•	Organization
	•	Product
	•	Resource
	•	User
	•	Version
	•	Time
Feedback collection should not interrupt routine work excessively.
 
⸻
 
11.89 UX Testing
Core workflows should be tested with representative users.
Priority workflows include:
	•	Create organization
	•	Add location
	•	Connect Google
	•	Enable product
	•	Review approval
	•	Publish GBP post
	•	Respond to review
	•	View report
	•	Resolve integration error
	•	Invite client user
	•	Change permissions
	•	Retry failed workflow
Testing should evaluate:
	•	Completion
	•	Errors
	•	Confusion
	•	Time
	•	Confidence
	•	Recovery
 
⸻
 
11.90 Interface Testing
Automated interface tests should cover:
	•	Authentication
	•	Navigation
	•	Organization switching
	•	Location switching
	•	Permission-based visibility
	•	Product entitlement visibility
	•	Form validation
	•	Approval actions
	•	Responsive behavior
	•	Accessibility checks
	•	Empty states
	•	Error states
	•	Workflow status updates
	•	Unsaved changes
	•	Destructive confirmations
 
⸻
 
11.91 Analytics and Privacy
Product analytics should avoid collecting unnecessary personal or sensitive data.
Analytics events may include:
	•	Page viewed
	•	Setup step completed
	•	Approval completed
	•	Report downloaded
	•	Integration connection attempted
	•	Workflow initiated
	•	Error displayed
Analytics should not include:
	•	Review text
	•	Lead messages
	•	API keys
	•	Personal contact details
	•	Full AI prompts
	•	Restricted client data
 
⸻
 
11.92 Initial UX Implementation Order
Stage 1 — Design System and Shell
Implement:
	•	Application shell
	•	Navigation
	•	Organization switcher
	•	Location switcher
	•	Context header
	•	Design tokens
	•	Core components
	•	Accessibility foundation
	•	Responsive foundation
Stage 2 — Identity and Organization Experience
Implement:
	•	Login
	•	Invitations
	•	Organization list
	•	Organization overview
	•	Location list
	•	User management
	•	Permission-aware navigation
Stage 3 — Onboarding
Implement:
	•	Organization setup
	•	Location setup
	•	Product selection
	•	Integration connection
	•	Readiness review
	•	Setup progress
Stage 4 — Shared Workflows
Implement:
	•	Work queue
	•	Approval inbox
	•	Notifications
	•	Activity history
	•	Workflow status
	•	Error recovery
	•	Diagnostics
Stage 5 — First Product Workspace
Implement SEO:
	•	Overview
	•	Properties
	•	Opportunities
	•	Performance
	•	Configuration
	•	History
Stage 6 — Additional Products
Implement:
	•	GBP
	•	Reviews
	•	Content
	•	Insights
	•	Leads
	•	Automations
Stage 7 — Platform Administration
Implement:
	•	Product definitions
	•	Providers
	•	AI configuration
	•	Prompt management
	•	Workflow management
	•	Runtime controls
	•	Security and operational views
 
⸻
 
11.93 UX Acceptance Requirements
A product interface is not production-ready until it includes:
	•	Clear organization scope
	•	Clear location scope
	•	Product status
	•	Product health
	•	Primary next action
	•	Setup state
	•	Empty states
	•	Loading states
	•	Success states
	•	Error states
	•	Degraded states
	•	Permission-aware controls
	•	Entitlement-aware navigation
	•	Approval experience
	•	History
	•	Data freshness
	•	Responsive behavior
	•	Accessibility
	•	Support path
	•	Analytics
	•	Documentation
 
⸻
 
11.94 UX Guardrails
The following are prohibited unless formally approved:
	1.	Actions without visible organization and location scope
	2.	Frontend navigation used as the only access control
	3.	Client portal exposing internal platform administration
	4.	Client users seeing unrelated operational diagnostics
	5.	Color used as the only status indicator
	6.	Generic failure messages without recovery guidance
	7.	Infinite loading indicators for asynchronous work
	8.	High-impact actions without consequence explanation
	9.	Approval applied to a different revision than the one reviewed
	10.	Product activation before required setup validation
	11.	Provider errors shown directly to ordinary client users
	12.	Hidden inherited configuration
	13.	Silent multi-location actions
	14.	Bulk actions without per-item results
	15.	Internal notes appearing in the client portal
	16.	AI-generated recommendations displayed as completed actions
	17.	AI output labeled as verified without validation
	18.	Unsaved long-form work lost without warning
	19.	Destructive actions placed as ordinary primary actions
	20.	Permanent configuration changes performed through temporary feature flags
	21.	Dense desktop tables reproduced unusably on mobile
	22.	Placeholder text used as the only form label
	23.	Status represented only through icons
	24.	Reports showing metrics without source, period, or freshness
	25.	Percentage changes without a comparison period
	26.	Search results revealing unauthorized records
	27.	Client dashboards dominated by internal implementation terminology
	28.	Permanent platform settings edited without history
	29.	Support requests submitted without scope context
	30.	Accessibility deferred until after product launch
 
⸻
 
11.95 Section Decisions
This section establishes the following decisions:
	1.	The platform provides separate agency, client, and platform-administration experiences.
	2.	The agency console prioritizes cross-client operations, work queues, diagnostics, and internal controls.
	3.	The client portal prioritizes status, approvals, reports, configuration, and required actions.
	4.	Organization and location scope must remain visible throughout the authenticated experience.
	5.	The application uses a consistent global, organization, location, product, and resource navigation hierarchy.
	6.	Product workspaces follow shared structural patterns while retaining product-specific functionality.
	7.	Lifecycle status and operational health are separate concepts.
	8.	Onboarding is modular, resumable, and product-specific.
	9.	Products can be added independently without repeating unrelated organization setup.
	10.	Integration connection flows explain requested access, external resource mapping, verification, and current health.
	11.	Configuration interfaces display effective values, inheritance, overrides, and impact.
	12.	The agency work queue consolidates actionable work across products.
	13.	Approval interfaces show the exact revision, supporting context, validation, risk, and external effect.
	14.	Material edits invalidate prior approval.
	15.	AI involvement is visible and inspectable according to user role.
	16.	Recommendations, proposed actions, completed actions, and measured outcomes are visually and linguistically distinct.
	17.	Data freshness is shown for provider-derived metrics.
	18.	Empty, loading, success, failure, and degraded states are required product behavior.
	19.	Notifications are actionable, scoped, preference-aware, and categorized.
	20.	Reporting provides source, period, comparison, freshness, and interpretation.
	21.	The platform uses a shared accessible design system.
	22.	Core workflows target WCAG 2.2 AA accessibility.
	23.	Desktop supports complex agency operations, while mobile supports essential review and action workflows.
	24.	Technical detail is translated into operational language for client users while remaining available to authorized internal users.
	25.	High-impact and destructive actions require explicit consequence-aware confirmation.
	26.	Operational diagnostics present interpreted status before raw technical detail.
	27.	Platform administration is separately permissioned and audited.
	28.	UX analytics must avoid collecting sensitive client content.
	29.	User experience testing must cover onboarding, approvals, integration recovery, reporting, and permission boundaries.
	30.	No product is production-ready without complete interface states, accessibility, history, support, and recovery behavior.

---

Section 12 — Product Framework and Product Specifications
12.1 Purpose of This Section
This section defines how products are designed, structured, extended, licensed, and maintained within the LILOs platform.
Rather than describing individual products in detail, this section establishes the framework that every present and future product must follow.
The objectives are to:
	•	Standardize product architecture
	•	Ensure consistency across products
	•	Define product lifecycle expectations
	•	Establish product ownership boundaries
	•	Define shared capabilities
	•	Prevent duplicate implementations
	•	Enable future products to be added without platform redesign
Individual product specifications (SEO, Google Business Profile, Reviews, Content, Leads, Insights, etc.) are defined in subsequent sections.
This section serves as the contract between the platform and every product built on top of it.
 
⸻
 
12.2 Definition of a Product
Within LILOs, a product is a self-contained business capability that solves a specific operational problem for a customer.
A product:
	•	Has its own workflows
	•	Owns its own domain model
	•	Owns its own business rules
	•	Has dedicated reporting
	•	Has dedicated configuration
	•	Uses shared platform services
	•	Can be enabled or disabled independently
	•	Can evolve independently without requiring platform redesign
Examples include:
	•	SEO
	•	Google Business Profile
	•	Reviews
	•	Content
	•	Leads
	•	Insights
	•	Future products
Products are not merely interface modules.
They are complete business systems built on shared platform infrastructure.
 
⸻
 
12.3 Product Design Principles
Every product must follow the same architectural principles.
Principle 1 — One Product, One Problem
Each product should solve one clearly defined operational problem.
Examples:
SEO
Problem: Improve search visibility and identify optimization opportunities.
Reviews
Problem: Manage customer reviews and responses.
Content
Problem: Create, review, publish, and measure content.
Products should not become collections of unrelated utilities.
 
⸻
 
Principle 2 — Platform Before Product
Products inherit:
	•	Authentication
	•	Permissions
	•	Organizations
	•	Locations
	•	Notifications
	•	Workflow engine
	•	AI routing
	•	Billing
	•	Audit
	•	Reporting framework
	•	Integrations
Products should not recreate platform functionality.
 
⸻
 
Principle 3 — Shared Experience
Although products solve different problems, users should experience them as one platform.
Shared behaviors include:
	•	Navigation
	•	Status
	•	Approvals
	•	History
	•	Configuration
	•	Search
	•	Notifications
	•	Reporting patterns
 
⸻
 
Principle 4 — Loose Coupling
Products communicate through platform workflows and events.
They do not directly manipulate another product’s internal state.
For example:
SEO identifies a content opportunity.
↓
Creates an event.
↓
Content product decides how to process it.
SEO does not generate or publish content directly.
 
⸻
 
Principle 5 — AI Is a Capability
Products may use AI.
Products do not depend upon AI.
Every product must define:
	•	AI-assisted behavior
	•	Non-AI behavior
	•	Human workflow
	•	Validation
 
⸻
 
Principle 6 — Human Ownership
AI generates.
People approve.
Platform executes.
This principle remains consistent across every product.
 
⸻
 
12.4 Product Anatomy
Every product contains the same major components.
Product

├── Overview
├── Configuration
├── Domain Objects
├── Workflows
├── AI Tasks
├── Reports
├── Integrations
├── Notifications
├── History
└── Administration
Products may extend this structure but should not replace it.
 
⸻
 
12.5 Required Product Components
Every production product must define:
Business Purpose
Why the product exists.
 
⸻
 
Users
Who uses it.
 
⸻
 
Domain Objects
Primary business entities.
 
⸻
 
Workflow Definitions
All workflow types.
 
⸻
 
Configuration
Every configurable option.
 
⸻
 
Permissions
Product-specific permissions.
 
⸻
 
AI Tasks
Where AI participates.
 
⸻
 
Integrations
External systems.
 
⸻
 
Reports
Outputs.
 
⸻
 
Metrics
Success measurements.
 
⸻
 
Notifications
User communication.
 
⸻
 
Audit Events
Tracked activities.
 
⸻
 
Failure Modes
Expected failures.
 
⸻
 
Recovery Procedures
How failures are resolved.
 
⸻
 
Acceptance Criteria
Definition of complete.
 
⸻
 
12.6 Product Lifecycle
Every product follows the same lifecycle.
Concept

↓

Design

↓

Internal Development

↓

Internal Testing

↓

Beta

↓

Limited Release

↓

General Availability

↓

Maintenance

↓

Enhancement

↓

Retirement
Products should never skip validation before general availability.
 
⸻
 
12.7 Product States
Each product instance for an organization may exist in one of the following states:
Not Enabled

↓

Setup Required

↓

Configuration Required

↓

Connection Required

↓

Ready

↓

Active

↓

Paused

↓

Degraded

↓

Suspended

↓

Archived
Operational health is tracked separately from lifecycle state.
 
⸻
 
12.8 Product Configuration Layers
Products inherit configuration through the platform hierarchy.
Platform

↓

Industry

↓

Organization

↓

Location

↓

Product

↓

Workflow

↓

Task
Products must clearly document:
	•	inherited values
	•	overridden values
	•	effective values
 
⸻
 
12.9 Product Ownership
Every product should have clearly defined ownership.
Each product defines:
	•	Product Owner
	•	Engineering Owner
	•	Operational Owner
	•	AI Owner
	•	Reporting Owner
Ownership responsibilities should not overlap ambiguously.
 
⸻
 
12.10 Product Boundaries
Products own:
	•	Their business logic
	•	Their domain model
	•	Their workflows
	•	Their reports
	•	Their metrics
Products do not own:
	•	Users
	•	Organizations
	•	Billing
	•	Authentication
	•	Workflow engine
	•	AI Gateway
	•	Notifications
	•	Audit
	•	Platform settings
 
⸻
 
12.11 Product Communication
Products communicate through:
	•	Workflow events
	•	Approved APIs
	•	Shared services
Products should not directly modify another product’s internal database structures.
 
⸻
 
12.12 Product Extensibility
Future products should be addable without modifying existing products.
Adding a new product should primarily require:
	•	Registration
	•	Entitlements
	•	Navigation
	•	Configuration
	•	Workflows
	•	Reports
	•	Permissions
Core platform architecture should remain unchanged.
 
⸻
 
12.13 Product Versioning
Products evolve independently.
Each product should maintain:
	•	Schema versions
	•	Workflow versions
	•	Prompt versions
	•	API compatibility
	•	Configuration compatibility
A change in one product should not require coordinated releases across unrelated products.
 
⸻
 
12.14 Shared Product Capabilities
Every product may leverage:
	•	Workflow Engine
	•	AI Gateway
	•	Notification Service
	•	Reporting Framework
	•	Approval Engine
	•	Search
	•	Audit
	•	Integrations
	•	Analytics
	•	Feature Flags
	•	Runtime Controls
Products should consume these capabilities rather than implement their own versions.
 
⸻
 
12.15 Product Quality Standards
Every product must meet minimum standards for:
	•	Reliability
	•	Security
	•	Accessibility
	•	Performance
	•	Observability
	•	Documentation
	•	Testing
	•	Recovery
	•	Operational ownership
No product is considered complete until it satisfies the platform-wide standards established in previous sections.
 
⸻
 
12.16 Standard Product Specification Template
Beginning with the next section, every product specification should follow a consistent structure.
Each product specification will include:
	1.	Purpose
	2.	Business Problem
	3.	Goals
	4.	Users
	5.	Domain Model
	6.	Configuration
	7.	Workflows
	8.	AI Responsibilities
	9.	Human Responsibilities
	10.	Integrations
	11.	Reporting
	12.	Metrics
	13.	Notifications
	14.	Permissions
	15.	Failure Modes
	16.	Recovery
	17.	Operational Requirements
	18.	Security Considerations
	19.	UX Requirements
	20.	Acceptance Criteria
	21.	Future Roadmap
This template ensures consistency across every product while allowing each product to address its own domain-specific requirements.
 
⸻
 
12.17 Initial Product Roadmap
The initial planned products are:
Phase 1
	•	SEO
	•	Google Business Profile
	•	Reviews
Phase 2
	•	Content
	•	Insights
Phase 3
	•	Leads
	•	Automations
Phase 4
Future platform products, including:
	•	Local Ads
	•	Social Media
	•	Reputation Intelligence
	•	Competitor Monitoring
	•	Call Intelligence
	•	CRM
	•	Scheduling
	•	Additional vertical-specific modules
 
⸻
 
12.18 Product Guardrails
Products must not:
	1.	Duplicate platform functionality.
	2.	Store data outside approved platform architecture.
	3.	Implement their own authentication or authorization systems.
	4.	Bypass workflow, approval, or audit mechanisms.
	5.	Create direct dependencies on another product’s internal implementation.
	6.	Assume AI availability.
	7.	Introduce inconsistent navigation or terminology.
	8.	Bypass tenant isolation.
	9.	Circumvent platform observability and operational controls.
	10.	Require architectural changes to support future products without clear justification.
 
⸻
 
12.19 Section Decisions
This section establishes the following decisions:
	1.	Products are self-contained business capabilities built on shared platform services.
	2.	Every product follows a common architectural framework and lifecycle.
	3.	Products own their business logic, workflows, domain model, reporting, and metrics.
	4.	Products inherit authentication, authorization, organizations, locations, workflow execution, AI routing, notifications, billing, and audit from the platform.
	5.	Products communicate through events, workflows, and defined service interfaces rather than direct coupling.
	6.	AI is an optional capability within a product, not the product itself.
	7.	Every product defines both AI-assisted and non-AI operational paths.
	8.	Product configuration follows the platform inheritance hierarchy.
	9.	Every product specification follows the standardized specification template defined in this section.
	10.	Future products must be addable without requiring redesign of the platform architecture.

---

Section 13 — SEO Product Specification
13.1 Purpose of This Product
The SEO product helps LILOs identify, prioritize, execute, and measure organic search opportunities for local businesses.
It is designed to convert fragmented search data into a controlled operating system for SEO work.
The product must support:
	•	Search performance monitoring
	•	Technical SEO monitoring
	•	Local organic visibility analysis
	•	Page and query opportunity detection
	•	Content opportunity detection
	•	Internal-linking recommendations
	•	On-page optimization
	•	Location-page and service-page strategy
	•	Competitor analysis
	•	Implementation tracking
	•	Measurement after changes
	•	Reporting
	•	Human review
	•	AI-assisted analysis and drafting
The SEO product is not intended to replace professional judgment.
It should reduce manual analysis, standardize recurring work, improve prioritization, and preserve a clear record of what was recommended, implemented, and measured.
 
⸻
 
13.2 Business Problem
Local SEO work commonly suffers from:
	•	Data spread across multiple systems
	•	Inconsistent prioritization
	•	Recommendations without evidence
	•	Work completed without implementation tracking
	•	Content created without measurable opportunity
	•	Repeated manual analysis
	•	Duplicate or conflicting recommendations
	•	Technical issues left unresolved
	•	Rankings tracked without connection to business outcomes
	•	Reports that summarize activity but do not explain decisions
	•	No clear record of what changed and whether it worked
The product must address the full operating loop:
Collect Data
    ↓
Detect Opportunity
    ↓
Validate
    ↓
Prioritize
    ↓
Recommend
    ↓
Approve
    ↓
Implement
    ↓
Verify
    ↓
Measure
    ↓
Learn
SEO analysis alone is not the product.
The product is the complete system for turning search data into measurable action.
 
⸻
 
13.3 Product Goals
The SEO product should:
	1.	Identify meaningful organic-search opportunities.
	2.	Separate high-value opportunities from low-value noise.
	3.	Produce evidence-backed recommendations.
	4.	Support location-specific and service-specific SEO.
	5.	Avoid duplicate, conflicting, or unnecessary content.
	6.	Track recommendations from discovery through implementation.
	7.	Verify that implementation occurred correctly.
	8.	Measure outcomes after implementation.
	9.	Preserve human control over strategic decisions.
	10.	Reduce recurring manual analysis.
	11.	Improve consistency across LILOs-managed accounts.
	12.	Support both restaurant and home-service clients.
	13.	Provide clear client-facing reporting.
	14.	Remain independent from any one rank tracker, crawler, or AI provider.
 
⸻
 
13.4 Non-Goals
The initial SEO product is not:
	•	A general-purpose website builder
	•	A replacement for Google Search Console
	•	A full enterprise crawler
	•	A backlink marketplace
	•	An autonomous link-building system
	•	A keyword-stuffing generator
	•	A bulk page generator without quality controls
	•	A black-box ranking predictor
	•	A guaranteed ranking system
	•	A system that publishes every recommendation automatically
	•	A system that treats rank movement as the only success metric
The product may integrate with site repositories and publishing systems, but it remains responsible for SEO operations rather than general website management.
 
⸻
 
13.5 Primary Users
SEO Strategist
Responsibilities:
	•	Review opportunities
	•	Validate intent
	•	Prioritize work
	•	Approve recommendations
	•	Assign implementation
	•	Review outcomes
 
⸻
 
SEO Operator
Responsibilities:
	•	Investigate issues
	•	Prepare recommendations
	•	Create briefs
	•	Implement approved changes
	•	Verify deployment
	•	Record evidence
 
⸻
 
Content Specialist
Responsibilities:
	•	Review content opportunities
	•	Create or edit content
	•	Validate search intent
	•	Avoid duplication
	•	Prepare drafts
	•	Support publication
 
⸻
 
Developer
Responsibilities:
	•	Implement technical changes
	•	Review repository changes
	•	Run tests
	•	Deploy approved updates
	•	Confirm implementation
 
⸻
 
Account Manager
Responsibilities:
	•	Review account priorities
	•	Explain recommendations
	•	Coordinate approvals
	•	Present results
	•	Escalate blockers
 
⸻
 
Client Approver
Responsibilities:
	•	Review significant content or website changes
	•	Approve business claims
	•	Confirm service or location information
	•	Review client-facing recommendations
 
⸻
 
Client Viewer
Responsibilities:
	•	View performance
	•	View completed work
	•	Review reports
	•	Understand current priorities
 
⸻
 
13.6 SEO Product Scope
The SEO product contains the following functional areas:
SEO Product

├── Data Connections
├── Data Collection
├── Site Inventory
├── Query Intelligence
├── Page Intelligence
├── Opportunity Detection
├── Technical Monitoring
├── Content Strategy
├── Local SEO Strategy
├── Competitor Analysis
├── Recommendation Management
├── Implementation Tracking
├── Verification
├── Measurement
├── Reporting
└── Administration
 
⸻
 
13.7 SEO Domain Model
The primary SEO domain objects are:
	•	SEO property
	•	Search property
	•	Site
	•	Page
	•	Query
	•	Query-page relationship
	•	Keyword
	•	Keyword cluster
	•	Search intent
	•	Topic
	•	Service
	•	Location target
	•	Competitor
	•	Ranking observation
	•	Search performance observation
	•	Technical issue
	•	Content issue
	•	Opportunity
	•	Recommendation
	•	Implementation task
	•	Verification
	•	Experiment
	•	Measurement period
	•	Outcome
	•	Annotation
	•	Report
 
⸻
 
13.8 SEO Property
An SEO property represents the complete SEO scope for one website or approved web property.
Recommended fields:
id
organization_id
location_id
name
primary_domain
canonical_domain
property_type
status
timezone
country
language
created_at
updated_at
Possible property types:
domain
subdomain
subdirectory
multi_location_site
single_location_site
A location may have:
	•	One dedicated website
	•	One section of a shared website
	•	Multiple relevant properties
The data model must support these cases without assuming one domain equals one location.
 
⸻
 
13.9 Search Property
A search property maps an external search-data source to an SEO property.
Examples:
	•	Google Search Console domain property
	•	Google Search Console URL-prefix property
	•	Bing Webmaster Tools property
	•	Rank-tracking campaign
Recommended fields:
id
seo_property_id
integration_connection_id
provider
external_property_id
property_url
status
last_synced_at
data_available_from
metadata
The system must distinguish:
	•	SEO property
	•	External provider property
	•	Physical business location
These are related but not interchangeable.
 
⸻
 
13.10 Site Records
A site record represents the crawlable website associated with an SEO property.
Recommended fields:
id
seo_property_id
base_url
canonical_host
protocol
trailing_slash_policy
status
last_crawled_at
robots_status
sitemap_status
The site record should store technical conventions used during validation.
Examples:
	•	HTTPS requirement
	•	www or non-www
	•	Trailing slash policy
	•	Canonical hostname
	•	Sitemap locations
 
⸻
 
13.11 Page Inventory
Every known indexable or relevant URL should have a page record.
Recommended fields:
id
seo_property_id
url
normalized_url
path
page_type
title
meta_description
h1
canonical_url
indexability_status
http_status
content_hash
word_count
last_crawled_at
published_at
updated_at
status
Possible page types:
homepage
service
location
service_location
product
category
blog
guide
menu
event
contact
about
landing_page
utility
unknown
Page classification should support industry-specific types.
Restaurant examples:
	•	Menu
	•	Brunch
	•	Happy hour
	•	Private events
	•	Location
	•	Venue
	•	Event
Home-service examples:
	•	Service
	•	City
	•	Service-city
	•	Emergency service
	•	Financing
	•	Insurance
	•	Commercial service
 
⸻
 
13.12 URL Normalization
The platform must normalize URLs before comparison.
Normalization should account for:
	•	Protocol
	•	Host casing
	•	Default ports
	•	Fragments
	•	Trailing slash policy
	•	Tracking parameters
	•	Duplicate query parameters
	•	Encoded characters
	•	www convention
Normalization must not combine genuinely different URLs.
The canonical URL and normalized operational URL should remain separate fields.
 
⸻
 
13.13 Query Records
A query record represents a search query discovered through an approved data source.
Recommended fields:
id
seo_property_id
query
normalized_query
language
search_intent
brand_classification
location_reference
service_reference
topic_id
first_seen_at
last_seen_at
status
Brand classifications:
branded
non_branded
mixed
competitor
unknown
Queries should be normalized for comparison without destroying meaningful wording.
 
⸻
 
13.14 Query-Page Relationships
Search performance should be stored as a relationship between:
	•	Query
	•	Page
	•	Date
	•	Device
	•	Country
	•	Search appearance where available
Recommended fields:
id
query_id
page_id
date
device
country
clicks
impressions
ctr
average_position
source
Aggregated records may be created for reporting, but raw provider-granularity data should remain available according to retention policy.
 
⸻
 
13.15 Keyword Records
A keyword is an intentionally tracked search phrase.
Unlike a query, a keyword may exist before it receives impressions.
Recommended fields:
id
seo_property_id
keyword
normalized_keyword
target_page_id
target_location_id
topic_id
intent
priority
tracking_status
source
created_at
Keyword sources may include:
	•	Search Console discovery
	•	Manual research
	•	Competitor research
	•	Local rank scans
	•	Client priority
	•	Service catalog
	•	AI-supported clustering
 
⸻
 
13.16 Query and Keyword Distinction
The platform must preserve the distinction:
Query = observed user search
Keyword = intentionally monitored target
A query may become a tracked keyword.
A keyword may have no recorded impressions yet.
Product interfaces and reports must not mix these concepts without labeling them.
 
⸻
 
13.17 Keyword Clusters
A keyword cluster groups queries and keywords around a shared intent.
Recommended fields:
id
seo_property_id
name
primary_keyword
topic_id
intent
location_scope
service_scope
status
created_by
Cluster membership should include:
cluster_id
query_id or keyword_id
relationship_type
confidence
review_status
Clusters should not be treated as permanent.
They may be revised as intent or site architecture changes.
 
⸻
 
13.18 Search Intent
Supported intent categories may include:
informational
commercial
transactional
navigational
local
local_commercial
local_transactional
comparison
support
unknown
Intent may be assigned through:
	•	Deterministic rules
	•	AI classification
	•	Human review
For high-impact content strategy, human validation should remain available.
 
⸻
 
13.19 Service Entities
The SEO product should reference shared organization or location services rather than storing disconnected service names.
A service may include:
id
organization_id
name
slug
category
description
status
available_locations
approved_claims
SEO records should link to service IDs where possible.
This prevents inconsistent naming across:
	•	SEO
	•	Content
	•	Leads
	•	GBP
	•	Website pages
 
⸻
 
13.20 Location Targets
SEO location targets may represent:
	•	Physical business locations
	•	Service areas
	•	Cities
	•	Neighborhoods
	•	Counties
	•	Regions
	•	Areas of relevance
Recommended fields:
id
seo_property_id
location_id
target_type
name
region
country
latitude
longitude
priority
status
A target location does not automatically justify a dedicated page.
Page creation requires opportunity validation and content differentiation.
 
⸻
 
13.21 Competitor Records
A competitor record should include:
id
seo_property_id
name
domain
location_scope
competitor_type
status
source
notes
Competitor types:
direct_business
organic_search
local_pack
content
directory
marketplace
informational
The platform must distinguish a true business competitor from a search-results competitor.
Examples of search-results competitors may include:
	•	Yelp
	•	TripAdvisor
	•	HomeAdvisor
	•	Angi
	•	Large publishers
	•	Local news sites
	•	Aggregators
 
⸻
 
13.22 Ranking Observations
Ranking observations may come from:
	•	Google Search Console
	•	Local rank scanning
	•	Third-party rank trackers
	•	Manual checks
	•	Search APIs
Recommended fields:
id
keyword_id
location_target_id
observed_at
rank
result_type
url
competitor_id
grid_point
device
source
Result types may include:
organic
local_pack
map
featured_snippet
people_also_ask
image
video
unknown
The product must display ranking-source limitations.
 
⸻
 
13.23 Local Rank Grid Support
The SEO product should support local-grid scan data where available.
A scan includes:
id
seo_property_id
location_id
keyword_id
center_latitude
center_longitude
grid_size
radius
scan_date
source
status
Each point includes:
latitude
longitude
rank
top_competitors
result_found
Derived metrics may include:
	•	Average rank
	•	Median rank
	•	Top-three percentage
	•	Top-ten percentage
	•	Share of local visibility
	•	Coverage by direction or area
Grid metrics should not be interpreted as exact user behavior.
They are directional visibility measurements.
 
⸻
 
13.24 Technical Issue Records
Technical issues should use standardized issue types.
Recommended fields:
id
seo_property_id
page_id
issue_type
severity
status
detected_at
last_detected_at
resolved_at
source
evidence
recommendation_id
Potential issue types:
	•	Broken internal link
	•	Broken external link
	•	Redirect chain
	•	Redirect loop
	•	Incorrect canonical
	•	Missing canonical
	•	Duplicate title
	•	Missing title
	•	Duplicate H1
	•	Missing H1
	•	Multiple H1
	•	Missing meta description
	•	Non-indexable target page
	•	Sitemap inconsistency
	•	Robots restriction
	•	Soft 404
	•	Server error
	•	Duplicate page
	•	Thin content
	•	Orphan page
	•	Structured-data error
	•	Mobile usability issue
	•	Core Web Vitals issue
	•	Image issue
	•	Incorrect hreflang
	•	Mixed protocol
	•	Incorrect trailing slash
	•	Internal link to redirect
	•	Stale URL
	•	Indexing discrepancy
 
⸻
 
13.25 Severity
Recommended technical severity:
critical
high
medium
low
informational
Severity should consider:
	•	Number of affected pages
	•	Page importance
	•	Indexing impact
	•	Ranking impact
	•	Conversion impact
	•	User experience
	•	Ease of remediation
	•	Confidence
Severity must not be based only on crawler convention.
 
⸻
 
13.26 Opportunity Records
An opportunity is the central business object of the SEO product.
An opportunity represents a validated area where action may improve organic visibility, traffic quality, conversion, or site integrity.
Recommended fields:
id
seo_property_id
organization_id
location_id
opportunity_type
title
summary
status
priority
confidence
business_value
estimated_effort
source
detected_at
validated_at
assigned_to
due_at
Potential opportunity types:
query_growth
high_impression_low_ctr
near_page_one
ranking_decline
traffic_decline
content_gap
service_gap
location_gap
cannibalization
internal_linking
title_optimization
meta_optimization
content_refresh
technical_issue
schema_improvement
local_visibility
conversion_alignment
competitor_gap
new_page
page_consolidation
page_removal
redirect_cleanup
 
⸻
 
13.27 Opportunity Status
Recommended lifecycle:
detected
needs_validation
validated
prioritized
recommended
approved
assigned
in_progress
implemented
verification_required
measuring
successful
neutral
unsuccessful
rejected
deferred
closed
The system must preserve why an opportunity was rejected or deferred.
 
⸻
 
13.28 Opportunity Evidence
Every opportunity should reference supporting evidence.
Evidence may include:
	•	Query metrics
	•	Page metrics
	•	Ranking changes
	•	Competitor pages
	•	Technical crawl results
	•	Local-grid results
	•	Existing page inventory
	•	Content similarity
	•	Client business priorities
	•	Conversion data
	•	Search-result observations
An opportunity without evidence should remain unvalidated.
 
⸻
 
13.29 Opportunity Scoring
Opportunity scoring should be explainable.
A score may consider:
	•	Impressions
	•	Current rank
	•	Click-through rate
	•	Query relevance
	•	Business value
	•	Conversion intent
	•	Location relevance
	•	Existing page strength
	•	Competitor difficulty
	•	Implementation effort
	•	Confidence
	•	Strategic importance
	•	Trend direction
Example conceptual structure:
Opportunity Score =
Business Value
× Search Potential
× Relevance
× Confidence
÷ Estimated Effort
The platform should not pretend this is a precise prediction.
The score is a prioritization mechanism.
 
⸻
 
13.30 Opportunity Score Components
Recommended normalized fields:
search_potential_score
business_value_score
intent_score
relevance_score
confidence_score
effort_score
competition_score
urgency_score
final_priority_score
Each component should preserve:
	•	Value
	•	Reason
	•	Source
	•	Calculation version
Scoring logic must be versioned.
 
⸻
 
13.31 Business Value
Business value should be configurable by organization and service.
Examples:
A home-service client may assign higher value to:
	•	Emergency water damage
	•	Electrical panel replacement
	•	High-value commercial work
A restaurant may assign higher value to:
	•	Private events
	•	Brunch
	•	Reservations
	•	Group dining
	•	Venue rental
Search volume alone must not define priority.
 
⸻
 
13.32 Recommendation Records
A recommendation describes the proposed action for an opportunity.
Recommended fields:
id
opportunity_id
recommendation_type
title
summary
rationale
proposed_action
target_page_id
target_query_ids
target_keyword_ids
risk_level
estimated_effort
status
revision
created_by
approved_by
Possible recommendation types:
update_page
create_page
consolidate_pages
redirect_page
remove_page
change_title
change_meta_description
change_heading
expand_content
add_internal_links
update_schema
fix_technical_issue
improve_conversion
monitor_only
 
⸻
 
13.33 Recommendation Quality Requirements
A recommendation must state:
	•	What should change
	•	Where it should change
	•	Why the change is justified
	•	Which evidence supports it
	•	Expected outcome
	•	Risks
	•	How success will be measured
	•	Whether client approval is required
	•	Whether development work is required
Recommendations such as “improve SEO” or “add more keywords” are invalid.
 
⸻
 
13.34 Implementation Tasks
An approved recommendation may create one or more implementation tasks.
Recommended fields:
id
recommendation_id
task_type
title
description
assignee
status
repository
branch
pull_request_url
cms_resource
due_at
completed_at
Task types may include:
content_edit
new_content
technical_change
schema_change
redirect_change
internal_linking
metadata_update
cms_update
manual_provider_change
measurement_setup
 
⸻
 
13.35 Implementation Status
Recommended statuses:
not_started
assigned
in_progress
blocked
ready_for_review
approved
deployed
verification_required
verified
failed
cancelled
Implementation and recommendation status should remain separate.
A recommendation may be approved while its implementation remains blocked.
 
⸻
 
13.36 Verification Records
Verification confirms that the approved change exists and works as intended.
Recommended fields:
id
implementation_task_id
verification_type
status
verified_at
verified_by
evidence
failure_reason
Verification types:
	•	Deployment verification
	•	URL response verification
	•	Title verification
	•	Canonical verification
	•	Schema verification
	•	Internal-link verification
	•	Indexability verification
	•	Content verification
	•	Provider verification
	•	Analytics verification
A completed code change is not automatically a verified SEO implementation.
 
⸻
 
13.37 Measurement Records
Measurement should compare relevant pre- and post-change periods.
Recommended fields:
id
opportunity_id
recommendation_id
measurement_start
measurement_end
comparison_start
comparison_end
status
metrics
interpretation
outcome
confidence
Possible outcomes:
positive
neutral
negative
inconclusive
not_measurable
Measurement periods should account for:
	•	Search-data delays
	•	Seasonality
	•	Algorithm changes
	•	Site-wide changes
	•	Provider limitations
	•	Low data volume
 
⸻
 
13.38 SEO Data Sources
The initial SEO product may use:
	•	Google Search Console
	•	Google Analytics 4
	•	Website crawl
	•	Sitemap
	•	Robots file
	•	Site repository
	•	Local visibility grid scans
	•	Google Business Profile data where relevant
	•	Approved rank-tracking provider
	•	Manual research
	•	Client service and location data
	•	Content inventory
Later sources may include:
	•	Bing Webmaster Tools
	•	PageSpeed Insights
	•	CrUX
	•	Third-party backlink data
	•	Additional rank trackers
	•	Call tracking
	•	CRM conversion data
 
⸻
 
13.39 Google Search Console Integration
Google Search Console is a primary data source.
The integration should support:
	•	Property discovery
	•	Property selection
	•	Query data
	•	Page data
	•	Date data
	•	Device
	•	Country
	•	Search appearance where available
	•	Sitemap information where available
	•	Inspection workflows where API support permits
The platform must account for provider limitations and delayed data.
 
⸻
 
13.40 Search Console Sync
The sync workflow should:
	1.	Verify active connection.
	2.	Verify selected property.
	3.	Determine sync date range.
	4.	Avoid requesting unavailable recent dates.
	5.	Pull dimensions in controlled batches.
	6.	Normalize queries and URLs.
	7.	Upsert observations.
	8.	Record provider limits or truncation.
	9.	Update freshness.
	10.	Detect anomalies.
	11.	Trigger opportunity analysis where appropriate.
The system must not imply complete query coverage when provider data is sampled, limited, or aggregated.
 
⸻
 
13.41 Search Console Data Windows
The product should support:
	•	Recent performance
	•	Previous period
	•	Year-over-year comparison
	•	Custom date ranges
	•	Rolling windows
	•	Post-implementation measurement
Recommended standard windows:
7 days
28 days
90 days
6 months
12 months
16 months where provider data permits
Date ranges must exclude incomplete data when appropriate.
 
⸻
 
13.42 Google Analytics 4 Integration
GA4 may provide:
	•	Organic sessions
	•	Landing-page engagement
	•	Conversions
	•	Events
	•	Revenue where applicable
	•	User behavior
GA4 data should not be treated as interchangeable with Search Console.
Search Console measures search appearance and clicks.
GA4 measures on-site activity after arrival.
 
⸻
 
13.43 Crawl System
The SEO product should support controlled crawling.
The initial crawler may be implemented internally or through an adapter to an approved external crawler.
Required crawl outputs include:
	•	URL
	•	HTTP status
	•	Content type
	•	Title
	•	Meta description
	•	H1
	•	Canonical
	•	Robots directives
	•	Internal links
	•	External links
	•	Word count
	•	Structured data presence
	•	Content hash
	•	Indexability
	•	Redirect destination
	•	Crawl depth
 
⸻
 
13.44 Crawl Controls
Crawling must support:
	•	Domain allowlist
	•	Maximum pages
	•	Crawl delay
	•	Maximum depth
	•	Query-parameter handling
	•	Exclusion patterns
	•	Authentication where approved
	•	User-agent identification
	•	Retry limits
	•	Timeout
	•	Respect for platform policy
The crawler should not create abusive load.
 
⸻
 
13.45 Sitemap Analysis
The product should:
	•	Discover sitemaps
	•	Parse sitemap indexes
	•	Record listed URLs
	•	Compare sitemap URLs with crawl inventory
	•	Detect non-indexable sitemap URLs
	•	Detect missing canonical pages
	•	Detect stale URLs
	•	Detect unexpected hostnames
Sitemap inclusion is evidence, not proof, of indexation.
 
⸻
 
13.46 Robots Analysis
The product should record:
	•	Robots file availability
	•	Relevant disallow rules
	•	Sitemap declarations
	•	User-agent-specific directives
	•	Conflicts with intended indexation
The product must distinguish:
	•	Crawl restriction
	•	Indexing directive
	•	Authentication failure
	•	Server failure
 
⸻
 
13.47 Repository Integration
For LILOs-managed websites, the SEO product may connect to GitHub.
Capabilities may include:
	•	Read repository metadata
	•	Map URLs to source files
	•	Inspect route definitions
	•	Inspect content collections
	•	Inspect schema
	•	Inspect redirects
	•	Create implementation branches
	•	Open draft pull requests
	•	Run validation
	•	Link code changes to recommendations
Repository access must follow the GitHub security model.
 
⸻
 
13.48 Repository Mapping
The product should support mapping:
Published URL
    ↓
Framework Route
    ↓
Source File
    ↓
Content Record
    ↓
Deployment
Mapping may use:
	•	Astro route files
	•	Content collection slugs
	•	CMS identifiers
	•	Route manifests
	•	Build output
	•	Manual mapping
The system must not modify a source file solely based on an unverified URL guess.
 
⸻
 
13.49 CMS Integration
The SEO product may integrate with:
	•	Keystatic
	•	WordPress
	•	Drupal
	•	Toast
	•	Booqable
	•	Custom CMS
	•	Repository-managed markdown
CMS adapters should expose normalized capabilities:
read_page
create_draft
update_draft
publish
read_metadata
update_metadata
read_revision
Publication must remain subject to permissions and approval.
 
⸻
 
13.50 SEO Configuration
SEO product configuration should include:
	•	Primary domain
	•	Canonical host
	•	Country
	•	Language
	•	Timezone
	•	Industry
	•	Priority services
	•	Priority locations
	•	Brand queries
	•	Competitors
	•	Conversion events
	•	Reporting cadence
	•	Data sources
	•	Approval policy
	•	Content policy
	•	Technical crawl policy
	•	Measurement windows
	•	Notification preferences
 
⸻
 
13.51 Brand Query Configuration
Organizations should be able to define:
	•	Business name
	•	Common variations
	•	Misspellings
	•	Product brands
	•	Location names
	•	Legacy names
	•	Excluded ambiguous terms
Brand classification should be reviewable.
A business name that is also a generic word requires special handling.
 
⸻
 
13.52 Priority Service Configuration
Each service may include:
service_id
priority
business_value
seasonality
target_locations
conversion_event
status
SEO recommendations should consider these priorities.
A query may have high search volume but low business relevance.
 
⸻
 
13.53 Priority Location Configuration
Each location target may include:
	•	Priority
	•	Service availability
	•	Physical presence
	•	Service-area relevance
	•	Existing page
	•	GBP connection
	•	Strategic importance
	•	Excluded areas
The product must not recommend targeting areas the business does not serve.
 
⸻
 
13.54 Competitor Configuration
Users may add or approve competitors.
Competitor configuration should include:
	•	Name
	•	Domain
	•	Geographic scope
	•	Services
	•	Relevance
	•	Competitor type
	•	Notes
	•	Active status
AI-discovered competitors should remain unapproved until reviewed.
 
⸻
 
13.55 SEO Workflow Categories
The product should support these major workflow categories:
	1.	Data synchronization
	2.	Site crawl
	3.	Opportunity detection
	4.	Opportunity validation
	5.	Recommendation generation
	6.	Approval
	7.	Implementation
	8.	Verification
	9.	Measurement
	10.	Reporting
	11.	Maintenance
	12.	Reconciliation
 
⸻
 
13.56 Search Data Sync Workflow
Schedule or Manual Trigger
    ↓
Validate Integration
    ↓
Determine Date Window
    ↓
Retrieve Data
    ↓
Normalize
    ↓
Store
    ↓
Update Freshness
    ↓
Run Data Quality Checks
    ↓
Detect Opportunities
The workflow must record:
	•	Requested range
	•	Retrieved range
	•	Rows retrieved
	•	Provider limits
	•	Errors
	•	Freshness
	•	Partial completion
 
⸻
 
13.57 Crawl Workflow
Trigger
    ↓
Load Crawl Configuration
    ↓
Discover Starting URLs
    ↓
Crawl Within Limits
    ↓
Normalize URLs
    ↓
Store Page and Link Data
    ↓
Detect Technical Issues
    ↓
Compare With Previous Crawl
    ↓
Update Site Health
Crawl failure must not delete prior known page state.
 
⸻
 
13.58 Opportunity Detection Workflow
New or Updated Data
    ↓
Run Deterministic Detectors
    ↓
Run Approved AI Analysis
    ↓
Create Candidate Opportunities
    ↓
Deduplicate
    ↓
Score
    ↓
Send for Validation
Candidate opportunities should not immediately become client-facing recommendations.
 
⸻
 
13.59 Opportunity Validation Workflow
Validation should confirm:
	•	Data quality
	•	Query relevance
	•	Business relevance
	•	Search intent
	•	Existing page coverage
	•	Content duplication risk
	•	Geographic relevance
	•	Service availability
	•	Measurement feasibility
	•	Strategic fit
Validation may result in:
validated
rejected
deferred
needs_more_data
 
⸻
 
13.60 Recommendation Workflow
Validated Opportunity
    ↓
Generate Recommendation Draft
    ↓
Apply Business Rules
    ↓
Review Evidence
    ↓
Human Review
    ↓
Approve, Reject, or Revise
    ↓
Create Implementation Tasks
Recommendation generation may use AI, but final strategic approval remains human-controlled.
 
⸻
 
13.61 Implementation Workflow
Implementation depends on the target system.
Possible paths:
Repository-Managed Site
Approved Recommendation
    ↓
Create Branch
    ↓
Apply Changes
    ↓
Run Tests and Build
    ↓
Open Draft Pull Request
    ↓
Review
    ↓
Merge
    ↓
Deploy
    ↓
Verify
CMS-Managed Site
Approved Recommendation
    ↓
Create CMS Draft
    ↓
Review
    ↓
Publish
    ↓
Verify
External Client Implementation
Approved Recommendation
    ↓
Create Client Task
    ↓
Provide Requirements
    ↓
Await Completion
    ↓
Verify
 
⸻
 
13.62 Verification Workflow
Implementation Marked Complete
    ↓
Wait for Deployment if Required
    ↓
Fetch Live Resource
    ↓
Run Verification Checks
    ↓
Compare Against Approved Change
    ↓
Pass or Fail
    ↓
Begin Measurement or Return to Implementation
Verification evidence should be stored.
 
⸻
 
13.63 Measurement Workflow
Verified Change
    ↓
Select Measurement Window
    ↓
Wait for Sufficient Data
    ↓
Collect Search and Conversion Metrics
    ↓
Compare Baseline
    ↓
Account for Confounding Factors
    ↓
Classify Outcome
    ↓
Record Interpretation
The product should avoid declaring success too early.
 
⸻
 
13.64 Reporting Workflow
Reporting Schedule
    ↓
Validate Data Freshness
    ↓
Aggregate Metrics
    ↓
Identify Completed Work
    ↓
Summarize Outcomes
    ↓
Identify Current Priorities
    ↓
Generate Draft Report
    ↓
Human Review
    ↓
Publish or Deliver
Reports must distinguish completed work from recommended future work.
 
⸻
 
13.65 SEO Opportunity Detectors
Initial deterministic detectors should include:
	•	High impressions with low CTR
	•	Queries ranking in positions 4–20
	•	Pages losing clicks
	•	Queries losing position
	•	Growing non-branded queries
	•	Relevant queries with no intentional target page
	•	Multiple pages competing for the same query cluster
	•	Pages receiving impressions for mismatched intent
	•	Priority pages with weak internal links
	•	Important pages missing from sitemap
	•	Indexed or ranking stale URLs
	•	Internal links pointing through redirects
	•	Duplicate titles
	•	Missing or duplicate H1s
	•	Thin priority pages
	•	Broken high-value pages
	•	Incorrect canonical tags
	•	Non-indexable target pages
	•	Location or service coverage gaps
	•	High-value pages with weak conversion alignment
 
⸻
 
13.66 High-Impression Low-CTR Detector
The detector should consider:
	•	Minimum impression threshold
	•	Average position
	•	Current CTR
	•	Expected CTR range
	•	Branded status
	•	Result type
	•	Device
	•	Query intent
	•	Title alignment
	•	SERP features
A low CTR at position 18 is not the same opportunity as low CTR at position 2.
 
⸻
 
13.67 Near-Page-One Detector
The detector should identify relevant queries or clusters within a configurable position range.
Recommended default:
Positions 4–20
It should exclude:
	•	Irrelevant queries
	•	Low-value services
	•	Unsupported locations
	•	Branded navigational queries already performing as expected
	•	Queries assigned to a more appropriate page
 
⸻
 
13.68 Cannibalization Detector
Potential cannibalization should be detected when:
	•	Multiple pages receive impressions for the same cluster.
	•	Ranking URLs alternate repeatedly.
	•	The pages have overlapping intent.
	•	Neither page clearly dominates.
	•	Internal linking or canonical signals are inconsistent.
Multiple pages ranking for related queries does not automatically mean cannibalization.
The detector must classify candidates for review rather than automatically consolidate pages.
 
⸻
 
13.69 Content Gap Detector
A content gap may exist when:
	•	A priority service lacks a relevant page.
	•	A priority location lacks appropriate coverage.
	•	Competitors consistently rank with content absent from the client site.
	•	Search Console reveals relevant query themes without a suitable target.
	•	Existing content does not satisfy intent.
	•	A current page is too broad to cover the opportunity.
The system must check for existing equivalent content before recommending a new page.
 
⸻
 
13.70 Content Refresh Detector
A refresh opportunity may be created when:
	•	A previously strong page loses performance.
	•	Facts are outdated.
	•	Search intent changes.
	•	Competitor coverage materially improves.
	•	Internal links become stale.
	•	Business information changes.
	•	The page has not been reviewed within a configured period.
Age alone is not sufficient reason to refresh a page.
 
⸻
 
13.71 Internal Linking Detector
The detector should identify:
	•	Important pages with few internal links
	•	Relevant source pages
	•	Broken internal links
	•	Links to redirects
	•	Overused generic anchors
	•	Orphan pages
	•	New pages requiring integration into site architecture
Recommendations should include:
	•	Source page
	•	Target page
	•	Suggested placement
	•	Suggested anchor intent
	•	Rationale
 
⸻
 
13.72 Local SEO Opportunity Detection
The SEO product should identify local organic opportunities using:
	•	Location pages
	•	Service-area relevance
	•	GBP data
	•	Local rank scans
	•	Search Console location modifiers
	•	Competitor coverage
	•	Internal linking
	•	Local business facts
	•	Conversion data
Local organic SEO and GBP optimization remain separate product responsibilities.
They may share evidence and events.
 
⸻
 
13.73 Restaurant SEO Patterns
Restaurant-specific analysis should support:
	•	Cuisine
	•	Brunch
	•	Happy hour
	•	Rooftop
	•	Private events
	•	Group dining
	•	Menu categories
	•	Neighborhood
	•	Occasion
	•	Venue features
	•	Reservations
	•	Live music
	•	Catering
	•	Seasonal events
Recommendations must reflect actual offerings.
The system must not invent:
	•	Menu items
	•	Hours
	•	Events
	•	Amenities
	•	Awards
	•	Pricing
	•	Reservation availability
 
⸻
 
13.74 Home-Service SEO Patterns
Home-service analysis should support:
	•	Service pages
	•	Emergency services
	•	Service-area pages
	•	City-service pages
	•	Commercial services
	•	Residential services
	•	Financing
	•	Insurance
	•	Licenses
	•	Certifications
	•	Response areas
Recommendations must reflect:
	•	Actual services
	•	Actual service areas
	•	Approved claims
	•	License information
	•	Operational capability
 
⸻
 
13.75 City and Service-Location Page Controls
The system must prevent uncontrolled page expansion.
Before recommending a new city or service-location page, confirm:
	•	The business serves the area.
	•	The service is offered there.
	•	Search intent exists.
	•	Existing content does not already cover the need.
	•	The page can contain meaningful unique information.
	•	The page fits site architecture.
	•	Internal links can support it.
	•	The business can substantiate local relevance.
Programmatic page generation without differentiated value is prohibited.
 
⸻
 
13.76 Page Consolidation
A consolidation recommendation should define:
	•	Primary surviving page
	•	Pages to merge
	•	Content to preserve
	•	Redirect mapping
	•	Internal-link updates
	•	Canonical updates
	•	Sitemap updates
	•	Measurement plan
Deletion without preservation analysis is prohibited.
 
⸻
 
13.77 Redirect Management
Redirect recommendations should support:
	•	Permanent redirect
	•	Temporary redirect
	•	Removal
	•	Direct destination update
	•	Chain cleanup
	•	Legacy URL mapping
Redirect records should include:
source_url
destination_url
status_code
reason
effective_date
verification_status
The product must detect:
	•	Loops
	•	Chains
	•	Redirects to irrelevant pages
	•	Redirects to non-canonical hosts
	•	Internal links pointing to redirect sources
 
⸻
 
13.78 Metadata Optimization
Metadata recommendations should account for:
	•	Search intent
	•	Query evidence
	•	Page purpose
	•	Brand
	•	Location
	•	Length
	•	Duplication
	•	Accuracy
	•	Conversion relevance
The platform must not use rigid character counts as the sole quality rule.
Generated titles and descriptions require validation.
 
⸻
 
13.79 Heading Optimization
Heading recommendations should:
	•	Preserve logical hierarchy
	•	Align H1 with page purpose
	•	Avoid duplicate page-level H1s
	•	Avoid forced keyword repetition
	•	Support readability
	•	Reflect actual content
A duplicate phrase across headings is not automatically a technical issue.
 
⸻
 
13.80 Structured Data
The SEO product may detect and recommend structured data for:
	•	LocalBusiness
	•	Restaurant
	•	Organization
	•	Service
	•	Article
	•	BreadcrumbList
	•	Event
	•	FAQ where appropriate
	•	Product where applicable
Structured data must reflect visible, accurate page content.
The product must not generate unsupported ratings, pricing, events, or business attributes.
 
⸻
 
13.81 SEO AI Responsibilities
AI may assist with:
	•	Query classification
	•	Query clustering
	•	Intent classification
	•	Opportunity summaries
	•	Competitor-content comparison
	•	Content-gap analysis
	•	Recommendation drafting
	•	Content-brief generation
	•	Metadata drafting
	•	Internal-link suggestions
	•	Report summaries
	•	Change-impact summaries
AI must not independently decide:
	•	Final publication
	•	Page deletion
	•	Redirect strategy
	•	Service availability
	•	Location eligibility
	•	Approved claims
	•	Client business priorities
	•	Success attribution
 
⸻
 
13.82 SEO AI Tasks
Initial task registry entries may include:
seo.query_classification
seo.intent_classification
seo.query_clustering
seo.opportunity_summary
seo.content_gap_analysis
seo.page_comparison
seo.recommendation_draft
seo.content_brief
seo.metadata_draft
seo.internal_link_suggestion
seo.performance_summary
seo.measurement_interpretation
Each task must define its own schema and evaluation criteria.
 
⸻
 
13.83 Query Classification Output
Example schema:
{
  "query": "best brunch little italy san diego",
  "brand_classification": "non_branded",
  "intent": "local_commercial",
  "service": "brunch",
  "location": "Little Italy, San Diego",
  "relevance": "high",
  "confidence": "high",
  "requires_review": false
}
The model must not create a new service record solely from classification output.
 
⸻
 
13.84 Opportunity Summary Output
Example schema:
{
  "summary": "The brunch page receives substantial impressions for non-branded Little Italy queries but ranks primarily between positions 7 and 12.",
  "evidence": [
    {
      "type": "search_console",
      "description": "3,420 impressions across the target query cluster in the last 90 days."
    }
  ],
  "recommended_direction": "Strengthen the existing brunch page rather than create a new page.",
  "risks": [
    "Existing page content must be checked against current service hours."
  ],
  "requires_human_review": true
}
 
⸻
 
13.85 Content Brief Output
A content brief should include:
	•	Target purpose
	•	Primary query cluster
	•	Secondary query themes
	•	Search intent
	•	Audience
	•	Existing competing pages
	•	Required business facts
	•	Approved claims
	•	Suggested structure
	•	Internal links
	•	Conversion action
	•	Prohibited duplication
	•	Measurement plan
The brief must not become a generic keyword list.
 
⸻
 
13.86 AI Grounding Requirements
SEO AI tasks should be grounded in:
	•	Search Console data
	•	Page inventory
	•	Crawl data
	•	Service data
	•	Location data
	•	Approved claims
	•	Existing content
	•	Competitor evidence
	•	Business priorities
The model should not rely primarily on general SEO knowledge when client-specific evidence exists.
 
⸻
 
13.87 AI Validation
SEO AI output should be checked for:
	•	Schema validity
	•	Correct client
	•	Correct page
	•	Correct location
	•	Correct service
	•	Supported metrics
	•	Unsupported claims
	•	Existing content duplication
	•	Recommendation feasibility
	•	Prohibited page generation
	•	Misstated causation
AI summaries must not present estimates as measured facts.
 
⸻
 
13.88 Human Responsibilities
Humans remain responsible for:
	•	Strategic priority
	•	Business-value assessment
	•	Search-intent validation
	•	Approval of major recommendations
	•	Client claim validation
	•	Page creation decisions
	•	Consolidation decisions
	•	Publication approval
	•	Outcome interpretation
	•	Client communication
AI may reduce analysis time but does not replace accountability.
 
⸻
 
13.89 SEO Permissions
Recommended product permissions:
seo.view
seo.view_sensitive
seo.configure
seo.connect_integrations
seo.run_sync
seo.run_crawl
seo.create_opportunity
seo.validate_opportunity
seo.create_recommendation
seo.approve_recommendation
seo.assign_implementation
seo.mark_implemented
seo.verify
seo.publish
seo.view_reports
seo.export
seo.manage_competitors
seo.manage_keywords
seo.manage_runtime
Permissions should remain action-specific.
 
⸻
 
13.90 Approval Policies
Approval may be required for:
	•	New page creation
	•	Major content rewrites
	•	Page consolidation
	•	Redirect changes
	•	Page removal
	•	Public claims
	•	Business-information changes
	•	Repository pull requests
	•	CMS publication
	•	High-impact schema changes
Low-risk internal analysis may not require approval.
 
⸻
 
13.91 Notifications
SEO notifications may include:
	•	Integration requires attention
	•	Data sync failed
	•	Crawl completed
	•	Critical technical issue detected
	•	Opportunity ready for validation
	•	Recommendation ready for approval
	•	Implementation assigned
	•	Verification failed
	•	Measurement ready
	•	Report ready
	•	Significant performance decline
	•	Data freshness delayed
Notifications should link directly to the relevant record.
 
⸻
 
13.92 SEO Dashboard
The SEO product overview should show:
	•	Property status
	•	Data freshness
	•	Search Console status
	•	Crawl status
	•	Current opportunities
	•	Critical issues
	•	Work in progress
	•	Recent implementations
	•	Measurement outcomes
	•	Key performance summary
Recommended primary actions:
	•	Review opportunities
	•	Run crawl
	•	View technical issues
	•	Review recommendations
	•	Connect data source
 
⸻
 
13.93 SEO Opportunity Workspace
The opportunity workspace should support:
	•	List
	•	Filters
	•	Score
	•	Evidence
	•	Page
	•	Query cluster
	•	Service
	•	Location
	•	Status
	•	Assignee
	•	Recommendation
	•	Outcome
Filters should include:
	•	Opportunity type
	•	Priority
	•	Status
	•	Service
	•	Location
	•	Page type
	•	Confidence
	•	Assignee
	•	Date detected
 
⸻
 
13.94 Opportunity Detail Experience
The detail view should include:
	•	Summary
	•	Evidence
	•	Metrics
	•	Query cluster
	•	Target page
	•	Existing page alternatives
	•	Competitors
	•	Score breakdown
	•	Risks
	•	Recommendation history
	•	Implementation status
	•	Measurement status
The user should be able to understand why the opportunity exists without reviewing raw provider exports.
 
⸻
 
13.95 Technical Issues Workspace
Technical issues should support grouping by:
	•	Issue type
	•	Severity
	•	Page type
	•	URL
	•	First detected
	•	Last detected
	•	Status
The interface should distinguish:
	•	New
	•	Existing
	•	Resolved
	•	Reopened
	•	Ignored
	•	Accepted risk
 
⸻
 
13.96 Keyword Workspace
The keyword workspace should support:
	•	Tracked keywords
	•	Query-derived keywords
	•	Clusters
	•	Target pages
	•	Locations
	•	Rank history
	•	Local-grid scans
	•	Priority
	•	Intent
	•	Status
The interface should avoid encouraging large keyword lists without strategic relevance.
 
⸻
 
13.97 Page Workspace
Each page detail should show:
	•	URL
	•	Page type
	•	Indexability
	•	Search performance
	•	Ranking queries
	•	Target keywords
	•	Technical issues
	•	Internal links
	•	Opportunities
	•	Recommendations
	•	Implementation history
	•	Measurement history
 
⸻
 
13.98 Competitor Workspace
The competitor workspace should show:
	•	Competitor type
	•	Domain
	•	Location relevance
	•	Overlapping queries
	•	Strong pages
	•	Content gaps
	•	Local visibility
	•	Last analysis
	•	Approved status
Competitive analysis must remain evidence-based.
 
⸻
 
13.99 Reporting Metrics
SEO reporting may include:
	•	Organic clicks
	•	Organic impressions
	•	Average position
	•	CTR
	•	Non-branded clicks
	•	Branded clicks
	•	Organic sessions
	•	Organic conversions
	•	Priority-page performance
	•	Query-cluster performance
	•	Local visibility
	•	Technical health
	•	Opportunities completed
	•	Recommendations implemented
	•	Positive outcomes
	•	Data freshness
No single metric should represent total SEO success.
 
⸻
 
13.100 Client-Facing SEO Reporting
Client reports should answer:
	1.	What changed?
	2.	What work was completed?
	3.	What improved?
	4.	What declined?
	5.	What requires attention?
	6.	What is planned next?
	7.	What data limitations exist?
Reports should avoid:
	•	Excessive technical jargon
	•	Unsupported ranking promises
	•	Vanity metrics without context
	•	Listing work without outcomes
	•	Hiding declines
 
⸻
 
13.101 Agency SEO Reporting
Agency users should additionally see:
	•	Sync quality
	•	Provider limits
	•	Data gaps
	•	Opportunity backlog
	•	Implementation backlog
	•	Verification failures
	•	Recommendation acceptance
	•	Time to implementation
	•	Outcome by opportunity type
	•	AI usage and edit rate
	•	Account profitability inputs
 
⸻
 
13.102 SEO Success Metrics
Product success should be measured through:
Operational Metrics
	•	Data-sync reliability
	•	Crawl completion
	•	Opportunity validation time
	•	Recommendation approval time
	•	Implementation time
	•	Verification pass rate
	•	Measurement completion
Quality Metrics
	•	Recommendation acceptance
	•	Recommendation rejection
	•	Duplicate recommendation rate
	•	Human revision rate
	•	Unsupported-claim rate
	•	False-positive opportunity rate
Business Metrics
	•	Organic conversion growth
	•	Priority-query improvement
	•	Priority-page growth
	•	Non-branded visibility growth
	•	Local visibility improvement
	•	Increased qualified traffic
	•	Completed high-value work
 
⸻
 
13.103 Failure Modes
Expected failure modes include:
	•	Search Console authorization expired
	•	Wrong property selected
	•	Provider data delayed
	•	Provider row limits
	•	Crawl blocked
	•	Crawl timeout
	•	Sitemap unavailable
	•	Repository mapping failed
	•	CMS publication failed
	•	Duplicate opportunity created
	•	AI misclassified query
	•	Implementation changed the wrong page
	•	Deployment succeeded but verification failed
	•	External site changed after recommendation
	•	Insufficient data for measurement
	•	Ranking volatility
	•	Algorithm update confounds results
 
⸻
 
13.104 Failure Handling
Each failure should define:
	•	Error category
	•	Retry eligibility
	•	User-visible message
	•	Internal diagnostic
	•	Workflow impact
	•	Recovery action
	•	Escalation owner
The platform must preserve prior valid data when a new sync fails.
 
⸻
 
13.105 Data Quality Controls
SEO data quality checks should detect:
	•	Sudden zero values
	•	Partial date ranges
	•	Wrong property
	•	Host mismatch
	•	URL normalization errors
	•	Duplicate rows
	•	Provider truncation
	•	Missing dimensions
	•	Unexpected timezone shift
	•	Large unexplained discontinuity
Low-quality data should block automated recommendations where appropriate.
 
⸻
 
13.106 SEO Security Considerations
The product must protect:
	•	Search Console credentials
	•	Analytics credentials
	•	Repository access
	•	CMS access
	•	Private drafts
	•	Lead or conversion data
	•	Client internal priorities
Repository and CMS write access require elevated permissions.
SEO users should not automatically receive broad client data access outside the product.
 
⸻
 
13.107 SEO Privacy Considerations
SEO analysis should minimize personal data.
Query data should be stored as supplied by providers, but the platform should avoid combining it with personal identities.
Analytics reporting should use aggregated metrics unless a specific approved use requires more detail.
 
⸻
 
13.108 SEO Operational Requirements
The product requires:
	•	Scheduled Search Console sync
	•	Controlled crawl execution
	•	Opportunity detector scheduling
	•	Queue monitoring
	•	Provider quota monitoring
	•	Failed-sync recovery
	•	Verification jobs
	•	Measurement scheduling
	•	Report scheduling
	•	Runtime pause controls
	•	Data-retention cleanup
 
⸻
 
13.109 SEO Health States
Recommended product health conditions:
healthy
data_delayed
connection_required
crawl_failed
partial_data
implementation_blocked
provider_degraded
configuration_required
The product may remain active while one data source is degraded.
 
⸻
 
13.110 Runtime Controls
Authorized operators should be able to:
	•	Pause data sync
	•	Pause crawl
	•	Pause AI analysis
	•	Pause automatic opportunity detection
	•	Disable repository writes
	•	Disable CMS publishing
	•	Pause a property
	•	Re-run a detector
	•	Reconcile a sync
	•	Mark provider data delayed
Runtime controls must be audited.
 
⸻
 
13.111 SEO Testing Requirements
Testing should cover:
	•	Tenant isolation
	•	Property mapping
	•	Search Console synchronization
	•	Date-window calculation
	•	URL normalization
	•	Query normalization
	•	Duplicate prevention
	•	Opportunity scoring
	•	Detector logic
	•	AI schema validation
	•	Permission checks
	•	Approval revision control
	•	Repository mapping
	•	CMS draft creation
	•	Redirect verification
	•	Crawl limits
	•	Measurement calculations
	•	Report generation
	•	Provider failures
	•	Data-delay behavior
 
⸻
 
13.112 Evaluation Datasets
SEO AI evaluation datasets should include:
	•	Branded and non-branded queries
	•	Restaurant query patterns
	•	Home-service query patterns
	•	Ambiguous intent
	•	Irrelevant queries
	•	Location modifiers
	•	Competitor terms
	•	Cannibalization examples
	•	Content-gap examples
	•	Technical recommendation examples
	•	Valid and invalid page-creation recommendations
Human-reviewed examples should be versioned.
 
⸻
 
13.113 SEO Acceptance Requirements
The initial SEO product is not production-ready until it supports:
	•	SEO property creation
	•	Search Console connection
	•	Search property selection
	•	Scheduled search-data sync
	•	Page and query storage
	•	URL normalization
	•	Query classification
	•	Page inventory
	•	Opportunity records
	•	At least five deterministic opportunity detectors
	•	Opportunity validation
	•	Explainable scoring
	•	Recommendation creation
	•	Approval
	•	Implementation task tracking
	•	Verification
	•	Measurement scheduling
	•	Client-facing reporting
	•	Agency operational reporting
	•	Permissions
	•	Audit history
	•	Error recovery
	•	Data freshness
	•	Tenant isolation
	•	Manual operation without AI
 
⸻
 
13.114 Minimum Viable SEO Product
The minimum viable product should include:
Data
	•	Google Search Console
	•	Page inventory
	•	Query observations
	•	Basic crawl
	•	Manual keyword targets
Opportunity Detection
	•	High-impression low-CTR
	•	Near-page-one
	•	Performance decline
	•	Content gap
	•	Technical issue
Workflow
	•	Detect
	•	Validate
	•	Recommend
	•	Approve
	•	Implement
	•	Verify
	•	Measure
Reporting
	•	Search performance
	•	Completed work
	•	Current opportunities
	•	Data freshness
	•	Initial outcome tracking
 
⸻
 
13.115 SEO Implementation Phases
Phase 1 — Foundation
Implement:
	•	SEO properties
	•	Search properties
	•	Google Search Console connection
	•	Data synchronization
	•	Query and page records
	•	Basic dashboard
	•	Data freshness
Phase 2 — Opportunity Engine
Implement:
	•	Query classification
	•	Opportunity records
	•	Deterministic detectors
	•	Deduplication
	•	Scoring
	•	Validation
Phase 3 — Recommendation Management
Implement:
	•	Recommendation drafts
	•	Evidence
	•	Approval
	•	Assignment
	•	Comments
	•	Notifications
Phase 4 — Site Intelligence
Implement:
	•	Crawl
	•	Page inventory
	•	Technical issues
	•	Sitemap comparison
	•	Internal links
	•	Content hashes
Phase 5 — Implementation
Implement:
	•	Task tracking
	•	GitHub integration
	•	CMS adapter
	•	Deployment evidence
	•	Verification
Phase 6 — Measurement
Implement:
	•	Baselines
	•	Post-change windows
	•	Outcome classification
	•	Performance reporting
	•	Recommendation effectiveness
Phase 7 — Advanced Local SEO
Implement:
	•	Local rank grids
	•	Location targets
	•	City-service analysis
	•	Competitor visibility
	•	Local organic and GBP coordination
 
⸻
 
13.116 Future SEO Capabilities
Potential future additions include:
	•	Bing Webmaster Tools
	•	PageSpeed and Core Web Vitals
	•	Advanced schema validation
	•	Backlink analysis
	•	Automated internal-link deployment
	•	Search-result feature tracking
	•	Market-share modeling
	•	Content-decay forecasting
	•	Conversion-value modeling
	•	Multi-location portfolio benchmarking
	•	Algorithm-update annotations
	•	Advanced experimentation
	•	Automated pull-request generation
	•	Client opportunity forecasting
Future capabilities must preserve the product’s evidence, approval, verification, and measurement model.
 
⸻
 
13.117 SEO Guardrails
The following are prohibited unless formally approved:
	1.	Creating recommendations without evidence
	2.	Treating search volume as the sole priority signal
	3.	Treating average position as an exact rank
	4.	Combining query and keyword concepts without labels
	5.	Creating location pages for unsupported areas
	6.	Creating service pages for services not offered
	7.	Generating large numbers of near-duplicate pages
	8.	Publishing AI-generated SEO content without validation
	9.	Inventing business facts
	10.	Inventing menu items, services, locations, credentials, awards, or hours
	11.	Automatically consolidating pages based only on query overlap
	12.	Deleting pages without preservation and redirect analysis
	13.	Modifying repository files based on unverified URL mapping
	14.	Publishing directly from a recommendation without implementation controls
	15.	Marking implementation complete without live verification
	16.	Declaring success without a defined measurement period
	17.	Presenting correlation as causation
	18.	Ignoring data freshness or provider limitations
	19.	Allowing failed syncs to overwrite prior valid data
	20.	Exposing provider credentials to product users
	21.	Running uncontrolled crawls
	22.	Treating every crawler warning as a business priority
	23.	Allowing AI to set business value or service availability
	24.	Allowing a product user to access unrelated client data
	25.	Creating duplicate recommendations for the same unresolved issue
	26.	Using hidden or unexplained opportunity scores
	27.	Treating local-grid scans as exact customer behavior
	28.	Allowing client reports to conceal meaningful declines
	29.	Recommending a new page before checking existing content
	30.	Making autonomous production changes without permissions, approval, testing, and audit
 
⸻
 
13.118 Section Decisions
This section establishes the following decisions:
	1.	The SEO product manages the complete lifecycle from data collection through measurement.
	2.	An opportunity is the central SEO business object.
	3.	SEO recommendations must be evidence-backed, explainable, and measurable.
	4.	Search queries and tracked keywords remain distinct concepts.
	5.	Pages, queries, clusters, services, locations, competitors, issues, opportunities, recommendations, implementations, verifications, and outcomes are explicit domain objects.
	6.	Google Search Console is the initial primary search-performance source.
	7.	GA4 may supplement search data with on-site conversion and engagement data.
	8.	The platform uses controlled crawling for page and technical analysis.
	9.	URL normalization, property mapping, and date-window handling are foundational requirements.
	10.	Opportunity scoring combines search potential, business value, relevance, confidence, competition, urgency, and effort.
	11.	Scores are prioritization aids rather than ranking predictions.
	12.	Deterministic detectors identify candidate opportunities before AI analysis.
	13.	AI supports classification, clustering, summarization, recommendation drafting, and reporting.
	14.	AI does not independently determine service availability, location eligibility, publication, deletion, or strategic priority.
	15.	New-page recommendations require evidence, business relevance, existing-content review, and differentiation.
	16.	Restaurant and home-service SEO use shared architecture with industry-specific opportunity logic.
	17.	Products may create content or implementation requests through shared workflows, but SEO does not directly own another product’s internal state.
	18.	Approved recommendations create separate implementation tasks.
	19.	Implementation is not complete until live verification passes.
	20.	Verified changes enter defined measurement periods.
	21.	Outcomes may be positive, neutral, negative, inconclusive, or not measurable.
	22.	Client reporting distinguishes data, completed work, outcomes, limitations, and next priorities.
	23.	The SEO product must remain fully operable through human workflows when AI is unavailable.
	24.	Repository and CMS changes require explicit permissions, approval, testing, audit, and recovery controls.
	25.	The minimum viable SEO product includes Search Console sync, page and query records, opportunity detection, recommendation management, implementation tracking, verification, measurement, and reporting.

---

Section 14 — Google Business Profile Product Specification
14.1 Purpose of This Product
The Google Business Profile product helps LILOs manage, optimize, monitor, publish to, and measure Google Business Profiles across one or many business locations.
It is designed to provide a controlled operating system for local-profile management.
The product must support:
	•	Profile connection and resource mapping
	•	Business-information synchronization
	•	Category management
	•	Hours and special-hours management
	•	Attribute monitoring
	•	Service and menu visibility
	•	Photo and media management
	•	Google Post planning and publication
	•	Profile completeness analysis
	•	Local relevance recommendations
	•	Performance-data collection
	•	Change detection
	•	Multi-location management
	•	Approval workflows
	•	Publication verification
	•	Error recovery
	•	Client reporting
	•	Coordination with Reviews, SEO, Content, and Insights
The product must preserve an accurate representation of the business.
It must not optimize a profile through unsupported claims, misleading categories, fabricated services, inaccurate hours, or unapproved business information.
 
⸻
 
14.2 Business Problem
Google Business Profile management commonly suffers from:
	•	Inconsistent business information
	•	Incorrect or incomplete categories
	•	Conflicting hours
	•	Stale services
	•	Duplicated or provider-generated menu items
	•	Missing attributes
	•	Poorly planned posts
	•	Unclear profile ownership
	•	Expired OAuth authorization
	•	Changes made without approval
	•	Profile edits that are not verified after publication
	•	Performance metrics viewed without operational context
	•	Multiple locations managed inconsistently
	•	No record of what changed, why, or by whom
	•	Recommendations based on generic local SEO advice rather than the actual business
The product must provide the full operating loop:
Connect
    ↓
Discover
    ↓
Normalize
    ↓
Compare
    ↓
Recommend
    ↓
Approve
    ↓
Publish
    ↓
Verify
    ↓
Monitor
    ↓
Measure
The product is not only a posting tool.
It is the system of record and operational workflow for profile management.
 
⸻
 
14.3 Product Goals
The Google Business Profile product should:
	1.	Maintain accurate profile information.
	2.	Improve profile relevance without violating provider rules.
	3.	Detect unexpected or unauthorized changes.
	4.	Standardize GBP management across client locations.
	5.	Support controlled category optimization.
	6.	Manage regular and special hours accurately.
	7.	Provide a reliable Google Post workflow.
	8.	Improve profile completeness.
	9.	Track provider synchronization and data freshness.
	10.	Measure profile performance.
	11.	Support multi-location businesses.
	12.	Reduce duplicate manual work.
	13.	Coordinate profile operations with SEO and Content.
	14.	Preserve human approval for material profile changes.
	15.	Remain independent from the internal structure of the Google API.
 
⸻
 
14.4 Non-Goals
The initial GBP product is not:
	•	A replacement for the Google Business Profile interface in every circumstance
	•	A guaranteed local-pack ranking system
	•	A general social-media scheduler
	•	A review-response product
	•	An autonomous profile-editing bot
	•	A provider-policy bypass
	•	A method for keyword stuffing the business name
	•	A system for creating unsupported categories
	•	A system for fabricating services or attributes
	•	A duplicate-listing creation tool
	•	A general website menu-management system
	•	A substitute for human judgment during suspensions or reinstatement disputes
Review ingestion and response management belong primarily to the Reviews product.
The GBP product may display review summaries and route review events, but it should not duplicate the full Reviews domain.
 
⸻
 
14.5 Primary Users
GBP Strategist
Responsibilities:
	•	Review profile structure
	•	Validate categories
	•	Identify optimization opportunities
	•	Review recommendations
	•	Define post strategy
	•	Monitor profile health
 
⸻
 
GBP Operator
Responsibilities:
	•	Synchronize profile data
	•	Prepare updates
	•	Create post drafts
	•	Manage special hours
	•	Review provider errors
	•	Verify changes
 
⸻
 
Account Manager
Responsibilities:
	•	Coordinate business information
	•	Request client confirmation
	•	Manage approvals
	•	Explain profile performance
	•	Escalate profile issues
 
⸻
 
Content Specialist
Responsibilities:
	•	Create Google Post copy
	•	Prepare media
	•	Ensure brand alignment
	•	Coordinate campaigns with the Content product
 
⸻
 
Client Administrator
Responsibilities:
	•	Connect Google account
	•	Confirm profile ownership
	•	Approve business-information changes
	•	Approve categories and hours
	•	Review scheduled posts
 
⸻
 
Client Approver
Responsibilities:
	•	Approve profile edits
	•	Approve public-facing posts
	•	Confirm factual business claims
 
⸻
 
Client Viewer
Responsibilities:
	•	View profile status
	•	View performance
	•	View completed work
	•	View scheduled and published posts
 
⸻
 
14.6 Product Scope
The GBP product contains the following functional areas:
Google Business Profile Product

├── Account Connections
├── Location Mapping
├── Profile Snapshot
├── Business Information
├── Categories
├── Hours
├── Attributes
├── Services and Menus
├── Photos and Media
├── Google Posts
├── Profile Recommendations
├── Change Detection
├── Performance Data
├── Publication
├── Verification
├── Reporting
└── Administration
 
⸻
 
14.7 Core Domain Objects
The primary domain objects are:
	•	GBP account
	•	GBP location
	•	Profile snapshot
	•	Profile field
	•	Category
	•	Category assignment
	•	Business hours
	•	Special hours
	•	Attribute
	•	Service item
	•	Menu source
	•	Menu item
	•	Media asset
	•	Media publication
	•	Google Post
	•	Post revision
	•	Recommendation
	•	Profile change request
	•	Publication attempt
	•	Verification record
	•	Provider event
	•	Performance observation
	•	Data freshness record
	•	Suspension or restriction case
	•	Report
 
⸻
 
14.8 GBP Account
A GBP account represents a Google account or business account available through an integration connection.
Recommended fields:
id
organization_id
integration_connection_id
provider_account_id
account_name
account_type
status
permission_level
last_discovered_at
created_at
updated_at
Possible account types:
personal
business_group
organization
unknown
The platform must not assume the connected Google user owns every discovered location.
 
⸻
 
14.9 GBP Location
A GBP location represents a Google Business Profile resource mapped to a LILOs organization and location.
Recommended fields:
id
organization_id
location_id
gbp_account_id
provider_location_id
store_code
title
primary_category_id
profile_status
verification_state
provider_state
last_synced_at
last_verified_at
created_at
updated_at
The mapping must be explicit.
A provider location must not be attached to a LILOs location solely because names are similar.
 
⸻
 
14.10 Location Mapping
Mapping should evaluate:
	•	Business name
	•	Address
	•	Phone
	•	Website
	•	Store code
	•	Provider resource ID
	•	Geographic coordinates
	•	Existing manual confirmation
Mapping states:
unmapped
suggested
confirmed
conflicted
disconnected
archived
A conflicted mapping must block publication until resolved.
 
⸻
 
14.11 Profile Snapshot
A profile snapshot stores the normalized state of a GBP location at a specific time.
Recommended fields:
id
gbp_location_id
captured_at
source
provider_updated_at
profile_hash
raw_payload_reference
normalized_payload
sync_status
Snapshots allow the product to detect:
	•	Provider changes
	•	Client changes
	•	Google-suggested changes
	•	Unexpected field changes
	•	Publication results
	•	Drift from approved configuration
Raw provider payloads should follow short-term retention and privacy controls.
 
⸻
 
14.12 Profile Fields
Profile fields may include:
	•	Business name
	•	Primary category
	•	Additional categories
	•	Address
	•	Service area
	•	Phone
	•	Additional phones
	•	Website
	•	Appointment URL
	•	Menu URL
	•	Order URL
	•	Reservation URL
	•	Description
	•	Opening date
	•	Regular hours
	•	Special hours
	•	More hours
	•	Attributes
	•	Services
	•	Business status
	•	Coordinates
Each field should preserve:
current_provider_value
approved_platform_value
proposed_value
source
last_changed_at
last_changed_by
verification_status
 
⸻
 
14.13 Field Authority
Not all fields have the same authority source.
Recommended authority order:
Verified client information
    ↓
Approved organization configuration
    ↓
Approved location configuration
    ↓
Verified external provider state
    ↓
Imported website information
    ↓
AI-derived suggestion
AI-generated or inferred values must never become authoritative without review.
 
⸻
 
14.14 Profile Status
Possible profile states include:
active
pending_verification
verification_required
suspended
disabled
duplicate
moved
permanently_closed
temporarily_closed
restricted
unknown
The platform must preserve the provider’s state while also presenting a normalized operational interpretation.
 
⸻
 
14.15 Product Health
Product health is separate from profile state.
Possible health states:
healthy
connection_required
permission_missing
mapping_required
sync_delayed
provider_degraded
publication_blocked
verification_required
suspended
configuration_required
Example:
Profile state: Active
Product health: Connection Required
 
⸻
 
14.16 Category Model
The product should maintain a provider category registry.
Recommended fields:
id
provider_category_id
display_name
language_code
country_code
status
first_seen_at
last_seen_at
metadata
Provider categories may change over time.
The registry must be refreshed rather than hardcoded indefinitely.
 
⸻
 
14.17 Category Assignment
Category assignments should include:
id
gbp_location_id
category_id
assignment_type
status
source
approved_by
published_at
verified_at
Assignment types:
primary
additional
proposed
historical
Only one primary category may be active.
 
⸻
 
14.18 Category Strategy
Category recommendations should consider:
	•	Actual business model
	•	Primary revenue activity
	•	Services or cuisine actually offered
	•	Provider category availability
	•	Current primary category
	•	Current additional categories
	•	Local competitor patterns
	•	Search relevance
	•	Business positioning
	•	Provider policy risk
Categories must describe the business.
They must not be selected merely because a keyword has search volume.
 
⸻
 
14.19 Primary Category Rules
The primary category should represent the business’s principal function.
The product must not recommend changing the primary category based only on:
	•	One keyword
	•	One rank scan
	•	One competitor
	•	A temporary campaign
	•	A secondary service
	•	A seasonal offer
A primary category recommendation requires explicit rationale and approval.
 
⸻
 
14.20 Additional Category Rules
Additional categories may represent meaningful secondary functions.
Before recommending an additional category, confirm:
	•	The business genuinely performs that function.
	•	The category is available in the relevant region.
	•	The category is materially relevant.
	•	The category does not misrepresent the business.
	•	The category does not duplicate the primary category without value.
The product should avoid adding every remotely related category.
 
⸻
 
14.21 Category Recommendation Record
A category recommendation should include:
current_primary_category
current_additional_categories
proposed_primary_category
proposed_additional_categories
business_evidence
search_evidence
competitor_evidence
provider_availability
risk
expected_effect
approval_required
The recommendation should state whether it proposes:
	•	No change
	•	Additional category
	•	Primary category change
	•	Category removal
	•	Category order review
 
⸻
 
14.22 Business Name
The platform should preserve the real-world business name.
The product must prohibit:
	•	Keyword stuffing
	•	Location stuffing
	•	Service stuffing
	•	Promotional language
	•	Unverified legal-name changes
	•	Temporary campaign text
Any proposed business-name change must be based on documented real-world branding and require elevated approval.
 
⸻
 
14.23 Address and Service Area
The product should support:
	•	Storefront businesses
	•	Service-area businesses
	•	Hybrid businesses
	•	Hidden-address configurations
	•	Multiple service areas
Address or service-area changes require:
	•	Client confirmation
	•	Provider capability validation
	•	Risk warning
	•	Approval
	•	Post-publication verification
Address changes may trigger provider reverification or suspension risk.
The interface must communicate that risk before publication.
 
⸻
 
14.24 Phone Numbers
Phone fields should distinguish:
	•	Primary phone
	•	Additional phone
	•	Tracking number
	•	Underlying business number
Call-tracking configurations must preserve provider requirements and business continuity.
The product must not replace a phone number without confirming:
	•	Ownership
	•	Routing
	•	Tracking configuration
	•	Client approval
	•	Rollback path
 
⸻
 
14.25 Website and Action URLs
URL fields may include:
	•	Website
	•	Appointment
	•	Reservation
	•	Menu
	•	Order
	•	Product
	•	Event
Each URL should be validated for:
	•	HTTPS
	•	Correct organization
	•	Correct location
	•	Response status
	•	Redirect destination
	•	Tracking parameters
	•	Mobile usability
	•	Intended function
The system should identify when a URL redirects to an unexpected host or unrelated location.
 
⸻
 
14.26 UTM Configuration
The platform may add approved UTM parameters to GBP URLs.
UTM configuration should be standardized.
Example structure:
utm_source=google
utm_medium=organic
utm_campaign=gbp
utm_content={location_or_action}
The exact convention should be configurable and documented.
The product must avoid creating duplicate or conflicting tracking parameters.
 
⸻
 
14.27 Business Description
The business description should reflect:
	•	Actual business identity
	•	Primary offering
	•	Location
	•	Differentiating factual information
	•	Approved claims
	•	Brand voice
It must not contain:
	•	Unsupported superlatives
	•	Promotional offers that violate provider rules
	•	URLs where prohibited
	•	Keyword repetition
	•	Fake awards
	•	Unverified dates
	•	Services not offered
AI may draft descriptions, but all business facts require validation.
 
⸻
 
14.28 Regular Hours
Regular hours should support:
	•	Day-of-week periods
	•	Split hours
	•	Overnight periods
	•	Closed days
	•	24-hour operation
	•	Multiple hour types where supported
Recommended fields:
gbp_location_id
day_of_week
open_time
close_time
period_index
source
effective_from
effective_to
status
The product must not force one open-close period per day.
 
⸻
 
14.29 Hours Authority
Hours may originate from:
	•	Client-confirmed schedule
	•	Approved platform configuration
	•	Website
	•	Booking system
	•	Restaurant platform
	•	Provider state
	•	Manual input
The effective value must identify its authority source.
A website conflict should create a warning, not silently overwrite approved hours.
 
⸻
 
14.30 Special Hours
Special hours should support:
	•	Holidays
	•	Temporary closures
	•	Extended hours
	•	Reduced hours
	•	Special events
	•	Seasonal exceptions
Recommended fields:
gbp_location_id
date
open_periods
is_closed
reason
source
approval_status
publication_status
Special hours should override regular hours only for the specified date.
 
⸻
 
14.31 Special-Hours Workflow
Upcoming Date Detected
    ↓
Determine Whether Special Hours Are Required
    ↓
Request or Import Confirmed Hours
    ↓
Validate
    ↓
Approve
    ↓
Publish
    ↓
Verify
    ↓
Return to Regular Schedule Automatically
The system must not guess holiday hours.
 
⸻
 
14.32 More Hours
The product should support provider-defined secondary hour types where relevant.
Examples may include:
	•	Brunch
	•	Happy hour
	•	Delivery
	•	Takeout
	•	Pickup
	•	Kitchen
	•	Senior hours
	•	Drive-through
	•	Online service hours
More-hours fields must correspond to actual operations.
They should not conflict with regular business hours without explanation.
 
⸻
 
14.33 Attributes
Attributes may include:
	•	Accessibility
	•	Amenities
	•	Service options
	•	Payments
	•	Dining options
	•	Offerings
	•	Planning
	•	Crowd
	•	Business identity
	•	Health and safety
	•	Other provider-supported fields
Attributes should be stored as provider-defined values rather than assumed permanent schema fields.
 
⸻
 
14.34 Attribute Management
Attribute states should distinguish:
true
false
unknown
not_applicable
provider_unavailable
Unknown must not be treated as false.
AI must not infer sensitive or identity-related attributes.
 
⸻
 
14.35 Services
The GBP product should support service items where the provider and category allow them.
A service item may include:
id
gbp_location_id
provider_service_id
organization_service_id
name
description
price
price_type
category
source
status
Services should preferably reference the shared platform service catalog.
 
⸻
 
14.36 Service Quality Controls
Service items must:
	•	Represent actual services
	•	Use accurate names
	•	Avoid duplicate variants
	•	Avoid excessive keyword repetition
	•	Preserve approved pricing
	•	Match the relevant location
	•	Remain consistent with website and lead-routing configuration
The product must not create a service solely because a keyword ranks well.
 
⸻
 
14.37 Menus and Food Ordering
Restaurant profiles may receive menu data from:
	•	Google-managed sources
	•	Website structured data
	•	Toast
	•	Third-party ordering platforms
	•	Direct API connections
	•	Manual profile entry
	•	Other data partners
The platform must identify the likely source before attempting correction.
 
⸻
 
14.38 Menu Source Model
Recommended fields:
id
gbp_location_id
source_type
provider
external_resource_id
status
item_count
last_synced_at
authority_level
metadata
Possible source types:
google_generated
restaurant_platform
website
direct_integration
third_party_partner
manual
unknown
 
⸻
 
14.39 Menu Reconciliation
The product should compare menu sources for:
	•	Item count
	•	Categories
	•	Prices
	•	Availability
	•	Duplicates
	•	Stale items
	•	Incorrect names
	•	Location mismatch
A discrepancy should create a reconciliation task.
The platform must not delete menu data before identifying the authoritative source and the consequences of disconnection.
 
⸻
 
14.40 Media Assets
Media assets may include:
	•	Logo
	•	Cover
	•	Exterior
	•	Interior
	•	Product
	•	Food and drink
	•	Team
	•	At-work
	•	Rooms
	•	Common areas
	•	Other provider-supported types
Recommended fields:
id
organization_id
location_id
asset_type
storage_reference
source
caption
alt_text
status
approved_at
created_at
 
⸻
 
14.41 Media Publication
A media publication should record:
id
gbp_location_id
media_asset_id
provider_media_id
category
publication_status
published_at
verified_at
failure_reason
Media publication must validate:
	•	File format
	•	File size
	•	Dimensions
	•	Orientation
	•	Content policy
	•	Location relevance
	•	Approval
 
⸻
 
14.42 Media Quality
Media recommendations should prioritize:
	•	Authenticity
	•	Correct location
	•	Accurate product or service depiction
	•	Current business appearance
	•	Good composition
	•	Appropriate resolution
	•	Useful category coverage
The product must not upload misleading stock imagery as if it depicts the actual business.
AI-generated media requires explicit policy and disclosure handling.
 
⸻
 
14.43 Media Coverage Analysis
The product may analyze whether the profile has current coverage across relevant media types.
Example:
Logo: Present
Cover: Present
Exterior: Outdated
Interior: Limited
Food and drink: Healthy
Team: Missing
Coverage analysis should not reduce media quality to an arbitrary photo count.
 
⸻
 
14.44 Google Posts
The Google Posts capability should support:
	•	Draft creation
	•	Media selection
	•	Call-to-action selection
	•	Scheduling
	•	Approval
	•	Publication
	•	Verification
	•	Expiration tracking
	•	Performance tracking where available
	•	Reuse through controlled templates
 
⸻
 
14.45 Post Types
The product should support provider-available post types, such as:
update
offer
event
product
Post capabilities may vary by category, region, and provider policy.
The platform should discover capabilities rather than assume every type is available.
 
⸻
 
14.46 Google Post Record
Recommended fields:
id
organization_id
location_id
gbp_location_id
post_type
title
summary
call_to_action_type
call_to_action_url
start_at
end_at
scheduled_at
status
current_revision
source
campaign_id
created_by
approved_by
 
⸻
 
14.47 Post Status
Recommended lifecycle:
idea
draft
review
revision_required
approved
scheduled
publishing
published
verification_failed
failed
expired
cancelled
archived
A scheduled post must not be treated as published.
 
⸻
 
14.48 Post Revision
Each material edit should create a revision.
A post revision may include:
post_id
revision_number
summary
title
cta
url
media_asset_ids
start_at
end_at
content_hash
created_by
created_at
Approval applies to a specific revision.
 
⸻
 
14.49 Post Content Requirements
Google Post content should:
	•	Reflect the location
	•	Reflect the actual offer, event, service, or update
	•	Use current factual information
	•	Use a clear call to action
	•	Follow brand rules
	•	Avoid repetitive wording
	•	Avoid unsupported claims
	•	Avoid unnecessary keyword stuffing
	•	Respect provider restrictions
 
⸻
 
14.50 Restaurant Post Patterns
Restaurant post topics may include:
	•	Brunch
	•	Happy hour
	•	Private events
	•	Seasonal menu
	•	Live music
	•	Weekly specials
	•	Holiday hours
	•	Reservations
	•	Group dining
	•	New menu items
The system must verify:
	•	Dates
	•	Times
	•	Prices
	•	Menu items
	•	Availability
	•	Participating location
 
⸻
 
14.51 Home-Service Post Patterns
Home-service post topics may include:
	•	Seasonal service reminders
	•	Emergency services
	•	Maintenance
	•	Financing
	•	Service-area updates
	•	Safety information
	•	Completed projects
	•	Educational content
	•	Promotions
The system must verify:
	•	Service availability
	•	Service areas
	•	Licensing claims
	•	Financing terms
	•	Offer dates
	•	Emergency availability
 
⸻
 
14.52 Post Scheduling
Scheduling must use the relevant location timezone.
The scheduler should validate:
	•	Approved revision
	•	Active profile
	•	Valid connection
	•	Available post type
	•	Media readiness
	•	CTA URL
	•	Start and end time
	•	No duplicate scheduled publication
	•	Entitlement
	•	Runtime controls
 
⸻
 
14.53 Recurring Post Strategy
The product may support recurring post templates.
A recurring strategy should define:
	•	Product or campaign
	•	Cadence
	•	Eligible locations
	•	Post type
	•	Content source
	•	Approval policy
	•	Variation requirements
	•	Start date
	•	End date
	•	Pause conditions
Recurring generation must not publish the same copy repeatedly without review controls.
 
⸻
 
14.54 Post Publication Workflow
Approved Post
    ↓
Validate Current Revision
    ↓
Validate Profile and Connection
    ↓
Validate Provider Capability
    ↓
Reserve Publication
    ↓
Upload Media if Required
    ↓
Publish Post
    ↓
Store Provider ID
    ↓
Verify
    ↓
Record Result
    ↓
Notify
Provider calls should occur outside long-running database transactions.
 
⸻
 
14.55 Publication Idempotency
A post publication must use an internal idempotency key based on:
	•	GBP location
	•	Post
	•	Approved revision
	•	Scheduled execution
Before retrying, the system should check whether the provider already created the post.
Blind retry is prohibited.
 
⸻
 
14.56 Publication Verification
Verification should confirm:
	•	Provider post exists
	•	Correct location
	•	Correct post type
	•	Correct text
	•	Correct CTA
	•	Correct URL
	•	Correct media
	•	Correct dates
	•	Provider state
Verification may result in:
verified
partial
failed
provider_delayed
manual_review_required
 
⸻
 
14.57 Post Expiration
The platform should track post expiration or end state.
Expired posts should remain in platform history.
The platform may create a follow-up when:
	•	An offer ends
	•	An event passes
	•	A recurring post needs replacement
	•	A seasonal campaign concludes
 
⸻
 
14.58 Post Templates
Post templates may provide reusable structure.
Templates should contain:
	•	Purpose
	•	Industry
	•	Post type
	•	Required facts
	•	Optional sections
	•	CTA rules
	•	Prohibited claims
	•	Media guidance
Templates should not contain permanent location-specific facts unless deliberately scoped.
 
⸻
 
14.59 Profile Recommendations
Recommendations may include:
	•	Category review
	•	Missing attribute
	•	Hours conflict
	•	Special-hours requirement
	•	Website URL issue
	•	Missing action link
	•	Description update
	•	Service cleanup
	•	Menu reconciliation
	•	Media gap
	•	Post cadence
	•	Profile inconsistency
	•	Provider-state issue
	•	Location mapping issue
 
⸻
 
14.60 Recommendation Record
Recommended fields:
id
gbp_location_id
recommendation_type
title
summary
current_value
proposed_value
evidence
risk
priority
confidence
status
created_by
approved_by
 
⸻
 
14.61 Recommendation Status
Recommended lifecycle:
detected
needs_validation
validated
recommended
approved
rejected
deferred
publishing
implemented
verified
failed
closed
 
⸻
 
14.62 Recommendation Quality
A recommendation must state:
	•	Current profile state
	•	Proposed change
	•	Business justification
	•	Search or profile evidence
	•	Provider risk
	•	Expected effect
	•	Required approval
	•	Verification method
Generic advice such as “add more keywords” is invalid.
 
⸻
 
14.63 Deterministic Profile Detectors
Initial detectors should include:
	•	Missing primary category
	•	Excessive or suspicious category changes
	•	Website URL unavailable
	•	URL redirects to unrelated host
	•	Hours conflict
	•	Missing holiday hours
	•	Authorization expired
	•	Profile mapping conflict
	•	Missing phone
	•	Missing business description
	•	Missing eligible attributes
	•	Inconsistent service area
	•	Stale media coverage
	•	No recent posts
	•	Failed publication
	•	Unverified publication
	•	Menu-source discrepancy
	•	Unexpected provider field change
	•	Duplicate external resource mapping
 
⸻
 
14.64 Profile Completeness
Profile completeness should be calculated from relevant eligible fields.
It must account for:
	•	Category
	•	Country
	•	Business type
	•	Provider capabilities
	•	Location type
	•	Industry
	•	Available attributes
The platform must not penalize a profile for fields that are unavailable or inapplicable.
A completeness score should show its components.
 
⸻
 
14.65 Change Detection
The system should compare profile snapshots and identify:
	•	User-approved changes
	•	Provider normalization
	•	Google updates
	•	External user changes
	•	Unexpected changes
	•	Removed fields
	•	New fields
	•	Category changes
	•	Hours changes
	•	URL changes
	•	Status changes
 
⸻
 
14.66 Change Classification
Changes may be classified as:
expected
approved
provider_normalization
external_user_change
google_suggested_change
unexpected
high_risk
unknown
High-risk unexpected changes should generate alerts.
 
⸻
 
14.67 Profile Change Request
A proposed material edit should create a profile change request.
Recommended fields:
id
gbp_location_id
field_name
current_value
proposed_value
reason
risk
status
revision
requested_by
approved_by
published_at
verified_at
 
⸻
 
14.68 Change Request Workflow
Recommendation or Manual Request
    ↓
Validate Proposed Value
    ↓
Compare With Current Snapshot
    ↓
Assess Risk
    ↓
Request Approval
    ↓
Publish
    ↓
Refresh Snapshot
    ↓
Verify
    ↓
Close or Escalate
 
⸻
 
14.69 High-Risk Profile Changes
High-risk changes include:
	•	Business name
	•	Primary category
	•	Address
	•	Service-area configuration
	•	Primary phone
	•	Website domain
	•	Business status
	•	Marking temporarily or permanently closed
	•	Reopening
	•	Profile ownership changes
	•	Major category removal
These require:
	•	Elevated permission
	•	Explicit confirmation
	•	Client approval where applicable
	•	Current snapshot
	•	Rollback or recovery plan
	•	Post-change verification
 
⸻
 
14.70 Performance Data
The product should ingest available GBP performance data.
Potential metrics include:
	•	Search impressions
	•	Maps impressions
	•	Website clicks
	•	Calls
	•	Direction requests
	•	Bookings
	•	Menu clicks
	•	Food-ordering actions
	•	Messages where available
	•	Conversation or interaction metrics
	•	Device or platform splits where available
Provider definitions may change.
The platform must version normalized metric mappings.
 
⸻
 
14.71 Performance Observation
Recommended fields:
id
gbp_location_id
metric_date
metric_type
value
dimensions
source
provider_definition_version
synced_at
Raw and aggregated data should remain distinguishable.
 
⸻
 
14.72 Data Freshness
The product must display:
	•	Last provider data date
	•	Last successful sync
	•	Expected provider delay
	•	Current freshness state
	•	Partial-data warnings
	•	Provider limitations
The interface should not label data delayed merely because the provider normally publishes it later.
 
⸻
 
14.73 Performance Sync Workflow
Schedule
    ↓
Validate Connection
    ↓
Determine Provider-Available Date Range
    ↓
Retrieve Metrics
    ↓
Normalize
    ↓
Store
    ↓
Run Data Quality Checks
    ↓
Update Freshness
    ↓
Refresh Reports
A failed new sync must not overwrite prior valid data.
 
⸻
 
14.74 Data Quality Checks
Checks should detect:
	•	Sudden zero values
	•	Missing date ranges
	•	Duplicate metrics
	•	Location mismatch
	•	Metric-definition changes
	•	Partial responses
	•	Provider lag
	•	Unexplained discontinuity
	•	Invalid negative values
	•	Unexpected resource changes
 
⸻
 
14.75 GBP and SEO Coordination
The GBP product may publish platform events such as:
gbp.category_changed
gbp.website_url_changed
gbp.hours_changed
gbp.performance_updated
gbp.profile_suspended
gbp.location_mapped
The SEO product may consume relevant events.
Examples:
	•	Category change may trigger local visibility monitoring.
	•	Website URL change may trigger URL verification.
	•	Performance update may refresh Insights.
The GBP product does not directly modify SEO recommendations or ranking records.
 
⸻
 
14.76 GBP and Reviews Coordination
The GBP product may:
	•	Provide the connected profile resource
	•	Display review counts and summaries
	•	Route new-review events
	•	Show response-product health
The Reviews product owns:
	•	Review records
	•	Risk classification
	•	Draft responses
	•	Approval
	•	Response publication
The products must not maintain conflicting review-response state.
 
⸻
 
14.77 GBP and Content Coordination
The Content product may provide:
	•	Campaign ideas
	•	Approved content
	•	Media assets
	•	Event details
	•	Offer details
	•	Brand guidance
The GBP product converts approved material into provider-specific posts.
The Content product does not directly publish through Google unless using the GBP product’s publication workflow.
 
⸻
 
14.78 GBP and Insights Coordination
The Insights product may consume:
	•	Performance observations
	•	Profile status
	•	Completed profile changes
	•	Published posts
	•	Data freshness
	•	Recommendation outcomes
Insights does not become the authoritative source for GBP state.
 
⸻
 
14.79 AI Responsibilities
AI may assist with:
	•	Post drafting
	•	Description drafting
	•	Recommendation summaries
	•	Category evidence summaries
	•	Attribute review summaries
	•	Menu discrepancy summaries
	•	Performance interpretation
	•	Change summaries
	•	Media caption drafting
	•	Multi-location content variation
AI must not independently determine:
	•	The legal business name
	•	Business address
	•	Service areas
	•	Hours
	•	Prices
	•	Menu items
	•	Services
	•	Amenities
	•	Primary category
	•	Profile ownership
	•	Closure status
	•	Publication approval
 
⸻
 
14.80 AI Task Registry
Initial tasks may include:
gbp.post_draft
gbp.post_variation
gbp.description_draft
gbp.recommendation_summary
gbp.category_analysis
gbp.profile_change_summary
gbp.menu_discrepancy_summary
gbp.performance_summary
gbp.media_caption
Each task requires:
	•	Input schema
	•	Output schema
	•	Grounding requirements
	•	Validation
	•	Approval policy
	•	Evaluation criteria
 
⸻
 
14.81 Post Draft Output
Example schema:
{
  "post_type": "update",
  "summary": "Join us for weekend brunch in Little Italy with a menu built for relaxed mornings and group celebrations.",
  "call_to_action": {
    "type": "learn_more",
    "url_reference": "brunch_page"
  },
  "required_fact_checks": [
    "Confirm brunch days and hours.",
    "Confirm current reservation URL."
  ],
  "risk_flags": [],
  "requires_human_review": true
}
The model should reference approved URL records rather than inventing URLs.
 
⸻
 
14.82 Category Analysis Output
Example schema:
{
  "current_primary_category": "Bar",
  "proposed_action": "review_primary_category",
  "candidate_categories": [
    {
      "category": "Restaurant",
      "assignment_type": "additional",
      "business_evidence": [
        "The location operates a full food menu."
      ],
      "confidence": "high"
    }
  ],
  "unsupported_categories": [],
  "requires_human_review": true
}
The AI output is a recommendation draft, not an authorized category change.
 
⸻
 
14.83 AI Grounding
GBP AI tasks should be grounded in:
	•	Approved business facts
	•	Current provider snapshot
	•	Category registry
	•	Product capabilities
	•	Organization brand rules
	•	Location configuration
	•	Services
	•	Menus
	•	Hours
	•	Approved campaign information
	•	Media assets
	•	Performance data
General web knowledge must not override approved client data.
 
⸻
 
14.84 AI Validation
AI output should be validated for:
	•	Correct organization
	•	Correct location
	•	Supported business facts
	•	Current hours
	•	Current dates
	•	Current pricing
	•	Available services
	•	Approved claims
	•	Provider character or field limits
	•	Duplicate copy
	•	Prohibited language
	•	Unsupported category
	•	Invalid URL
	•	Wrong CTA
	•	Cross-location contamination
 
⸻
 
14.85 Human Responsibilities
Humans remain responsible for:
	•	Business-information accuracy
	•	Category strategy
	•	Address changes
	•	Hours confirmation
	•	Offer validation
	•	Event validation
	•	Service and menu validation
	•	High-risk profile changes
	•	Publication approval
	•	Suspension response
	•	Client communication
 
⸻
 
14.86 Permissions
Recommended permissions:
gbp.view
gbp.view_performance
gbp.configure
gbp.connect
gbp.map_location
gbp.sync
gbp.create_post
gbp.edit_post
gbp.approve_post
gbp.publish_post
gbp.manage_media
gbp.create_change_request
gbp.approve_change
gbp.publish_change
gbp.manage_categories
gbp.manage_hours
gbp.manage_services
gbp.manage_menus
gbp.view_diagnostics
gbp.manage_runtime
gbp.export
Permissions should distinguish drafting from publishing.
 
⸻
 
14.87 Approval Policies
Approval should be configurable by action type.
Potential policies:
no_approval
internal_approval
client_approval
dual_approval
Recommended defaults:
	•	Routine post: internal or client policy
	•	Offer post: client approval
	•	Event post: client approval unless event data is already approved
	•	Additional category: client approval
	•	Primary category: dual approval
	•	Regular hours: client approval
	•	Special hours: client approval or trusted confirmed source
	•	Business name: dual approval
	•	Address: dual approval
	•	Permanent closure: dual approval and explicit confirmation
 
⸻
 
14.88 Notifications
Notifications may include:
	•	Connection requires attention
	•	Location mapping required
	•	Profile suspended
	•	Verification required
	•	Hours conflict detected
	•	Holiday hours required
	•	Post ready for approval
	•	Post published
	•	Post publication failed
	•	Profile change detected
	•	Change request ready for approval
	•	Change verification failed
	•	Menu discrepancy detected
	•	Data delayed
	•	Performance report ready
 
⸻
 
14.89 GBP Dashboard
The product overview should show:
	•	Profile state
	•	Product health
	•	Connection status
	•	Mapping status
	•	Last profile sync
	•	Last performance date
	•	Current categories
	•	Hours status
	•	Upcoming special-hours needs
	•	Scheduled posts
	•	Recent publications
	•	Pending approvals
	•	Current recommendations
	•	Critical alerts
	•	Performance summary
 
⸻
 
14.90 Profile Workspace
Recommended tabs:
Overview
Business Information
Categories
Hours
Services and Menus
Media
Posts
Performance
Recommendations
History
Visibility depends on provider capabilities and permissions.
 
⸻
 
14.91 Business Information View
The view should show:
	•	Current provider value
	•	Approved platform value
	•	Source
	•	Last changed
	•	Verification
	•	Conflicts
	•	Proposed changes
Material conflicts should be visually prominent.
 
⸻
 
14.92 Category Workspace
The category workspace should show:
	•	Current primary category
	•	Current additional categories
	•	Historical changes
	•	Provider availability
	•	Recommendations
	•	Competitor evidence where authorized
	•	Risks
	•	Approval status
The interface must not imply that adding more categories always improves performance.
 
⸻
 
14.93 Hours Workspace
The hours workspace should show:
	•	Regular hours
	•	More hours
	•	Special hours
	•	Upcoming holidays
	•	Source
	•	Conflicts
	•	Approval state
	•	Publication status
	•	Last verification
A calendar view may support special-hours planning.
 
⸻
 
14.94 Services and Menus Workspace
The workspace should display:
	•	Active sources
	•	Authority
	•	Item counts
	•	Discrepancies
	•	Duplicate items
	•	Stale items
	•	Pending reconciliation
	•	Current published state where available
The interface must explain when data is controlled by a third-party provider rather than directly editable through LILOs.
 
⸻
 
14.95 Media Workspace
The media workspace should support:
	•	Asset library
	•	Provider media
	•	Category coverage
	•	Approval
	•	Upload
	•	Publication status
	•	Verification
	•	Duplicate detection
	•	Rejected media
	•	Historical media
 
⸻
 
14.96 Posts Workspace
The posts workspace should support:
	•	Calendar
	•	List
	•	Drafts
	•	Pending approval
	•	Scheduled
	•	Publishing
	•	Published
	•	Failed
	•	Expired
Filters should include:
	•	Location
	•	Post type
	•	Campaign
	•	Status
	•	Author
	•	Scheduled date
	•	Approval state
 
⸻
 
14.97 Post Detail
A post detail should include:
	•	Current revision
	•	Preview
	•	Location
	•	Post type
	•	Text
	•	CTA
	•	URL
	•	Media
	•	Schedule
	•	Validation
	•	Approval
	•	Publication attempt
	•	Provider ID
	•	Verification
	•	History
	•	Performance where available
 
⸻
 
14.98 Recommendation Workspace
Recommendations should support filtering by:
	•	Location
	•	Recommendation type
	•	Priority
	•	Risk
	•	Status
	•	Assignee
	•	Detected date
The detail view should include:
	•	Current state
	•	Proposed state
	•	Evidence
	•	Provider implications
	•	Approval
	•	Publication
	•	Verification
	•	Outcome
 
⸻
 
14.99 Performance Workspace
The performance workspace should support:
	•	Date range
	•	Comparison period
	•	Location
	•	Metric
	•	Device or surface where available
	•	Annotations
	•	Data freshness
	•	Provider-definition notes
It should connect metric changes to:
	•	Profile edits
	•	Post campaigns
	•	Seasonal events
	•	Provider outages
	•	Data-definition changes
Without claiming causation where it cannot be established.
 
⸻
 
14.100 Multi-Location Operations
The product should support:
	•	Portfolio overview
	•	Location filters
	•	Shared templates
	•	Shared campaign scheduling
	•	Location-specific facts
	•	Bulk recommendations
	•	Bulk approval
	•	Bulk publication
	•	Per-location verification
	•	Per-item failure handling
Bulk actions must validate each location independently.
 
⸻
 
14.101 Bulk Post Campaigns
A multi-location post campaign should define:
campaign_name
eligible_locations
base_content
location_variables
media_policy
schedule_policy
approval_policy
variation_policy
Each location should receive its own post record and publication result.
One location failure must not hide successful publications elsewhere.
 
⸻
 
14.102 Cross-Location Content Controls
The platform should prevent:
	•	Wrong city
	•	Wrong address
	•	Wrong phone
	•	Wrong hours
	•	Wrong offer
	•	Wrong menu item
	•	Wrong service
	•	Wrong reservation URL
	•	Wrong media
Location-specific validation is mandatory before publication.
 
⸻
 
14.103 Suspension and Restriction Cases
The product should support operational tracking for:
	•	Suspension
	•	Disabled profile
	•	Duplicate listing
	•	Ownership conflict
	•	Verification failure
	•	Reverification
	•	Unauthorized changes
	•	Reinstatement request
Recommended case fields:
id
gbp_location_id
case_type
provider_state
detected_at
status
owner
evidence
submitted_at
provider_case_id
resolution
resolved_at
 
⸻
 
14.104 Suspension Workflow
Suspension Detected
    ↓
Block High-Risk Publication
    ↓
Capture Current Snapshot
    ↓
Assign Case
    ↓
Collect Evidence
    ↓
Review Recent Changes
    ↓
Prepare Submission
    ↓
Human Approval
    ↓
Submit Through Supported Channel
    ↓
Track
    ↓
Verify Resolution
The product must not promise reinstatement.
 
⸻
 
14.105 Suspension Evidence
Evidence may include:
	•	Business license
	•	Utility bill
	•	Lease
	•	Exterior signage
	•	Interior signage
	•	Website
	•	Domain ownership
	•	State registration
	•	Photos
	•	Recent profile-change history
Restricted documents require tighter access and retention controls.
 
⸻
 
14.106 Reporting Metrics
Client-facing GBP reporting may include:
	•	Search visibility metrics
	•	Maps visibility metrics
	•	Website clicks
	•	Calls
	•	Direction requests
	•	Bookings
	•	Menu actions
	•	Published posts
	•	Profile updates
	•	Media activity
	•	Profile completeness
	•	Data freshness
	•	Current issues
 
⸻
 
14.107 Reporting Interpretation
Reports should explain:
	•	What changed
	•	What work was completed
	•	Which metrics moved
	•	Which data is delayed
	•	Which issues remain
	•	What is planned next
	•	Which changes require client confirmation
Reports must not claim that one profile edit caused a ranking or conversion change without sufficient evidence.
 
⸻
 
14.108 Agency Reporting
Agency users should additionally see:
	•	Connection health
	•	Mapping conflicts
	•	Publication failure rate
	•	Verification failure rate
	•	Approval turnaround
	•	Post cadence
	•	Category-change history
	•	Special-hours completion
	•	Data freshness
	•	Provider quota usage
	•	AI edit rate
	•	Work backlog
 
⸻
 
14.109 Product Success Metrics
Operational Metrics
	•	Connection success rate
	•	Profile sync reliability
	•	Publication success rate
	•	Verification pass rate
	•	Performance-sync freshness
	•	Special-hours completion
	•	Mapping accuracy
	•	Reauthorization time
Quality Metrics
	•	Recommendation acceptance
	•	Recommendation rejection
	•	Post revision rate
	•	Unsupported fact rate
	•	Wrong-location error rate
	•	Duplicate post rate
	•	Unexpected profile-change detection
	•	Category recommendation precision
Business Metrics
	•	Increase in qualified profile interactions
	•	Improved local visibility
	•	Improved completeness
	•	Reduced stale information
	•	Reduced profile downtime
	•	Improved response to seasonal changes
	•	Consistent publishing
	•	Faster resolution of provider issues
 
⸻
 
14.110 Failure Modes
Expected failure modes include:
	•	OAuth authorization expired
	•	Required scope missing
	•	Account inaccessible
	•	Location not discovered
	•	Location mapped incorrectly
	•	Provider permission insufficient
	•	Profile suspended
	•	Profile requires verification
	•	Provider API unavailable
	•	Rate limit exceeded
	•	Partial profile response
	•	Unsupported field
	•	Category unavailable
	•	Post type unavailable
	•	Media rejected
	•	Publication timed out
	•	Publication succeeded but response failed
	•	Verification delayed
	•	Performance data delayed
	•	Menu controlled by third party
	•	Unexpected external edit
	•	Duplicate publication attempt
	•	Location-specific content mismatch
 
⸻
 
14.111 Failure Handling
Each failure should define:
	•	Error category
	•	Retry eligibility
	•	Publication risk
	•	User-visible explanation
	•	Internal diagnostic
	•	Required permission
	•	Recovery action
	•	Reconciliation behavior
	•	Escalation owner
The system must not overwrite the last valid profile state with an incomplete provider response.
 
⸻
 
14.112 Reconciliation
Reconciliation is required when:
	•	A post may have published but no provider ID was recorded.
	•	A profile change request timed out.
	•	Media upload status is ambiguous.
	•	Provider state differs from the approved platform state.
	•	A third-party menu source changed unexpectedly.
Reconciliation should:
	1.	Retrieve current provider state.
	2.	Compare against the intended action.
	3.	Identify matching external resources.
	4.	Update internal records.
	5.	Avoid duplicate action.
	6.	Create an exception if ambiguous.
 
⸻
 
14.113 Security Considerations
The product must protect:
	•	OAuth credentials
	•	Business account access
	•	Location ownership
	•	Sensitive suspension evidence
	•	Internal recommendations
	•	Publication authority
	•	Client configuration
	•	Performance data
Provider tokens must not be exposed to frontend code.
High-risk profile changes require elevated permission.
 
⸻
 
14.114 Privacy Considerations
GBP data is largely business information, but privacy concerns may include:
	•	Connected user identity
	•	Account email
	•	Support case documents
	•	Personal phone numbers
	•	Sensitive ownership records
	•	Internal notes
The platform should store only the provider-account identity required for operations.
 
⸻
 
14.115 Operational Requirements
The product requires:
	•	Scheduled profile synchronization
	•	Scheduled performance synchronization
	•	Category-registry refresh
	•	Special-hours reminders
	•	Post scheduler
	•	Publication worker
	•	Media worker
	•	Verification jobs
	•	Change-detection jobs
	•	Reconciliation jobs
	•	Provider-health monitoring
	•	Quota monitoring
	•	Runtime kill switches
 
⸻
 
14.116 Runtime Controls
Authorized operators should be able to:
	•	Pause all GBP publication
	•	Pause one organization
	•	Pause one location
	•	Pause profile edits
	•	Pause posts only
	•	Pause media uploads
	•	Pause performance sync
	•	Disable a provider capability
	•	Re-run profile sync
	•	Re-run verification
	•	Mark a provider incident
	•	Force manual approval
All controls must be audited.
 
⸻
 
14.117 Testing Requirements
Testing should cover:
	•	Tenant isolation
	•	Account discovery
	•	Location mapping
	•	Scope validation
	•	Category registry
	•	Primary-category rules
	•	Hours with split periods
	•	Overnight hours
	•	Special hours
	•	Attribute states
	•	Service mapping
	•	Menu-source reconciliation
	•	Media validation
	•	Post revisions
	•	Approval invalidation
	•	Scheduling timezone
	•	Publication idempotency
	•	Provider timeout
	•	Reconciliation
	•	Multi-location variation
	•	Wrong-location prevention
	•	Performance sync
	•	Data-delay handling
	•	Suspension state
	•	Permission checks
	•	Runtime controls
 
⸻
 
14.118 AI Evaluation Dataset
Evaluation examples should include:
	•	Restaurant posts
	•	Home-service posts
	•	Event posts
	•	Offer posts
	•	Category recommendations
	•	Unsupported categories
	•	Conflicting hours
	•	Menu-source discrepancies
	•	Multi-location variation
	•	Incorrect business facts
	•	Wrong-location information
	•	Unsupported claims
	•	Provider-limit scenarios
Human-reviewed examples should be versioned.
 
⸻
 
14.119 Minimum Viable GBP Product
The minimum viable product should include:
Connection
	•	Google OAuth
	•	Account discovery
	•	Location discovery
	•	Manual mapping
	•	Connection health
Profile
	•	Profile snapshot
	•	Business information
	•	Categories
	•	Regular hours
	•	Special hours
	•	Basic attributes
	•	Change detection
Posts
	•	Draft
	•	Approval
	•	Scheduling
	•	Publication
	•	Verification
	•	Failure recovery
Performance
	•	Scheduled metric sync
	•	Freshness
	•	Basic reporting
Operations
	•	Permissions
	•	Audit
	•	Notifications
	•	Runtime pause
	•	Manual operation without AI
 
⸻
 
14.120 Implementation Phases
Phase 1 — Connection and Profile Foundation
Implement:
	•	Google OAuth
	•	Account discovery
	•	Location discovery
	•	Mapping
	•	Profile snapshots
	•	Connection health
	•	Basic profile display
Phase 2 — Business Information and Categories
Implement:
	•	Normalized fields
	•	Category registry
	•	Category assignments
	•	Regular hours
	•	Special hours
	•	Change requests
	•	Approval
	•	Verification
Phase 3 — Google Posts
Implement:
	•	Post records
	•	Revisions
	•	Media
	•	Templates
	•	Scheduling
	•	Approval
	•	Publication
	•	Verification
	•	Reconciliation
Phase 4 — Performance
Implement:
	•	Performance sync
	•	Metric normalization
	•	Freshness
	•	Comparison views
	•	Reporting
Phase 5 — Recommendations
Implement:
	•	Deterministic detectors
	•	Completeness analysis
	•	AI-assisted summaries
	•	Recommendation workflow
	•	Outcome tracking
Phase 6 — Services, Menus, and Advanced Media
Implement:
	•	Service items
	•	Menu-source discovery
	•	Menu reconciliation
	•	Media coverage
	•	Media recommendations
Phase 7 — Multi-Location and Suspension Operations
Implement:
	•	Portfolio views
	•	Bulk campaigns
	•	Per-location variation
	•	Suspension cases
	•	Reinstatement tracking
	•	Advanced runtime controls
 
⸻
 
14.121 Future Capabilities
Potential future capabilities include:
	•	Provider-supported messaging
	•	Product catalog management
	•	Advanced booking-action monitoring
	•	Automated holiday-hours collection
	•	Franchise configuration templates
	•	Local-grid correlation
	•	Media performance analysis
	•	Image-quality scoring
	•	Post experiment analysis
	•	Provider suggestion review
	•	Automated profile-drift remediation
	•	Advanced duplicate-location detection
	•	Enhanced reinstatement case management
	•	Additional local listing providers
Future capabilities must preserve provider compliance, approval, verification, and tenant isolation.
 
⸻
 
14.122 GBP Guardrails
The following are prohibited unless formally approved:
	1.	Keyword stuffing the business name
	2.	Inventing business information
	3.	Adding unsupported categories
	4.	Changing the primary category based only on rank data
	5.	Adding every remotely relevant category
	6.	Publishing inaccurate hours
	7.	Guessing holiday hours
	8.	Publishing unverified offers or events
	9.	Creating services the business does not offer
	10.	Inventing menu items or prices
	11.	Removing menu sources without authority analysis
	12.	Publishing posts to the wrong location
	13.	Reusing location-specific copy without validation
	14.	Publishing an unapproved revision
	15.	Blindly retrying provider writes
	16.	Marking a post published before verification
	17.	Overwriting valid state with partial provider data
	18.	Treating unknown attributes as false
	19.	Uploading misleading media
	20.	Uploading AI-generated images as authentic location photography without explicit policy
	21.	Changing address without warning about provider risk
	22.	Changing closure status through an ordinary edit
	23.	Exposing OAuth tokens to users or AI
	24.	Treating completeness score as ranking proof
	25.	Claiming direct causation from profile edits without evidence
	26.	Hiding data delays
	27.	Combining Reviews workflow state with GBP publication state
	28.	Allowing bulk publication without per-location validation
	29.	Automatically resolving unexpected external changes
	30.	Allowing AI to publish high-risk profile edits autonomously
 
⸻
 
14.123 Acceptance Requirements
The initial GBP product is not production-ready until it supports:
	•	Google authentication
	•	Account discovery
	•	Location discovery
	•	Confirmed location mapping
	•	Profile snapshots
	•	Connection health
	•	Normalized business information
	•	Category registry
	•	Category management
	•	Regular hours
	•	Special hours
	•	Change requests
	•	Approval
	•	Google Post drafts
	•	Post revisions
	•	Scheduling
	•	Publication
	•	Idempotency
	•	Verification
	•	Reconciliation
	•	Performance synchronization
	•	Data freshness
	•	Notifications
	•	Reporting
	•	Permissions
	•	Audit history
	•	Multi-tenant isolation
	•	Provider failure handling
	•	Manual operation without AI
 
⸻
 
14.124 Section Decisions
This section establishes the following decisions:
	1.	The GBP product manages profile connection, normalization, optimization, publication, verification, monitoring, and reporting.
	2.	Each provider location is explicitly mapped to a LILOs organization and location.
	3.	Profile snapshots preserve provider state and support change detection.
	4.	Approved platform values and current provider values remain separately visible.
	5.	Category management uses a refreshed provider-category registry.
	6.	The primary category represents the business’s principal function and requires stronger approval controls.
	7.	Additional categories must describe genuine secondary functions.
	8.	Business names must reflect real-world branding and may not be keyword-stuffed.
	9.	Hours require an explicit authority source.
	10.	Special hours are date-specific overrides and must not be guessed.
	11.	Attributes preserve true, false, unknown, unavailable, and not-applicable states.
	12.	Services should reference the shared platform service catalog where possible.
	13.	Restaurant menu data requires source identification and reconciliation before modification.
	14.	Media must accurately depict the relevant business or offering.
	15.	Google Posts use versioned drafts, approval, scheduling, idempotent publication, and verification.
	16.	Approval applies to a specific post or change revision.
	17.	High-risk profile changes require elevated permission and explicit confirmation.
	18.	Profile lifecycle state and product operational health remain separate.
	19.	Performance data includes provider-delay and definition metadata.
	20.	The product coordinates with SEO, Reviews, Content, and Insights through events and service contracts.
	21.	AI supports drafting, classification, summarization, and analysis but does not establish authoritative business facts.
	22.	Bulk multi-location actions create and validate independent location-level records.
	23.	Provider writes require reconciliation when the outcome is ambiguous.
	24.	Suspensions and verification issues are tracked through dedicated cases.
	25.	The minimum viable product includes connection, profile state, categories, hours, posts, performance, approval, verification, reconciliation, reporting, and manual operation.


---

Section 15 — Reviews Product Specification
15.1 Purpose of This Product
The Reviews product helps LILOs collect, classify, prioritize, respond to, monitor, and measure customer reviews across supported platforms.
It is designed to provide a controlled operating system for reputation management.
The product must support:
	•	Review ingestion
	•	Platform and location mapping
	•	Review normalization
	•	Sentiment and topic classification
	•	Risk detection
	•	Response-priority scoring
	•	Draft generation
	•	Human editing
	•	Approval
	•	Publication
	•	Publication verification
	•	Escalation
	•	Internal notes
	•	Response-time tracking
	•	Multi-location management
	•	Reporting
	•	Recovery from provider failures
	•	Coordination with GBP, Insights, Leads, and Content
The product must preserve factual accuracy, brand appropriateness, and appropriate escalation.
It must not automatically respond to every review without considering risk, context, platform capability, and client policy.
 
⸻
 
15.2 Business Problem
Review management commonly suffers from:
	•	Reviews spread across multiple platforms
	•	Slow response times
	•	Inconsistent tone
	•	Generic responses
	•	High-risk reviews handled casually
	•	Sensitive claims overlooked
	•	Incorrect facts included in responses
	•	Responses published to the wrong location
	•	Duplicate responses
	•	No distinction between operational and legal risk
	•	Poor visibility into unresolved complaints
	•	No clear approval process
	•	No record of who approved or published a response
	•	Reporting focused only on average rating
	•	No connection between recurring review themes and business improvement
The product must support the full operating loop:
Collect
    ↓
Normalize
    ↓
Classify
    ↓
Prioritize
    ↓
Draft
    ↓
Review
    ↓
Approve
    ↓
Publish
    ↓
Verify
    ↓
Measure
    ↓
Learn
The Reviews product is not merely a response generator.
It is the system of record and workflow for reputation operations.
 
⸻
 
15.3 Product Goals
The Reviews product should:
	1.	Centralize reviews from supported platforms.
	2.	Map every review to the correct organization and location.
	3.	Identify high-risk reviews quickly.
	4.	Improve response speed.
	5.	Maintain a consistent but non-repetitive brand voice.
	6.	Prevent unsupported claims or admissions.
	7.	Preserve human review for sensitive cases.
	8.	Support configurable approval policies.
	9.	Publish responses safely and idempotently.
	10.	Verify provider publication.
	11.	Track unresolved operational issues.
	12.	Identify recurring customer-experience themes.
	13.	Support multi-location reporting.
	14.	Provide clear client-facing reputation reporting.
	15.	Remain usable when AI is unavailable.
 
⸻
 
15.4 Non-Goals
The initial Reviews product is not:
	•	A legal-advice system
	•	A crisis-communications replacement
	•	A customer-support ticketing platform
	•	A general social-listening platform
	•	A fake-review generator
	•	A review-gating system
	•	A review-removal guarantee
	•	A system for manipulating ratings
	•	A system for offering undisclosed incentives for positive reviews
	•	An autonomous responder for every review
	•	A substitute for internal operational correction
	•	A replacement for provider dispute and appeal processes
The product may identify potentially removable or policy-violating reviews, but it must not guarantee provider removal.
 
⸻
 
15.5 Primary Users
Reputation Strategist
Responsibilities:
	•	Define response policy
	•	Review risk rules
	•	Analyze reputation trends
	•	Review escalated cases
	•	Approve high-risk response strategies
 
⸻
 
Review Operator
Responsibilities:
	•	Review incoming reviews
	•	Correct classifications
	•	Prepare drafts
	•	Assign escalations
	•	Submit responses for approval
	•	Monitor publication
 
⸻
 
Account Manager
Responsibilities:
	•	Coordinate client input
	•	Review sensitive cases
	•	Explain trends
	•	Track unresolved operational issues
	•	Escalate legal or executive concerns
 
⸻
 
Client Administrator
Responsibilities:
	•	Configure review policies
	•	Approve sensitive responses
	•	Assign internal contacts
	•	Review performance
 
⸻
 
Client Approver
Responsibilities:
	•	Approve
	•	Reject
	•	Request revision
	•	Add factual context
	•	Confirm resolution language
 
⸻
 
Client Viewer
Responsibilities:
	•	View reviews
	•	View published responses
	•	View reporting
	•	View recurring themes
 
⸻
 
15.6 Product Scope
The Reviews product contains the following functional areas:
Reviews Product

├── Platform Connections
├── Review Ingestion
├── Review Normalization
├── Risk Classification
├── Topic Classification
├── Prioritization
├── Response Drafting
├── Approval
├── Publication
├── Verification
├── Escalation
├── Dispute Tracking
├── Theme Analysis
├── Reporting
└── Administration
 
⸻
 
15.7 Core Domain Objects
The primary domain objects are:
	•	Review source
	•	Review account
	•	Review location mapping
	•	Review
	•	Reviewer identity reference
	•	Review revision
	•	Rating
	•	Review topic
	•	Review classification
	•	Risk flag
	•	Response policy
	•	Response draft
	•	Response revision
	•	Approval request
	•	Response publication
	•	Verification
	•	Escalation case
	•	Dispute case
	•	Internal note
	•	Theme
	•	Performance observation
	•	Report
 
⸻
 
15.8 Review Source
A review source represents a supported provider.
Examples may include:
	•	Google
	•	Yelp
	•	Facebook
	•	TripAdvisor
	•	Industry-specific platforms
	•	First-party review systems
	•	Other approved providers
Recommended fields:
id
provider
display_name
status
capabilities
supports_read
supports_response
supports_edit
supports_delete
supports_webhooks
supports_rating
supports_media
metadata
Provider capabilities must be discovered or configured rather than assumed.
 
⸻
 
15.9 Review Account
A review account represents the connected provider account used to access reviews.
Recommended fields:
id
organization_id
integration_connection_id
provider
provider_account_id
account_name
status
permission_level
last_discovered_at
created_at
updated_at
The account must not be treated as authority for every discovered location without explicit mapping.
 
⸻
 
15.10 Review Location Mapping
A provider location must be mapped to a LILOs organization and location.
Recommended fields:
id
organization_id
location_id
review_account_id
provider_location_id
provider_location_name
status
confirmed_by
confirmed_at
Mapping states:
unmapped
suggested
confirmed
conflicted
disconnected
archived
Publication must be blocked for conflicted or unconfirmed mappings.
 
⸻
 
15.11 Review Record
A review record represents one provider review.
Recommended fields:
id
organization_id
location_id
review_source_id
provider_review_id
provider_location_id
reviewer_reference
rating
title
body
language
review_created_at
review_updated_at
ingested_at
status
provider_state
raw_payload_reference
The provider review ID and provider location ID should form part of duplicate prevention.
 
⸻
 
15.12 Review Status
Recommended review lifecycle:
new
classified
triaged
drafting
awaiting_approval
approved
publishing
responded
publication_failed
escalated
disputed
closed
archived
Review status should remain distinct from response status.
A review may remain active while a response is published.
 
⸻
 
15.13 Review Revisions
Some providers allow reviewers to edit reviews.
The product should preserve review revisions.
Recommended fields:
id
review_id
revision_number
rating
title
body
captured_at
content_hash
change_summary
A materially changed review should trigger:
	•	Reclassification
	•	Risk reassessment
	•	Response review
	•	Possible escalation
An existing response should not automatically remain appropriate after a material review change.
 
⸻
 
15.14 Reviewer Identity
The product should store only the reviewer identity information supplied by the provider and necessary for operations.
Possible fields:
display_name
provider_profile_reference
is_local_guide
review_count
avatar_reference
The platform should not attempt to enrich or identify anonymous reviewers through external investigation.
 
⸻
 
15.15 Rating Model
The product should support provider-specific rating scales.
Normalized rating fields may include:
provider_rating
provider_rating_max
normalized_rating
rating_band
Recommended normalized bands:
very_negative
negative
neutral
positive
very_positive
unrated
A three-star review may be operationally neutral or negative depending on provider and business context.
 
⸻
 
15.16 Review Language
The product should detect or preserve review language.
Recommended fields:
source_language
detected_language
response_language
translation_status
Responses should generally use the review’s language when:
	•	The organization supports that language.
	•	The response can be reviewed adequately.
	•	The provider supports publication.
	•	The client policy permits it.
Machine translation must be labeled and reviewed for sensitive cases.
 
⸻
 
15.17 Review Classification
Each review should receive structured classifications.
Possible dimensions:
	•	Sentiment
	•	Topic
	•	Risk
	•	Urgency
	•	Resolution need
	•	Response recommendation
	•	Business function
	•	Service
	•	Product
	•	Location detail
	•	Staff mention
	•	Repeat issue
	•	Suspected spam or policy violation
Classification should preserve confidence and source.
 
⸻
 
15.18 Sentiment Classification
Recommended sentiment classes:
strongly_negative
negative
mixed
neutral
positive
strongly_positive
unknown
Sentiment should not be inferred from rating alone.
A five-star review may contain a complaint.
A one-star review may contain minimal usable context.
 
⸻
 
15.19 Topic Classification
Topics may include:
Restaurant
	•	Food quality
	•	Service
	•	Wait time
	•	Reservations
	•	Pricing
	•	Cleanliness
	•	Atmosphere
	•	Noise
	•	Drinks
	•	Menu availability
	•	Parking
	•	Private events
	•	Hours
	•	Accessibility
Home Services
	•	Response time
	•	Technician conduct
	•	Work quality
	•	Pricing
	•	Estimate accuracy
	•	Scheduling
	•	Communication
	•	Cleanup
	•	Warranty
	•	Emergency response
	•	Office support
	•	Service area
	•	Safety
Topics should be configurable by industry.
 
⸻
 
15.20 Topic Record
Recommended fields:
id
industry_id
name
description
status
parent_topic_id
risk_defaults
Review-topic assignments should include:
review_id
topic_id
confidence
source
review_status
 
⸻
 
15.21 Risk Classification
Risk classification determines whether a review requires elevated handling.
Recommended risk levels:
low
moderate
high
critical
Risk is separate from rating.
A one-star complaint about a long wait may be moderate.
A five-star review containing personal medical information may still require privacy review.
 
⸻
 
15.22 Risk Flags
Potential risk flags include:
	•	Legal threat
	•	Litigation mention
	•	Regulatory complaint
	•	Safety allegation
	•	Injury allegation
	•	Discrimination allegation
	•	Harassment allegation
	•	Employee misconduct
	•	Criminal allegation
	•	Fraud allegation
	•	Chargeback or payment dispute
	•	Refund demand
	•	Privacy issue
	•	Personal data
	•	Health information
	•	Threat of violence
	•	Self-harm content
	•	Media or influencer escalation
	•	Government-agency mention
	•	Licensing issue
	•	Insurance issue
	•	Defamation concern
	•	Extortion or coercion
	•	Review manipulation allegation
Risk flags should be individually visible.
 
⸻
 
15.23 Critical Risk Rules
A critical review may require:
	•	Immediate notification
	•	Response pause
	•	Human-only drafting
	•	Legal or executive escalation
	•	Restricted access
	•	Evidence preservation
	•	No admission of liability
	•	No public discussion of personal data
	•	Separate internal response plan
The product must not provide legal conclusions.
It should identify risk and route the matter to qualified decision-makers.
 
⸻
 
15.24 Urgency
Recommended urgency levels:
routine
priority
urgent
immediate
Urgency may consider:
	•	Risk
	•	Rating
	•	Recency
	•	Public visibility
	•	Reviewer reach where supplied
	•	Existing client policy
	•	Unresolved operational impact
	•	Provider escalation
Urgency and risk should remain distinct.
 
⸻
 
15.25 Response Recommendation
The system should classify whether a response is:
recommended
optional
not_recommended
blocked
requires_escalation
Examples:
	•	Positive review with meaningful detail: recommended
	•	Empty five-star rating: optional
	•	Obvious spam under active dispute: may be not recommended
	•	Legal threat: requires escalation
	•	Privacy-sensitive review: blocked pending review
 
⸻
 
15.26 Priority Score
A response-priority score may consider:
	•	Risk
	•	Rating
	•	Review age
	•	Review detail
	•	Customer-impact severity
	•	Topic importance
	•	Response policy
	•	Public visibility
	•	Repeat issue
	•	Existing response state
	•	Client escalation rules
The score must remain explainable.
 
⸻
 
15.27 Priority Score Components
Recommended fields:
risk_score
urgency_score
rating_score
recency_score
detail_score
business_impact_score
policy_score
final_priority_score
calculation_version
The score should not be presented as a prediction of reputation damage.
It is a work-ordering mechanism.
 
⸻
 
15.28 Response Policy
Each organization or location should have a response policy.
Recommended fields:
id
organization_id
location_id
response_required
positive_review_policy
negative_review_policy
empty_review_policy
approval_policy
maximum_response_time
escalation_rules
language_policy
signoff_style
contact_offline_policy
status
Policies may inherit from organization to location.
 
⸻
 
15.29 Positive Review Policy
Positive response policies may define:
	•	Whether all positive reviews receive responses
	•	Minimum review detail
	•	Response cadence
	•	Personalization expectations
	•	Staff-name handling
	•	Service or menu references
	•	Signoff
	•	Brand style
	•	Repetition limits
The platform should avoid repetitive, low-value responses.
 
⸻
 
15.30 Negative Review Policy
Negative response policies should define:
	•	Required response
	•	Approval level
	•	Escalation triggers
	•	Offline contact instructions
	•	Compensation-language restrictions
	•	Liability-language restrictions
	•	Staff-reference rules
	•	Privacy constraints
	•	Response-time objective
 
⸻
 
15.31 Empty Review Policy
A rating without text may be handled differently.
Possible policies:
respond_to_all
respond_positive_only
respond_negative_only
do_not_respond
manual_review
The platform should not invent details to personalize an empty review.
 
⸻
 
15.32 Response Tone
Tone configuration may include:
	•	Warm
	•	Professional
	•	Direct
	•	Casual
	•	Formal
	•	Hospitality-oriented
	•	Service-oriented
Tone should remain subordinate to:
	•	Accuracy
	•	Risk
	•	Provider policy
	•	Client policy
	•	Review context
A negative legal complaint should not receive an overly casual response because the normal brand voice is casual.
 
⸻
 
15.33 Response Structure
A response may include:
	1.	Acknowledgment
	2.	Specific reference to the review
	3.	Appreciation or apology where appropriate
	4.	Clarification without argument
	5.	Corrective or next-step language
	6.	Offline contact invitation
	7.	Signoff
Not every response requires every element.
 
⸻
 
15.34 Response Draft
Recommended fields:
id
review_id
status
current_revision
response_strategy
risk_level
requires_approval
created_by
assigned_to
created_at
updated_at
 
⸻
 
15.35 Response Revision
Recommended fields:
id
response_draft_id
revision_number
body
language
content_hash
source
ai_execution_id
created_by
created_at
Approval applies to one specific revision.
 
⸻
 
15.36 Response Status
Recommended lifecycle:
not_started
draft
revision_required
awaiting_approval
approved
scheduled
publishing
published
verification_failed
failed
cancelled
superseded
 
⸻
 
15.37 Response Quality Requirements
A response should:
	•	Address the correct reviewer
	•	Match the correct location
	•	Reflect the actual review
	•	Avoid generic repetition
	•	Avoid unsupported facts
	•	Avoid private information
	•	Avoid defensive argument
	•	Avoid blame
	•	Avoid promises the business has not approved
	•	Avoid admissions of legal liability
	•	Use approved contact information
	•	Match the required language
	•	Follow provider limits
	•	Follow client tone
 
⸻
 
15.38 Positive Response Guidance
Positive responses should:
	•	Thank the reviewer
	•	Reference a genuine detail when available
	•	Reinforce the business naturally
	•	Remain concise
	•	Avoid turning every response into an advertisement
The platform should detect repeated response patterns across recent publications.
 
⸻
 
15.39 Negative Response Guidance
Negative responses should:
	•	Acknowledge the experience
	•	Remain calm
	•	Avoid disputing facts publicly unless necessary and approved
	•	Avoid exposing internal records
	•	Avoid asking the reviewer to publish personal details
	•	Move complex resolution offline
	•	Use approved contact information
	•	Avoid guaranteeing a specific outcome
 
⸻
 
15.40 Apology Language
The product should distinguish:
	•	Empathy
	•	Regret
	•	Apology
	•	Admission
Example:
“We’re sorry to hear the visit did not meet expectations.”
does not necessarily admit a specific allegation.
High-risk cases should use approved response strategies.
The platform must not provide legal advice on whether language creates liability.
 
⸻
 
15.41 Offline Contact
Offline contact instructions should use approved contact channels.
Possible channels:
	•	Phone
	•	Email
	•	Contact form
	•	Manager callback
	•	Support desk
The response should not publish:
	•	Personal employee contact details
	•	Private phone numbers
	•	Internal escalation addresses
	•	Unapproved direct contacts
 
⸻
 
15.42 Staff Mentions
When a review names an employee, the product should consider:
	•	Whether the mention is positive or negative
	•	Employee privacy
	•	Allegation severity
	•	Client policy
	•	Whether a public response should repeat the name
Negative employee allegations should generally not be investigated publicly.
 
⸻
 
15.43 Compensation and Refund Language
The system should not promise:
	•	Refunds
	•	Credits
	•	Free services
	•	Reimbursement
	•	Specific compensation
	•	Charge reversal
unless the client has explicitly authorized the offer.
Compensation decisions should be tracked separately from public response text.
 
⸻
 
15.44 Review Ingestion Workflow
Schedule or Provider Event
    ↓
Validate Connection
    ↓
Retrieve Reviews
    ↓
Normalize Provider Fields
    ↓
Deduplicate
    ↓
Store Review or Revision
    ↓
Map Organization and Location
    ↓
Classify
    ↓
Score Priority
    ↓
Route
A failed sync must not remove prior valid review records.
 
⸻
 
15.45 Ingestion Deduplication
Duplicate prevention should use:
	•	Provider
	•	Provider location
	•	Provider review ID
	•	Revision timestamp or content hash
The product should distinguish:
	•	Duplicate provider delivery
	•	Edited review
	•	Reposted review
	•	Separate review by the same person
 
⸻
 
15.46 Classification Workflow
New or Revised Review
    ↓
Run Deterministic Rules
    ↓
Run Approved AI Classification
    ↓
Validate Output
    ↓
Assign Topics
    ↓
Assign Risk Flags
    ↓
Calculate Priority
    ↓
Route for Drafting or Escalation
Deterministic high-risk rules should take precedence over low-confidence AI output.
 
⸻
 
15.47 Deterministic Risk Rules
Initial rules may detect:
	•	Legal keywords
	•	Threats
	•	Injury references
	•	Discrimination language
	•	Refund demand
	•	Chargeback
	•	Police or regulator mention
	•	Personal phone or email
	•	Medical information
	•	Violence
	•	Staff accusation
	•	Fraud claim
	•	License complaint
	•	Insurance complaint
	•	Media escalation
Keyword matches should create candidates for review, not final legal conclusions.
 
⸻
 
15.48 Drafting Workflow
Eligible Review
    ↓
Load Response Policy
    ↓
Load Approved Business Context
    ↓
Select Response Strategy
    ↓
Generate or Create Draft
    ↓
Validate
    ↓
Check Repetition
    ↓
Route for Approval or Publication
AI drafting may be skipped for:
	•	Human-only cases
	•	Critical-risk cases
	•	Unsupported language
	•	Provider restrictions
	•	Client policy
 
⸻
 
15.49 Approval Workflow
Draft Ready
    ↓
Validate Current Review Revision
    ↓
Present Review, Risk, and Draft
    ↓
Approve, Reject, or Request Revision
    ↓
Lock Approved Revision
    ↓
Queue Publication
If the review changes after approval:
	•	Publication should pause.
	•	The response should be revalidated.
	•	Approval should be invalidated where the change is material.
 
⸻
 
15.50 Publication Workflow
Approved Response
    ↓
Validate Mapping
    ↓
Validate Provider Capability
    ↓
Validate Current Review State
    ↓
Reserve Publication
    ↓
Publish
    ↓
Store Provider Result
    ↓
Verify
    ↓
Notify
 
⸻
 
15.51 Publication Idempotency
A response-publication idempotency key should include:
	•	Provider
	•	Provider location
	•	Review
	•	Approved response revision
Before retrying, the system must check whether the response already exists externally.
Blind retry is prohibited.
 
⸻
 
15.52 Response Editing
Where a provider supports editing, the product may support response updates.
An edit must:
	•	Create a new response revision
	•	Preserve prior published text
	•	Require approval according to policy
	•	Revalidate current review state
	•	Publish through a new controlled action
	•	Verify the updated response
 
⸻
 
15.53 Response Deletion
Where supported, response deletion should require:
	•	Elevated permission
	•	Reason
	•	Explicit confirmation
	•	Audit
	•	Provider verification
Deletion should not erase internal response history.
 
⸻
 
15.54 Publication Verification
Verification should confirm:
	•	Response exists
	•	Correct review
	•	Correct location
	•	Correct text
	•	Correct revision
	•	Provider state
	•	Publication timestamp
Verification states:
verified
partial
failed
provider_delayed
manual_review_required
 
⸻
 
15.55 Reconciliation
Reconciliation is required when:
	•	Publication timed out.
	•	Provider returned an ambiguous error.
	•	The response exists externally but internal status is incomplete.
	•	A response was changed through the provider interface.
	•	A provider no longer returns a previously stored response.
Reconciliation should:
	1.	Retrieve current provider state.
	2.	Match the expected response.
	3.	Update internal records.
	4.	Avoid duplicate publication.
	5.	Create an exception if ambiguous.
 
⸻
 
15.56 Escalation Case
An escalation case tracks a review requiring additional handling.
Recommended fields:
id
review_id
case_type
severity
status
owner
assigned_team
reason
restricted
opened_at
due_at
resolved_at
resolution
 
⸻
 
15.57 Escalation Case Types
Potential case types:
legal
safety
discrimination
employee_conduct
refund
fraud
privacy
threat
media
regulatory
executive
operational
provider_dispute
other
 
⸻
 
15.58 Escalation Workflow
Risk Trigger
    ↓
Pause Automated Response
    ↓
Create Case
    ↓
Notify Responsible Owner
    ↓
Collect Internal Context
    ↓
Select Response Strategy
    ↓
Approve
    ↓
Respond or Withhold
    ↓
Track Resolution
    ↓
Close
Escalation cases may remain unresolved after a public response is published.
 
⸻
 
15.59 Internal Context
Authorized users may attach:
	•	Order reference
	•	Service record
	•	Reservation record
	•	Staff notes
	•	Client explanation
	•	Previous communication
	•	Resolution status
The interface must prevent internal context from appearing in the public response accidentally.
 
⸻
 
15.60 Restricted Cases
Cases involving legal, medical, safety, discrimination, or personal-data concerns may require restricted access.
Restricted case controls should include:
	•	Smaller role set
	•	Separate audit events
	•	Limited export
	•	Redacted notifications
	•	Shorter sensitive-data retention
	•	No ordinary AI processing unless explicitly approved
 
⸻
 
15.61 Review Dispute Case
A dispute case tracks a request to report or remove a review through provider-supported processes.
Recommended fields:
id
review_id
reason
provider_policy_category
evidence
status
submitted_at
provider_case_id
decision
resolved_at
 
⸻
 
15.62 Dispute Reasons
Potential reasons include:
	•	Spam
	•	Conflict of interest
	•	Harassment
	•	Hate speech
	•	Personal information
	•	Off-topic content
	•	Fake engagement
	•	Prohibited content
	•	Review for wrong business
	•	Duplicate content
	•	Extortion
The platform should not classify a review as removable merely because it is negative.
 
⸻
 
15.63 Dispute Workflow
Potential Violation Detected
    ↓
Human Review
    ↓
Select Provider Policy Basis
    ↓
Collect Evidence
    ↓
Approve Submission
    ↓
Submit Through Supported Channel
    ↓
Track Provider Decision
    ↓
Close or Escalate
The platform must not promise removal.
 
⸻
 
15.64 Review Solicitation Coordination
The Reviews product may coordinate with a future review-request capability.
Any review-request workflow must:
	•	Follow provider policy
	•	Avoid review gating
	•	Avoid undisclosed incentives
	•	Respect consent
	•	Provide a neutral request
	•	Stop after configured limits
	•	Record delivery and opt-out
Review solicitation should remain a separate workflow from public response management.
 
⸻
 
15.65 Theme Analysis
The product should identify recurring review themes.
Examples:
	•	Long wait times
	•	Pricing confusion
	•	Specific service praise
	•	Staff conduct
	•	Menu availability
	•	Scheduling delays
	•	Communication problems
	•	Cleanliness
	•	Parking
	•	Quality consistency
Theme analysis should use aggregated evidence.
 
⸻
 
15.66 Theme Record
Recommended fields:
id
organization_id
location_id
topic_id
period_start
period_end
review_count
sentiment_distribution
trend
confidence
summary
status
 
⸻
 
15.67 Theme Detection
Theme detection should consider:
	•	Frequency
	•	Change over time
	•	Rating distribution
	•	Location concentration
	•	Service concentration
	•	Staff mentions
	•	Review recency
	•	Statistical sufficiency
One review should not be presented as a recurring trend.
 
⸻
 
15.68 Operational Feedback
Recurring themes may create events for:
	•	Insights
	•	Account management
	•	Client operations
	•	Content
	•	Training
	•	Service improvement
The Reviews product should not directly modify operational systems without an approved workflow.
 
⸻
 
15.69 Multi-Location Operations
The product should support:
	•	Portfolio review inbox
	•	Location filters
	•	Shared policies
	•	Location overrides
	•	Bulk assignments
	•	Central approval
	•	Per-location publication
	•	Per-location reporting
	•	Cross-location theme comparison
Location-specific validation remains mandatory.
 
⸻
 
15.70 Cross-Location Safeguards
The product must prevent:
	•	Wrong business name
	•	Wrong location
	•	Wrong manager contact
	•	Wrong service
	•	Wrong menu item
	•	Wrong reviewer reference
	•	Wrong provider review
	•	Wrong language
	•	Wrong signoff
Bulk response publication without independent review validation is prohibited.
 
⸻
 
15.71 Review Inbox
The review inbox should show:
	•	Rating
	•	Review excerpt
	•	Reviewer display name
	•	Location
	•	Source
	•	Review age
	•	Risk
	•	Priority
	•	Topics
	•	Response status
	•	Assignee
	•	Due time
Recommended filters:
	•	Organization
	•	Location
	•	Source
	•	Rating
	•	Sentiment
	•	Risk
	•	Topic
	•	Status
	•	Assignee
	•	Age
	•	Language
 
⸻
 
15.72 Review Detail
The review detail should include:
	•	Full review
	•	Rating
	•	Review history
	•	Provider
	•	Location
	•	Classification
	•	Risk flags
	•	Priority score
	•	Internal notes
	•	Response draft
	•	Revision history
	•	Approval
	•	Publication status
	•	Verification
	•	Escalation
	•	Dispute status
	•	Related themes
 
⸻
 
15.73 Approval Experience
The approval view should present:
	•	Original review
	•	Current review revision
	•	Risk classification
	•	Factual context
	•	Proposed response
	•	Required fact checks
	•	Warnings
	•	Publication destination
	•	Current location
	•	Previous responses for repetition review
 
⸻
 
15.74 Response Preview
The preview should show the response as it will appear where practical.
The interface should clearly identify:
	•	Provider
	•	Business location
	•	Reviewer
	•	Response language
	•	Approved revision
	•	Public visibility
 
⸻
 
15.75 Internal Notes
Internal notes must:
	•	Be clearly labeled
	•	Remain hidden from clients unless explicitly shared
	•	Never be copied automatically into public responses
	•	Be access-controlled
	•	Be auditable
A visibility selector should distinguish:
Internal
Client Visible
Restricted
 
⸻
 
15.76 Review Analytics
The analytics workspace should support:
	•	Average rating
	•	Rating distribution
	•	Review volume
	•	Response rate
	•	Median response time
	•	Risk volume
	•	Topic trends
	•	Sentiment trends
	•	Location comparison
	•	Source comparison
	•	Unresolved escalation count
	•	Dispute outcomes
Average rating should never be shown without review volume and period context.
 
⸻
 
15.77 Response-Time Measurement
Response time should be measured from:
review_created_at
or
review_ingested_at
The platform should report both where provider delivery may be delayed.
Recommended metrics:
	•	Median response time
	•	90th percentile response time
	•	Percentage within policy objective
	•	Oldest unresponded review
 
⸻
 
15.78 Reporting
Client-facing review reports should answer:
	1.	How many reviews were received?
	2.	How did rating and sentiment change?
	3.	How quickly were reviews answered?
	4.	Which themes improved or worsened?
	5.	Which locations require attention?
	6.	Which cases remain unresolved?
	7.	What actions were completed?
	8.	What operational recommendations follow?
 
⸻
 
15.79 Agency Reporting
Agency users should additionally see:
	•	Ingestion failures
	•	Connection health
	•	Draft backlog
	•	Approval backlog
	•	Publication failure rate
	•	Verification failures
	•	AI edit rate
	•	Classification correction rate
	•	High-risk review volume
	•	Escalation age
	•	Dispute status
	•	Location-policy compliance
 
⸻
 
15.80 Product Success Metrics
Operational Metrics
	•	Review-ingestion reliability
	•	Classification completion time
	•	Draft completion time
	•	Approval turnaround
	•	Publication success
	•	Verification pass rate
	•	Response-time objective compliance
	•	Escalation assignment time
Quality Metrics
	•	Human classification correction rate
	•	AI draft edit rate
	•	Unsupported-fact rate
	•	Repetition rate
	•	Wrong-location error rate
	•	Escalation false-positive rate
	•	Escalation false-negative rate
	•	Response rejection rate
Business Metrics
	•	Response-rate improvement
	•	Response-time improvement
	•	Rating trend
	•	Sentiment trend
	•	Reduction in unresolved negative reviews
	•	Faster operational escalation
	•	Improvement in recurring themes
	•	Increased client participation
 
⸻
 
15.81 AI Responsibilities
AI may assist with:
	•	Sentiment classification
	•	Topic classification
	•	Risk candidate detection
	•	Review summarization
	•	Draft generation
	•	Draft variation
	•	Translation
	•	Theme analysis
	•	Performance summaries
	•	Escalation summaries
AI must not independently:
	•	Determine legal liability
	•	Promise compensation
	•	Publish critical-risk responses
	•	Reveal private customer information
	•	Decide review-removal eligibility conclusively
	•	Resolve employee misconduct allegations
	•	Classify a reviewer as fraudulent without evidence
	•	Modify client policy
	•	Publish to an unconfirmed location
 
⸻
 
15.82 AI Task Registry
Initial tasks may include:
reviews.sentiment_classification
reviews.topic_classification
reviews.risk_classification
reviews.response_strategy
reviews.response_draft
reviews.response_variation
reviews.translation
reviews.theme_summary
reviews.performance_summary
reviews.escalation_summary
 
⸻
 
15.83 Classification Output
Example schema:
{
  "sentiment": "negative",
  "topics": [
    {
      "topic": "wait_time",
      "confidence": "high"
    },
    {
      "topic": "service",
      "confidence": "medium"
    }
  ],
  "risk_level": "moderate",
  "risk_flags": [],
  "urgency": "priority",
  "response_recommendation": "recommended",
  "requires_human_review": true
}
 
⸻
 
15.84 Response Strategy Output
Example schema:
{
  "strategy": "acknowledge_and_move_offline",
  "key_points": [
    "Acknowledge the delayed service.",
    "Avoid disputing the stated wait time.",
    "Invite the reviewer to contact the manager through the approved channel."
  ],
  "prohibited_content": [
    "Do not offer compensation publicly.",
    "Do not identify the employee mentioned."
  ],
  "requires_approval": true
}
 
⸻
 
15.85 Response Draft Output
Example schema:
{
  "body": "Thank you for sharing this feedback. We’re sorry the wait and service did not meet expectations. We would appreciate the opportunity to learn more and address the experience directly. Please contact our management team through the approved contact channel.",
  "language": "en",
  "fact_checks": [
    "Confirm the approved contact method."
  ],
  "risk_flags": [],
  "requires_human_review": true
}
The model should reference approved contact data rather than inventing phone numbers or email addresses.
 
⸻
 
15.86 AI Grounding
AI tasks should be grounded in:
	•	Review text
	•	Rating
	•	Review revision
	•	Location
	•	Provider
	•	Approved business facts
	•	Response policy
	•	Brand voice
	•	Approved contacts
	•	Service catalog
	•	Risk rules
	•	Recent published responses
	•	Internal context where access is explicitly allowed
Restricted internal notes should not automatically enter AI context.
 
⸻
 
15.87 AI Validation
AI output should be validated for:
	•	Correct reviewer
	•	Correct location
	•	Correct source
	•	Correct language
	•	Unsupported facts
	•	Private information
	•	Compensation promise
	•	Liability admission
	•	Staff accusation
	•	Wrong contact details
	•	Repetitive response
	•	Excessive length
	•	Prohibited language
	•	Cross-client contamination
	•	Risk-policy compliance
 
⸻
 
15.88 Repetition Control
The system should compare proposed responses with recent published responses.
It may flag:
	•	Exact duplicates
	•	Near duplicates
	•	Repeated opening lines
	•	Repeated closing lines
	•	Repeated promotional language
	•	Repeated apologies
Repetition controls should not force unnatural variation at the expense of clarity.
 
⸻
 
15.89 Translation
Translation workflows should preserve:
	•	Meaning
	•	Tone
	•	Risk
	•	Contact details
	•	Business names
	•	Provider constraints
High-risk translated responses should require review by a qualified speaker or approved reviewer where practical.
 
⸻
 
15.90 Human Responsibilities
Humans remain responsible for:
	•	Review-policy configuration
	•	High-risk classification review
	•	Legal or regulatory escalation
	•	Employee allegation handling
	•	Compensation decisions
	•	Factual validation
	•	Approval
	•	Publication strategy
	•	Client communication
	•	Operational correction
 
⸻
 
15.91 Permissions
Recommended permissions:
reviews.view
reviews.view_restricted
reviews.configure
reviews.connect
reviews.sync
reviews.classify
reviews.assign
reviews.create_response
reviews.edit_response
reviews.approve_response
reviews.publish_response
reviews.edit_published_response
reviews.delete_response
reviews.create_escalation
reviews.manage_escalation
reviews.create_dispute
reviews.submit_dispute
reviews.view_analytics
reviews.export
reviews.manage_runtime
Permissions should separate ordinary review work from restricted and destructive actions.
 
⸻
 
15.92 Approval Policies
Potential approval policies:
no_approval
internal_approval
client_approval
dual_approval
human_only
Recommended defaults:
	•	Positive low-risk review: configurable
	•	Neutral or mixed review: internal approval
	•	Negative review: internal or client approval
	•	High-risk review: dual approval or human-only
	•	Critical review: blocked pending escalation
	•	Compensation language: client approval
	•	Published-response edit: same or stronger approval than original
	•	Response deletion: elevated approval
 
⸻
 
15.93 Notifications
Notifications may include:
	•	New critical review
	•	New high-risk review
	•	Response deadline approaching
	•	Response ready for approval
	•	Approval rejected
	•	Publication failed
	•	Verification failed
	•	Review materially edited
	•	Escalation assigned
	•	Dispute decision received
	•	Connection requires attention
	•	Review sync delayed
	•	Recurring negative theme detected
	•	Report ready
 
⸻
 
15.94 Product Health
Recommended health states:
healthy
connection_required
mapping_required
sync_delayed
provider_degraded
publication_blocked
approval_backlog
critical_case_open
configuration_required
The product may remain active while one provider is degraded.
 
⸻
 
15.95 Runtime Controls
Authorized operators should be able to:
	•	Pause all response publication
	•	Pause one provider
	•	Pause one organization
	•	Pause one location
	•	Force human approval
	•	Disable AI drafting
	•	Disable automatic classification
	•	Re-run review sync
	•	Re-run classification
	•	Re-run verification
	•	Mark provider incident
	•	Block one review from publication
All controls must be audited.
 
⸻
 
15.96 Failure Modes
Expected failure modes include:
	•	OAuth authorization expired
	•	Missing provider scope
	•	Location mapping conflict
	•	Review sync delayed
	•	Provider review edited
	•	Duplicate provider delivery
	•	AI classification invalid
	•	Risk missed
	•	False high-risk classification
	•	Wrong response language
	•	Draft contains unsupported fact
	•	Review changed after approval
	•	Provider write timed out
	•	Response published but internal state failed
	•	Provider does not support response
	•	Response rejected by provider
	•	Response edit unsupported
	•	Dispute submission unavailable
	•	Restricted data exposed in draft
	•	Wrong-location publication attempt
 
⸻
 
15.97 Failure Handling
Each failure should define:
	•	Error category
	•	Retry eligibility
	•	Risk level
	•	User-visible message
	•	Internal diagnostic
	•	Required next action
	•	Reconciliation behavior
	•	Escalation owner
The system must preserve the current review and response history during failures.
 
⸻
 
15.98 Security Considerations
The product must protect:
	•	Provider credentials
	•	Reviewer information
	•	Internal context
	•	Restricted cases
	•	Employee allegations
	•	Legal communications
	•	Compensation decisions
	•	Private client contacts
	•	Publication authority
Provider tokens must not be exposed to frontend code or AI prompts.
 
⸻
 
15.99 Privacy Considerations
Review content may contain:
	•	Names
	•	Phone numbers
	•	Email addresses
	•	Medical information
	•	Financial information
	•	Employee information
	•	Allegations
The product should:
	•	Detect likely personal data
	•	Restrict access where necessary
	•	Avoid repeating private information publicly
	•	Redact exports where appropriate
	•	Apply retention policies to sensitive internal context
 
⸻
 
15.100 Operational Requirements
The product requires:
	•	Scheduled review synchronization
	•	Provider event handling where available
	•	Classification workers
	•	Priority calculation
	•	Draft workers
	•	Approval queues
	•	Publication workers
	•	Verification jobs
	•	Reconciliation jobs
	•	Escalation alerts
	•	Response-time monitoring
	•	Theme-analysis scheduling
	•	Provider-health monitoring
	•	Runtime kill switches
 
⸻
 
15.101 Testing Requirements
Testing should cover:
	•	Tenant isolation
	•	Provider account mapping
	•	Location mapping
	•	Review deduplication
	•	Review revisions
	•	Rating normalization
	•	Sentiment classification
	•	Topic classification
	•	Risk rules
	•	Priority scoring
	•	Response-policy inheritance
	•	AI output validation
	•	Repetition detection
	•	Approval revision locking
	•	Review change after approval
	•	Publication idempotency
	•	Provider timeout
	•	Reconciliation
	•	Response editing
	•	Restricted access
	•	Multi-location safeguards
	•	Translation
	•	Dispute workflow
	•	Runtime controls
 
⸻
 
15.102 Evaluation Dataset
The Reviews AI evaluation dataset should include:
	•	Positive detailed reviews
	•	Positive empty reviews
	•	Mixed reviews
	•	One-star reviews
	•	Legal threats
	•	Safety allegations
	•	Refund demands
	•	Employee accusations
	•	Sarcasm
	•	Multiple languages
	•	Personal information
	•	Fake-review indicators
	•	Restaurant reviews
	•	Home-service reviews
	•	Wrong-location traps
	•	Unsupported compensation language
	•	Repetitive draft examples
Human-reviewed examples should be versioned.
 
⸻
 
15.103 Minimum Viable Reviews Product
The minimum viable product should include:
Connection and Ingestion
	•	Google review access
	•	Location mapping
	•	Scheduled synchronization
	•	Review normalization
	•	Revision tracking
Classification
	•	Sentiment
	•	Topic
	•	Risk
	•	Priority
	•	Manual correction
Response
	•	Draft
	•	Edit
	•	Approval
	•	Publication
	•	Idempotency
	•	Verification
	•	Failure recovery
Operations
	•	Escalation
	•	Notifications
	•	Response-time tracking
	•	Basic reporting
	•	Permissions
	•	Audit
	•	Manual operation without AI
 
⸻
 
15.104 Implementation Phases
Phase 1 — Review Foundation
Implement:
	•	Review sources
	•	Account connection
	•	Location mapping
	•	Review ingestion
	•	Review revisions
	•	Inbox
	•	Review detail
Phase 2 — Classification and Prioritization
Implement:
	•	Sentiment
	•	Topics
	•	Risk flags
	•	Deterministic rules
	•	Priority score
	•	Manual correction
	•	Routing
Phase 3 — Response Workflow
Implement:
	•	Response policy
	•	Drafts
	•	Revisions
	•	Approval
	•	Publication
	•	Verification
	•	Reconciliation
Phase 4 — Escalation and Disputes
Implement:
	•	Escalation cases
	•	Restricted cases
	•	Internal context
	•	Dispute tracking
	•	Provider-case references
Phase 5 — Analytics and Themes
Implement:
	•	Response-time reporting
	•	Rating trends
	•	Topic trends
	•	Theme detection
	•	Location comparison
	•	Client reporting
Phase 6 — Multi-Provider and Multi-Location
Implement:
	•	Additional providers
	•	Provider capability abstraction
	•	Portfolio inbox
	•	Shared policies
	•	Location overrides
	•	Advanced bulk operations
 
⸻
 
15.105 Future Capabilities
Potential future capabilities include:
	•	Review-request campaigns
	•	First-party feedback capture
	•	Customer-resolution tracking
	•	CRM integration
	•	Ticketing integration
	•	Staff-performance insights with privacy controls
	•	Advanced spam detection
	•	Review authenticity signals
	•	Provider-dispute automation
	•	Executive-risk dashboards
	•	Predictive issue detection
	•	Voice-of-customer analytics
	•	Competitor reputation benchmarking
	•	AI-assisted internal response playbooks
Future capabilities must preserve fairness, privacy, policy compliance, and human oversight.
 
⸻
 
15.106 Reviews Guardrails
The following are prohibited unless formally approved:
	1.	Publishing a response to an unconfirmed location
	2.	Automatically responding to every review regardless of risk
	3.	Inventing facts about the customer interaction
	4.	Disclosing private customer information
	5.	Disclosing employee records
	6.	Admitting legal liability through uncontrolled generation
	7.	Promising refunds or compensation without authorization
	8.	Accusing a reviewer of lying or fraud without approved evidence
	9.	Arguing with the reviewer publicly
	10.	Repeating sensitive allegations unnecessarily
	11.	Treating a negative review as removable solely because it is negative
	12.	Guaranteeing review removal
	13.	Review gating
	14.	Undisclosed incentives for positive reviews
	15.	Publishing an unapproved response revision
	16.	Publishing after a material review edit without revalidation
	17.	Blindly retrying provider response writes
	18.	Marking a response published before verification
	19.	Allowing AI to resolve legal, safety, discrimination, or employee-conduct cases autonomously
	20.	Including restricted internal notes in AI context without authorization
	21.	Copying internal notes into public responses
	22.	Using generic duplicate responses at scale
	23.	Exposing provider credentials
	24.	Enriching anonymous reviewer identities
	25.	Treating sentiment as equivalent to rating
	26.	Treating one review as a recurring theme
	27.	Concealing unresolved critical cases in reporting
	28.	Allowing bulk publication without per-review validation
	29.	Deleting response history after provider deletion
	30.	Allowing the Reviews product to bypass shared approval, audit, security, or workflow controls
 
⸻
 
15.107 Acceptance Requirements
The initial Reviews product is not production-ready until it supports:
	•	Provider connection
	•	Review location mapping
	•	Scheduled ingestion
	•	Deduplication
	•	Review revisions
	•	Rating normalization
	•	Sentiment classification
	•	Topic classification
	•	Risk flags
	•	Priority scoring
	•	Response policies
	•	Draft creation
	•	Revision history
	•	Approval
	•	Publication
	•	Idempotency
	•	Verification
	•	Reconciliation
	•	Escalation cases
	•	Notifications
	•	Response-time reporting
	•	Permissions
	•	Audit history
	•	Tenant isolation
	•	Restricted-case handling
	•	Manual operation without AI
 
⸻
 
15.108 Section Decisions
This section establishes the following decisions:
	1.	The Reviews product manages the complete lifecycle from ingestion through response measurement and theme analysis.
	2.	Every provider review is mapped explicitly to a LILOs organization and location.
	3.	Provider review revisions are preserved and may invalidate existing approval.
	4.	Rating, sentiment, risk, urgency, and priority remain separate concepts.
	5.	Risk classification uses deterministic rules, AI assistance, and human correction.
	6.	High-risk and critical reviews receive stronger access, approval, and escalation controls.
	7.	Response policies inherit through organization and location configuration.
	8.	Positive, negative, mixed, and empty reviews may use different response policies.
	9.	Response drafts are versioned, and approval applies to one specific revision.
	10.	A material review change requires reclassification and response revalidation.
	11.	Provider publication uses idempotency, verification, and reconciliation.
	12.	Blind retry of response publication is prohibited.
	13.	The product supports response editing and deletion only where provider capability and permissions allow.
	14.	Internal notes, client-visible comments, and restricted context are distinct.
	15.	Escalation cases remain separate from the public-response lifecycle.
	16.	Dispute workflows identify provider-policy candidates but do not guarantee removal.
	17.	AI supports classification, summarization, translation, and drafting.
	18.	AI does not determine legal liability, authorize compensation, or publish critical-risk responses autonomously.
	19.	Repetition detection is required to prevent low-quality templated responses.
	20.	Review analytics include volume, rating, sentiment, response rate, response time, risk, themes, and unresolved cases.
	21.	Theme analysis requires sufficient repeated evidence.
	22.	The product may produce events for Insights and operational workflows but does not directly alter unrelated product state.
	23.	Restricted review content receives enhanced privacy and access controls.
	24.	The minimum viable product includes ingestion, classification, drafting, approval, publication, verification, escalation, reporting, and manual operation.
	25.	No response may be published without confirmed tenant, location, review, revision, policy, and permission context.

---

Section 16 — Content Product Specification
16.1 Purpose of This Product
The Content product manages the complete lifecycle of digital content across the LILOs platform.
It provides a structured operating system for planning, creating, approving, publishing, measuring, and maintaining content across multiple channels while preserving factual accuracy, brand consistency, SEO quality, and human oversight.
The product must support:
	•	Content strategy
	•	Editorial planning
	•	Topic discovery
	•	Keyword opportunities
	•	Content briefs
	•	AI-assisted drafting
	•	Human editing
	•	Brand validation
	•	SEO validation
	•	Multi-stage approval
	•	Publication
	•	Scheduling
	•	Versioning
	•	Performance measurement
	•	Content refresh
	•	Content retirement
	•	Multi-location content
	•	Multi-channel distribution
	•	Reporting
	•	Workflow coordination
The Content product is responsible for the content lifecycle—not merely text generation.
 
⸻
 
16.2 Business Problem
Most organizations create content through disconnected tools and inconsistent processes.
Common problems include:
	•	No editorial strategy
	•	Duplicate topics
	•	Inconsistent quality
	•	AI hallucinations
	•	Poor SEO implementation
	•	Missing approvals
	•	Publishing outdated information
	•	No content ownership
	•	No refresh process
	•	Weak performance tracking
	•	Brand inconsistency
	•	Cross-location duplication
	•	No structured reuse
	•	Content decays over time
The Content product provides the complete operational lifecycle:
Discover
    ↓
Prioritize
    ↓
Brief
    ↓
Draft
    ↓
Validate
    ↓
Review
    ↓
Approve
    ↓
Publish
    ↓
Measure
    ↓
Refresh
    ↓
Retire
 
⸻
 
16.3 Product Goals
The Content product should:
	1.	Centralize content operations.
	2.	Standardize editorial workflows.
	3.	Produce high-quality factual content.
	4.	Support AI without depending upon AI.
	5.	Coordinate with SEO.
	6.	Support multiple industries.
	7.	Maintain version history.
	8.	Prevent duplicate work.
	9.	Enable scalable multi-location publishing.
	10.	Track business outcomes.
 
⸻
 
16.4 Non-Goals
The initial Content product is not:
	•	A CMS replacement
	•	A website builder
	•	A design application
	•	A social media management suite
	•	A digital asset management platform
	•	A marketing automation platform
	•	A plagiarism detector
	•	A translation management platform
	•	A newsroom system
Publishing destinations remain external systems.
 
⸻
 
16.5 Primary Users
Content Strategist
Responsibilities:
	•	Editorial planning
	•	Keyword prioritization
	•	Topic selection
	•	Campaign planning
	•	Performance review
 
⸻
 
Content Writer
Responsibilities:
	•	Draft articles
	•	Edit copy
	•	Improve clarity
	•	Apply SEO recommendations
 
⸻
 
SEO Specialist
Responsibilities:
	•	Keyword mapping
	•	Internal linking
	•	Search optimization
	•	Content validation
 
⸻
 
Account Manager
Responsibilities:
	•	Coordinate client approval
	•	Schedule publishing
	•	Review factual accuracy
 
⸻
 
Client Approver
Responsibilities:
	•	Approve business facts
	•	Approve publication
	•	Request revisions
 
⸻
 
Client Viewer
Responsibilities:
	•	Review published work
	•	Monitor performance
 
⸻
 
16.6 Product Scope
Content Product

├── Editorial Calendar
├── Content Opportunities
├── Keyword Planning
├── Topic Management
├── Briefs
├── Drafts
├── Revisions
├── SEO Validation
├── Brand Validation
├── Approval
├── Publishing
├── Scheduling
├── Performance
├── Refresh
├── Retirement
└── Reporting
 
⸻
 
16.7 Core Domain Objects
The product manages:
	•	Editorial calendar
	•	Campaign
	•	Topic
	•	Keyword target
	•	Search opportunity
	•	Content brief
	•	Draft
	•	Revision
	•	Publication
	•	Publishing target
	•	Approval
	•	Validation report
	•	Performance record
	•	Refresh recommendation
	•	Retirement recommendation
 
⸻
 
16.8 Content Types
Initial supported types include:
	•	Blog article
	•	Service page
	•	Location page
	•	Landing page
	•	FAQ
	•	Google Business Profile post
	•	Case study
	•	Resource page
	•	Event page
	•	Seasonal page
Future content types should extend the registry rather than require schema changes.
 
⸻
 
16.9 Editorial Calendar
The editorial calendar manages planned work.
Fields:
id
organization_id
campaign_id
title
planned_publish_date
owner
status
priority
channel
Calendar entries reference content—not drafts.
 
⸻
 
16.10 Campaigns
Campaigns group related work.
Examples:
	•	Spring HVAC
	•	Holiday Catering
	•	Summer Roofing
	•	Restaurant Brunch
	•	Water Damage Awareness
Campaigns may span multiple locations.
 
⸻
 
16.11 Content Opportunity
A content opportunity represents an identified business opportunity.
Sources may include:
	•	Search Console
	•	Keyword research
	•	GBP trends
	•	Competitor analysis
	•	Client requests
	•	Seasonal planning
	•	Manual ideas
Opportunities remain separate from approved work.
 
⸻
 
16.12 Topic Registry
Every content item references a canonical topic.
Topics include:
	•	Primary keyword
	•	Supporting keywords
	•	Search intent
	•	Industry
	•	Business relevance
	•	Content type
	•	Priority
Topics prevent duplication.
 
⸻
 
16.13 Keyword Targets
Each content item contains:
	•	Primary keyword
	•	Secondary keywords
	•	Supporting entities
	•	Geographic modifiers
	•	Search intent
	•	Difficulty
	•	Opportunity score
Keyword targets guide creation but do not override readability.
 
⸻
 
16.14 Content Brief
Every major content item begins with a structured brief.
A brief should contain:
	•	Purpose
	•	Audience
	•	Primary keyword
	•	Search intent
	•	Required facts
	•	Required sections
	•	Required CTAs
	•	Internal links
	•	External references
	•	Prohibited claims
	•	Brand notes
Briefs become immutable after approval.
 
⸻
 
16.15 Draft Lifecycle
Recommended lifecycle:
idea
briefing
draft
editing
seo_review
client_review
approved
scheduled
published
refresh_due
retired
Draft lifecycle remains independent from publication lifecycle.
 
⸻
 
16.16 Draft Structure
Each draft stores:
	•	Title
	•	Slug
	•	Summary
	•	Body
	•	Meta title
	•	Meta description
	•	Canonical URL
	•	Structured data
	•	CTA references
	•	Related assets
 
⸻
 
16.17 Revision Model
Every material edit creates a revision.
Revision fields:
revision_number
author
created_at
summary
content_hash
approval_state
Published revisions remain immutable.
 
⸻
 
16.18 Validation Pipeline
Validation occurs before approval.
Validation categories:
	•	SEO
	•	Brand
	•	Grammar
	•	Accessibility
	•	Structure
	•	Readability
	•	Required facts
	•	Links
	•	Images
	•	Metadata
	•	Duplicate detection
Validation failures block publication according to policy.
 
⸻
 
16.19 SEO Validation
SEO validation checks:
	•	H1
	•	Heading hierarchy
	•	Title length
	•	Meta description
	•	Canonical
	•	Internal links
	•	Image alt text
	•	Structured data
	•	Keyword coverage
	•	Entity coverage
	•	Duplicate titles
	•	Duplicate descriptions
Validation produces recommendations—not automatic rewrites.
 
⸻
 
16.20 Brand Validation
Brand validation checks:
	•	Voice
	•	Tone
	•	Terminology
	•	Claims
	•	Contact information
	•	Business facts
	•	Prohibited phrases
	•	Approved messaging
Brand rules are organization-specific.
 
⸻
 
16.21 Approval Workflow
Draft Ready
      ↓
Validation
      ↓
SEO Review
      ↓
Brand Review
      ↓
Client Review
      ↓
Approval
      ↓
Publication Queue
Approval locks a specific revision.
 
⸻
 
16.22 Publication
Publishing supports:
	•	Immediate publication
	•	Scheduled publication
	•	Manual publication
	•	Multi-location publication
	•	Multi-channel publication
Publishing destinations are abstracted behind adapters.
 
⸻
 
16.23 Publishing Targets
Initial targets may include:
	•	Astro websites
	•	CMS integrations
	•	Google Business Profile
	•	Future social platforms
	•	Email systems
Targets expose capabilities through shared interfaces.
 
⸻
 
16.24 Scheduling
Scheduling validates:
	•	Approved revision
	•	Destination availability
	•	Required assets
	•	Publish window
	•	Timezone
	•	Dependencies
Scheduling never implies successful publication.
 
⸻
 
16.25 Performance Tracking
Performance metrics may include:
	•	Organic traffic
	•	Clicks
	•	Impressions
	•	Average position
	•	Engagement
	•	Conversions
	•	Leads
	•	Scroll depth
	•	Publication age
Performance records remain immutable.
 
⸻
 
16.26 Refresh Recommendations
Refresh candidates may be identified from:
	•	Declining traffic
	•	Outdated information
	•	Product changes
	•	New services
	•	Seasonal changes
	•	Algorithm updates
	•	Client request
Refresh creates a new draft—not an in-place overwrite.
 
⸻
 
16.27 Retirement
Content retirement supports:
	•	Redirect planning
	•	Archive
	•	Deindex recommendation
	•	Merge recommendation
	•	Historical preservation
Retired content remains auditable.
 
⸻
 
16.28 AI Responsibilities
AI may assist with:
	•	Brief generation
	•	Outline generation
	•	Draft generation
	•	Title suggestions
	•	Meta descriptions
	•	FAQ creation
	•	Internal-link suggestions
	•	Refresh recommendations
	•	Content summaries
	•	Readability improvements
AI must not independently:
	•	Invent business facts
	•	Invent testimonials
	•	Invent pricing
	•	Invent services
	•	Publish content
	•	Approve content
	•	Override validation
 
⸻
 
16.29 AI Task Registry
Initial tasks include:
content.brief_generation
content.outline_generation
content.article_draft
content.meta_generation
content.title_generation
content.refresh_summary
content.internal_linking
content.faq_generation
content.readability_review
content.performance_summary
Each task requires structured inputs and outputs.
 
⸻
 
16.30 AI Grounding
Grounding sources include:
	•	Approved business facts
	•	Service catalog
	•	GBP data
	•	SEO opportunities
	•	Existing content
	•	Brand rules
	•	Editorial brief
	•	Organization configuration
General model knowledge never overrides approved business information.
 
⸻
 
16.31 AI Validation
AI-generated content is validated for:
	•	Unsupported claims
	•	Duplicate content
	•	Brand violations
	•	Incorrect locations
	•	Wrong phone numbers
	•	Wrong services
	•	Wrong pricing
	•	Hallucinated facts
	•	Missing CTAs
	•	Structural errors
 
⸻
 
16.32 Multi-Location Content
Shared content supports:
	•	Common framework
	•	Local business facts
	•	Local services
	•	Local testimonials where approved
	•	Local CTAs
	•	Local contact information
Every location receives an independent revision.
 
⸻
 
16.33 Duplicate Prevention
The system checks:
	•	Topic overlap
	•	Keyword overlap
	•	Similar titles
	•	Similar outlines
	•	Similar body content
	•	Similar slugs
Duplicate detection creates warnings—not automatic rejection.
 
⸻
 
16.34 Reporting
Client reports include:
	•	Published content
	•	Traffic
	•	Rankings
	•	Conversions
	•	Refresh work
	•	Planned content
	•	Editorial progress
Agency reporting additionally includes:
	•	Workflow bottlenecks
	•	Validation failures
	•	AI edit rates
	•	Publication success
	•	Approval turnaround
	•	Refresh backlog
 
⸻
 
16.35 Product Success Metrics
Operational metrics:
	•	Draft completion time
	•	Approval turnaround
	•	Publication success
	•	Validation pass rate
Quality metrics:
	•	AI edit rate
	•	Duplicate rate
	•	Fact correction rate
	•	SEO validation failures
Business metrics:
	•	Organic traffic growth
	•	Ranking improvements
	•	Conversion growth
	•	Content engagement
	•	Lead generation
 
⸻
 
16.36 Permissions
Recommended permissions:
content.view
content.create
content.edit
content.delete
content.review
content.approve
content.publish
content.schedule
content.refresh
content.retire
content.export
content.configure
Publishing requires stronger permission than editing.
 
⸻
 
16.37 Runtime Controls
Authorized operators may:
	•	Pause publishing
	•	Pause AI drafting
	•	Pause scheduling
	•	Disable destinations
	•	Re-run validation
	•	Force refresh
	•	Suspend publication queues
Runtime actions are fully audited.
 
⸻
 
16.38 Failure Modes
Expected failures include:
	•	Destination unavailable
	•	Validation failure
	•	Missing approval
	•	AI generation failure
	•	Duplicate publication
	•	Scheduling conflict
	•	Publishing timeout
	•	Wrong destination
	•	Missing assets
	•	Revision mismatch
Every failure records diagnostics and recovery steps.
 
⸻
 
16.39 Security
The Content product protects:
	•	Drafts
	•	Client revisions
	•	Brand guidelines
	•	Internal strategies
	•	Publishing credentials
	•	AI prompts
	•	Editorial history
Publishing credentials remain server-side.
 
⸻
 
16.40 Minimum Viable Product
The MVP includes:
	•	Editorial calendar
	•	Topics
	•	Content briefs
	•	Drafts
	•	Revisions
	•	Validation
	•	Approval
	•	Publishing
	•	Scheduling
	•	Performance
	•	Refresh workflow
	•	Reporting
	•	Manual operation without AI
 
⸻
 
16.41 Implementation Phases
Phase 1
Editorial calendar
Topic registry
Briefs
Drafts
 
⸻
 
Phase 2
Validation
SEO review
Brand review
Approvals
 
⸻
 
Phase 3
Publishing
Scheduling
Revision history
Performance
 
⸻
 
Phase 4
AI drafting
AI validation
Refresh recommendations
 
⸻
 
Phase 5
Multi-location content
Campaigns
Advanced reporting
Cross-channel publishing
 
⸻
 
16.42 Content Guardrails
The following are prohibited unless explicitly approved:
	1.	Inventing business facts.
	2.	Inventing testimonials.
	3.	Inventing pricing.
	4.	Publishing unapproved drafts.
	5.	Publishing failed validation.
	6.	Overwriting published revisions.
	7.	Publishing to the wrong destination.
	8.	Reusing location-specific content without validation.
	9.	AI publishing autonomously.
	10.	Removing audit history.
	11.	Ignoring duplicate warnings.
	12.	Creating content without an approved topic.
	13.	Allowing unpublished revisions to replace approved revisions.
	14.	Exposing publishing credentials.
	15.	Treating AI output as authoritative business information.
 
⸻
 
16.43 Acceptance Requirements
The Content product is not production-ready until it supports:
	•	Editorial planning
	•	Topic management
	•	Content briefs
	•	Draft lifecycle
	•	Revision history
	•	Validation
	•	Approval
	•	Publication
	•	Scheduling
	•	Performance tracking
	•	Refresh workflows
	•	Reporting
	•	Permissions
	•	Audit
	•	Tenant isolation
	•	Manual operation without AI
 
⸻
 
16.44 Section Decisions
This section establishes the following decisions:
	1.	The Content product manages the entire editorial lifecycle.
	2.	Every major content item begins with an approved brief.
	3.	Revisions are immutable after publication.
	4.	Validation precedes approval.
	5.	Approval applies to a specific revision.
	6.	Publishing is destination-agnostic through adapters.
	7.	AI assists creation but never establishes business facts.
	8.	Refreshes create new revisions instead of modifying history.
	9.	Multi-location content creates independent location revisions.
	10.	Performance measurement informs refresh rather than automatically changing content.
	11.	Editorial planning, publishing, and reporting remain separate concerns.
	12.	Publishing requires verification and auditability.
	13.	The product operates without AI when necessary.
	14.	Business facts always originate from approved platform data.
	15.	Content quality is enforced through deterministic validation and human oversight before publication.

---

Section 17 — Leads Product Specification
17.1 Purpose of This Product
The Leads product manages the complete lifecycle of inbound business opportunities across the LILOs platform.
It provides a controlled operating system for capturing, validating, routing, contacting, assigning, tracking, and measuring leads across supported channels.
The product must support:
	•	Lead capture
	•	Source attribution
	•	Identity normalization
	•	Duplicate detection
	•	Spam detection
	•	Consent tracking
	•	Qualification
	•	Urgency classification
	•	Service and location matching
	•	Assignment
	•	Speed-to-lead automation
	•	Email and SMS communication
	•	Human handoff
	•	Conversation tracking
	•	Appointment or estimate progression
	•	Conversion tracking
	•	Lost-lead analysis
	•	Multi-location routing
	•	Reporting
	•	Recovery from provider failures
	•	Coordination with Reviews, GBP, SEO, Content, Insights, and external CRMs
The Leads product is responsible for lead operations.
It is not merely a form inbox or autoresponder.
 
⸻
 
17.2 Business Problem
Inbound leads commonly arrive through disconnected systems.
Examples include:
	•	Website forms
	•	Phone calls
	•	Google Business Profile
	•	Email
	•	SMS
	•	Booking systems
	•	Advertising platforms
	•	Third-party lead marketplaces
	•	Social platforms
	•	Manual referrals
Common operational problems include:
	•	Slow response
	•	Missed leads
	•	Duplicate leads
	•	Incorrect location routing
	•	Leads sent to unavailable services
	•	No after-hours policy
	•	Automated messages sent without consent
	•	Poor source attribution
	•	Unclear ownership
	•	Multiple staff members contacting the same lead
	•	No follow-up sequence
	•	No visibility into lead status
	•	No conversion measurement
	•	No connection between marketing source and revenue
	•	Lead data exposed too broadly
	•	Spam consuming staff time
The product must support the full operating loop:
Capture
    ↓
Validate
    ↓
Normalize
    ↓
Deduplicate
    ↓
Classify
    ↓
Route
    ↓
Acknowledge
    ↓
Assign
    ↓
Contact
    ↓
Qualify
    ↓
Progress
    ↓
Convert or Close
    ↓
Measure
The product should reduce the time between customer intent and meaningful business response.
 
⸻
 
17.3 Product Goals
The Leads product should:
	1.	Centralize inbound leads.
	2.	Preserve the original lead source.
	3.	Route leads to the correct organization, location, service, and owner.
	4.	Reduce initial response time.
	5.	Prevent duplicate or conflicting outreach.
	6.	Respect communication consent and channel restrictions.
	7.	Support both automated and human response paths.
	8.	Identify urgent or high-value opportunities.
	9.	Preserve full lead history.
	10.	Track lead progression through conversion.
	11.	Measure marketing-source quality.
	12.	Support multi-location and service-area businesses.
	13.	Integrate with external CRMs without making one CRM mandatory.
	14.	Remain operational when AI is unavailable.
	15.	Protect lead personal data.
 
⸻
 
17.4 Non-Goals
The initial Leads product is not:
	•	A complete enterprise CRM
	•	A full call-center platform
	•	A predictive revenue engine
	•	A telephony carrier
	•	A payment processor
	•	A field-service management replacement
	•	A booking platform
	•	A general email marketing system
	•	A cold-outreach platform
	•	A purchased-lead marketplace
	•	An autonomous sales representative
	•	A system for contacting people without a lawful and approved basis
	•	A replacement for emergency dispatch
The product may coordinate with CRM, scheduling, booking, phone, email, and field-service systems through adapters.
 
⸻
 
17.5 Primary Users
Lead Coordinator
Responsibilities:
	•	Monitor new leads
	•	Correct routing
	•	Assign owners
	•	Review urgent leads
	•	Resolve duplicate or spam classifications
	•	Track stalled leads
 
⸻
 
Sales or Service Representative
Responsibilities:
	•	Contact leads
	•	Qualify opportunities
	•	Update status
	•	Schedule next steps
	•	Record outcomes
 
⸻
 
Dispatcher
Responsibilities:
	•	Review urgent service requests
	•	Confirm service area
	•	Assign operational teams
	•	Escalate emergencies
 
⸻
 
Account Manager
Responsibilities:
	•	Monitor client lead health
	•	Review response times
	•	Coordinate configuration
	•	Resolve routing problems
	•	Present lead reporting
 
⸻
 
Client Administrator
Responsibilities:
	•	Configure services
	•	Configure locations
	•	Configure routing
	•	Manage users
	•	Approve communication templates
	•	Review reporting
 
⸻
 
Client Operator
Responsibilities:
	•	Accept assigned leads
	•	Update lead status
	•	Communicate with customers
	•	Record conversion outcomes
 
⸻
 
Client Viewer
Responsibilities:
	•	View lead volume
	•	View response metrics
	•	View conversion reporting
	•	View source performance
 
⸻
 
17.6 Product Scope
The Leads product contains the following functional areas:
Leads Product

├── Lead Sources
├── Lead Capture
├── Identity Normalization
├── Consent
├── Validation
├── Deduplication
├── Spam Detection
├── Qualification
├── Urgency Classification
├── Service Matching
├── Location Routing
├── Assignment
├── Acknowledgment
├── Communication
├── Follow-Up
├── Conversion Tracking
├── CRM Synchronization
├── Reporting
└── Administration
 
⸻
 
17.7 Core Domain Objects
The primary domain objects are:
	•	Lead source
	•	Lead source connection
	•	Lead
	•	Lead identity
	•	Contact point
	•	Consent record
	•	Lead submission
	•	Lead message
	•	Lead attachment
	•	Lead classification
	•	Qualification
	•	Service request
	•	Location match
	•	Routing decision
	•	Assignment
	•	Conversation
	•	Communication attempt
	•	Communication template
	•	Follow-up sequence
	•	Appointment reference
	•	Estimate reference
	•	Conversion
	•	Lost reason
	•	Spam decision
	•	Lead event
	•	External CRM reference
	•	Report
 
⸻
 
17.8 Lead Source
A lead source identifies where a lead originated.
Examples:
website_form
website_chat
phone_call
sms
email
google_business_profile
google_ads
meta_ads
bing_ads
referral
booking_platform
third_party_marketplace
manual_entry
crm_import
unknown
Recommended fields:
id
organization_id
name
source_type
provider
status
default_location_id
default_service_id
tracking_configuration
metadata
created_at
updated_at
 
⸻
 
17.9 Source Attribution
Source attribution should preserve:
	•	Original source
	•	Provider
	•	Campaign
	•	Medium
	•	Referrer
	•	Landing page
	•	Form
	•	Tracking number
	•	UTM values
	•	Click identifiers
	•	External lead ID
	•	First-touch source
	•	Latest-touch source where configured
The system must distinguish:
Lead origin
Marketing attribution
Operational intake channel
Example:
A lead may originate from Google Ads, submit through a website form, and later communicate through SMS.
Those are separate facts.
 
⸻
 
17.10 Lead Record
A lead represents one potential customer opportunity.
Recommended fields:
id
organization_id
primary_location_id
source_id
status
priority
urgency
quality
owner_user_id
team_id
first_received_at
first_response_at
last_activity_at
closed_at
created_at
updated_at
Lead records should not use email address or phone number as the primary identifier.
 
⸻
 
17.11 Lead Identity
A lead identity represents the person or business associated with the opportunity.
Recommended fields:
id
organization_id
display_name
first_name
last_name
company_name
identity_type
preferred_language
timezone
created_at
updated_at
Possible identity types:
person
business
property_manager
insurance_contact
vendor
unknown
Identity and opportunity should remain separate.
One identity may create multiple legitimate leads over time.
 
⸻
 
17.12 Contact Points
Contact points may include:
	•	Email
	•	Mobile phone
	•	Landline
	•	SMS-capable phone
	•	Mailing address
	•	Preferred contact channel
Recommended fields:
id
lead_identity_id
contact_type
normalized_value
display_value
verification_status
is_primary
source
created_at
updated_at
Contact points must be access-controlled because they contain personal data.
 
⸻
 
17.13 Lead Submission
A lead submission preserves the original inbound payload.
Recommended fields:
id
lead_id
source_id
external_submission_id
received_at
raw_payload_reference
normalized_payload
ip_reference
user_agent_reference
landing_page
form_id
submission_hash
status
The raw payload should use limited retention.
The normalized lead record remains the primary operational representation.
 
⸻
 
17.14 Lead Messages
A lead message represents inbound or outbound communication.
Recommended fields:
id
lead_id
conversation_id
direction
channel
sender_type
sender_reference
body
subject
provider_message_id
sent_at
received_at
delivery_status
content_classification
created_at
Direction values:
inbound
outbound
internal
Internal notes must not be represented as outbound customer messages.
 
⸻
 
17.15 Lead Attachments
Attachments may include:
	•	Photos
	•	Documents
	•	Screenshots
	•	Estimates
	•	Property-damage evidence
	•	Project files
Recommended fields:
id
lead_id
message_id
storage_reference
filename
content_type
size_bytes
scan_status
classification
uploaded_at
retention_policy
Attachments require:
	•	File validation
	•	Malware scanning where available
	•	Access control
	•	Signed download URLs
	•	Retention policy
	•	Restricted handling for sensitive documents
 
⸻
 
17.16 Lead Status
Recommended lifecycle:
new
validating
unassigned
assigned
acknowledged
contact_attempted
contacted
qualifying
qualified
appointment_requested
appointment_scheduled
estimate_requested
estimate_sent
decision_pending
converted
nurture
unresponsive
disqualified
lost
spam
duplicate
cancelled
archived
Not every organization must use every status.
The platform should support a normalized status with optional client-specific mapping.
 
⸻
 
17.17 Lead Status Rules
Status transitions should follow explicit rules.
Examples:
	•	new may become spam.
	•	new may become duplicate.
	•	assigned may become contact_attempted.
	•	qualified may become appointment_scheduled.
	•	estimate_sent may become converted or lost.
	•	converted should not silently return to new.
Manual correction should remain possible with permission and audit.
 
⸻
 
17.18 Lead Priority
Recommended priority levels:
low
normal
high
urgent
Priority should consider:
	•	Service value
	•	Customer urgency
	•	Service availability
	•	Location match
	•	Lead quality
	•	Source quality
	•	Response deadline
	•	Existing customer status
	•	Safety concerns
Priority should not be based solely on estimated revenue.
 
⸻
 
17.19 Lead Urgency
Urgency should represent time sensitivity.
Recommended urgency values:
routine
same_day
urgent
emergency
unknown
Examples:
	•	General catering inquiry: routine
	•	Private-event inquiry for next week: same-day follow-up
	•	No power in occupied home: urgent
	•	Active flooding or electrical fire risk: emergency
The product must not represent automated messaging as emergency dispatch.
 
⸻
 
17.20 Emergency Handling
Emergency indicators may trigger:
	•	Immediate human notification
	•	Automation suppression
	•	Emergency disclaimer
	•	Priority routing
	•	Phone-first contact
	•	After-hours escalation
The platform should never imply guaranteed emergency response unless the client has approved and operationally supports that claim.
A message should not instruct a customer to wait for platform response when immediate public emergency services may be appropriate.
 
⸻
 
17.21 Lead Quality
Recommended lead-quality states:
unknown
low
moderate
high
verified
invalid
Quality may consider:
	•	Contact validity
	•	Service relevance
	•	Location relevance
	•	Completeness
	•	Spam indicators
	•	Intent
	•	Budget where voluntarily supplied
	•	Timeline
	•	Duplicate history
AI-derived quality should remain advisory.
 
⸻
 
17.22 Service Request
A lead may contain one or more service requests.
Recommended fields:
id
lead_id
service_id
raw_service_text
service_match_status
priority
confidence
confirmed_by
created_at
Service matching should use the shared platform service catalog.
The system must not route a lead to a service the organization does not offer.
 
⸻
 
17.23 Location Information
Lead location data may include:
	•	Business location selected
	•	Service address
	•	City
	•	State
	•	Postal code
	•	Coordinates
	•	Service area
	•	Preferred venue
	•	Event location
Recommended fields:
lead_id
address_line_1
address_line_2
city
region
postal_code
country
latitude
longitude
location_source
verification_status
Precise addresses should be visible only to users who need them.
 
⸻
 
17.24 Location Matching
Location matching should determine:
	•	Which business location owns the lead
	•	Whether the service address is supported
	•	Whether multiple locations are eligible
	•	Whether manual review is required
Matching inputs may include:
	•	Selected location
	•	Postal code
	•	Coordinates
	•	Service area
	•	Store code
	•	Landing page
	•	Tracking number
	•	Provider location
	•	Service availability
 
⸻
 
17.25 Location Match Status
Recommended states:
unmatched
suggested
matched
ambiguous
outside_service_area
manual_review_required
An ambiguous match should block automatic external outreach if the wrong business identity could be used.
 
⸻
 
17.26 Service-Area Routing
Service-area routing should support:
	•	Radius
	•	Postal codes
	•	Cities
	•	Counties
	•	Polygons
	•	Priority zones
	•	Excluded areas
	•	Service-specific areas
	•	Time-based availability
Service-area definitions should be versioned.
A changed service area must not rewrite historical routing decisions.
 
⸻
 
17.27 Consent Model
Consent is a foundational domain object.
Consent records should identify:
id
lead_identity_id
lead_id
channel
consent_type
status
source
disclosure_version
captured_at
withdrawn_at
evidence
Possible consent types:
transactional_email
transactional_sms
marketing_email
marketing_sms
phone_call
automated_call
Transactional and marketing consent must remain distinct.
 
⸻
 
17.28 Consent Status
Recommended values:
granted
denied
unknown
not_required
withdrawn
expired
Unknown must not be treated as granted.
The platform should apply the strictest relevant rule when consent evidence is incomplete.
 
⸻
 
17.29 Consent Evidence
Consent evidence may include:
	•	Form checkbox
	•	Form disclosure
	•	Timestamp
	•	IP reference
	•	Provider record
	•	Recorded verbal consent reference
	•	Existing customer relationship
	•	Manual administrative record
The platform must preserve the disclosure version shown when consent was captured.
 
⸻
 
17.30 Communication Suppression
The system should support suppression for:
	•	SMS opt-out
	•	Email unsubscribe
	•	Do-not-call request
	•	Client blocklist
	•	Legal restriction
	•	Invalid contact
	•	Complaint
	•	Wrong person
	•	Deceased individual where known
	•	Provider suppression
Suppression should apply before any automated send.
 
⸻
 
17.31 Validation
Lead validation should include:
	•	Required fields
	•	Contact format
	•	Service match
	•	Location match
	•	Consent
	•	Duplicate check
	•	Spam check
	•	Attachment validation
	•	Provider signature
	•	Payload integrity
	•	Tenant scope
Validation failure should not always discard the lead.
Potential outcomes include:
accepted
accepted_with_warning
manual_review
rejected
quarantined
 
⸻
 
17.32 Spam Detection
Spam detection may use:
	•	Honeypot fields
	•	Rate limits
	•	CAPTCHA
	•	IP reputation where approved
	•	Repeated payloads
	•	Invalid contact patterns
	•	Suspicious links
	•	Nonsensical text
	•	Known spam signatures
	•	Submission velocity
	•	AI-assisted classification
Spam detection must allow manual correction.
 
⸻
 
17.33 Spam Status
Recommended states:
not_evaluated
likely_valid
suspected_spam
confirmed_spam
released
Suspected spam should not be permanently deleted automatically.
 
⸻
 
17.34 Duplicate Detection
Duplicate detection should consider:
	•	Same provider lead ID
	•	Same submission ID
	•	Same normalized email
	•	Same normalized phone
	•	Same service address
	•	Same service
	•	Similar message
	•	Time proximity
	•	Existing open lead
Duplicate detection should distinguish:
	•	Repeated provider delivery
	•	Repeated form submission
	•	Customer follow-up
	•	New request from existing customer
	•	Separate project at same address
 
⸻
 
17.35 Duplicate Resolution
Possible outcomes:
same_submission
merge_into_existing
link_as_related
keep_separate
manual_review
Merging must preserve:
	•	Original source
	•	All messages
	•	All consent evidence
	•	Attachments
	•	Timestamps
	•	Assignment history
	•	External IDs
 
⸻
 
17.36 Lead Qualification
Qualification should determine whether the opportunity fits the business.
Potential qualification dimensions:
	•	Service fit
	•	Location fit
	•	Timing
	•	Budget where relevant
	•	Project type
	•	Property type
	•	Event size
	•	Availability
	•	Decision authority
	•	Insurance involvement
	•	Commercial or residential
	•	Existing customer
	•	Urgency
	•	Contact validity
Qualification should be industry-specific.
 
⸻
 
17.37 Restaurant and Event Lead Qualification
Restaurant or venue inquiries may include:
	•	Event date
	•	Guest count
	•	Event type
	•	Preferred time
	•	Budget
	•	Food and beverage needs
	•	Private room
	•	Full buyout
	•	Accessibility
	•	Deposit readiness
The platform must not promise availability.
 
⸻
 
17.38 Home-Service Lead Qualification
Home-service inquiries may include:
	•	Service needed
	•	Property type
	•	Address
	•	Urgency
	•	Active damage
	•	Insurance status
	•	Ownership or authorization
	•	Preferred appointment time
	•	Access limitations
	•	Commercial or residential
	•	Safety concerns
The platform should avoid asking unnecessary sensitive questions during initial intake.
 
⸻
 
17.39 Qualification Record
Recommended fields:
id
lead_id
qualification_status
service_fit
location_fit
timeline_fit
value_band
confidence
questions_completed
qualified_by
qualified_at
reason
Qualification status:
unqualified
partially_qualified
qualified
disqualified
needs_human_review
 
⸻
 
17.40 Routing Decision
A routing decision records why a lead was assigned to a location, team, or user.
Recommended fields:
id
lead_id
routing_rule_version
location_id
team_id
user_id
reason
confidence
status
created_at
Routing decisions should be immutable after execution.
A later reroute creates a new decision.
 
⸻
 
17.41 Routing Rules
Routing may consider:
	•	Organization
	•	Location
	•	Service
	•	Service address
	•	Postal code
	•	Business hours
	•	On-call schedule
	•	Lead source
	•	Priority
	•	Language
	•	Existing customer
	•	Workload
	•	Staff capability
	•	Client-specific ownership
Rules should be explicit and testable.
 
⸻
 
17.42 Routing Hierarchy
Recommended hierarchy:
Exact provider-location mapping
    ↓
Explicit form or phone routing
    ↓
Service and geographic eligibility
    ↓
Priority routing rule
    ↓
Team availability
    ↓
Fallback queue
    ↓
Manual review
The platform must not silently assign to an arbitrary location when matching fails.
 
⸻
 
17.43 Assignment
Assignments may target:
	•	User
	•	Team
	•	Location queue
	•	Shared dispatch queue
	•	External CRM owner
Recommended fields:
id
lead_id
assignee_type
assignee_id
assigned_at
assigned_by
accepted_at
declined_at
reason
status
 
⸻
 
17.44 Assignment Status
Recommended states:
pending
assigned
accepted
declined
expired
reassigned
completed
The platform should support assignment timeouts and fallback routing.
 
⸻
 
17.45 Assignment Acceptance
Where required, assignees should accept responsibility.
If an assignment is not accepted within a configured period:
Notify
    ↓
Escalate
    ↓
Reassign
    ↓
Return to Queue
The system must avoid multiple active owners unless the workflow explicitly supports shared ownership.
 
⸻
 
17.46 Business Hours
Lead automation should reference location-specific operating hours.
Hours may include:
	•	Normal business hours
	•	Sales hours
	•	Dispatch hours
	•	Emergency hours
	•	Holiday hours
	•	Temporary closures
The Leads product should consume approved hours from shared configuration or GBP where appropriate.
It must not infer that GBP opening hours equal lead-response availability.
 
⸻
 
17.47 After-Hours Policy
Each organization or location should define:
	•	Whether acknowledgment is allowed
	•	Whether SMS is allowed
	•	Whether phone escalation occurs
	•	Which services qualify as urgent
	•	On-call routing
	•	Expected next contact time
	•	Emergency disclaimer
	•	Suppression windows
After-hours policy must be explicit.
 
⸻
 
17.48 Speed-to-Lead
Speed-to-lead measures the time from lead receipt to meaningful response.
The product should track:
received_at
validated_at
assigned_at
acknowledged_at
first_outbound_attempt_at
first_human_response_at
first_two_way_contact_at
These timestamps represent different stages.
They must not be collapsed into one metric.
 
⸻
 
17.49 Meaningful Response
A meaningful response may include:
	•	Human phone contact
	•	Human SMS
	•	Human email
	•	Confirmed appointment
	•	Approved automated interaction that addresses the request and enables progression
A generic receipt confirmation should not automatically count as successful human contact.
 
⸻
 
17.50 Response-Time Objectives
Response-time objectives may vary by:
	•	Service
	•	Urgency
	•	Source
	•	Business hours
	•	Location
	•	Client plan
	•	Lead value
Example policy:
Emergency lead:
Immediate routing

High-priority lead during business hours:
Human attempt within 5 minutes

Routine lead after hours:
Immediate acknowledgment and human follow-up next business period
Objectives must be configurable rather than hardcoded.
 
⸻
 
17.51 Acknowledgment
Acknowledgment confirms receipt.
It should:
	•	Identify the business
	•	Confirm the request was received
	•	Set realistic expectations
	•	Provide the correct next step
	•	Avoid promising service availability
	•	Respect consent
	•	Use the correct location and language
Acknowledgment is not the same as qualification or booking.
 
⸻
 
17.52 Automated Acknowledgment
Automated acknowledgment may be allowed when:
	•	Source and mapping are valid.
	•	Consent permits the channel.
	•	Contact is not suppressed.
	•	Template is approved.
	•	Current time is allowed.
	•	The lead is not high-risk or ambiguous.
	•	The correct business identity is known.
Automation should pause when these requirements are not satisfied.
 
⸻
 
17.53 Communication Channels
Initial supported channels may include:
	•	Email through Resend
	•	SMS through an approved provider
	•	Internal notification
	•	Phone task creation
	•	External CRM task
Future channels may include:
	•	WhatsApp
	•	Provider messaging
	•	Web chat
	•	Voice automation
Channel capabilities should be abstracted.
 
⸻
 
17.54 Communication Template
Recommended fields:
id
organization_id
location_id
channel
template_type
language
body
subject
required_variables
approval_status
version
status
Template types may include:
receipt_acknowledgment
after_hours_acknowledgment
qualification_question
appointment_request
follow_up
missed_contact
estimate_follow_up
closure
opt_out_confirmation
 
⸻
 
17.55 Template Variables
Variables may include:
first_name
business_name
location_name
service_name
received_time
expected_response_window
approved_phone
approved_email
appointment_link
Every variable must have:
	•	Defined source
	•	Validation
	•	Fallback behavior
	•	Escaping rules
A missing variable must not produce broken customer-facing copy.
 
⸻
 
17.56 Communication Attempt
Recommended fields:
id
lead_id
conversation_id
channel
direction
template_id
message_revision
status
provider_message_id
scheduled_at
attempted_at
delivered_at
failed_at
failure_reason
created_by
 
⸻
 
17.57 Delivery Status
Recommended statuses:
draft
scheduled
queued
sending
sent
delivered
failed
bounced
undeliverable
blocked
suppressed
cancelled
unknown
Sent must not be treated as delivered.
 
⸻
 
17.58 Communication Idempotency
Outbound communication must use idempotency based on:
	•	Lead
	•	Channel
	•	Template or message revision
	•	Workflow step
	•	Scheduled execution
Before retrying, the system should reconcile provider state where possible.
Blind duplicate messaging is prohibited.
 
⸻
 
17.59 Conversation
A conversation groups communications with a lead.
Recommended fields:
id
lead_id
channel
status
assigned_to
started_at
last_message_at
closed_at
external_thread_id
Conversation status:
open
awaiting_customer
awaiting_business
paused
closed
blocked
 
⸻
 
17.60 Two-Way Messaging
Two-way messaging should support:
	•	Inbound message ingestion
	•	Thread association
	•	Sender verification
	•	Consent and opt-out processing
	•	Assignment
	•	Notifications
	•	Human takeover
	•	Conversation closure
The system must process common SMS opt-out terms according to provider and legal requirements.
 
⸻
 
17.61 Automated Qualification
Automated qualification may ask approved questions.
Requirements:
	•	One question or small set at a time
	•	Clear business identity
	•	No unnecessary sensitive data
	•	Consent-compliant channel
	•	Human takeover
	•	Stop conditions
	•	Language support
	•	Maximum attempts
	•	Audit trail
The system must not simulate a human identity deceptively.
 
⸻
 
17.62 Automation Disclosure
Where required by law, provider policy, or client policy, automated communication should disclose that it is automated.
The disclosure approach should be configurable by:
	•	Channel
	•	Jurisdiction
	•	Message type
	•	Risk
	•	Client policy
 
⸻
 
17.63 Human Handoff
Human handoff should occur when:
	•	Lead requests a person
	•	Confidence is low
	•	Routing is ambiguous
	•	Service is unclear
	•	Emergency risk exists
	•	Customer is upset
	•	Pricing negotiation begins
	•	Sensitive information appears
	•	Automation fails
	•	Maximum automation steps are reached
	•	Client policy requires it
Handoff should preserve the full conversation context.
 
⸻
 
17.64 Follow-Up Sequences
A follow-up sequence may define:
	•	Trigger
	•	Channel
	•	Delay
	•	Message
	•	Stop conditions
	•	Maximum attempts
	•	Business-hour restrictions
	•	Consent requirement
	•	Owner
	•	Escalation
Example:
Lead acknowledged
    ↓
No human contact after configured period
    ↓
Internal alert
    ↓
Second contact attempt
    ↓
No customer response
    ↓
Final follow-up
    ↓
Move to unresponsive
 
⸻
 
17.65 Follow-Up Stop Conditions
Follow-up must stop when:
	•	Customer replies
	•	Lead converts
	•	Lead declines
	•	Lead opts out
	•	Contact is invalid
	•	Lead is marked spam
	•	Lead is disqualified
	•	Human owner pauses automation
	•	Maximum attempts reached
	•	Legal or policy block applies
 
⸻
 
17.66 Follow-Up Frequency
The system should prevent excessive outreach.
Limits should be configurable by:
	•	Channel
	•	Lead source
	•	Organization
	•	Status
	•	Time window
	•	Jurisdiction
	•	Consent type
Marketing-style nurture must remain separate from transactional lead follow-up.
 
⸻
 
17.67 Appointment References
The Leads product may store references to external scheduling records.
Recommended fields:
id
lead_id
provider
external_appointment_id
status
scheduled_start
scheduled_end
timezone
location_reference
created_at
updated_at
The external scheduling system remains authoritative unless LILOs owns the scheduling workflow.
 
⸻
 
17.68 Estimate References
Estimate records may reference:
	•	External CRM
	•	Field-service system
	•	Proposal platform
	•	Manual estimate
Recommended fields:
id
lead_id
provider
external_estimate_id
status
amount_band
sent_at
accepted_at
declined_at
Sensitive pricing should be permission-controlled.
 
⸻
 
17.69 Conversion
A conversion represents the business outcome of a lead.
Possible conversion types:
appointment_booked
estimate_scheduled
reservation_made
event_booked
job_won
deposit_paid
purchase_completed
qualified_opportunity
other
Recommended fields:
id
lead_id
conversion_type
converted_at
value
currency
source
external_reference
verified_status
created_at
Conversion value should be optional.
 
⸻
 
17.70 Conversion Verification
Conversion status may be:
unverified
provider_reported
client_reported
system_verified
reconciled
rejected
Reports should distinguish verified conversions from inferred conversions.
 
⸻
 
17.71 Lead Closure
A lead may close as:
converted
lost
disqualified
unresponsive
spam
duplicate
cancelled
Closure should require a reason where relevant.
 
⸻
 
17.72 Lost Reasons
Recommended normalized lost reasons:
no_response
price
timing
outside_service_area
service_not_offered
unavailable
competitor_selected
duplicate
invalid_contact
not_qualified
customer_cancelled
capacity
unknown
other
Organizations may map custom CRM reasons to normalized values.
 
⸻
 
17.73 Lost-Lead Analysis
The product should analyze:
	•	Source
	•	Service
	•	Location
	•	Response time
	•	Owner
	•	Lost reason
	•	Day and time
	•	Follow-up completion
	•	Qualification
	•	Customer response
The platform should avoid attributing loss to one factor without sufficient evidence.
 
⸻
 
17.74 CRM Integration
The Leads product may integrate with:
	•	Field-service CRMs
	•	Sales CRMs
	•	Restaurant event systems
	•	Booking platforms
	•	Custom systems
CRM adapters may expose:
create_lead
update_lead
read_lead
assign_owner
create_task
create_note
read_status
read_conversion
 
⸻
 
17.75 System of Record
Each organization must define the system of record for:
	•	Lead identity
	•	Lead status
	•	Assignment
	•	Conversation
	•	Appointment
	•	Estimate
	•	Conversion
Possible patterns:
LILOs authoritative
External CRM authoritative
Field-level shared authority
Authority must be explicit.
 
⸻
 
17.76 CRM Synchronization
Synchronization should support:
	•	Outbound creation
	•	Inbound updates
	•	Status mapping
	•	Owner mapping
	•	Duplicate prevention
	•	Conflict detection
	•	Retry
	•	Reconciliation
The system should not overwrite a newer external change with stale platform state.
 
⸻
 
17.77 Status Mapping
Each CRM may use different statuses.
The platform should maintain:
provider_status
normalized_status
mapping_version
direction
A provider status that cannot be mapped should create an exception rather than silently default.
 
⸻
 
17.78 Synchronization Conflict
Conflicts may occur when:
	•	Both systems update status
	•	Both systems change owner
	•	Contact details differ
	•	One system closes the lead
	•	External record is deleted
	•	Duplicate records exist
Conflict resolution should follow configured authority.
 
⸻
 
17.79 Lead Events
The product should emit events such as:
lead.created
lead.validated
lead.assigned
lead.acknowledged
lead.contacted
lead.qualified
lead.appointment_scheduled
lead.converted
lead.lost
lead.opted_out
lead.spam_confirmed
lead.escalated
Events should use the standard platform event envelope.
 
⸻
 
17.80 Coordination with SEO
The SEO product may consume aggregated lead outcomes to evaluate:
	•	Landing-page quality
	•	Query value
	•	Service demand
	•	Location demand
	•	Conversion performance
The Leads product should not expose personal lead details to SEO workflows.
 
⸻
 
17.81 Coordination with GBP
The GBP product may provide:
	•	Profile location
	•	Action URL
	•	Business hours
	•	Approved phone
	•	Booking links
The Leads product may provide aggregated conversion outcomes for profile interactions.
The products should not maintain conflicting contact or hours data.
 
⸻
 
17.82 Coordination with Content
The Content product may consume aggregated lead themes such as:
	•	Common questions
	•	Service confusion
	•	Qualification barriers
	•	Location demand
	•	High-performing topics
Lead personal data should not be inserted into content-generation context.
 
⸻
 
17.83 Coordination with Reviews
A converted customer may later participate in an approved review-request workflow.
The Leads product may provide eligibility events.
The Reviews product or a future review-request module owns the solicitation workflow.
Review gating is prohibited.
 
⸻
 
17.84 Coordination with Insights
The Insights product may consume:
	•	Lead volume
	•	Source
	•	Service
	•	Location
	•	Response time
	•	Qualification
	•	Conversion
	•	Lost reason
	•	Value
Insights should receive aggregated or appropriately permissioned data.
 
⸻
 
17.85 AI Responsibilities
AI may assist with:
	•	Lead-message classification
	•	Service matching
	•	Urgency detection
	•	Spam classification
	•	Qualification summaries
	•	Suggested routing
	•	Draft acknowledgments
	•	Draft follow-up messages
	•	Conversation summaries
	•	Lost-reason suggestions
	•	Reporting interpretation
AI must not independently:
	•	Establish consent
	•	Override suppression
	•	Promise service availability
	•	Promise prices
	•	Commit appointments
	•	Confirm emergency response
	•	Make legal eligibility decisions
	•	Mark a lead converted without evidence
	•	Contact an unverified destination
	•	Reveal unrelated client information
 
⸻
 
17.86 AI Task Registry
Initial tasks may include:
leads.message_classification
leads.service_match
leads.urgency_classification
leads.spam_classification
leads.qualification_summary
leads.routing_suggestion
leads.acknowledgment_draft
leads.follow_up_draft
leads.conversation_summary
leads.lost_reason_suggestion
leads.performance_summary
 
⸻
 
17.87 Lead Classification Output
Example schema:
{
  "service_candidates": [
    {
      "service": "water damage restoration",
      "confidence": "high"
    }
  ],
  "urgency": "emergency",
  "location_reference": {
    "city": "Carlsbad",
    "postal_code": "92008"
  },
  "risk_flags": [
    "active_water_intrusion"
  ],
  "requires_human_review": true
}
AI output does not authorize routing until deterministic service and location checks pass.
 
⸻
 
17.88 Routing Suggestion Output
Example schema:
{
  "suggested_location_id": "location_uuid",
  "suggested_team": "emergency_dispatch",
  "reason": [
    "The postal code is inside the location's approved service area.",
    "The requested service is enabled for the location."
  ],
  "confidence": "high",
  "requires_manual_review": false
}
The referenced IDs must come from provided approved candidates.
 
⸻
 
17.89 Acknowledgment Draft Output
Example schema:
{
  "channel": "sms",
  "body": "We received your request regarding water damage in Carlsbad. Our team is reviewing the details now. If there is immediate danger, leave the affected area and contact the appropriate emergency service.",
  "required_fact_checks": [
    "Confirm that emergency-intake acknowledgment is enabled.",
    "Confirm SMS consent."
  ],
  "requires_human_review": false
}
The model must not promise arrival time unless supplied by an authoritative scheduling source.
 
⸻
 
17.90 AI Grounding
AI tasks should be grounded in:
	•	Lead submission
	•	Approved services
	•	Approved service areas
	•	Location configuration
	•	Business hours
	•	Response policy
	•	Consent status
	•	Communication templates
	•	Approved contacts
	•	Existing conversation
	•	CRM status
	•	Industry rules
The model must not use unrelated historical lead data.
 
⸻
 
17.91 AI Validation
AI outputs should be validated for:
	•	Correct tenant
	•	Correct lead
	•	Correct location candidates
	•	Supported service
	•	Consent
	•	Suppression
	•	Approved contact
	•	Business hours
	•	Unsupported price
	•	Unsupported availability
	•	Unsupported emergency promise
	•	Personal-data leakage
	•	Cross-client contamination
	•	Excessive outreach
	•	Invalid language
	•	Hallucinated appointment
 
⸻
 
17.92 Human Responsibilities
Humans remain responsible for:
	•	Routing-policy design
	•	Service-area configuration
	•	Consent-policy approval
	•	Emergency handling
	•	Lead ownership
	•	Qualification decisions where ambiguous
	•	Pricing
	•	Scheduling commitments
	•	Conversion confirmation
	•	Sensitive communication
	•	Client communication
	•	Compliance review
 
⸻
 
17.93 Permissions
Recommended permissions:
leads.view
leads.view_contact_details
leads.view_sensitive
leads.create
leads.edit
leads.assign
leads.accept_assignment
leads.contact
leads.send_email
leads.send_sms
leads.manage_conversation
leads.qualify
leads.schedule
leads.convert
leads.close
leads.merge
leads.mark_spam
leads.release_spam
leads.configure_routing
leads.configure_templates
leads.configure_consent
leads.connect_crm
leads.export
leads.view_reports
leads.manage_runtime
Contact details and exports require stronger controls than general lead visibility.
 
⸻
 
17.94 Notification Types
Notifications may include:
	•	New urgent lead
	•	New emergency lead
	•	Unassigned lead
	•	Assignment awaiting acceptance
	•	Response objective approaching
	•	Response objective missed
	•	Customer replied
	•	Contact failed
	•	Consent unavailable
	•	Routing conflict
	•	CRM sync failed
	•	Lead stalled
	•	Appointment created
	•	Lead converted
	•	High spam volume
	•	Provider outage
 
⸻
 
17.95 Lead Inbox
The lead inbox should display:
	•	Name or display identity
	•	Service
	•	Location
	•	Source
	•	Received time
	•	Status
	•	Priority
	•	Urgency
	•	Owner
	•	Last activity
	•	Response-time state
	•	Consent indicators
Recommended filters:
	•	Organization
	•	Location
	•	Service
	•	Source
	•	Status
	•	Priority
	•	Urgency
	•	Assignee
	•	Response objective
	•	Created date
	•	Conversion state
 
⸻
 
17.96 Lead Detail
The lead detail should include:
	•	Contact identity
	•	Contact methods
	•	Consent
	•	Source
	•	Attribution
	•	Service request
	•	Location
	•	Original submission
	•	Attachments
	•	Classification
	•	Routing
	•	Assignment
	•	Conversation
	•	Qualification
	•	Appointments
	•	Estimates
	•	Conversion
	•	Activity
	•	External CRM state
	•	Internal notes
Sensitive data should be hidden unless the user has permission.
 
⸻
 
17.97 Communication Interface
The communication interface should show:
	•	Channel
	•	Conversation history
	•	Delivery state
	•	Consent
	•	Opt-out status
	•	Approved templates
	•	Draft message
	•	Human or automated sender
	•	Next scheduled follow-up
	•	Stop controls
Internal notes must be visually separate from customer communications.
 
⸻
 
17.98 Lead Timeline
The lead timeline should include:
	•	Submission
	•	Validation
	•	Routing
	•	Assignment
	•	Acknowledgment
	•	Contact attempts
	•	Customer replies
	•	Qualification
	•	Scheduling
	•	Estimate
	•	Conversion
	•	Closure
	•	CRM synchronization
The timeline should remain business-readable.
 
⸻
 
17.99 Multi-Location Operations
The product should support:
	•	Portfolio inbox
	•	Shared service catalog
	•	Location-specific services
	•	Location routing
	•	Shared teams
	•	Location-specific hours
	•	Shared templates
	•	Location overrides
	•	Cross-location reporting
	•	Rerouting
Every outbound message must use the correct business identity.
 
⸻
 
17.100 Cross-Location Safeguards
The system must prevent:
	•	Wrong business name
	•	Wrong location
	•	Wrong phone number
	•	Wrong service
	•	Wrong service area
	•	Wrong hours
	•	Wrong booking link
	•	Wrong representative
	•	Wrong language
	•	Wrong CRM account
Bulk lead operations require per-lead validation.
 
⸻
 
17.101 Reporting Metrics
Client-facing metrics may include:
	•	Lead volume
	•	Lead source
	•	Service demand
	•	Location demand
	•	Initial response time
	•	Human response time
	•	Contact rate
	•	Qualification rate
	•	Appointment rate
	•	Estimate rate
	•	Conversion rate
	•	Lost reasons
	•	Unresponsive rate
	•	Spam rate
	•	Data freshness
 
⸻
 
17.102 Response-Time Reporting
Response reporting should distinguish:
	•	Acknowledgment time
	•	First outbound attempt
	•	First human response
	•	First two-way contact
	•	Assignment time
	•	Response-objective compliance
Median and percentile metrics are preferable to averages alone.
 
⸻
 
17.103 Source Reporting
Source reporting should include:
	•	Leads
	•	Valid leads
	•	Qualified leads
	•	Conversions
	•	Conversion rate
	•	Response time
	•	Lost reasons
	•	Verified value where available
	•	Attribution confidence
Lead volume alone does not represent source quality.
 
⸻
 
17.104 Agency Reporting
Agency users should additionally see:
	•	Ingestion failures
	•	Routing conflicts
	•	Unassigned backlog
	•	Response-objective breaches
	•	Communication failures
	•	Consent blocks
	•	Spam false positives
	•	CRM sync failures
	•	AI correction rate
	•	Duplicate merge rate
	•	Client follow-up compliance
	•	Provider costs
 
⸻
 
17.105 Product Success Metrics
Operational Metrics
	•	Lead-ingestion reliability
	•	Validation time
	•	Routing time
	•	Assignment time
	•	Acknowledgment time
	•	Human response time
	•	Communication delivery rate
	•	CRM sync success
	•	Reconciliation completion
Quality Metrics
	•	Routing accuracy
	•	Duplicate-detection accuracy
	•	Spam correction rate
	•	Wrong-location error rate
	•	Consent violation rate
	•	AI service-match correction rate
	•	Unsupported-promise rate
	•	Contact-data exposure incidents
Business Metrics
	•	Contact rate
	•	Qualification rate
	•	Appointment rate
	•	Estimate rate
	•	Conversion rate
	•	Verified lead value
	•	Reduced missed leads
	•	Reduced response time
	•	Improved source quality
	•	Lower unresponsive rate
 
⸻
 
17.106 Failure Modes
Expected failure modes include:
	•	Form webhook unavailable
	•	Invalid provider signature
	•	Duplicate submission
	•	Contact information invalid
	•	Location ambiguous
	•	Service unsupported
	•	Lead outside service area
	•	Consent missing
	•	SMS suppressed
	•	Email bounced
	•	Provider timeout
	•	Assignment unaccepted
	•	Wrong CRM mapping
	•	CRM unavailable
	•	Status conflict
	•	Communication delivered but callback failed
	•	Lead reply cannot be matched
	•	AI misclassifies urgency
	•	Spam falsely detected
	•	Emergency lead not escalated
	•	Wrong-location message attempt
	•	External conversion not synchronized
 
⸻
 
17.107 Failure Handling
Each failure should define:
	•	Error category
	•	Retry eligibility
	•	Customer-contact risk
	•	User-visible message
	•	Internal diagnostic
	•	Lead state impact
	•	Required next action
	•	Reconciliation behavior
	•	Escalation owner
Lead capture failures should preserve the submission whenever safely possible.
 
⸻
 
17.108 Reconciliation
Reconciliation is required when:
	•	Provider message outcome is ambiguous.
	•	CRM creation may have succeeded.
	•	External assignment differs.
	•	A reply cannot be matched.
	•	Conversion state conflicts.
	•	Duplicate external records exist.
	•	Appointment status differs.
Reconciliation should:
	1.	Retrieve authoritative external state.
	2.	Compare identifiers and timestamps.
	3.	Apply configured authority.
	4.	Preserve conflicts.
	5.	Avoid duplicate customer contact.
	6.	Escalate unresolved ambiguity.
 
⸻
 
17.109 Security Considerations
The product must protect:
	•	Names
	•	Emails
	•	Phone numbers
	•	Addresses
	•	Property information
	•	Conversation content
	•	Attachments
	•	Estimates
	•	Conversion values
	•	CRM credentials
	•	SMS and email credentials
	•	Internal notes
Personal data must not be visible through general portfolio reporting.
 
⸻
 
17.110 Privacy Considerations
The product should apply:
	•	Data minimization
	•	Purpose limitation
	•	Consent evidence
	•	Channel suppression
	•	Retention
	•	Access logging
	•	Export controls
	•	Deletion and anonymization workflows
	•	Sensitive attachment restrictions
Lead data must not be repurposed for unrelated marketing without appropriate authorization and consent.
 
⸻
 
17.111 Retention
Retention should be configurable according to:
	•	Client agreement
	•	Business need
	•	Conversion state
	•	Legal requirements
	•	Consent
	•	Industry
	•	Data classification
Possible actions:
retain
archive
anonymize
delete
restrict
Audit and financial records may require separate retention.
 
⸻
 
17.112 Operational Requirements
The product requires:
	•	Secure intake endpoints
	•	Webhook processing
	•	Email ingestion where supported
	•	SMS ingestion
	•	Validation workers
	•	Deduplication
	•	Routing
	•	Assignment timers
	•	Response-objective timers
	•	Communication workers
	•	Consent enforcement
	•	Follow-up scheduling
	•	CRM synchronization
	•	Reconciliation
	•	Reporting
	•	Provider-health monitoring
	•	Runtime controls
 
⸻
 
17.113 Product Health
Recommended health states:
healthy
intake_degraded
routing_degraded
connection_required
communication_degraded
crm_sync_delayed
assignment_backlog
response_objective_at_risk
consent_configuration_required
provider_degraded
A degraded CRM should not block lead capture.
 
⸻
 
17.114 Runtime Controls
Authorized operators should be able to:
	•	Pause automated email
	•	Pause automated SMS
	•	Pause one organization
	•	Pause one location
	•	Pause one source
	•	Pause follow-up sequences
	•	Force manual routing
	•	Force human approval
	•	Disable AI classification
	•	Disable CRM writes
	•	Re-run routing
	•	Re-run synchronization
	•	Block one lead from automation
	•	Activate incident mode
All runtime actions must be audited.
 
⸻
 
17.115 Testing Requirements
Testing should cover:
	•	Tenant isolation
	•	Secure intake
	•	Provider signature validation
	•	Submission deduplication
	•	Lead identity separation
	•	Contact normalization
	•	Consent enforcement
	•	Opt-out processing
	•	Spam detection
	•	Manual spam release
	•	Service matching
	•	Location matching
	•	Service-area routing
	•	Assignment
	•	Assignment timeout
	•	After-hours policy
	•	Emergency routing
	•	Template variables
	•	Communication idempotency
	•	Delivery-state handling
	•	Inbound reply matching
	•	Follow-up stop conditions
	•	CRM synchronization
	•	Status conflict
	•	Conversion verification
	•	Data export permissions
	•	Runtime controls
 
⸻
 
17.116 AI Evaluation Dataset
The Leads AI evaluation dataset should include:
	•	Restaurant event inquiries
	•	Reservation-related inquiries
	•	Home-service emergencies
	•	Routine home-service leads
	•	Unsupported services
	•	Out-of-area leads
	•	Ambiguous locations
	•	Spam
	•	Duplicate submissions
	•	Consent-sensitive cases
	•	Pricing questions
	•	Customer frustration
	•	Multiple languages
	•	Personal-data-heavy messages
	•	Wrong-location traps
	•	False emergency language
	•	Valid emergency language
Human-reviewed examples should be versioned.
 
⸻
 
17.117 Minimum Viable Leads Product
The minimum viable product should include:
Intake
	•	Website form intake
	•	Manual lead entry
	•	Secure webhook endpoint
	•	Submission storage
	•	Source attribution
Validation
	•	Contact validation
	•	Consent records
	•	Duplicate detection
	•	Spam detection
	•	Service matching
	•	Location routing
Operations
	•	Lead inbox
	•	Assignment
	•	Status
	•	Acknowledgment
	•	Email communication
	•	SMS through an approved provider
	•	Human handoff
	•	Response-time tracking
Outcome
	•	Qualification
	•	Appointment reference
	•	Conversion
	•	Lost reason
	•	Reporting
Platform Controls
	•	Permissions
	•	Audit
	•	Notifications
	•	Runtime pause
	•	Tenant isolation
	•	Manual operation without AI
 
⸻
 
17.118 Implementation Phases
Phase 1 — Lead Foundation
Implement:
	•	Lead sources
	•	Secure intake
	•	Lead records
	•	Identity
	•	Contact points
	•	Submissions
	•	Inbox
	•	Lead detail
	•	Manual status management
Phase 2 — Validation and Routing
Implement:
	•	Consent
	•	Suppression
	•	Contact validation
	•	Duplicate detection
	•	Spam detection
	•	Service matching
	•	Location matching
	•	Routing rules
	•	Assignment
Phase 3 — Speed-to-Lead
Implement:
	•	Response objectives
	•	Business-hour policy
	•	Acknowledgment
	•	Email
	•	SMS adapter
	•	Delivery tracking
	•	Human handoff
	•	Notifications
Phase 4 — Follow-Up and Qualification
Implement:
	•	Conversation
	•	Inbound replies
	•	Qualification
	•	Follow-up sequences
	•	Stop conditions
	•	Appointment references
	•	Lost reasons
Phase 5 — CRM and Conversion
Implement:
	•	CRM adapters
	•	Status mapping
	•	Synchronization
	•	Conflict handling
	•	Conversion tracking
	•	Value reporting
	•	Reconciliation
Phase 6 — Advanced Intelligence
Implement:
	•	AI-assisted classification
	•	Suggested routing
	•	Conversation summaries
	•	Source-quality analysis
	•	Stalled-lead detection
	•	Advanced multi-location routing
 
⸻
 
17.119 Future Capabilities
Potential future capabilities include:
	•	Voice and call intelligence
	•	Call recording integrations
	•	Automated call summaries
	•	Appointment scheduling
	•	Quote or estimate workflows
	•	Field-service dispatch
	•	Advanced lead scoring
	•	Revenue forecasting
	•	Customer identity resolution
	•	Multi-touch attribution
	•	Website chat
	•	WhatsApp
	•	AI voice intake
	•	Customer reactivation
	•	Review-request eligibility
	•	Referral tracking
	•	Capacity-aware routing
	•	Advanced sales coaching
Future capabilities must preserve consent, identity, audit, human control, and tenant isolation.
 
⸻
 
17.120 Leads Guardrails
The following are prohibited unless formally approved:
	1.	Sending automated messages without valid channel authorization
	2.	Treating unknown consent as granted
	3.	Ignoring opt-outs
	4.	Contacting suppressed recipients
	5.	Sending to an unverified location mapping
	6.	Assigning unsupported services
	7.	Routing outside an approved service area without review
	8.	Promising service availability without authoritative data
	9.	Promising emergency response times without operational support
	10.	Inventing prices or estimates
	11.	Confirming appointments without a scheduling authority
	12.	Marking leads converted without evidence
	13.	Treating acknowledgment as human contact
	14.	Treating sent messages as delivered
	15.	Blindly retrying outbound communication
	16.	Sending duplicate follow-up messages
	17.	Continuing follow-up after customer response or opt-out
	18.	Combining transactional and marketing consent
	19.	Exposing contact details to unauthorized users
	20.	Passing lead personal data into unrelated AI workflows
	21.	Enriching lead identities without approved purpose
	22.	Deleting duplicate submissions before preserving history
	23.	Allowing AI to establish consent
	24.	Allowing AI to make final emergency, legal, or eligibility decisions
	25.	Silently resolving CRM conflicts
	26.	Overwriting newer external CRM data
	27.	Hiding missed response objectives
	28.	Using source volume as the only quality metric
	29.	Reusing one location’s contact identity for another location
	30.	Allowing the Leads product to bypass shared workflow, security, approval, audit, or notification controls
 
⸻
 
17.121 Acceptance Requirements
The initial Leads product is not production-ready until it supports:
	•	Secure lead intake
	•	Source attribution
	•	Identity and contact normalization
	•	Consent records
	•	Suppression
	•	Duplicate detection
	•	Spam detection
	•	Service matching
	•	Location matching
	•	Routing
	•	Assignment
	•	Business-hour policy
	•	Acknowledgment
	•	Email communication
	•	SMS communication through an approved provider
	•	Delivery-state tracking
	•	Human handoff
	•	Qualification
	•	Follow-up stop conditions
	•	Response-time measurement
	•	Conversion tracking
	•	Lost reasons
	•	Reporting
	•	Permissions
	•	Audit history
	•	Tenant isolation
	•	Personal-data controls
	•	Runtime pause controls
	•	Manual operation without AI
 
⸻
 
17.122 Section Decisions
This section establishes the following decisions:
	1.	The Leads product manages the complete lifecycle from intake through verified conversion or closure.
	2.	Lead source, marketing attribution, and communication channel remain separate concepts.
	3.	Lead identity and lead opportunity remain separate domain objects.
	4.	Consent is an explicit, versioned, and auditable domain object.
	5.	Transactional and marketing consent remain separate.
	6.	Unknown consent is never treated as granted.
	7.	Service and location routing use approved platform configuration.
	8.	Ambiguous routing blocks unsafe automated communication.
	9.	Routing decisions are immutable records and rerouting creates new decisions.
	10.	Assignment may require acceptance and may expire.
	11.	Speed-to-lead includes separate acknowledgment, human response, and two-way-contact measurements.
	12.	Automated acknowledgment does not automatically count as human contact.
	13.	Business-hours and after-hours lead policies are independent from public GBP hours.
	14.	Emergency indicators require priority routing and do not create a promise of emergency service.
	15.	Outbound communication uses approved templates, consent validation, idempotency, and delivery-state tracking.
	16.	Follow-up sequences have explicit limits and stop conditions.
	17.	Human handoff is mandatory when automation lacks confidence, permission, or appropriate scope.
	18.	External CRM authority is explicitly configured by field or domain.
	19.	CRM conflicts are preserved and resolved through configured authority rather than silent overwrite.
	20.	Conversion reporting distinguishes inferred, client-reported, provider-reported, and verified outcomes.
	21.	Lead personal data is excluded from unrelated SEO, Content, GBP, Reviews, and Insights workflows.
	22.	AI supports classification, summarization, drafting, and routing suggestions.
	23.	AI does not establish consent, promise prices or availability, confirm appointments, or determine conversion.
	24.	The minimum viable product includes intake, validation, routing, acknowledgment, communication, assignment, qualification, conversion tracking, reporting, and manual operation.
	25.	No outbound lead communication may occur without confirmed tenant, destination, consent, suppression, business identity, policy, and idempotency context.

---

Section 18 — Insights Product Specification
18.1 Purpose of This Product
The Insights product converts data from across the LILOs platform into understandable, evidence-based business intelligence.
It provides a shared analytical layer for:
	•	Performance monitoring
	•	Cross-product reporting
	•	KPI calculation
	•	Trend analysis
	•	Anomaly detection
	•	Goal tracking
	•	Attribution
	•	Forecasting where justified
	•	Operational diagnostics
	•	Executive summaries
	•	Recommendation support
	•	Client reporting
	•	Agency portfolio analysis
The Insights product is responsible for helping users understand:
	•	What happened
	•	Where it happened
	•	Why it may have happened
	•	What data supports the interpretation
	•	What requires attention
	•	What action should be considered next
The product does not merely display charts.
It creates a governed, explainable, and reusable decision-support system across SEO, GBP, Reviews, Content, Leads, billing, and future products.
 
⸻
 
18.2 Business Problem
Marketing and operational data is commonly fragmented across:
	•	Google Search Console
	•	Google Analytics
	•	Google Business Profile
	•	Review platforms
	•	Website forms
	•	Phone systems
	•	CRMs
	•	Booking systems
	•	Advertising platforms
	•	Content systems
	•	Rank trackers
	•	Spreadsheets
	•	Manual reports
This creates recurring problems:
	•	Conflicting metric definitions
	•	Inconsistent date ranges
	•	Duplicate reporting
	•	Data freshness hidden from users
	•	Attribution overstated
	•	Performance summarized without context
	•	Vanity metrics emphasized over business outcomes
	•	Multiple versions of the same KPI
	•	Reports created manually every month
	•	Declines identified too late
	•	Recommendations disconnected from evidence
	•	Product teams interpreting the same data differently
	•	Clients unable to understand what matters
	•	Agency operators spending excessive time preparing reports
The Insights product must support the full analytical loop:
Collect
    ↓
Normalize
    ↓
Validate
    ↓
Aggregate
    ↓
Compare
    ↓
Detect
    ↓
Interpret
    ↓
Explain
    ↓
Recommend
    ↓
Measure
    ↓
Learn
The product is not a replacement for source systems.
It is the governed interpretation and reporting layer above them.
 
⸻
 
18.3 Product Goals
The Insights product should:
	1.	Provide consistent KPI definitions.
	2.	Normalize data from multiple products and providers.
	3.	Display data freshness and limitations.
	4.	Support organization, location, product, service, and campaign analysis.
	5.	Connect marketing activity to measurable business outcomes.
	6.	Identify meaningful changes and anomalies.
	7.	Distinguish correlation from causation.
	8.	Generate clear executive summaries.
	9.	Reduce manual reporting work.
	10.	Support client-facing and agency-facing reporting.
	11.	Preserve access controls across aggregated data.
	12.	Provide drill-down from summary to evidence.
	13.	Support goals, benchmarks, and targets.
	14.	Measure recommendation and workflow outcomes.
	15.	Remain functional without AI.
 
⸻
 
18.4 Non-Goals
The initial Insights product is not:
	•	A general-purpose enterprise data warehouse
	•	A replacement for every provider analytics interface
	•	A guaranteed attribution system
	•	A financial accounting platform
	•	A machine-learning experimentation platform
	•	A universal forecasting engine
	•	A customer data platform
	•	A raw SQL interface for ordinary users
	•	A system that automatically changes strategy without approval
	•	A system that conceals uncertainty
	•	A system that treats every statistical change as meaningful
	•	A system that claims causation without sufficient evidence
The product may use warehouse-style analytical patterns while remaining proportionate to the initial platform architecture.
 
⸻
 
18.5 Primary Users
Agency Executive
Responsibilities:
	•	Review portfolio performance
	•	Identify account risk
	•	Monitor product adoption
	•	Review agency operational efficiency
	•	Track commercial health
 
⸻
 
Agency Administrator
Responsibilities:
	•	Configure reports
	•	Manage metric definitions
	•	Review integration health
	•	Monitor cross-account data quality
	•	Control reporting access
 
⸻
 
Account Manager
Responsibilities:
	•	Review client performance
	•	Prepare reports
	•	Explain meaningful changes
	•	Identify next actions
	•	Track unresolved issues
 
⸻
 
Product Specialist
Responsibilities:
	•	Analyze product-specific performance
	•	Validate anomalies
	•	Investigate recommendations
	•	Review completed work and outcomes
 
⸻
 
Client Administrator
Responsibilities:
	•	Review organization and location performance
	•	Configure business goals
	•	Approve reporting audiences
	•	Validate business context
 
⸻
 
Client Executive
Responsibilities:
	•	Review high-level outcomes
	•	Understand priorities
	•	Compare locations
	•	Monitor progress against goals
 
⸻
 
Client Viewer
Responsibilities:
	•	View authorized dashboards
	•	View reports
	•	Review completed work
	•	Access approved exports
 
⸻
 
18.6 Product Scope
The Insights product contains the following functional areas:
Insights Product

├── Data Sources
├── Metric Registry
├── Dimension Registry
├── Data Normalization
├── Data Quality
├── Aggregation
├── Goals and Targets
├── Benchmarks
├── Trend Analysis
├── Anomaly Detection
├── Attribution
├── Outcome Measurement
├── Recommendation Intelligence
├── Dashboards
├── Reports
├── Executive Summaries
├── Exports
└── Administration
 
⸻
 
18.7 Core Domain Objects
The primary domain objects are:
	•	Insight source
	•	Metric definition
	•	Dimension definition
	•	Metric observation
	•	Metric aggregate
	•	Goal
	•	Target
	•	Benchmark
	•	Comparison period
	•	Annotation
	•	Event marker
	•	Anomaly
	•	Trend
	•	Insight
	•	Insight evidence
	•	Recommendation reference
	•	Attribution model
	•	Attribution result
	•	Outcome measurement
	•	Dashboard
	•	Dashboard widget
	•	Report
	•	Report section
	•	Report revision
	•	Scheduled delivery
	•	Export
	•	Data-quality issue
 
⸻
 
18.8 Insight Source
An insight source represents a product or provider contributing analytical data.
Examples:
	•	SEO product
	•	GBP product
	•	Reviews product
	•	Content product
	•	Leads product
	•	Billing system
	•	Google Search Console
	•	Google Analytics
	•	External CRM
	•	Rank tracker
	•	Call-tracking provider
	•	Booking provider
Recommended fields:
id
organization_id
source_type
provider
product_key
integration_connection_id
status
authority_scope
last_synced_at
data_available_from
metadata
created_at
updated_at
The product should prefer normalized platform product data over direct provider access when the platform product already owns that domain.
 
⸻
 
18.9 Analytical Authority
The authoritative source must be defined for each analytical domain.
Examples:
Search impressions:
SEO product normalized Search Console data

GBP calls:
GBP product normalized performance data

Review response time:
Reviews product

Lead conversion:
Leads product or configured external CRM

Subscription revenue:
Billing system
Insights must not independently redefine product-owned state.
It consumes normalized records and produces analytical interpretations.
 
⸻
 
18.10 Metric Registry
Every supported metric must be defined in a central registry.
Recommended fields:
id
metric_key
display_name
description
product_owner
data_type
unit
aggregation_type
directionality
default_format
freshness_expectation
calculation_version
status
Example metric keys:
seo.organic_clicks
seo.non_branded_clicks
gbp.website_clicks
reviews.average_rating
reviews.median_response_time
content.organic_conversions
leads.qualified_leads
leads.conversion_rate
billing.monthly_recurring_revenue
Metric keys must be stable and machine-readable.
 
⸻
 
18.11 Metric Definition
A metric definition must document:
	•	Business meaning
	•	Source
	•	Calculation
	•	Unit
	•	Valid dimensions
	•	Aggregation behavior
	•	Time granularity
	•	Freshness expectation
	•	Known limitations
	•	Ownership
	•	Version
	•	Deprecation status
A metric is not production-ready until its definition is explicit.
 
⸻
 
18.12 Metric Types
Supported metric types may include:
count
sum
average
median
percentage
ratio
currency
duration
rank
score
distribution
boolean
status
The metric type should control:
	•	Formatting
	•	Aggregation
	•	Comparison
	•	Visualization
	•	Validation
 
⸻
 
18.13 Aggregation Types
Recommended aggregation types:
sum
average
weighted_average
median
minimum
maximum
latest
distinct_count
ratio_of_sums
non_aggregatable
custom
The platform must not average percentages or ranks unless the metric definition explicitly allows it.
 
⸻
 
18.14 Metric Directionality
Directionality indicates whether movement is typically favorable.
Possible values:
higher_is_better
lower_is_better
target_range
context_dependent
neutral
Examples:
	•	Qualified leads: higher is generally better.
	•	Median response time: lower is generally better.
	•	Average rank: lower numerical value is better.
	•	Refund rate: context-dependent and normally lower is better.
	•	Review volume: higher may not be meaningful without quality context.
Directionality informs presentation but does not replace interpretation.
 
⸻
 
18.15 Metric Units
Supported units may include:
	•	Count
	•	Percentage
	•	Seconds
	•	Minutes
	•	Hours
	•	Days
	•	Position
	•	Score
	•	Miles
	•	Dollars
	•	Other configured currencies
	•	No unit
Currency metrics must preserve their source currency.
The product must not aggregate different currencies without an explicit conversion method and dated exchange-rate source.
 
⸻
 
18.16 Dimension Registry
Dimensions define how metrics may be segmented.
Common dimensions include:
	•	Organization
	•	Location
	•	Product
	•	Service
	•	Page
	•	Query
	•	Keyword
	•	Campaign
	•	Channel
	•	Source
	•	Device
	•	Country
	•	Region
	•	Review topic
	•	Lead status
	•	Conversion type
	•	User
	•	Team
	•	Date
	•	Week
	•	Month
	•	Quarter
	•	Year
Recommended fields:
id
dimension_key
display_name
description
owner
value_type
hierarchy
status
 
⸻
 
18.17 Dimension Compatibility
Each metric must declare valid dimensions.
Examples:
seo.organic_clicks may support:
	•	Organization
	•	Location
	•	Page
	•	Query
	•	Device
	•	Country
	•	Date
reviews.average_rating may support:
	•	Organization
	•	Location
	•	Review source
	•	Topic
	•	Date
The system must reject invalid analytical combinations.
 
⸻
 
18.18 Metric Observation
A metric observation represents a normalized measured value.
Recommended fields:
id
organization_id
location_id
metric_key
observed_at
period_start
period_end
granularity
value_numeric
value_text
unit
dimensions
source_id
source_record_reference
calculation_version
quality_status
created_at
Observations should remain immutable after finalization.
Corrections create replacement or superseding records.
 
⸻
 
18.19 Metric Aggregate
Aggregates may be materialized for performance.
Recommended fields:
id
organization_id
location_id
metric_key
period_start
period_end
granularity
dimension_hash
dimensions
value
source_count
calculation_version
computed_at
quality_status
Aggregates must be reproducible from source observations or documented transformation logic.
 
⸻
 
18.20 Time Granularity
Supported granularities may include:
hour
day
week
month
quarter
year
rolling_period
custom
Not every source supports every granularity.
The interface should not imply hourly precision when only daily data exists.
 
⸻
 
18.21 Timezone Rules
Metrics must retain their relevant timezone context.
Potential timezones include:
	•	Provider timezone
	•	Organization timezone
	•	Location timezone
	•	User display timezone
	•	UTC storage timezone
The system should store timestamps in UTC while preserving the business timezone used for period boundaries.
 
⸻
 
18.22 Date Completeness
Every reporting period should indicate whether it is:
complete
partial
provider_delayed
estimated
provisional
unknown
Current-day or current-month comparisons should not be presented as complete unless the data source supports real-time finality.
 
⸻
 
18.23 Comparison Periods
Supported comparisons should include:
	•	Previous period
	•	Previous week
	•	Previous month
	•	Previous quarter
	•	Previous year
	•	Year over year
	•	Custom baseline
	•	Pre-implementation period
	•	Post-implementation period
	•	Goal comparison
	•	Benchmark comparison
Comparison logic must align equivalent period lengths and business timezones.
 
⸻
 
18.24 Comparable Period Rules
The product should account for:
	•	Day count
	•	Day-of-week mix
	•	Holidays
	•	Seasonality
	•	Business closures
	•	Provider delays
	•	Partial periods
	•	Leap years
	•	Location timezone
	•	Campaign duration
A 28-day period should not be silently compared with a 31-day period without disclosure.
 
⸻
 
18.25 Data Normalization
Normalization should standardize:
	•	Metric names
	•	Units
	•	Date boundaries
	•	Timezones
	•	Source identifiers
	•	Location identifiers
	•	Campaign identifiers
	•	Service identifiers
	•	Status values
	•	Currency
	•	Missing values
	•	Provider-specific definitions
Normalization must preserve the original provider meaning.
 
⸻
 
18.26 Missing Data
Missing values must remain distinct from zero.
Recommended states:
present
zero
missing
not_applicable
not_available
provider_delayed
suppressed
invalid
Examples:
	•	Zero calls means the provider reported zero.
	•	Missing calls means no valid value was received.
	•	Not available means the provider does not expose the metric.
	•	Suppressed may indicate privacy or provider thresholding.
 
⸻
 
18.27 Data-Quality Status
Recommended quality states:
valid
provisional
partial
suspect
invalid
corrected
suppressed
Data marked suspect or invalid should not drive automatic recommendations without review.
 
⸻
 
18.28 Data-Quality Checks
Checks should include:
	•	Missing periods
	•	Duplicate observations
	•	Negative values where invalid
	•	Impossible percentages
	•	Sudden zero values
	•	Unexpected spikes
	•	Source mismatch
	•	Currency mismatch
	•	Location mismatch
	•	Timezone shift
	•	Provider-definition change
	•	Aggregation inconsistency
	•	Stale data
	•	Incomplete current period
	•	Broken dimensional mapping
 
⸻
 
18.29 Data-Quality Issue
Recommended fields:
id
organization_id
location_id
source_id
metric_key
issue_type
severity
status
detected_at
period_start
period_end
evidence
resolution
resolved_at
Quality issue severity should reflect reporting impact.
 
⸻
 
18.30 Data Freshness
The product must display freshness for every major data domain.
Freshness includes:
	•	Latest available data date
	•	Latest successful sync
	•	Expected provider delay
	•	Current delay
	•	Quality status
	•	Partial-period warning
	•	Source health
A report may include metrics with different freshness dates.
This must be visible.
 
⸻
 
18.31 Freshness States
Recommended states:
current
within_expected_delay
delayed
stale
unavailable
unknown
Freshness thresholds should be defined by metric or source.
 
⸻
 
18.32 Goal
A goal represents a desired business outcome.
Recommended fields:
id
organization_id
location_id
name
description
goal_type
metric_key
target_type
target_value
period_start
period_end
status
owner
created_at
updated_at
Goal types may include:
increase
decrease
maintain
reach
stay_within_range
complete
 
⸻
 
18.33 Goal Scope
Goals may apply to:
	•	Organization
	•	Location
	•	Product
	•	Service
	•	Campaign
	•	Metric
	•	Workflow
	•	Team
Goals must define one authoritative scope.
 
⸻
 
18.34 Goal Target Types
Supported target types may include:
absolute
percentage_change
minimum
maximum
range
milestone
trend
Examples:
	•	Reach 100 qualified leads in a quarter.
	•	Reduce median lead response time below five minutes.
	•	Maintain an average review rating between 4.5 and 5.0.
	•	Increase non-branded organic clicks by 15% year over year.
 
⸻
 
18.35 Goal Status
Recommended lifecycle:
draft
active
at_risk
on_track
achieved
missed
paused
cancelled
archived
Goal status should be calculated from evidence where possible but remain manually reviewable.
 
⸻
 
18.36 Target Progress
Progress calculations should account for:
	•	Current value
	•	Expected pace
	•	Period elapsed
	•	Seasonality
	•	Data completeness
	•	Directionality
	•	Target type
The product must not label a goal missed before the measurement period is complete unless failure is mathematically unavoidable.
 
⸻
 
18.37 Benchmarks
Benchmarks provide reference context.
Possible benchmark sources:
	•	Organization history
	•	Location portfolio
	•	Industry cohort
	•	Product default
	•	Client target
	•	Agency-defined standard
	•	Provider benchmark
Recommended fields:
id
benchmark_key
scope
metric_key
segment_definition
period
value
source
confidence
status
 
⸻
 
18.38 Benchmark Restrictions
Benchmarks must state:
	•	Population
	•	Time period
	•	Sample size
	•	Source
	•	Geography
	•	Industry
	•	Calculation
	•	Limitations
The platform should not present an opaque industry average as authoritative.
 
⸻
 
18.39 Portfolio Benchmarking
Multi-location organizations may compare:
	•	Locations
	•	Regions
	•	Services
	•	Teams
	•	Campaigns
Portfolio comparisons should account for:
	•	Business size
	•	Operating hours
	•	Service mix
	•	Market size
	•	Location age
	•	Data availability
A small location should not be judged solely against a flagship location’s total volume.
 
⸻
 
18.40 Trend
A trend represents sustained movement over time.
Recommended fields:
id
organization_id
location_id
metric_key
period_start
period_end
direction
magnitude
confidence
method
dimensions
status
Trend directions:
increasing
decreasing
stable
volatile
insufficient_data
 
⸻
 
18.41 Trend Detection
Trend detection may use:
	•	Moving averages
	•	Linear slope
	•	Period comparison
	•	Seasonally adjusted comparison
	•	Change-point detection
	•	Product-specific rules
The method must be appropriate to the metric and data volume.
 
⸻
 
18.42 Anomaly
An anomaly represents an unexpected deviation from a baseline.
Recommended fields:
id
organization_id
location_id
metric_key
detected_at
period_start
period_end
anomaly_type
severity
expected_range
observed_value
confidence
status
method
 
⸻
 
18.43 Anomaly Types
Potential anomaly types:
spike
drop
zero_value
missing_data
step_change
volatility_change
seasonal_deviation
cross_metric_mismatch
A data-quality issue and a business-performance anomaly must remain separate.
 
⸻
 
18.44 Anomaly Severity
Severity should consider:
	•	Magnitude
	•	Business importance
	•	Duration
	•	Metric reliability
	•	Goal impact
	•	Number of locations affected
	•	Confidence
	•	Whether the change is expected
Recommended levels:
informational
low
moderate
high
critical
 
⸻
 
18.45 Anomaly Detection Workflow
New Valid Data
    ↓
Load Metric Rules
    ↓
Establish Baseline
    ↓
Run Detection
    ↓
Check Data Quality
    ↓
Compare Known Events
    ↓
Create Candidate Anomaly
    ↓
Validate
    ↓
Notify or Monitor
Candidate anomalies should not immediately become client-facing alerts.
 
⸻
 
18.46 Known Event Correlation
Anomalies should be compared against known events such as:
	•	Website deployment
	•	GBP category change
	•	Holiday
	•	Business closure
	•	Promotion
	•	Campaign launch
	•	Algorithm update annotation
	•	Provider outage
	•	Tracking change
	•	New location
	•	Service launch
	•	Major review incident
Known-event overlap provides context but does not prove causation.
 
⸻
 
18.47 Annotation
Annotations add business context to a timeline.
Recommended fields:
id
organization_id
location_id
annotation_type
title
description
occurred_at
end_at
source
visibility
created_by
Annotation types may include:
deployment
campaign
promotion
closure
holiday
provider_incident
algorithm_update
tracking_change
profile_change
content_publication
operational_event
manual_note
 
⸻
 
18.48 Insight
An insight is an interpreted analytical finding supported by evidence.
Recommended fields:
id
organization_id
location_id
insight_type
title
summary
status
priority
confidence
period_start
period_end
created_by
assigned_to
created_at
updated_at
Potential insight types:
performance_change
goal_progress
anomaly
cross_product_relationship
opportunity
risk
operational_bottleneck
attribution_result
benchmark_gap
outcome_summary
 
⸻
 
18.49 Insight Evidence
Every insight should reference supporting evidence.
Recommended fields:
id
insight_id
evidence_type
metric_key
source_id
period_start
period_end
dimensions
value
comparison_value
reference
description
An insight without evidence must remain a draft or hypothesis.
 
⸻
 
18.50 Insight Confidence
Recommended confidence levels:
low
moderate
high
verified
Confidence should consider:
	•	Data quality
	•	Sample size
	•	Source reliability
	•	Number of supporting signals
	•	Confounding factors
	•	Human validation
	•	Measurement design
 
⸻
 
18.51 Insight Status
Recommended lifecycle:
detected
needs_validation
validated
published
assigned
actioned
monitoring
resolved
dismissed
archived
Dismissed insights should preserve the reason.
 
⸻
 
18.52 Insight Priority
Priority should consider:
	•	Business impact
	•	Urgency
	•	Goal impact
	•	Confidence
	•	Scope
	•	Reversibility
	•	Required response
	•	Existing unresolved work
High magnitude alone does not determine priority.
 
⸻
 
18.53 Cross-Product Insights
The Insights product should support analysis across product boundaries.
Examples:
	•	Organic traffic increased after a content update.
	•	GBP website clicks rose while lead conversion declined.
	•	Review complaints about wait time increased during a period of higher reservation volume.
	•	Faster lead response correlated with a higher appointment rate.
	•	A new service page increased qualified leads for that service.
	•	GBP category changes coincided with improved local-grid visibility.
	•	Content publishing volume increased, but organic conversion remained flat.
Cross-product insight generation must respect data access permissions.
 
⸻
 
18.54 Cross-Product Relationship Types
Relationships may be classified as:
temporal_overlap
correlation
consistent_sequence
possible_contribution
measured_experiment
verified_attribution
unknown
The system must not label temporal overlap as causation.
 
⸻
 
18.55 Attribution
Attribution estimates how outcomes should be associated with sources or activities.
The platform should support multiple attribution models because no single model is universally correct.
Potential models include:
	•	First touch
	•	Last touch
	•	Linear
	•	Position based
	•	Time decay
	•	Provider reported
	•	Client reported
	•	Rule based
	•	Experiment based
 
⸻
 
18.56 Attribution Model
Recommended fields:
id
organization_id
name
model_type
scope
lookback_window
channel_rules
conversion_types
status
version
created_at
updated_at
Attribution models should be versioned.
 
⸻
 
18.57 Attribution Result
Recommended fields:
id
organization_id
location_id
conversion_id
model_id
touchpoint_id
attributed_value
attributed_fraction
confidence
calculated_at
Attributed fractions for one conversion should follow the model’s defined total.
 
⸻
 
18.58 Attribution Limitations
Attribution reporting must display:
	•	Model
	•	Lookback window
	•	Included channels
	•	Missing channels
	•	Identity limitations
	•	Consent limitations
	•	Cross-device limitations
	•	Offline conversion gaps
	•	Provider-reported assumptions
Attribution should be described as a model, not objective truth.
 
⸻
 
18.59 Source Quality Analysis
The product should evaluate source quality using:
	•	Lead volume
	•	Valid lead rate
	•	Qualification rate
	•	Conversion rate
	•	Response time
	•	Lost reasons
	•	Verified value
	•	Cost where available
	•	Attribution confidence
High-volume low-quality sources should be identifiable.
 
⸻
 
18.60 Cost and Efficiency Metrics
Where authorized data exists, the product may calculate:
cost_per_lead
cost_per_qualified_lead
cost_per_appointment
cost_per_conversion
return_on_ad_spend
marketing_efficiency_ratio
gross_margin_contribution
Each calculation must document:
	•	Included costs
	•	Included revenue
	•	Attribution model
	•	Currency
	•	Period
	•	Data completeness
 
⸻
 
18.61 Revenue Data
Revenue may come from:
	•	CRM
	•	Booking platform
	•	Payment provider
	•	Client report
	•	Manual import
	•	Billing system
Revenue authority must be explicit.
The product should distinguish:
estimated_value
quoted_value
booked_value
collected_value
recognized_value
Insights is not the accounting system of record.
 
⸻
 
18.62 Outcome Measurement
Outcome measurement evaluates whether a recommendation, implementation, workflow, or campaign produced an observable result.
Recommended fields:
id
organization_id
location_id
subject_type
subject_id
baseline_start
baseline_end
measurement_start
measurement_end
metric_keys
comparison_method
outcome
confidence
interpretation
status
 
⸻
 
18.63 Measurable Subjects
Outcome measurement may apply to:
	•	SEO recommendation
	•	Content publication
	•	GBP change
	•	Google Post campaign
	•	Review-response initiative
	•	Lead-routing change
	•	Follow-up workflow
	•	Marketing campaign
	•	Operational improvement
	•	Product adoption
 
⸻
 
18.64 Outcome Types
Recommended outcomes:
positive
negative
neutral
mixed
inconclusive
not_measurable
measurement_pending
A mixed outcome may occur when:
	•	Traffic rises but conversion declines.
	•	Leads rise while qualification rate falls.
	•	Review volume increases while rating falls.
 
⸻
 
18.65 Measurement Design
A measurement design should define:
	•	Subject
	•	Expected effect
	•	Primary metric
	•	Secondary metrics
	•	Baseline period
	•	Measurement period
	•	Comparison method
	•	Minimum data threshold
	•	Confounding factors
	•	Success criteria
	•	Stop condition
Measurement design should be created before results are interpreted where practical.
 
⸻
 
18.66 Confounding Factors
Possible confounding factors include:
	•	Seasonality
	•	Algorithm updates
	•	Website redesign
	•	Pricing changes
	•	Business closures
	•	Promotions
	•	New competitors
	•	Provider definition changes
	•	Tracking failures
	•	Capacity constraints
	•	Weather
	•	Economic conditions
	•	Multiple simultaneous changes
The product should preserve known confounders with the outcome record.
 
⸻
 
18.67 Recommendation Intelligence
The Insights product may identify situations requiring attention.
Examples:
	•	Goal is at risk.
	•	Lead response time is degrading.
	•	Organic clicks increased without corresponding leads.
	•	Review rating declined at one location.
	•	GBP interactions fell after an unexpected profile change.
	•	Content output is high but refresh backlog is growing.
	•	One service has strong visibility but weak conversion.
	•	A location has consistently weaker performance than comparable locations.
These become insight records, not automatically approved work.
 
⸻
 
18.68 Recommendation Routing
An insight may create an event or request for another product.
Examples:
Insight: Organic CTR decline
    ↓
SEO opportunity candidate

Insight: Review complaints increasing
    ↓
Reviews or operational escalation

Insight: Lead response objective missed
    ↓
Leads workflow review

Insight: Published content declining
    ↓
Content refresh candidate
Insights does not directly modify another product’s domain state.
 
⸻
 
18.69 Executive Summary
An executive summary should explain:
	•	Overall performance
	•	Important gains
	•	Important declines
	•	Completed work
	•	Goal progress
	•	Current risks
	•	Recommended next actions
	•	Data limitations
The summary should prioritize decision relevance over metric volume.
 
⸻
 
18.70 Executive Summary Structure
Recommended structure:
Performance Overview

What Improved

What Declined

Work Completed

Goals and Progress

Risks and Blockers

Recommended Next Actions

Data Notes
The product may omit empty sections.
 
⸻
 
18.71 AI Responsibilities
AI may assist with:
	•	Metric summarization
	•	Trend explanation
	•	Anomaly description
	•	Cross-product synthesis
	•	Executive-summary drafting
	•	Recommendation drafting
	•	Goal-risk explanation
	•	Report narrative
	•	Data-quality explanation
	•	Outcome interpretation
AI must not independently:
	•	Create metric values
	•	Change authoritative source data
	•	Hide unfavorable data
	•	Assert causation without evidence
	•	Select business goals
	•	Mark an outcome successful without defined criteria
	•	Change attribution models
	•	Publish high-impact recommendations without review
	•	Infer private lead details from aggregates
	•	Override data-quality warnings
 
⸻
 
18.72 AI Task Registry
Initial tasks may include:
insights.metric_summary
insights.trend_interpretation
insights.anomaly_summary
insights.cross_product_summary
insights.goal_progress_summary
insights.executive_summary
insights.recommendation_draft
insights.outcome_interpretation
insights.data_quality_explanation
insights.report_narrative
 
⸻
 
18.73 AI Input Requirements
AI inputs should provide:
	•	Metric definitions
	•	Current values
	•	Comparison values
	•	Date ranges
	•	Dimensions
	•	Data freshness
	•	Quality status
	•	Known events
	•	Goals
	•	Benchmarks
	•	Relevant completed work
	•	Allowed business context
	•	Required uncertainty language
The model should not calculate authoritative metrics from prose.
 
⸻
 
18.74 AI Output Requirements
AI outputs should be structured.
Example:
{
  "summary": "Qualified leads increased while overall lead volume remained stable.",
  "supporting_metrics": [
    {
      "metric_key": "leads.qualified_leads",
      "current_value": 84,
      "comparison_value": 67,
      "change_percent": 25.4
    }
  ],
  "possible_contributors": [
    {
      "description": "Median human response time improved during the same period.",
      "relationship": "correlation",
      "confidence": "moderate"
    }
  ],
  "limitations": [
    "Conversion data for the final three days remains provisional."
  ],
  "recommended_action": "Continue monitoring qualification rate and response time before changing routing policy.",
  "requires_human_review": true
}
 
⸻
 
18.75 AI Grounding
AI tasks should be grounded in:
	•	Metric registry
	•	Normalized observations
	•	Aggregates
	•	Goals
	•	Benchmarks
	•	Annotations
	•	Product activity
	•	Outcome measurements
	•	Data-quality state
	•	Approved business context
The model should not rely on generalized marketing assumptions when platform evidence is available.
 
⸻
 
18.76 AI Validation
AI output should be checked for:
	•	Correct metric values
	•	Correct date ranges
	•	Correct organization and location
	•	Correct comparison
	•	Correct directionality
	•	Unsupported causation
	•	Missing freshness warnings
	•	Omitted negative performance
	•	Conflicting recommendations
	•	Unsupported benchmark claims
	•	Currency mismatch
	•	Personal-data leakage
	•	Cross-tenant contamination
	•	Exaggerated confidence
	•	Invented source data
 
⸻
 
18.77 Deterministic Calculations
All authoritative calculations should occur outside the language model.
Examples:
	•	Percentage change
	•	Conversion rate
	•	Median response time
	•	Goal progress
	•	Attribution fractions
	•	Rolling averages
	•	Trend slopes
	•	Percentile values
AI may explain results but should not be the calculation engine.
 
⸻
 
18.78 Human Responsibilities
Humans remain responsible for:
	•	KPI selection
	•	Goal definition
	•	Benchmark approval
	•	Attribution-model selection
	•	Insight validation
	•	Strategic interpretation
	•	Client communication
	•	High-impact recommendations
	•	Financial interpretation
	•	Causation claims
	•	Report approval
 
⸻
 
18.79 Dashboard
A dashboard is a configured analytical view.
Recommended fields:
id
organization_id
name
audience
scope
status
default_date_range
comparison_mode
created_by
created_at
updated_at
Audience values may include:
agency_internal
client_executive
client_operational
product_specialist
platform_admin
 
⸻
 
18.80 Dashboard Widget
Recommended widget types:
metric_card
time_series
comparison
distribution
funnel
table
ranking
goal_progress
status
annotation_timeline
insight_list
work_summary
data_freshness
Each widget should define:
	•	Metric
	•	Dimensions
	•	Filters
	•	Date range
	•	Comparison
	•	Visualization
	•	Access requirements
 
⸻
 
18.81 Dashboard Configuration
Dashboard configuration should support:
	•	Organization default
	•	Industry default
	•	Product default
	•	Location override
	•	User preference
	•	Shared saved view
Configuration inheritance should remain visible.
 
⸻
 
18.82 Client Executive Dashboard
The client executive dashboard should prioritize:
	•	Business outcomes
	•	Goal progress
	•	Important changes
	•	Completed work
	•	Risks
	•	Next actions
	•	Data freshness
It should avoid overwhelming users with operational diagnostics.
 
⸻
 
18.83 Client Operational Dashboard
The operational dashboard may include:
	•	Lead response
	•	Review response
	•	GBP status
	•	Content schedule
	•	Open approvals
	•	Current recommendations
	•	Location comparisons
	•	Workflow blockers
 
⸻
 
18.84 Agency Account Dashboard
The agency account dashboard should include:
	•	Product health
	•	Data freshness
	•	Current performance
	•	Open work
	•	Approval backlog
	•	Account risks
	•	Recent outcomes
	•	Client engagement
	•	Reporting readiness
 
⸻
 
18.85 Agency Portfolio Dashboard
Portfolio reporting may include:
	•	Organization health
	•	Location health
	•	Product adoption
	•	Accounts at risk
	•	Data-source failures
	•	Goal status
	•	Approval delays
	•	Lead response compliance
	•	Review response compliance
	•	SEO opportunity backlog
	•	Content publication throughput
	•	Commercial metrics where authorized
 
⸻
 
18.86 Drill-Down
Every summary should support drill-down where permissions allow.
Example:
Qualified Leads
    ↓
Locations
    ↓
Services
    ↓
Sources
    ↓
Lead Records
Users should be able to inspect evidence behind important conclusions.
 
⸻
 
18.87 Report
A report is a versioned, publishable analytical artifact.
Recommended fields:
id
organization_id
location_id
report_type
title
period_start
period_end
comparison_start
comparison_end
status
audience
current_revision
created_by
approved_by
published_at
 
⸻
 
18.88 Report Types
Initial report types may include:
monthly_performance
quarterly_business_review
executive_summary
product_performance
location_comparison
campaign_report
goal_report
incident_report
custom
 
⸻
 
18.89 Report Sections
Potential sections include:
	•	Executive summary
	•	Goals
	•	SEO
	•	GBP
	•	Reviews
	•	Content
	•	Leads
	•	Cross-product insights
	•	Completed work
	•	Risks
	•	Recommendations
	•	Data notes
Sections should be audience-appropriate and permission-aware.
 
⸻
 
18.90 Report Revision
A report revision should preserve:
report_id
revision_number
content
metric_snapshot_reference
data_as_of
created_by
created_at
approval_state
Published report revisions must remain immutable.
 
⸻
 
18.91 Metric Snapshot
Published reports should reference a fixed metric snapshot.
This prevents the report from changing when:
	•	Late provider data arrives
	•	Source data is corrected
	•	A calculation version changes
	•	A metric is reprocessed
The live dashboard may update, but the published report remains historically accurate to its data-as-of time.
 
⸻
 
18.92 Report Workflow
Reporting Schedule
    ↓
Validate Required Data
    ↓
Create Metric Snapshot
    ↓
Generate Charts and Tables
    ↓
Detect Important Changes
    ↓
Draft Narrative
    ↓
Human Review
    ↓
Approve
    ↓
Publish
    ↓
Deliver
    ↓
Track Access
 
⸻
 
18.93 Reporting Readiness
A report should not enter final review until:
	•	Required data sources are available or explicitly waived.
	•	Freshness is known.
	•	Material quality issues are disclosed.
	•	Required sections are generated.
	•	Current period completeness is understood.
	•	Metric snapshot is created.
 
⸻
 
18.94 Report Approval
Approval applies to a specific report revision and metric snapshot.
If a material data correction occurs after approval but before publication:
	•	Approval should be invalidated.
	•	The affected sections should regenerate.
	•	The report should return to review.
 
⸻
 
18.95 Report Delivery
Delivery may include:
	•	Client portal
	•	Email notification
	•	PDF export
	•	Secure link
	•	Scheduled internal distribution
Sensitive reports should not be attached to insecure or unapproved destinations.
 
⸻
 
18.96 Scheduled Delivery
Recommended fields:
id
report_id or report_template_id
recipients
delivery_channel
schedule
timezone
approval_policy
status
last_delivered_at
next_delivery_at
Scheduled delivery must validate recipient access at delivery time.
 
⸻
 
18.97 Exports
Supported exports may include:
	•	CSV
	•	XLSX
	•	PDF
	•	JSON for approved integrations
Exports should preserve:
	•	Metric definitions
	•	Date ranges
	•	Timezone
	•	Filters
	•	Data-as-of timestamp
	•	Freshness
	•	Currency
	•	Attribution model
	•	Quality notes
 
⸻
 
18.98 Export Security
Exports require:
	•	Permission
	•	Scope validation
	•	Audit
	•	Expiration where applicable
	•	Personal-data controls
	•	Row limits
	•	Restricted-field redaction
Portfolio exports must not include unauthorized client data.
 
⸻
 
18.99 Reporting Language
Reports should distinguish:
Measured fact
Calculated result
Observed relationship
Possible contributor
Hypothesis
Recommendation
These categories should not be blended.
 
⸻
 
18.100 Data Visualization Standards
Visualizations should:
	•	Use correct scales
	•	Label units
	•	Display date range
	•	Display comparison period
	•	Show partial data
	•	Avoid misleading axes
	•	Avoid excessive decoration
	•	Support accessibility
	•	Preserve tooltip definitions
	•	Display sample size where relevant
 
⸻
 
18.101 Metric Cards
A metric card should include:
	•	Metric name
	•	Current value
	•	Comparison value
	•	Change
	•	Direction
	•	Date range
	•	Freshness
	•	Quality warning
	•	Definition access
A green or red indicator should not be used when directionality is context-dependent.
 
⸻
 
18.102 Time-Series Charts
Time-series charts should support:
	•	Current series
	•	Comparison series
	•	Annotations
	•	Missing-data gaps
	•	Granularity
	•	Timezone
	•	Optional goal line
	•	Optional benchmark
Missing observations should not be plotted as zero.
 
⸻
 
18.103 Funnels
Funnels may support:
Leads
    ↓
Valid Leads
    ↓
Qualified Leads
    ↓
Appointments
    ↓
Conversions
Every funnel stage must define:
	•	Inclusion rule
	•	Time basis
	•	Deduplication rule
	•	Authority
	•	Measurement window
 
⸻
 
18.104 Location Comparisons
Location comparison should support:
	•	Absolute values
	•	Rates
	•	Per-operating-day values
	•	Goal progress
	•	Benchmark variance
	•	Trend
The default should not rank locations solely by total volume.
 
⸻
 
18.105 Product Health Reporting
The Insights product should display health for:
	•	Data-source connections
	•	Product synchronization
	•	Reporting readiness
	•	Data quality
	•	Scheduled delivery
	•	Metric computation
	•	AI narrative generation
Health should remain distinct from business performance.
 
⸻
 
18.106 Product Success Metrics
Operational Metrics
	•	Data pipeline success rate
	•	Metric computation time
	•	Report preparation time
	•	Scheduled delivery success
	•	Dashboard load time
	•	Data freshness compliance
	•	Quality-issue resolution time
Quality Metrics
	•	Metric-definition disputes
	•	Report correction rate
	•	Insight dismissal rate
	•	Unsupported-causation rate
	•	AI narrative edit rate
	•	Data-quality false-positive rate
	•	Attribution reconciliation rate
Adoption Metrics
	•	Dashboard active users
	•	Report views
	•	Drill-down usage
	•	Goal adoption
	•	Insight action rate
	•	Scheduled report use
	•	Export use
Business Metrics
	•	Reduction in manual reporting time
	•	Faster identification of account risks
	•	Increased recommendation completion
	•	Improved client understanding
	•	Improved goal tracking
	•	Reduced reporting inconsistency
	•	Increased retention signals where measurable
 
⸻
 
18.107 Permissions
Recommended permissions:
insights.view
insights.view_financial
insights.view_lead_detail
insights.view_portfolio
insights.configure_metrics
insights.configure_dashboards
insights.create_goal
insights.edit_goal
insights.approve_goal
insights.create_report
insights.edit_report
insights.approve_report
insights.publish_report
insights.schedule_report
insights.export
insights.validate_insight
insights.dismiss_insight
insights.configure_attribution
insights.view_diagnostics
insights.manage_runtime
Financial, lead-level, and portfolio data require distinct permissions.
 
⸻
 
18.108 Notification Types
Notifications may include:
	•	Critical performance anomaly
	•	Goal at risk
	•	Goal achieved
	•	Data source delayed
	•	Report ready for review
	•	Report approval required
	•	Report delivery failed
	•	Data-quality issue
	•	Attribution conflict
	•	Outcome measurement ready
	•	Cross-product insight ready
	•	Portfolio account at risk
	•	Scheduled report delivered
Notifications should link directly to the relevant evidence or workflow.
 
⸻
 
18.109 Product Health States
Recommended states:
healthy
partial_data
source_delayed
quality_issue
reporting_blocked
metric_computation_delayed
delivery_degraded
configuration_required
provider_degraded
The product may remain active while one source is delayed.
 
⸻
 
18.110 Runtime Controls
Authorized operators should be able to:
	•	Pause one data source
	•	Pause metric computation
	•	Pause anomaly detection
	•	Pause AI narrative generation
	•	Pause scheduled delivery
	•	Disable a metric
	•	Mark a source incident
	•	Recompute a period
	•	Rebuild an aggregate
	•	Invalidate a report snapshot
	•	Force manual report approval
	•	Pause one organization or location
All runtime actions must be audited.
 
⸻
 
18.111 Failure Modes
Expected failure modes include:
	•	Product data unavailable
	•	Provider data delayed
	•	Metric definition missing
	•	Invalid aggregation
	•	Dimension mapping failure
	•	Duplicate observations
	•	Currency conflict
	•	Timezone mismatch
	•	Partial current period
	•	Data-quality false alarm
	•	Anomaly false positive
	•	Goal calculation failure
	•	Attribution conflict
	•	Report snapshot incomplete
	•	AI narrative contains unsupported claim
	•	Scheduled delivery fails
	•	Recipient permission revoked
	•	Export too large
	•	Historical metric version changed
	•	Dashboard references deprecated metric
 
⸻
 
18.112 Failure Handling
Each failure should define:
	•	Error category
	•	Retry eligibility
	•	Reporting impact
	•	User-visible explanation
	•	Internal diagnostic
	•	Affected metrics
	•	Affected reports
	•	Recovery action
	•	Escalation owner
A failed recomputation must not overwrite prior valid aggregates until the replacement succeeds.
 
⸻
 
18.113 Recalculation and Backfill
The product should support controlled recalculation when:
	•	Metric logic changes
	•	Source data is corrected
	•	Missing history becomes available
	•	Dimension mapping changes
	•	Timezone configuration changes
	•	Provider definitions change
Backfills must record:
	•	Reason
	•	Scope
	•	Calculation version
	•	Start and end periods
	•	Previous record references
	•	Completion status
	•	Quality result
 
⸻
 
18.114 Metric Versioning
Metric calculation changes require a new version when they affect interpretation.
Examples:
	•	Conversion definition changes
	•	Response-time start point changes
	•	Attribution model changes
	•	Organic traffic filtering changes
	•	Review response-rate denominator changes
Historical reports should preserve the version used at publication.
 
⸻
 
18.115 Metric Deprecation
Deprecation should include:
active
deprecated
replacement_available
retired
Deprecated metrics remain readable for historical reports.
New dashboards should not use retired metrics.
 
⸻
 
18.116 Security Considerations
The product must protect:
	•	Cross-product data
	•	Lead information
	•	Financial metrics
	•	Client goals
	•	Internal agency benchmarks
	•	Portfolio performance
	•	Report recipients
	•	Export files
	•	Provider identifiers
	•	Commercial analysis
Aggregation must not become a path around underlying product permissions.
 
⸻
 
18.117 Privacy Considerations
Insights should prefer aggregated data.
Lead-level, reviewer-level, or employee-level data should be exposed only when:
	•	Necessary
	•	Authorized
	•	Relevant to the analysis
	•	Consistent with source-product policy
Small-group reporting may require suppression to avoid exposing individual behavior.
 
⸻
 
18.118 Small-Sample Controls
The product should support suppression or warning when:
	•	Review count is too low
	•	Conversion count is too low
	•	Employee-level data is sparse
	•	Location comparison is statistically weak
	•	A segment may expose an individual
Thresholds should be configurable by metric.
 
⸻
 
18.119 Retention
Retention should distinguish:
	•	Raw observations
	•	Aggregates
	•	Report snapshots
	•	Published reports
	•	Exports
	•	AI narratives
	•	Data-quality diagnostics
Published reports and financial records may require longer retention than temporary analytical intermediates.
 
⸻
 
18.120 Operational Requirements
The product requires:
	•	Product-event ingestion
	•	Metric-normalization jobs
	•	Aggregation jobs
	•	Quality checks
	•	Freshness monitoring
	•	Goal calculations
	•	Anomaly detection
	•	Insight generation
	•	Outcome measurement
	•	Report generation
	•	Scheduled delivery
	•	Export processing
	•	Recalculation controls
	•	Provider-health monitoring
	•	Runtime kill switches
 
⸻
 
18.121 Testing Requirements
Testing should cover:
	•	Tenant isolation
	•	Metric registry
	•	Dimension compatibility
	•	Aggregation rules
	•	Ratio-of-sums calculations
	•	Missing versus zero
	•	Timezone boundaries
	•	Partial periods
	•	Previous-period comparison
	•	Year-over-year comparison
	•	Currency preservation
	•	Goal progress
	•	Benchmark selection
	•	Trend detection
	•	Anomaly detection
	•	Data-quality precedence
	•	Attribution fractions
	•	Outcome measurement
	•	Report snapshot immutability
	•	Approval invalidation
	•	Export permissions
	•	Scheduled recipient validation
	•	AI narrative validation
	•	Metric backfill
	•	Deprecated metrics
	•	Runtime controls
 
⸻
 
18.122 Evaluation Dataset
The Insights AI evaluation dataset should include:
	•	Clear increases
	•	Clear declines
	•	Mixed outcomes
	•	Partial data
	•	Delayed provider data
	•	Missing data
	•	Seasonal changes
	•	Small sample sizes
	•	Confounding events
	•	Cross-product correlations
	•	Unsupported causation traps
	•	Goal at-risk cases
	•	Goal achieved cases
	•	Attribution uncertainty
	•	Restaurant accounts
	•	Home-service accounts
	•	Multi-location comparisons
	•	Financial metrics
	•	Negative results that must not be omitted
Human-reviewed examples should be versioned.
 
⸻
 
18.123 Minimum Viable Insights Product
The minimum viable product should include:
Data Foundation
	•	Product-owned metric ingestion
	•	Metric registry
	•	Dimension registry
	•	Daily observations
	•	Aggregates
	•	Data freshness
	•	Quality status
Analysis
	•	Date comparisons
	•	Trend detection
	•	Deterministic anomaly detection
	•	Goals
	•	Annotations
	•	Basic cross-product insights
Experience
	•	Client executive dashboard
	•	Agency account dashboard
	•	Metric drill-down
	•	Data-definition access
	•	Data-freshness warnings
Reporting
	•	Monthly report
	•	Metric snapshot
	•	Revision history
	•	Approval
	•	Portal publication
	•	PDF export
	•	Scheduled notification
Platform Controls
	•	Permissions
	•	Audit
	•	Tenant isolation
	•	Runtime pause
	•	Manual narrative creation without AI
 
⸻
 
18.124 Implementation Phases
Phase 1 — Metric Foundation
Implement:
	•	Insight sources
	•	Metric registry
	•	Dimension registry
	•	Observations
	•	Aggregates
	•	Freshness
	•	Data-quality status
	•	Basic metric API
Phase 2 — Dashboards
Implement:
	•	Dashboard configuration
	•	Metric cards
	•	Time series
	•	Comparisons
	•	Location views
	•	Product views
	•	Drill-down
	•	Saved filters
Phase 3 — Goals and Annotations
Implement:
	•	Goals
	•	Targets
	•	Progress
	•	Event annotations
	•	Goal alerts
	•	Goal reporting
Phase 4 — Reports
Implement:
	•	Report templates
	•	Metric snapshots
	•	Report revisions
	•	Approval
	•	Publication
	•	PDF export
	•	Delivery scheduling
Phase 5 — Anomalies and Insights
Implement:
	•	Deterministic anomaly detection
	•	Insight records
	•	Evidence
	•	Validation
	•	Notifications
	•	Recommendation routing
Phase 6 — Attribution and Outcomes
Implement:
	•	Attribution models
	•	Touchpoint ingestion
	•	Conversion linkage
	•	Outcome measurement
	•	Campaign reporting
	•	Source-quality reporting
Phase 7 — Advanced Intelligence
Implement:
	•	AI-assisted summaries
	•	Cross-product synthesis
	•	Advanced trend models
	•	Portfolio benchmarks
	•	Forecasting where justified
	•	Strategic recommendation support
 
⸻
 
18.125 Future Capabilities
Potential future capabilities include:
	•	Dedicated analytical warehouse
	•	Advanced cohort analysis
	•	Customer lifetime value
	•	Capacity-adjusted lead analysis
	•	Marketing-mix modeling
	•	Incrementality testing
	•	Experiment design
	•	Advanced forecasting
	•	Natural-language analytical queries
	•	Custom report builder
	•	White-label reporting
	•	Embedded client dashboards
	•	Industry benchmark marketplace
	•	Automated quarterly business reviews
	•	Agency profitability analysis
	•	Churn-risk modeling
	•	Recommendation impact ranking
Future capabilities must preserve metric governance, evidence, access control, and uncertainty disclosure.
 
⸻
 
18.126 Insights Guardrails
The following are prohibited unless formally approved:
	1.	Creating authoritative metric values through AI
	2.	Using undefined metrics
	3.	Changing metric calculations without versioning
	4.	Treating missing data as zero
	5.	Hiding partial periods
	6.	Hiding provider delays
	7.	Averaging non-aggregatable metrics
	8.	Aggregating different currencies without an explicit conversion method
	9.	Claiming causation from temporal overlap
	10.	Presenting attribution as objective truth
	11.	Using opaque benchmarks
	12.	Comparing non-equivalent date periods without disclosure
	13.	Publishing reports without a fixed metric snapshot
	14.	Modifying a published report revision
	15.	Regenerating historical results without preserving calculation version
	16.	Allowing AI to omit unfavorable metrics
	17.	Allowing AI to invent explanations
	18.	Exposing lead-level data through general dashboards
	19.	Exposing cross-client portfolio data without permission
	20.	Ranking locations solely by total volume
	21.	Treating one observation as a trend
	22.	Treating a data-quality anomaly as a business-performance anomaly
	23.	Marking goals missed before the period is complete without justification
	24.	Marking outcomes successful without defined criteria
	25.	Generating recommendations without evidence
	26.	Allowing reports to conceal uncertainty
	27.	Allowing dashboard configuration to bypass product permissions
	28.	Sending reports to recipients without current access
	29.	Overwriting prior valid aggregates with failed recomputations
	30.	Allowing the Insights product to modify another product’s authoritative domain state directly
 
⸻
 
18.127 Acceptance Requirements
The initial Insights product is not production-ready until it supports:
	•	Insight source registration
	•	Metric registry
	•	Dimension registry
	•	Product-owned data ingestion
	•	Daily metric observations
	•	Aggregation
	•	Metric versioning
	•	Missing-value handling
	•	Data freshness
	•	Data-quality status
	•	Date comparisons
	•	Goals
	•	Annotations
	•	Basic trend detection
	•	Basic anomaly detection
	•	Insight evidence
	•	Client dashboards
	•	Agency dashboards
	•	Drill-down
	•	Report creation
	•	Metric snapshots
	•	Report revisions
	•	Approval
	•	Publication
	•	Secure delivery
	•	PDF export
	•	Permissions
	•	Audit history
	•	Tenant isolation
	•	Runtime controls
	•	Manual operation without AI
 
⸻
 
18.128 Section Decisions
This section establishes the following decisions:
	1.	The Insights product is the governed analytical and reporting layer across the LILOs platform.
	2.	Product modules remain authoritative for their own domain data.
	3.	Insights consumes normalized product records rather than recreating product state.
	4.	Every metric is registered, documented, versioned, and assigned an owner.
	5.	Metrics declare valid dimensions, aggregation behavior, unit, freshness, and limitations.
	6.	Missing, zero, unavailable, delayed, suppressed, and invalid values remain distinct.
	7.	Data freshness and quality are visible throughout dashboards and reports.
	8.	Organization, location, product, service, source, campaign, and time are shared analytical dimensions.
	9.	Date comparisons must use equivalent and clearly disclosed periods.
	10.	Timezone and period-completeness rules are explicit.
	11.	Goals are first-class, scoped, versioned business objects.
	12.	Benchmarks must disclose their source, population, period, and limitations.
	13.	Trends require sustained evidence rather than a single comparison.
	14.	Business anomalies and data-quality issues remain separate objects.
	15.	Every insight includes evidence, confidence, scope, and status.
	16.	Cross-product relationships are classified according to the strength of evidence.
	17.	Temporal overlap and correlation do not establish causation.
	18.	Attribution is model-based, versioned, and accompanied by limitations.
	19.	Revenue states such as estimated, quoted, booked, collected, and recognized remain distinct.
	20.	Outcome measurement uses defined baselines, periods, metrics, success criteria, and confounding factors.
	21.	Insights may route recommendations to product workflows but does not directly alter product-owned state.
	22.	Authoritative calculations occur deterministically outside the language model.
	23.	AI supports explanation, synthesis, and drafting but does not create source data or conceal uncertainty.
	24.	Dashboards are audience-specific, permission-aware, and capable of evidence drill-down.
	25.	Published reports use immutable revisions and fixed metric snapshots.
	26.	Report approval applies to one revision and one data snapshot.
	27.	Historical reports preserve the metric and calculation versions used at publication.
	28.	Portfolio analytics must not bypass organization-level access controls.
	29.	The minimum viable product includes normalized metrics, quality and freshness, comparisons, goals, dashboards, reports, insights, exports, and manual operation.
	30.	No insight or report may present an unsupported claim, undefined metric, hidden limitation, or unauthorized data scope.


---

Section 19 — Integration Framework & External Systems
19.1 Purpose
The Integration Framework defines how the LILOs platform connects to, exchanges data with, and performs controlled actions in external systems.
It provides a standardized architecture for:
	•	Authentication
	•	Connection management
	•	Capability discovery
	•	Data synchronization
	•	Webhook ingestion
	•	Polling
	•	Outbound actions
	•	Entity mapping
	•	Conflict resolution
	•	Rate-limit handling
	•	Retry
	•	Reconciliation
	•	Provider health
	•	Audit
	•	Testing
	•	Connector lifecycle management
The framework must prevent each product from implementing unrelated provider logic independently.
All external systems should connect through governed adapters that conform to shared contracts.
 
⸻
 
19.2 Business Problem
External integrations commonly become unstable because each provider is implemented differently.
Typical problems include:
	•	Authentication logic duplicated across products
	•	Tokens stored inconsistently
	•	Provider errors handled differently
	•	No standard health status
	•	No centralized retry policy
	•	Duplicate webhook processing
	•	Polling jobs that overlap
	•	Incorrect tenant or location mapping
	•	Provider-specific fields leaking into product models
	•	Silent synchronization failures
	•	Outbound actions retried blindly
	•	No reconciliation after ambiguous failures
	•	API changes breaking unrelated workflows
	•	Rate limits affecting the entire platform
	•	No consistent sandbox strategy
	•	No connector testing standard
	•	Provider credentials exposed too broadly
	•	New integrations requiring extensive custom infrastructure
The framework must support the complete lifecycle:
Discover
    ↓
Authorize
    ↓
Connect
    ↓
Map
    ↓
Synchronize
    ↓
Operate
    ↓
Monitor
    ↓
Reconcile
    ↓
Renew
    ↓
Disconnect
 
⸻
 
19.3 Goals
The Integration Framework should:
	1.	Standardize provider integration behavior.
	2.	Separate provider models from platform models.
	3.	Centralize authentication and secrets.
	4.	Support OAuth, API keys, service accounts, and signed webhooks.
	5.	Prevent duplicate processing.
	6.	Support safe inbound and outbound operations.
	7.	Provide consistent provider health.
	8.	Handle rate limits and transient failures.
	9.	Preserve synchronization history.
	10.	Detect conflicts and drift.
	11.	Support provider capability differences.
	12.	Make connectors independently testable.
	13.	Reduce the effort required to add providers.
	14.	Support sandbox and production environments.
	15.	Preserve tenant isolation.
	16.	Allow products to operate during partial provider failure.
 
⸻
 
19.4 Non-Goals
The framework is not:
	•	A generic public integration marketplace in the initial release
	•	An unrestricted workflow automation platform
	•	A replacement for product-domain logic
	•	A system for scraping providers without authorization
	•	A mechanism for bypassing provider policies
	•	A universal ETL platform
	•	A direct database replication service
	•	A low-code transformation builder
	•	A provider credential management interface for ordinary users
	•	A guarantee that every provider supports real-time synchronization
 
⸻
 
19.5 Architectural Principle
Products own business behavior.
Connectors own provider communication.
The separation is:
Product Domain
    ↓
Integration Service Contract
    ↓
Provider Connector
    ↓
External Provider
A product must not call a provider SDK directly.
A connector must not make product-level business decisions.
 
⸻
 
19.6 Core Components
Integration Framework

├── Connector Registry
├── Capability Registry
├── Connection Manager
├── Authentication Service
├── Secrets Service
├── Entity Mapping
├── Sync Engine
├── Webhook Gateway
├── Polling Scheduler
├── Outbound Action Service
├── Rate-Limit Manager
├── Retry Manager
├── Reconciliation Service
├── Provider Health
├── Audit
├── Connector SDK
└── Testing Harness
 
⸻
 
19.7 Core Domain Objects
The framework manages:
	•	Provider
	•	Connector
	•	Connector version
	•	Provider capability
	•	Integration connection
	•	Authentication credential reference
	•	Provider account
	•	Provider resource
	•	Entity mapping
	•	Sync cursor
	•	Sync run
	•	Sync item
	•	Webhook endpoint
	•	Webhook delivery
	•	Polling schedule
	•	Outbound action
	•	Provider request
	•	Provider response
	•	Rate-limit state
	•	Reconciliation case
	•	Provider incident
	•	Connector health record
	•	Integration event
 
⸻
 
19.8 Provider
A provider represents an external service or platform.
Examples:
	•	Google
	•	Stripe
	•	Resend
	•	Twilio
	•	Toast
	•	Booqable
	•	Jobber
	•	Housecall Pro
	•	WordPress
	•	Drupal
	•	HubSpot
Recommended fields:
id
provider_key
display_name
provider_type
status
documentation_reference
support_reference
terms_reference
privacy_reference
metadata
Provider keys must be stable.
Examples:
google_business_profile
google_search_console
google_analytics
stripe
resend
twilio
toast
booqable
jobber
 
⸻
 
19.9 Connector
A connector implements communication with one provider service.
Recommended fields:
id
provider_id
connector_key
display_name
version
status
authentication_types
capabilities
configuration_schema
runtime_environment
created_at
updated_at
One provider may have multiple connectors.
Example:
google_business_profile
google_search_console
google_analytics_4
google_ads
These should not be treated as one undifferentiated Google integration.
 
⸻
 
19.10 Connector Versioning
Connectors must be versioned when changes affect:
	•	Authentication
	•	Data mapping
	•	Request behavior
	•	Provider API version
	•	Capability support
	•	Error interpretation
	•	Pagination
	•	Webhook format
	•	Outbound action behavior
Recommended lifecycle:
development
testing
active
deprecated
retired
disabled
Connections should record the connector version used.
 
⸻
 
19.11 Capability Registry
Provider differences must be represented through explicit capabilities.
Examples:
reviews.read
reviews.respond
reviews.edit_response
reviews.delete_response

gbp.read_profile
gbp.update_hours
gbp.publish_post
gbp.upload_media

leads.read
leads.create
leads.update
leads.assign

content.publish
content.update
content.unpublish

payments.read
payments.refund
payments.read_payouts
Products should query capabilities rather than assume support.
 
⸻
 
19.12 Capability Definition
Recommended fields:
capability_key
description
operation_type
risk_level
supports_batch
supports_webhook
supports_idempotency
supports_verification
required_permissions
status
Capability availability may vary by:
	•	Provider account
	•	Authentication scope
	•	Provider plan
	•	Location
	•	Region
	•	API version
	•	Account verification
	•	Provider policy
 
⸻
 
19.13 Capability Discovery
Capability discovery may be:
static
scope_based
account_based
runtime_discovered
manually_configured
The framework should store:
	•	Advertised connector capability
	•	Current connection capability
	•	Last verified capability
	•	Limitation reason
A connector supporting an operation does not mean every connection can use it.
 
⸻
 
19.14 Integration Connection
An integration connection represents one authorized relationship between LILOs and an external provider.
Recommended fields:
id
organization_id
provider_id
connector_id
connector_version
environment
status
display_name
authentication_type
credential_reference
authorized_scopes
provider_account_reference
connected_by
connected_at
last_verified_at
expires_at
revoked_at
metadata
 
⸻
 
19.15 Connection Status
Recommended states:
pending
authorizing
connected
limited
attention_required
expired
revoked
provider_disabled
disconnected
archived
A connection may remain connected while one capability is unavailable.
 
⸻
 
19.16 Connection Environment
Every connection must specify:
sandbox
test
production
Test and production credentials must never share one credential record.
Test provider data must not appear in production reporting unless explicitly marked.
 
⸻
 
19.17 Authentication Types
The framework should support:
	•	OAuth 2.0 authorization code
	•	OAuth 2.0 with PKCE
	•	API key
	•	Secret token
	•	Service account
	•	Basic authentication where unavoidable
	•	Signed webhook secret
	•	Provider application credentials
	•	User-delegated token
	•	Client certificate where required
Authentication mechanisms must be connector-defined.
 
⸻
 
19.18 OAuth Flow
Standard OAuth flow:
User Initiates Connection
    ↓
Create Authorization State
    ↓
Redirect to Provider
    ↓
Provider Consent
    ↓
Validate Callback State
    ↓
Exchange Authorization Code
    ↓
Store Encrypted Credential Reference
    ↓
Discover Account and Capabilities
    ↓
Require Resource Mapping
    ↓
Activate Connection
 
⸻
 
19.19 OAuth State
OAuth state must include or reference:
	•	Organization
	•	User
	•	Connector
	•	Environment
	•	Requested scopes
	•	Redirect destination
	•	Expiration
	•	Nonce
	•	PKCE verifier reference where used
State must be:
	•	Signed
	•	Short-lived
	•	Single-use
	•	Tenant-bound
 
⸻
 
19.20 OAuth Token Storage
Access and refresh tokens must:
	•	Be encrypted at rest
	•	Remain server-side
	•	Be referenced indirectly
	•	Never appear in logs
	•	Never enter AI prompts
	•	Never be returned to frontend clients
	•	Be rotated where supported
	•	Be deleted or invalidated on disconnect
The database should store a credential reference rather than plaintext secrets.
 
⸻
 
19.21 Token Refresh
Token refresh should:
	1.	Acquire a connection-level lock.
	2.	Verify current token state.
	3.	Refresh using the provider.
	4.	Replace credential material atomically.
	5.	Update expiration.
	6.	Record the refresh event.
	7.	Release the lock.
Concurrent refresh attempts must be prevented.
 
⸻
 
19.22 Token Refresh Failure
Refresh failures should be categorized as:
transient_provider_error
invalid_refresh_token
scope_revoked
account_disabled
credential_expired
provider_configuration_error
unknown
Invalid or revoked credentials should not be retried indefinitely.
The connection should move to attention_required or revoked.
 
⸻
 
19.23 API Key Management
API keys must be:
	•	Encrypted
	•	Redacted in the interface
	•	Scoped where possible
	•	Rotatable
	•	Audited
	•	Validated before activation
	•	Associated with an environment
	•	Associated with one connection or approved shared provider application
The platform should never display the full stored key after creation.
 
⸻
 
19.24 Service Accounts
Service-account integrations should store:
	•	Provider account identifier
	•	Credential reference
	•	Granted access
	•	Impersonation settings where applicable
	•	Rotation date
	•	Validation status
Uploaded credential files must be parsed securely and not retained unnecessarily in their original form.
 
⸻
 
19.25 Secrets Service
The Secrets Service should provide:
store_secret
retrieve_secret
rotate_secret
revoke_secret
delete_secret
validate_secret_reference
Secret values should be retrieved only at execution time by authorized backend services.
 
⸻
 
19.26 Secret Access Controls
Secret access should be limited by:
	•	Service identity
	•	Connector
	•	Environment
	•	Connection
	•	Operation
	•	Time
	•	Runtime policy
Administrative users may manage references but should not ordinarily retrieve secret values.
 
⸻
 
19.27 Provider Account Discovery
After authentication, the connector should discover available provider accounts or workspaces.
Examples:
	•	Google accounts
	•	GBP account groups
	•	Stripe accounts
	•	CRM workspaces
	•	CMS sites
	•	Toast restaurant locations
Discovered accounts must not automatically map to platform organizations.
 
⸻
 
19.28 Provider Resource Discovery
Provider resources may include:
	•	Locations
	•	Properties
	•	Websites
	•	Ad accounts
	•	Calendars
	•	CRM pipelines
	•	Lists
	•	Stores
	•	Payment accounts
	•	Phone numbers
	•	Messaging services
Recommended provider resource fields:
provider_resource_id
resource_type
display_name
parent_resource_id
status
metadata
discovered_at
 
⸻
 
19.29 Entity Mapping
Entity mapping connects provider resources to platform entities.
Examples:
Google location → LILOs location
Search Console property → Website
GA4 property → Website
CRM pipeline → Lead pipeline
CMS site → Publishing target
Stripe account → Billing account
Mapping must be explicit.
 
⸻
 
19.30 Entity Mapping Record
Recommended fields:
id
organization_id
connection_id
provider_resource_type
provider_resource_id
platform_entity_type
platform_entity_id
status
confidence
mapping_source
confirmed_by
confirmed_at
created_at
updated_at
 
⸻
 
19.31 Mapping Status
Recommended states:
unmapped
suggested
confirmed
conflicted
stale
disconnected
archived
Write operations require confirmed mappings.
Read-only sync may be permitted for suggested mappings only when the product explicitly supports it.
 
⸻
 
19.32 Suggested Mapping
Suggested mapping may use:
	•	Exact provider ID
	•	Business name
	•	Domain
	•	Address
	•	Phone
	•	Store code
	•	Account metadata
	•	Existing configuration
Suggested mappings must display their evidence.
Confidence must not replace human confirmation for high-risk write operations.
 
⸻
 
19.33 Canonical Models
Provider payloads must be normalized into canonical platform models.
Examples:
	•	Review
	•	Lead
	•	Location
	•	Metric observation
	•	Content publication
	•	Payment event
	•	Message
	•	Appointment reference
Provider-specific payloads should not become the primary product model.
 
⸻
 
19.34 Provider Payload Preservation
The framework may preserve raw provider payloads for:
	•	Troubleshooting
	•	Reconciliation
	•	Audit
	•	Reprocessing
	•	Provider-version migration
Raw payloads should:
	•	Be encrypted where sensitive
	•	Use limited retention
	•	Be referenced rather than copied broadly
	•	Follow product privacy rules
 
⸻
 
19.35 Mapping Functions
Connector mapping should be separated into:
provider_to_canonical
canonical_to_provider
provider_error_to_platform_error
provider_status_to_platform_status
Mapping functions should be deterministic and unit-tested.
 
⸻
 
19.36 Sync Engine
The Sync Engine coordinates inbound synchronization.
Supported sync types:
full
incremental
delta
backfill
reconciliation
manual
webhook_follow_up
 
⸻
 
19.37 Sync Run
Recommended fields:
id
organization_id
connection_id
connector_version
sync_type
resource_type
status
started_at
completed_at
cursor_before
cursor_after
items_received
items_created
items_updated
items_unchanged
items_failed
error_summary
 
⸻
 
19.38 Sync Status
Recommended states:
queued
running
partially_completed
completed
failed
cancelled
rate_limited
attention_required
A partially completed run must identify failed items.
 
⸻
 
19.39 Incremental Synchronization
Incremental sync should use provider-supported mechanisms such as:
	•	Updated timestamp
	•	Cursor
	•	Page token
	•	Change token
	•	Event sequence
	•	Provider webhook checkpoint
The cursor must advance only after durable processing.
 
⸻
 
19.40 Sync Cursor
Recommended fields:
connection_id
resource_type
cursor_type
cursor_value
last_successful_sync_at
last_attempted_sync_at
version
Cursor updates should be atomic.
 
⸻
 
19.41 Full Synchronization
Full synchronization should be used for:
	•	Initial connection
	•	Backfill
	•	Reconciliation
	•	Provider cursor invalidation
	•	Mapping change
	•	Connector migration
Full syncs must be bounded and resumable.
 
⸻
 
19.42 Sync Item Processing
Each provider item should follow:
Receive
    ↓
Validate
    ↓
Normalize
    ↓
Deduplicate
    ↓
Map
    ↓
Apply Product Rules
    ↓
Persist
    ↓
Emit Event
One invalid item should not necessarily fail the entire synchronization.
 
⸻
 
19.43 Sync Idempotency
Sync idempotency should use:
	•	Provider
	•	Provider resource
	•	Provider object ID
	•	Revision or update timestamp
	•	Content hash where needed
Repeated provider delivery must not create duplicate platform records.
 
⸻
 
19.44 Polling Framework
Polling is used when webhooks are unavailable or insufficient.
Polling schedules should define:
connection_id
resource_type
frequency
lookback_window
timezone
enabled
priority
last_run_at
next_run_at
 
⸻
 
19.45 Polling Rules
Polling should account for:
	•	Provider rate limits
	•	Data freshness requirements
	•	Account size
	•	Business priority
	•	Provider delay
	•	Failure history
	•	Incremental support
	•	Current incidents
Polling frequency should not be globally identical for all providers.
 
⸻
 
19.46 Polling Overlap Prevention
A polling job must acquire a scoped lock based on:
connection
resource_type
sync_mode
A second overlapping job should:
	•	Skip
	•	Join
	•	Reschedule
	•	Or cancel according to policy
 
⸻
 
19.47 Webhook Gateway
The Webhook Gateway provides centralized inbound event handling.
Responsibilities:
	•	Endpoint routing
	•	Signature verification
	•	Timestamp validation
	•	Replay protection
	•	Payload size validation
	•	Provider acknowledgment
	•	Durable storage
	•	Asynchronous processing
	•	Delivery deduplication
	•	Audit
 
⸻
 
19.48 Webhook Endpoint
Recommended fields:
id
connector_id
connection_id
provider_endpoint_id
secret_reference
status
created_at
last_received_at
last_verified_at
Endpoints may be:
	•	Shared by provider
	•	Connection-specific
	•	Organization-specific
	•	Resource-specific
 
⸻
 
19.49 Webhook Processing
Receive Request
    ↓
Validate Provider
    ↓
Validate Signature
    ↓
Validate Timestamp
    ↓
Check Replay and Duplicate
    ↓
Persist Delivery
    ↓
Return Provider-Accepted Response
    ↓
Process Asynchronously
    ↓
Emit Product Event
Provider acknowledgment should not wait for full product processing unless required.
 
⸻
 
19.50 Webhook Delivery
Recommended fields:
id
provider
connection_id
provider_event_id
event_type
received_at
signature_status
processing_status
attempt_count
payload_reference
error
processed_at
 
⸻
 
19.51 Webhook Replay Protection
Replay protection may use:
	•	Provider event ID
	•	Signature timestamp
	•	Nonce
	•	Payload hash
	•	Configured tolerance window
Repeated deliveries should be acknowledged safely without duplicate processing.
 
⸻
 
19.52 Webhook Failure Handling
Invalid signatures should:
	•	Be rejected
	•	Be logged safely
	•	Increment security diagnostics
	•	Never be retried internally
	•	Trigger alerting if repeated
Valid deliveries that fail processing should enter a retry queue.
 
⸻
 
19.53 Outbound Action Service
The Outbound Action Service coordinates provider write operations.
Examples:
	•	Publish GBP post
	•	Respond to review
	•	Send email
	•	Send SMS
	•	Create CRM lead
	•	Update CMS page
	•	Issue Stripe refund
	•	Upload media
Outbound actions require stricter controls than read synchronization.
 
⸻
 
19.54 Outbound Action Record
Recommended fields:
id
organization_id
connection_id
capability_key
resource_mapping_id
requested_by
approval_reference
idempotency_key
request_payload_reference
status
provider_request_id
provider_result_reference
attempt_count
created_at
executed_at
verified_at
 
⸻
 
19.55 Outbound Action Status
Recommended lifecycle:
draft
validated
awaiting_approval
approved
queued
executing
provider_accepted
verification_pending
verified
failed
ambiguous
cancelled
reconciled
Provider acceptance is not equivalent to verified completion.
 
⸻
 
19.56 Outbound Validation
Before execution, the framework should validate:
	•	Tenant
	•	Connection
	•	Environment
	•	Capability
	•	Scope
	•	Resource mapping
	•	Approval
	•	Credential state
	•	Provider health
	•	Rate limit
	•	Idempotency
	•	Payload schema
	•	Product-specific preconditions
	•	Runtime kill switch
 
⸻
 
19.57 Outbound Idempotency
The framework should generate or accept an idempotency key based on:
	•	Organization
	•	Provider
	•	Capability
	•	Target resource
	•	Product object
	•	Approved revision
	•	Workflow execution
Provider-native idempotency should be used where available.
Platform idempotency remains required even when the provider supports it.
 
⸻
 
19.58 Ambiguous Provider Outcomes
An outcome is ambiguous when:
	•	Request timed out after transmission.
	•	Connection closed before response.
	•	Provider returned an unknown state.
	•	Provider accepted a job but final status is delayed.
	•	Internal persistence failed after provider success.
Ambiguous actions must not be retried blindly.
They should move to reconciliation.
 
⸻
 
19.59 Verification
Verification confirms that the expected provider state exists.
Verification may use:
	•	Immediate read-after-write
	•	Delayed polling
	•	Provider webhook
	•	Provider status endpoint
	•	Manual confirmation
Verification requirements should be capability-specific.
 
⸻
 
19.60 Reconciliation Service
Reconciliation compares platform expectations with provider state.
Typical cases:
	•	Possible duplicate publication
	•	Missing internal result
	•	Provider-side manual change
	•	Deleted external record
	•	Mismatched status
	•	Stale mapping
	•	Partial batch completion
 
⸻
 
19.61 Reconciliation Case
Recommended fields:
id
organization_id
connection_id
action_id
resource_type
case_type
status
expected_state
provider_state
difference
resolution
created_at
resolved_at
 
⸻
 
19.62 Reconciliation Workflow
Ambiguous or Conflicting State
    ↓
Retrieve Provider State
    ↓
Compare Expected and Actual
    ↓
Match Existing Provider Object
    ↓
Update Internal State
    ↓
Retry Only if Confirmed Safe
    ↓
Escalate if Unresolved
 
⸻
 
19.63 Retry Strategy
Retries should be based on error classification.
Retryable examples:
	•	Timeout
	•	Temporary provider outage
	•	HTTP 429
	•	HTTP 502
	•	HTTP 503
	•	Network interruption
Usually non-retryable examples:
	•	Invalid credentials
	•	Missing scope
	•	Invalid payload
	•	Unsupported operation
	•	Resource not found
	•	Permission denied
	•	Provider policy rejection
 
⸻
 
19.64 Retry Policy
Recommended retry configuration:
maximum_attempts
initial_delay
backoff_multiplier
maximum_delay
jitter
retryable_error_categories
deadline
reconciliation_required
Retry policies should be connector- and capability-specific.
 
⸻
 
19.65 Retry Isolation
Retries must be scoped to:
	•	Connection
	•	Operation
	•	Resource
	•	Provider
A failing provider connection must not block unrelated organizations.
 
⸻
 
19.66 Rate-Limit Manager
The Rate-Limit Manager coordinates provider usage.
It should track:
	•	Provider
	•	Connection
	•	Endpoint
	•	Capability
	•	Window
	•	Remaining quota
	•	Reset time
	•	Retry-after value
	•	Estimated usage
 
⸻
 
19.67 Rate-Limit Strategy
Rate-limit handling may include:
	•	Request queueing
	•	Priority tiers
	•	Backoff
	•	Batch operations
	•	Reduced polling
	•	Deferred low-priority work
	•	Provider-specific concurrency limits
High-priority actions should not automatically bypass provider limits.
 
⸻
 
19.68 Request Priority
Recommended priorities:
critical
high
normal
low
background
Examples:
	•	Emergency lead notification: high
	•	Review response publication: normal
	•	Historical metric backfill: background
Priority affects queue ordering, not authorization.
 
⸻
 
19.69 Provider Request Record
Provider requests should record safe metadata:
id
connection_id
action_or_sync_id
method
endpoint_template
request_started_at
request_completed_at
status_code
latency_ms
result_category
provider_request_id
retry_after
Request bodies, secrets, and sensitive headers should not be logged by default.
 
⸻
 
19.70 Standard Error Model
Provider errors should normalize into:
authentication_error
authorization_error
validation_error
not_found
conflict
rate_limited
provider_unavailable
timeout
network_error
unsupported_capability
mapping_error
policy_rejection
ambiguous_result
internal_connector_error
unknown
The original provider error may be preserved securely for diagnostics.
 
⸻
 
19.71 Error Response Contract
Internal integration errors should include:
{
  "code": "PROVIDER_PERMISSION_DENIED",
  "category": "authorization_error",
  "provider": "example_provider",
  "operation": "reviews.respond",
  "retryable": false,
  "user_action_required": true,
  "safe_message": "The connected account does not have permission to publish review responses."
}
User-facing messages must not expose secrets or unnecessary provider internals.
 
⸻
 
19.72 Provider Health
Provider health should be assessed at multiple levels:
Global provider
Connector
Connection
Capability
Resource mapping
One unhealthy connection should not mark the provider globally unavailable.
 
⸻
 
19.73 Health States
Recommended states:
healthy
degraded
rate_limited
authentication_required
permission_limited
mapping_required
provider_incident
disabled
unknown
 
⸻
 
19.74 Health Checks
Health checks may validate:
	•	Credential validity
	•	Required scope
	•	Account accessibility
	•	Resource existence
	•	Capability availability
	•	API reachability
	•	Webhook status
	•	Sync freshness
	•	Recent error rate
Health checks should avoid unnecessary write actions.
 
⸻
 
19.75 Provider Incident
Recommended fields:
id
provider_id
connector_id
scope
severity
status
started_at
detected_at
resolved_at
summary
affected_capabilities
source
Incidents may be:
	•	Provider-reported
	•	Platform-detected
	•	Manually declared
 
⸻
 
19.76 Circuit Breaker
The framework should support circuit breakers for repeated provider failures.
Recommended states:
closed
open
half_open
When open:
	•	New low-priority requests pause.
	•	Repeated failing calls stop.
	•	Health probes continue.
	•	Users see degraded status.
	•	Recovery is tested gradually.
 
⸻
 
19.77 Connection Diagnostics
Authorized users should be able to inspect:
	•	Connection status
	•	Scopes
	•	Capability state
	•	Resource mappings
	•	Last successful sync
	•	Last error category
	•	Webhook health
	•	Rate-limit state
	•	Required action
	•	Connector version
Secrets must never appear.
 
⸻
 
19.78 Integration Permissions
Recommended permissions:
integrations.view
integrations.connect
integrations.disconnect
integrations.reauthorize
integrations.map_resources
integrations.manage_credentials
integrations.run_sync
integrations.run_backfill
integrations.execute_action
integrations.view_diagnostics
integrations.manage_webhooks
integrations.manage_runtime
integrations.export_logs
Credential management and outbound action execution should be separate permissions.
 
⸻
 
19.79 Connection Approval
Some connections may require:
no_approval
organization_admin
agency_admin
dual_approval
platform_admin
High-risk payment or messaging integrations may require stronger approval than read-only analytics integrations.
 
⸻
 
19.80 Disconnect Workflow
Disconnect Requested
    ↓
Check Active Workflows
    ↓
Warn About Impact
    ↓
Pause New Operations
    ↓
Attempt Provider Revocation
    ↓
Disable Webhooks
    ↓
Revoke Local Credentials
    ↓
Preserve Historical Data
    ↓
Mark Disconnected
Disconnecting should not delete historical product records automatically.
 
⸻
 
19.81 Credential Rotation
Rotation workflow:
Add New Credential
    ↓
Validate
    ↓
Activate
    ↓
Run Health Check
    ↓
Retire Previous Credential
    ↓
Revoke Old Credential
    ↓
Audit
The platform should avoid downtime during supported rotations.
 
⸻
 
19.82 Connector SDK
The Connector SDK should define standard interfaces.
Example conceptual interface:
class Connector:
    def get_manifest(self): ...
    def authorize(self, request): ...
    def exchange_credentials(self, callback): ...
    def refresh_credentials(self, connection): ...
    def discover_accounts(self, connection): ...
    def discover_resources(self, connection): ...
    def discover_capabilities(self, connection): ...
    def sync(self, context): ...
    def execute_action(self, context): ...
    def verify_action(self, context): ...
    def reconcile(self, context): ...
    def health_check(self, connection): ...
    def handle_webhook(self, request): ...
Connectors may omit unsupported interfaces only when the manifest declares that limitation.
 
⸻
 
19.83 Connector Manifest
Each connector should provide a manifest containing:
connector_key
provider_key
version
authentication_types
capabilities
resource_types
webhook_event_types
polling_support
rate_limit_profile
configuration_schema
required_secrets
supported_environments
data_classifications
The platform should validate the manifest during registration.
 
⸻
 
19.84 Connector Configuration Schema
Connector-specific configuration may include:
	•	Account identifiers
	•	Region
	•	API base URL
	•	Webhook mode
	•	Polling preference
	•	Provider version
	•	Feature flags
	•	Custom field mappings
Configuration should be schema-validated and versioned.
 
⸻
 
19.85 Connector Isolation
Connector execution should be isolated logically by:
	•	Tenant
	•	Connection
	•	Provider
	•	Environment
	•	Operation
A connector failure must not corrupt platform state outside its execution context.
 
⸻
 
19.86 Connector Runtime
Initial implementation may run connectors inside the modular backend and worker environment.
A connector may later move to an isolated service when justified by:
	•	Security
	•	Resource demand
	•	Provider dependency
	•	Deployment frequency
	•	Reliability
	•	Language runtime
The initial architecture should not require microservices.
 
⸻
 
19.87 Product Integration Contract
Products should request integration operations through shared service methods.
Examples:
integration.read_resources
integration.start_sync
integration.execute_action
integration.verify_action
integration.get_health
integration.get_capabilities
Products should receive canonical data or normalized operation results.
 
⸻
 
19.88 Event Ingestion
Provider events should be converted into platform events.
Example:
Provider webhook
    ↓
Connector event normalization
    ↓
Integration event
    ↓
Product handler
Standard event envelope should include:
event_id
event_type
organization_id
connection_id
provider
resource_type
resource_id
occurred_at
received_at
payload_reference
schema_version
 
⸻
 
19.89 Event Ordering
The framework should not assume provider events always arrive in order.
Event processing should use:
	•	Provider timestamps
	•	Revision values
	•	Sequence values where supported
	•	Idempotency
	•	Current provider state
	•	Reconciliation
Older events must not overwrite newer state.
 
⸻
 
19.90 File Transfer
Some integrations require file exchange.
Examples:
	•	CMS asset upload
	•	Lead attachment import
	•	Report export
	•	Product catalog import
	•	Credential file upload
File operations should validate:
	•	Type
	•	Size
	•	Integrity
	•	Malware status
	•	Access
	•	Retention
	•	Provider capability
 
⸻
 
19.91 Batch Operations
Batch operations should support:
	•	Per-item validation
	•	Per-item result
	•	Partial completion
	•	Resume
	•	Idempotency
	•	Rate-limit awareness
	•	Maximum batch size
A batch must not be represented as successful when some items failed.
 
⸻
 
19.92 Data Deletion Requests
Provider deletion requests may arise from:
	•	User disconnect
	•	Privacy request
	•	Provider webhook
	•	Account removal
	•	Resource deletion
The framework should route deletion events to product-specific retention logic.
Connectors must not independently delete product history.
 
⸻
 
19.93 Audit Requirements
Audit events should include:
	•	Connection created
	•	Connection authorized
	•	Scopes changed
	•	Credential rotated
	•	Connection reauthorized
	•	Resource mapped
	•	Resource unmapped
	•	Manual sync started
	•	Backfill started
	•	Outbound action requested
	•	Action verified
	•	Action failed
	•	Webhook secret rotated
	•	Connector version changed
	•	Connection disconnected
	•	Runtime control activated
 
⸻
 
19.94 Observability
Integration observability should include:
	•	Request rate
	•	Success rate
	•	Error rate
	•	Latency
	•	Retry count
	•	Rate-limit events
	•	Webhook volume
	•	Webhook failures
	•	Sync lag
	•	Queue depth
	•	Reconciliation backlog
	•	Connection health
	•	Connector version distribution
Metrics should be tagged without exposing secrets or personal data.
 
⸻
 
19.95 Logging
Logs should contain:
	•	Correlation ID
	•	Organization reference
	•	Connection reference
	•	Connector
	•	Operation
	•	Safe resource reference
	•	Result category
	•	Timing
Logs should not contain:
	•	Access tokens
	•	Refresh tokens
	•	API keys
	•	Full authorization headers
	•	Sensitive payloads
	•	Unredacted personal data
 
⸻
 
19.96 Correlation IDs
Every sync, webhook, and outbound action should use a correlation ID.
The correlation ID should connect:
	•	API request
	•	Workflow execution
	•	Connector request
	•	Provider response
	•	Product update
	•	Audit event
	•	Error record
 
⸻
 
19.97 Sandbox Support
Where providers support sandbox environments, connectors should expose them explicitly.
Sandbox behavior should define:
	•	Authentication endpoint
	•	API endpoint
	•	Test credentials
	•	Test resources
	•	Webhook endpoint
	•	Known limitations
	•	Reset behavior
The platform must not infer that sandbox behavior exactly matches production.
 
⸻
 
19.98 Provider Mocking
For providers without sandboxes, the test harness should support provider mocks.
Mocks should reproduce:
	•	Success
	•	Pagination
	•	Rate limits
	•	Timeouts
	•	Invalid credentials
	•	Permission errors
	•	Partial failures
	•	Webhook replay
	•	Ambiguous write result
	•	Provider schema changes
 
⸻
 
19.99 Contract Tests
Every connector should pass contract tests for:
	•	Manifest
	•	Authentication
	•	Resource discovery
	•	Capability discovery
	•	Sync
	•	Pagination
	•	Idempotency
	•	Error normalization
	•	Rate-limit behavior
	•	Webhook verification
	•	Outbound actions
	•	Verification
	•	Reconciliation
	•	Health checks
 
⸻
 
19.100 Mapping Tests
Mapping tests should verify:
	•	Provider-to-canonical conversion
	•	Canonical-to-provider conversion
	•	Missing fields
	•	Unknown enum values
	•	Timezone conversion
	•	Currency preservation
	•	Pagination boundaries
	•	Duplicate detection
	•	Revision handling
Provider fixtures should be versioned.
 
⸻
 
19.101 Migration Testing
Connector upgrades should test:
	•	Existing credentials
	•	Existing mappings
	•	Existing cursors
	•	Existing webhooks
	•	Historical payload compatibility
	•	New provider fields
	•	Removed fields
	•	Changed error behavior
	•	Rollback
 
⸻
 
19.102 Connector Release Process
Recommended release lifecycle:
Implement
    ↓
Unit Test
    ↓
Contract Test
    ↓
Sandbox Test
    ↓
Internal Pilot
    ↓
Limited Production
    ↓
General Availability
    ↓
Monitor
High-risk connectors should use a smaller initial rollout.
 
⸻
 
19.103 Feature Flags
Connector capabilities may be controlled by:
	•	Global flag
	•	Organization flag
	•	Connection flag
	•	Environment flag
	•	Capability flag
	•	Connector-version flag
Feature flags must not bypass permission or approval checks.
 
⸻
 
19.104 Connector Deprecation
Deprecation should include:
	•	Replacement connector
	•	Migration path
	•	Deadline
	•	Affected connections
	•	Capability changes
	•	User communication
	•	Rollback plan
Retired connectors must not accept new connections.
 
⸻
 
19.105 Initial Provider Priorities
Initial implementation should prioritize integrations necessary for the first production workflows.
Priority 1
	•	Google Business Profile
	•	Google Search Console
	•	Google Analytics 4
	•	Resend
	•	Stripe
	•	Supabase
	•	Astro publishing adapter
Priority 2
	•	Google Ads
	•	Twilio or approved SMS provider
	•	WordPress
	•	Drupal
	•	Toast
	•	Booqable
Priority 3
	•	Jobber
	•	Housecall Pro
	•	FieldworkHQ
	•	HubSpot
	•	GoHighLevel
	•	Slack
Provider priority should be driven by product requirements and active client demand.
 
⸻
 
19.106 Google Integration Family
Google connectors should share common provider application configuration where practical while preserving separate:
	•	Scopes
	•	Tokens
	•	Capabilities
	•	APIs
	•	Resource mappings
	•	Health
A Search Console connection must not imply authorization for GBP or Google Ads.
 
⸻
 
19.107 CMS Publishing Adapters
CMS connectors should support a normalized publishing contract.
Potential capabilities:
content.create
content.update
content.publish
content.unpublish
content.read
content.upload_asset
content.read_status
Provider-specific concerns include:
	•	Slugs
	•	Content formats
	•	Draft status
	•	Categories
	•	Authors
	•	Media
	•	SEO metadata
	•	Structured data
	•	Revisions
 
⸻
 
19.108 Astro Publishing Adapter
The Astro adapter may operate through:
	•	GitHub pull request
	•	Git commit
	•	Content API
	•	Repository automation
	•	Approved deployment pipeline
The preferred initial method should preserve:
	•	Version control
	•	Review
	•	Build validation
	•	Deployment verification
	•	Rollback
Direct production-file mutation is prohibited.
 
⸻
 
19.109 CRM Connectors
CRM connectors should support a shared lead contract.
Potential operations:
lead.create
lead.update
lead.read
lead.assign
lead.add_note
lead.create_task
lead.read_status
lead.read_conversion
CRM authority rules must be configured per field or domain.
 
⸻
 
19.110 Messaging Connectors
Messaging connectors should support:
	•	Send
	•	Delivery status
	•	Inbound message
	•	Opt-out event
	•	Phone-number capability
	•	Template support
	•	Provider error
	•	Cost metadata where available
Consent and suppression remain owned by the Leads product.
 
⸻
 
19.111 Payment Connectors
Payment connectors require elevated security.
Potential capabilities:
	•	Read customers
	•	Read subscriptions
	•	Read charges
	•	Read payouts
	•	Read disputes
	•	Issue refund
	•	Manage billing portal references
Write operations such as refunds require:
	•	Elevated permission
	•	Explicit approval
	•	Amount validation
	•	Idempotency
	•	Audit
	•	Verification
 
⸻
 
19.112 Integration UX
The integration workspace should include:
	•	Available integrations
	•	Connected integrations
	•	Connection status
	•	Required action
	•	Capabilities
	•	Accounts
	•	Resource mappings
	•	Last sync
	•	Health
	•	Diagnostics
	•	Disconnect
	•	Reauthorize
 
⸻
 
19.113 Connection Wizard
Recommended flow:
Select Provider
    ↓
Review Capabilities
    ↓
Authorize
    ↓
Select Provider Account
    ↓
Map Resources
    ↓
Validate
    ↓
Configure Sync
    ↓
Review Permissions
    ↓
Activate
 
⸻
 
19.114 Mapping Interface
The mapping interface should display:
	•	Provider resource
	•	Suggested platform entity
	•	Matching evidence
	•	Confidence
	•	Existing mappings
	•	Conflict warnings
	•	Confirmation action
Bulk confirmation should remain restricted.
 
⸻
 
19.115 Integration Diagnostics UX
Diagnostics should show:
	•	Safe status summary
	•	Last successful operation
	•	Last failed operation
	•	Error category
	•	User action required
	•	Provider action required
	•	Retry state
	•	Scope status
	•	Mapping status
	•	Sync freshness
Raw provider payloads should be restricted to authorized technical users.
 
⸻
 
19.116 Notifications
Notifications may include:
	•	Connection expired
	•	Reauthorization required
	•	Scope removed
	•	Mapping conflict
	•	Sync delayed
	•	Webhook failing
	•	Provider degraded
	•	Rate limit sustained
	•	Outbound action failed
	•	Ambiguous action requires reconciliation
	•	Connector upgrade required
	•	Credential rotation due
 
⸻
 
19.117 Runtime Controls
Authorized operators should be able to:
	•	Pause one connector
	•	Pause one provider
	•	Pause one connection
	•	Pause one capability
	•	Disable outbound actions
	•	Disable webhook processing
	•	Disable polling
	•	Force read-only mode
	•	Trigger health check
	•	Trigger sync
	•	Trigger reconciliation
	•	Mark provider incident
	•	Roll back connector version
All controls must be audited.
 
⸻
 
19.118 Security Requirements
The framework must enforce:
	•	Tenant isolation
	•	Server-side credentials
	•	Encryption at rest
	•	Encryption in transit
	•	Least privilege
	•	Scope validation
	•	Signature validation
	•	Replay protection
	•	Secret redaction
	•	Audit
	•	Environment separation
	•	Restricted diagnostics
	•	Credential revocation
 
⸻
 
19.119 Privacy Requirements
Connectors should request only data necessary for approved product behavior.
The framework should support:
	•	Field minimization
	•	Limited raw-payload retention
	•	Data-classification tagging
	•	Product-specific retention
	•	Deletion routing
	•	Export restriction
	•	Sensitive-data redaction
 
⸻
 
19.120 Operational Requirements
The Integration Framework requires:
	•	Durable queues
	•	Scheduled workers
	•	Webhook gateway
	•	Locking
	•	Idempotency storage
	•	Secret storage
	•	Connection health
	•	Rate-limit tracking
	•	Reconciliation queues
	•	Connector registry
	•	Audit
	•	Monitoring
	•	Incident controls
 
⸻
 
19.121 Minimum Viable Integration Framework
The initial framework should include:
Connection Management
	•	Provider registry
	•	Connector registry
	•	OAuth
	•	API key support
	•	Encrypted credential references
	•	Connection status
	•	Disconnect
Mapping
	•	Account discovery
	•	Resource discovery
	•	Explicit entity mapping
	•	Mapping conflicts
Synchronization
	•	Full sync
	•	Incremental sync
	•	Cursor
	•	Polling
	•	Idempotency
	•	Partial failure
Webhooks
	•	Signature verification
	•	Replay protection
	•	Durable delivery storage
	•	Asynchronous processing
Outbound Actions
	•	Capability validation
	•	Approval reference
	•	Idempotency
	•	Verification
	•	Reconciliation
Operations
	•	Health
	•	Error normalization
	•	Retry
	•	Rate-limit handling
	•	Audit
	•	Runtime controls
	•	Test harness
 
⸻
 
19.122 Implementation Phases
Phase 1 — Registry and Connections
Implement:
	•	Provider registry
	•	Connector manifests
	•	Connection records
	•	OAuth
	•	API keys
	•	Credential references
	•	Connection diagnostics
Phase 2 — Resource Mapping
Implement:
	•	Account discovery
	•	Resource discovery
	•	Suggested mappings
	•	Confirmation
	•	Conflict handling
	•	Capability discovery
Phase 3 — Synchronization
Implement:
	•	Sync engine
	•	Full sync
	•	Incremental sync
	•	Cursors
	•	Polling
	•	Item-level results
	•	Idempotency
Phase 4 — Webhooks
Implement:
	•	Gateway
	•	Signature adapters
	•	Replay protection
	•	Durable delivery records
	•	Asynchronous processing
	•	Event normalization
Phase 5 — Outbound Actions
Implement:
	•	Action records
	•	Validation
	•	Provider writes
	•	Idempotency
	•	Verification
	•	Reconciliation
	•	Approval linkage
Phase 6 — Reliability
Implement:
	•	Rate-limit manager
	•	Circuit breakers
	•	Provider incidents
	•	Advanced diagnostics
	•	Connector migration
	•	Backfills
	•	Runtime controls
Phase 7 — Connector SDK
Implement:
	•	Shared interfaces
	•	Contract tests
	•	Mock providers
	•	Release workflow
	•	Connector documentation
	•	Internal developer tooling
 
⸻
 
19.123 Future Capabilities
Potential future capabilities include:
	•	Public connector marketplace
	•	Partner-developed connectors
	•	Connector certification
	•	Customer-defined webhooks
	•	Custom REST connectors
	•	GraphQL connectors
	•	Secure file-transfer connectors
	•	Low-code field mapping
	•	Integration usage billing
	•	Regional connector execution
	•	Dedicated integration workers
	•	Connector analytics
	•	Automated schema-change detection
	•	Provider API changelog monitoring
Future capabilities must preserve security, tenant isolation, contract validation, and product authority boundaries.
 
⸻
 
19.124 Integration Guardrails
The following are prohibited unless formally approved:
	1.	Products calling provider SDKs directly
	2.	Storing plaintext provider credentials
	3.	Returning provider tokens to the frontend
	4.	Logging authentication headers
	5.	Placing credentials in AI prompts
	6.	Assuming capabilities without discovery or configuration
	7.	Automatically mapping provider resources for write access
	8.	Writing through unconfirmed mappings
	9.	Treating provider acceptance as verified completion
	10.	Blindly retrying ambiguous write operations
	11.	Advancing sync cursors before durable processing
	12.	Treating missing provider data as deletion without confirmation
	13.	Allowing old webhook events to overwrite newer state
	14.	Ignoring webhook signatures
	15.	Ignoring replay protection
	16.	Using one environment’s credentials in another environment
	17.	Allowing provider-specific payloads to become primary product models
	18.	Allowing connectors to make product business decisions
	19.	Allowing products to manage secrets directly
	20.	Retrying authorization failures indefinitely
	21.	Allowing one connection failure to block unrelated tenants
	22.	Reporting partial batch success as complete success
	23.	Overwriting newer external state with stale platform state
	24.	Deleting historical product data when disconnecting
	25.	Exposing raw provider payloads to ordinary users
	26.	Releasing connectors without contract tests
	27.	Changing connector behavior without versioning
	28.	Allowing feature flags to bypass authorization
	29.	Executing high-risk provider actions without approval and audit
	30.	Allowing the Integration Framework to bypass product, workflow, security, or tenant controls
 
⸻
 
19.125 Acceptance Requirements
The Integration Framework is not production-ready until it supports:
	•	Provider registry
	•	Connector registry
	•	Connector manifests
	•	Connector versioning
	•	Capability discovery
	•	OAuth
	•	API keys
	•	Encrypted credential references
	•	Token refresh
	•	Connection health
	•	Account discovery
	•	Resource discovery
	•	Explicit mapping
	•	Full synchronization
	•	Incremental synchronization
	•	Sync cursors
	•	Polling
	•	Webhook verification
	•	Replay protection
	•	Delivery deduplication
	•	Outbound actions
	•	Idempotency
	•	Verification
	•	Reconciliation
	•	Error normalization
	•	Retry classification
	•	Rate-limit handling
	•	Audit
	•	Tenant isolation
	•	Environment separation
	•	Runtime controls
	•	Contract testing
 
⸻
 
19.126 Section Decisions
This section establishes the following decisions:
	1.	External providers connect through standardized connectors.
	2.	Products do not call provider APIs or SDKs directly.
	3.	Products own business logic; connectors own provider communication.
	4.	Provider payloads are normalized into canonical platform models.
	5.	Provider-specific payloads may be retained for diagnostics but do not become authoritative product state.
	6.	Every connector provides a versioned manifest.
	7.	Capabilities are explicit and may vary by account, scope, plan, resource, and environment.
	8.	Authentication and secret handling are centralized.
	9.	Credentials remain encrypted, server-side, redacted, and excluded from AI context.
	10.	OAuth state is signed, short-lived, single-use, and tenant-bound.
	11.	Provider accounts and resources require explicit platform mapping.
	12.	Write operations require confirmed mappings.
	13.	Synchronization supports full, incremental, backfill, manual, and reconciliation modes.
	14.	Sync cursors advance only after durable processing.
	15.	Webhooks use signature validation, replay protection, durable storage, and asynchronous handling.
	16.	Polling supplements webhooks where provider behavior requires it.
	17.	Inbound processing is idempotent.
	18.	Outbound actions use capability checks, approval linkage, idempotency, verification, and audit.
	19.	Provider acceptance does not equal verified completion.
	20.	Ambiguous write results enter reconciliation rather than blind retry.
	21.	Retry behavior is determined by normalized error category.
	22.	Rate limiting is managed by provider, connection, endpoint, and priority.
	23.	Provider health is measured globally and per connection, capability, and resource.
	24.	Circuit breakers prevent repeated provider failure from overwhelming the platform.
	25.	Disconnecting revokes future access but preserves historical product records.
	26.	Connector changes affecting behavior require versioning and migration testing.
	27.	Connector implementations must pass shared contract tests.
	28.	Initial connector execution remains within the modular backend and worker architecture unless isolation becomes justified.
	29.	The minimum viable framework includes connection management, mapping, sync, webhooks, outbound actions, health, reconciliation, and testing.
	30.	No external operation may execute without confirmed tenant, connection, environment, capability, mapping, credential, permission, idempotency, and runtime context.

---

Section 20 — Platform Administration & Configuration

20.1 Purpose of This Section
This section defines the administrative control plane for the LILOs platform and the configuration system used by platform operators, agency personnel, client administrators, products, workflows, integrations, and runtime services.

It establishes:
- Administrative scopes and responsibilities
- Configuration ownership and inheritance
- Versioned and effective-dated configuration
- Product registration, entitlement, readiness, activation, suspension, and retirement
- Business facts and authority
- Policy registries
- Feature flags and runtime controls
- User, organization, location, and integration administration
- Approval-policy administration
- Onboarding and offboarding controls
- Support access and impersonation boundaries
- Change previews, validation, audit, rollback, and recovery

This section does not redefine product business logic from Sections 12–18, security controls from Section 9, or connector behavior from Section 19. It defines how authorized administrators configure and operate those systems without bypassing their ownership boundaries.

20.2 Administrative Principles
Platform administration must follow these principles:
1. Configuration is data, not hidden code.
2. Effective behavior must be explainable from its source configuration.
3. More specific configuration may override broader defaults only where the schema permits it.
4. Security, legal, privacy, tenant-isolation, and mandatory platform controls cannot be weakened by lower scopes.
5. Administrative changes are validated before activation.
6. Material changes are versioned, attributable, and reversible where technically possible.
7. Product readiness is proven, not inferred from an enabled flag.
8. Client-visible administration is separated from LILOs internal administration.
9. Emergency runtime controls do not become permanent undocumented configuration.
10. No administrator receives universal access merely because an interface exposes a control.

20.3 Administrative Scopes
The platform supports the following administrative scopes:
- Platform scope: global registries, platform defaults, supported providers, security baselines, and system-wide controls.
- Agency scope: LILOs workspace operations across authorized client organizations.
- Organization scope: customer account, commercial configuration, users, products, integrations, and policies.
- Location scope: physical location, service area, operating unit, local business facts, and product overrides.
- Product scope: product-specific configuration and readiness.
- Workflow scope: versioned workflow parameters and approval policy.
- Integration scope: provider connection, mapped resources, capabilities, health, and synchronization policy.
- User scope: memberships, preferences, notification settings, and permitted personal defaults.

Every administrative command must carry an explicit scope. A missing or inferred tenant scope is an error.

20.4 Administrative Roles
Recommended administrative role families include:
- platform_super_admin
- platform_security_admin
- platform_operations_admin
- platform_billing_admin
- agency_owner
- agency_admin
- agency_operator
- agency_analyst
- organization_owner
- organization_admin
- location_admin
- product_admin
- integration_admin
- approver
- auditor
- support_operator

Role names do not grant authority by themselves. Permissions, memberships, explicit scope, sensitive-action controls, and deny rules determine access.

20.5 Separation of Duties
The platform should support separation of duties for high-impact administration. Examples include:
- A user who changes a security-sensitive policy should not be the sole approver of that change when dual approval is required.
- A support operator may inspect an account but may not modify billing or secrets.
- A billing administrator may change commercial settings but may not publish client content.
- An integration administrator may reconnect a provider but may not broaden product entitlements.
- A platform operator may activate maintenance mode but may not edit audit history.

The initial release may use a limited set of roles, but permission boundaries must support later separation without redesign.

20.6 Configuration Registry
All configurable behavior must be represented through a configuration registry or a product-owned schema registered with the platform.

Each configuration definition should include:
- configuration_key
- owning_module
- schema_version
- value_type
- allowed_scopes
- default_value or default resolver
- validation rules
- sensitivity classification
- whether inheritance is allowed
- whether lower-scope override is allowed
- whether approval is required
- activation behavior
- rollback behavior
- documentation
- deprecation state

Unknown configuration keys must not be silently accepted in production.

20.7 Configuration Hierarchy
The authoritative hierarchy is:
Platform baseline
    ↓
Industry default
    ↓
Agency template, where authorized
    ↓
Organization configuration
    ↓
Location configuration
    ↓
Product configuration
    ↓
Workflow or resource configuration

The effective configuration resolver must:
- Return the final effective value
- Return the source scope and version for each value
- Identify inherited and overridden values
- Identify blocked overrides
- Validate compatibility across related settings
- Expose an explanation suitable for administrative interfaces and diagnostics

20.8 Mandatory Controls
Certain controls are non-overridable below platform scope. These include:
- Tenant isolation
- Authentication requirements
- Secret-handling rules
- Audit requirements
- Opt-out and communication suppression
- Restricted-data exclusions from AI context
- Mandatory approval for defined high-risk actions
- Provider restrictions required by data classification
- Retention minimums required for security and audit
- Prohibition on direct product-to-provider calls

A lower scope may impose stricter controls but may not weaken these baselines.

20.9 Configuration Records
A configuration value should preserve:
- id
- configuration_definition_id
- scope_type
- scope_id
- value
- schema_version
- status
- effective_from
- effective_until
- created_by
- created_at
- approved_by
- approved_at
- supersedes_id
- change_reason
- source_template_id, when applicable

Approved versions are immutable. Corrections create a superseding version.

20.10 Configuration States
Recommended states are:
- draft
- validation_failed
- pending_approval
- approved
- scheduled
- active
- superseded
- revoked
- expired
- archived

Draft configuration must not influence runtime behavior.

20.11 Effective-Dated Configuration
Configuration may become active immediately or at an approved future time.
The system must prevent:
- Overlapping active versions for the same single-valued key and scope
- Activation before required approval
- Activation with unresolved validation errors
- Retroactive changes that rewrite historical interpretation

Historical workflows and reports should retain references to the configuration versions used at execution time.

20.12 Configuration Validation
Validation occurs at several levels:
1. Schema validation
2. Type and range validation
3. Scope validation
4. Cross-field validation
5. Product-readiness validation
6. Permission and approval validation
7. Provider-capability validation where applicable
8. Security and privacy validation
9. Conflict validation
10. Activation validation

A validation result must distinguish errors, warnings, and informational findings. Errors block activation. Warnings require acknowledgment or approval according to policy.

20.13 Change Preview and Impact Analysis
Before a material administrative change, the platform should show:
- Current value
- Proposed value
- Effective scope
- Inherited descendants affected
- Products and workflows affected
- External systems affected
- Required approvals
- Expected side effects
- Rollback limitations
- Scheduled activation time

High-impact changes require consequence-aware confirmation.

20.14 Configuration Rollback
Rollback creates a new approved version based on a prior valid value. It must not delete history or reactivate an old database row in place.

Rollback may be unavailable when:
- An external irreversible action already occurred
- A schema migration removed compatibility
- Reinstating the value would violate a current platform rule
- The referenced provider capability no longer exists

The platform must explain when rollback requires compensating action rather than a simple version change.

20.15 Business Facts Registry
Business facts are structured, authoritative facts used by products, reports, and AI tasks.
Examples include:
- Legal and public business names
- Addresses and service areas
- Phone numbers
- Hours
- Services
- Licenses and certifications
- Approved guarantees
- Pricing rules
- Amenities
- Reservation or appointment URLs
- Approved brand claims

Each fact should include source, authority, scope, status, validity period, sensitivity, and approval state.

20.16 Business Fact Authority
Authority order must be explicit. A recommended order is:
1. Verified organization-approved record
2. Verified provider record designated authoritative for that field
3. Approved location record
4. Published first-party website record
5. Approved internal operating record
6. Unverified imported record

Conflicts must be surfaced rather than silently resolved when authority is ambiguous.

20.17 Business Fact Lifecycle
Recommended states include:
- discovered
- unverified
- proposed
- pending_approval
- approved
- active
- disputed
- superseded
- expired
- rejected

Only active approved facts may be used for public claims unless a product specification explicitly permits a safe general statement.

20.18 Product Registry
The platform product registry defines each supported product and version. It should include:
- product_key
- display_name
- owning_module
- current_version
- lifecycle_state
- required_core_capabilities
- optional_capabilities
- required_integrations
- configuration_schema
- readiness_checks
- permission namespace
- metric namespace
- event namespace
- documentation references

Product registration is distinct from entitlement and activation.

20.19 Product Entitlements
An entitlement records commercial or internal authorization to use a product or capability. It should include:
- organization and optional location scope
- product and capability
- entitlement source
- start and end dates
- limits
- service tier
- status
- trial state
- billing reference
- suspension policy

Product code evaluates entitlements through the shared entitlement service rather than directly calling Stripe.

20.20 Product Readiness
Readiness is calculated from required conditions, including:
- Entitlement active
- Required configuration valid
- Required integrations connected
- Provider resources mapped
- Required permissions available
- Required business facts approved
- Required workflow definitions active
- Required notification path configured
- No blocking runtime control

Readiness checks return individual findings and remediation actions. A product may be entitled but not ready.

20.21 Product Lifecycle Administration
Recommended lifecycle states are:
- registered
- not_enabled
- setup_required
- connection_required
- configuration_required
- ready
- active
- paused
- degraded
- suspended
- retiring
- archived

Transitions must be validated and audited. Suspension, pausing, and archival have different meanings and must not be conflated.

20.22 Activation
Activation requires a readiness evaluation at the intended scope and records:
- actor
- product version
- entitlement version
- effective configuration snapshot
- required connection references
- approval reference
- activation time
- initial sync or workflow action

Activation failures leave the product in a non-active state with actionable findings.

20.23 Suspension and Pausing
Pause temporarily stops selected workflows while preserving entitlement and configuration.
Suspension blocks product operation because of commercial, security, compliance, or administrative policy.

Suspension must define:
- Trigger
- Scope
- Existing queued-work handling
- In-progress-work handling
- User visibility
- Data access behavior
- Recovery requirements

Neither state permits destructive data deletion by default.

20.24 Feature Flags
Feature flags control controlled rollout, testing, and emergency disabling. Each flag requires:
- owner
- purpose
- allowed environments
- targeting rules
- default state
- expiration or review date
- risk classification
- audit behavior
- removal plan

Feature flags cannot bypass authorization, tenant isolation, approval, or contractual entitlement.

20.25 Runtime Controls
Runtime controls are operational commands with immediate behavioral effect, such as:
- Pause a workflow type
- Disable outbound communication
- Disable provider writes
- Disable an AI task
- Disable a connector capability
- Put a product in read-only mode
- Block a tenant from a damaged integration
- Activate platform maintenance mode

Runtime controls are separately permissioned, time-bounded where possible, prominently visible, and audited. Permanent policy changes must be migrated into normal configuration.

20.26 Policy Registry
The platform should maintain registries for:
- Approval policies
- Notification policies
- Communication policies
- Data-retention policies
- AI routing and data-use policies
- Security policies
- Retry policies
- Publication policies
- Escalation policies

Policies are versioned assets with explicit scope and owners.

20.27 Approval-Policy Administration
Approval policies define:
- Action type
- Risk class
- Required approver role
- Number of approvals
- Self-approval allowance
- Expiration
- Material-edit invalidation
- Emergency override behavior
- Scope

Changes that weaken approval requirements require elevated authorization and may require dual approval.

20.28 Notification-Policy Administration
Notification administration defines event subscriptions, recipients, channels, urgency, quiet hours, digest behavior, escalation, and mandatory delivery.
Mandatory security, billing, consent, and critical operational notifications cannot be suppressed by ordinary user preferences.

20.29 Integration Administration
Authorized administrators may:
- Create or reconnect a connection
- Inspect granted scopes
- Discover provider accounts and resources
- Confirm mappings
- Set synchronization policy
- Review capability availability
- Pause reads or writes
- Revoke a connection
- Start reconciliation

Credentials and tokens remain hidden. Administrative interfaces display metadata and health, not secret values.

20.30 User and Membership Administration
Administrative capabilities include:
- Invite user
- Resend or revoke invitation
- Assign membership
- Assign scoped roles
- Add explicit permission restrictions
- Deactivate user
- Revoke sessions
- Require MFA where policy permits
- Transfer organization ownership under controlled procedure

Every change is scope-validated and audited.

20.31 Support Access
Support access must use an explicit support session rather than shared credentials or hidden impersonation.
A support session records:
- support operator
- customer scope
- reason
- ticket or incident reference
- approved capabilities
- start and expiration
- actions taken

The client-facing interface should visibly indicate an active support session when appropriate. Support sessions may not expose secrets or bypass action approvals.

20.32 Platform Impersonation Guardrail
The platform should prefer “view as” and delegated support sessions over true identity impersonation.
When identity assumption is technically required, the system must preserve the original actor, assumed identity, reason, time limit, and complete audit chain. The assumed session cannot alter audit records or its own authorization.

20.33 Onboarding Administration
Onboarding is a resumable checklist composed of reusable steps:
- Organization profile
- Locations
- Users
- Product selection
- Entitlements
- Integrations
- Resource mappings
- Business facts
- Product configuration
- Approval policy
- Notification policy
- Readiness check
- Initial synchronization
- Acceptance verification

Each step has owner, status, blocking effect, evidence, and remediation guidance.

20.34 Offboarding Administration
Offboarding must define:
- Product deactivation
- Workflow cancellation
- External write suspension
- Credential revocation
- Data export
- Retention or deletion policy
- User access removal
- Billing transition
- Historical report preservation
- Final audit record

Offboarding must not delete records merely because a subscription ends.

20.35 Administrative Search and Audit
Authorized operators must be able to find administrative changes by:
- Actor
- Organization
- Location
- Product
- Configuration key
- Policy
- Time range
- Approval state
- Change reason
- Incident or support reference

Search results must respect scope and sensitivity restrictions.

20.36 Bulk Administration
Bulk changes may be supported for agency templates and platform operations, but require:
- Explicit target set
- Dry-run preview
- Per-target validation
- Idempotency
- Partial-failure reporting
- Approval where required
- Per-target audit records
- Safe retry behavior

A bulk operation must not become an unscoped cross-tenant write.

20.37 Administrative APIs
Administrative APIs use the standard service and API architecture. They require:
- Explicit permission
- Tenant or platform scope
- Idempotency for state-changing requests where applicable
- Optimistic concurrency or current-version checks
- Standard error contracts
- Audit linkage
- Rate limits

Administrative actions must not be implemented as direct database edits in normal operations.

20.38 Concurrency and Conflict Handling
Material administrative updates should use version checks. If the current resource changed after the administrator loaded it, the update must fail with a conflict response or require explicit reconciliation.
Last-write-wins is not acceptable for security, entitlement, business-fact, integration-mapping, or approval-policy changes.

20.39 Administrative Diagnostics
Diagnostics should explain:
- Current effective configuration
- Product readiness
- Blocking controls
- Integration health
- Last successful workflow or sync
- Recent failures
- Pending approvals
- Data freshness
- Recommended remediation

Raw logs and provider payloads remain restricted to authorized technical roles.

20.40 Administrative Data Visibility
The interface distinguishes:
- Client-visible configuration
- Agency-internal configuration
- Platform-internal configuration
- Sensitive operational metadata
- Secret material

Visibility is enforced by backend authorization and serialization, not frontend hiding.

20.41 Configuration Export and Import
Configuration exports may support migration, review, and disaster recovery. Exports must:
- Be scoped
- Exclude secrets
- Include schema versions
- Include dependency references
- Identify non-portable provider resources
- Be signed or integrity-checked for controlled imports

Imports run validation and dry-run analysis before activation.

20.42 Administrative Events
Material administration emits versioned events such as:
- organization.updated
- location.updated
- membership.changed
- entitlement.changed
- product.activated
- product.paused
- product.suspended
- configuration.activated
- policy.activated
- runtime_control.activated
- integration.mapping_changed
- support_session.started

Events contain identifiers and references, not unrestricted sensitive payloads.

20.43 Failure Handling
Administrative failure must preserve the previous valid state. Partial changes require transaction boundaries or compensating workflow.
The platform must distinguish:
- Validation failure
- Authorization failure
- Approval failure
- Concurrency conflict
- Provider failure
- Activation failure
- Partial bulk failure
- Irreversible external-effect failure

20.44 Initial Administrative Scope
The initial production scope must include:
- Organizations and locations
- Membership and role administration
- Product registry and entitlements
- Product readiness and lifecycle controls
- Configuration registry and effective-value resolution
- Business facts
- Integration connection and mapping administration
- Approval and notification policies
- Feature flags and runtime controls
- Onboarding and offboarding checklists
- Support-session audit

Advanced bulk templating and partner administration may follow after the core controls are proven.

20.45 Administrative Acceptance Requirements
Platform administration is not production-ready until:
- Every state-changing action is authorized and audited.
- Effective configuration can be resolved and explained.
- Approved versions are immutable.
- Invalid configuration cannot activate.
- Product activation requires readiness.
- Feature flags cannot bypass security or entitlements.
- Support access is time-bounded and attributable.
- Secrets never appear in administrative payloads.
- Concurrent changes are detected.
- Rollback or compensating action is documented for material changes.
- Onboarding and offboarding are resumable and auditable.
- Tenant-isolation tests cover administrative APIs.

20.46 Guardrails
The following are prohibited:
1. Hidden production configuration known only to one operator.
2. Direct database edits as a routine administrative interface.
3. Editable approved configuration history.
4. Product activation based only on a boolean flag.
5. Feature flags that grant permission or entitlement.
6. Client administrators modifying platform security baselines.
7. Support access through shared customer credentials.
8. Bulk changes without target preview and per-target audit.
9. Secret values returned to frontend clients.
10. Silent fallback to an inherited value after an invalid override.
11. Lower-scope policy weakening mandatory controls.
12. Unbounded permanent emergency controls.

20.47 Section Decisions
This section establishes that administration is a permissioned, versioned, auditable platform capability; configuration is schema-governed and explainable; effective values follow an explicit hierarchy; product entitlement, readiness, and activation are separate; business facts are authoritative structured records; policies, flags, and runtime controls have distinct purposes; support access is explicit and time-bounded; and no administrative interface may bypass product, workflow, security, integration, or tenant boundaries.

---

Section 21 — Observability, Monitoring & Platform Operations

21.1 Purpose and Authority Boundary
This section defines runtime observability and operational response. Section 10 remains authoritative for infrastructure topology. Section 23 is authoritative for environments and release execution. This section is authoritative for logs, metrics, traces, health, alerts, incidents, operational dashboards, service objectives, emergency controls, replay, and runbooks.

21.2 Operational Objectives
The platform must allow an authorized operator to determine:
- What failed
- When it failed
- Which tenant, location, product, workflow, integration, or provider is affected
- Whether data or external state may be inconsistent
- Whether the failure is ongoing
- What automatic recovery occurred
- What manual action is safe
- Whether users should be notified

21.3 Observability Standards
All production services must emit structured machine-readable telemetry. Telemetry must be correlated across HTTP requests, workflows, jobs, provider calls, AI calls, and outbound actions. Sensitive data must be redacted before emission.

21.4 Structured Logging
Required fields should include:
- timestamp
- severity
- environment
- service
- deployment_version
- event_name
- message
- correlation_id
- trace_id
- request_id or execution_id
- organization_id and location_id when authorized
- product
- actor_type and actor_id reference
- outcome
- duration_ms where applicable
- normalized_error_code

Logs must not contain secrets, full tokens, passwords, unrestricted personal data, or raw AI prompts by default.

21.5 Log Levels
Use DEBUG for controlled diagnostics outside ordinary production retention, INFO for meaningful lifecycle events, WARN for recoverable abnormal conditions, ERROR for failed operations requiring investigation, and CRITICAL for platform-wide or security-sensitive failures. Logging normal validation errors as ERROR should be avoided unless they indicate system malfunction.

21.6 Correlation and Causation
A correlation identifier begins at the external request, scheduler event, webhook, or operator action and propagates through all downstream work. Workflow, step, job, outbound action, AI execution, and provider-request identifiers remain distinct but linked.

21.7 Distributed Tracing
Tracing should cover:
- API ingress
- Service-layer operations
- Database queries above threshold
- Queue dispatch and consumption
- Workflow steps
- Connector calls
- AI gateway calls
- External publication and verification

Trace sampling may be adjusted by environment and risk, but error traces and critical workflow traces should be retained at higher rates.

21.8 Metrics Model
Metrics must be low-cardinality and definition-controlled. Tenant identifiers should not be used as unrestricted metric labels. Tenant-level diagnosis should rely on logs, traces, and operational records where necessary.

21.9 Core Platform Metrics
Core metrics include:
- Request rate, error rate, and latency
- Authentication failures
- Authorization denials
- Database connection usage and latency
- Queue depth and age
- Worker availability and throughput
- Scheduler lag
- Workflow success and failure
- Notification delivery
- Integration synchronization freshness
- Outbound-action verification
- AI success, validation, latency, and cost
- Data freshness and report generation

21.10 API Monitoring
API dashboards must show p50, p95, and p99 latency; status-code distribution; error categories; request volume; rate limiting; dependency latency; and endpoint availability. High-volume client validation errors must be separated from platform faults.

21.11 Worker Monitoring
Worker monitoring includes:
- Active workers
- Heartbeat age
- Jobs started, completed, failed, retried, and canceled
- Throughput by queue and job type
- Job duration
- Memory and CPU saturation
- Stuck-job count
- Deployment-version distribution

A worker that stops heartbeating must become unhealthy and stop receiving work.

21.12 Queue Monitoring
Every queue must expose:
- Current depth
- Oldest message age
- Enqueue rate
- Dequeue rate
- Retry volume
- Dead-letter volume
- Processing latency
- Capacity

Alerts should prioritize age and business impact rather than depth alone.

21.13 Scheduler Monitoring
The scheduler records planned time, dispatch time, actual start time, completion, and outcome. Monitoring identifies missed schedules, duplicate dispatch, excessive lag, and schedules disabled by runtime control.

21.14 Workflow Monitoring
Workflow monitoring exposes state, current step, attempt, wait reason, approval dependency, timeout, last progress time, and recovery options. A workflow with no progress beyond its expected interval must be detected as stalled.

21.15 Integration Monitoring
Integration monitoring covers global provider health and connection-specific health. It includes authentication expiration, token refresh failure, capability changes, webhook delivery failure, synchronization freshness, rate-limit pressure, write-verification failure, reconciliation backlog, and circuit-breaker state.

21.16 AI Monitoring
AI monitoring includes task volume, provider and model usage, schema validity, policy failures, fallback rate, refusal rate, latency, token usage, cost, approval rate, edit rate, and detected quality regression. Raw customer content must not be exposed in general operational dashboards.

21.17 Database Monitoring
Database monitoring includes connection saturation, transaction failures, deadlocks, slow queries, replication or backup status where applicable, storage growth, index health, migration state, and query latency. Query text containing sensitive values must be sanitized.

21.18 Frontend Monitoring
Frontend monitoring may include page-load performance, route failure, JavaScript errors, API failure correlation, and core workflow completion. Client-side analytics must avoid sensitive content and respect privacy configuration.

21.19 Health Endpoints
Services expose:
- Liveness: process is running.
- Readiness: service can safely receive work.
- Dependency status: authorized diagnostic view of required dependencies.
- Version: deployed build identity.

Public health endpoints return minimal information. Detailed dependency diagnostics require authorization.

21.20 Readiness Rules
A service is not ready when it cannot safely perform its core responsibility. Examples include unavailable required database connection, unapplied blocking migration, missing critical secret reference, or inability to dispatch required jobs. Optional provider degradation should not make unrelated platform services unready.

21.21 Synthetic Monitoring
Production should use synthetic checks for critical user journeys such as authentication, loading an authorized organization, viewing an approval queue, API health, worker dispatch, and a non-destructive integration read. Synthetic accounts must be isolated and clearly identified.

21.22 Alert Design
Every alert must define:
- Signal
- Threshold or condition
- Severity
- Required response time
- Owner
- Runbook
- Deduplication and suppression behavior
- Resolution signal

Alerts that do not lead to an action should be removed or converted to dashboards.

21.23 Severity Levels
Recommended incident severities:
- SEV-1: broad production outage, confirmed cross-tenant exposure, destructive data loss, or uncontrolled external action.
- SEV-2: major product or provider capability unavailable for multiple tenants, significant backlog, or serious security event without confirmed broad exposure.
- SEV-3: limited tenant or product degradation requiring prompt repair.
- SEV-4: minor defect, warning, or operational maintenance item.

21.24 Incident Lifecycle
The incident lifecycle is:
Detected → Acknowledged → Scoped → Mitigated → Recovered → Verified → Closed → Reviewed

Incident records include commander, affected scope, timeline, decisions, customer communication, mitigation, recovery evidence, and follow-up actions.

21.25 Incident Command
SEV-1 and SEV-2 incidents require an incident commander. The commander coordinates response, assigns technical owners, controls communications, and prevents conflicting changes. The commander need not be the person implementing the fix.

21.26 Customer Communication
Communication is based on impact, not merely internal severity. It should state known impact, affected timeframe, current status, workarounds, and next update without speculation. Security incidents follow the security response policy.

21.27 Operational Dashboards
Required dashboard groups include:
- Platform overview
- API and frontend
- Database
- Workers and queues
- Scheduler and workflows
- Integrations and providers
- AI usage and quality
- Notifications
- Data freshness and reporting
- Per-organization operational diagnostics

21.28 Service-Level Indicators
SLIs should measure availability, successful request rate, workflow completion, queue delay, data freshness, provider-write verification, notification delivery, and recovery performance.

21.29 Service-Level Objectives
Initial production objectives are defined in Section 26. SLO measurement must exclude documented maintenance only when maintenance was scheduled, communicated, and executed according to policy. Provider-caused failures may be reported separately but remain visible in customer impact.

21.30 Error Budgets
Error budgets guide release and reliability decisions. Exhaustion of a critical SLO error budget triggers review and may pause non-essential feature rollout until reliability returns to acceptable levels.

21.31 Dead-Letter Queues
A dead-letter record preserves original job reference, payload reference, failure category, attempts, first and last failure, tenant scope, and replay eligibility. Sensitive payloads remain in protected storage and are referenced rather than copied into dashboards.

21.32 Job Replay
Replay requires:
- Permission
- Current-state validation
- Idempotency assessment
- Original and new execution linkage
- Dry-run where available
- Approval for external side effects
- Audit

Jobs with ambiguous external outcomes cannot be replayed blindly; they require reconciliation.

21.33 Stuck-Work Recovery
Operators may cancel, resume, replay, or compensate stalled work only through supported operations. Directly editing workflow state in the database is prohibited except under an emergency runbook with explicit audit.

21.34 Maintenance Mode
Maintenance mode may be platform-wide or scoped by product, tenant, integration, or write capability. It defines allowed reads, blocked writes, queued-work behavior, user messaging, activation authority, start and expiration, and recovery validation.

21.35 Emergency Controls
Emergency controls include provider-write disablement, outbound-message suppression, AI-task disablement, queue pause, scheduler pause, read-only product mode, tenant isolation, and credential revocation. They must fail safe, be separately permissioned, expire or require review, and emit critical audit events.

21.36 Operational Runbooks
Runbooks are required for:
- Database unavailable
- Queue backlog
- Worker failure
- Scheduler failure
- Provider outage
- OAuth/token failure
- Webhook replay or signature failure
- Outbound write ambiguity
- AI provider outage or quality regression
- Notification failure
- Deployment rollback
- Backup restore
- Suspected cross-tenant exposure
- Data corruption

Each runbook includes detection, safety checks, diagnosis, mitigation, recovery, verification, communication, and escalation.

21.37 On-Call Ownership
Every critical service and alert has an owner. Ownership includes dashboard maintenance, runbook maintenance, SLO review, and post-incident action follow-through. The initial team may use a simplified rotation, but ownership cannot be undefined.

21.38 Capacity Management
Capacity reviews consider API traffic, database storage and connections, queue throughput, worker concurrency, provider limits, AI budget, and report workload. Scaling decisions use measured utilization and forecasted demand rather than premature complexity.

21.39 Cost Monitoring
Operational cost monitoring covers infrastructure, storage, email/SMS, external APIs, AI usage, and provider overages. Alerts identify abnormal changes by service, product, and tenant where attribution is available.

21.40 Security Monitoring
Security-relevant telemetry includes repeated authentication failure, unusual privilege changes, secret-access anomalies, unexpected support sessions, cross-tenant denial spikes, webhook signature failures, and restricted-data policy violations. Security monitoring follows Section 9 and may use separate restricted retention.

21.41 Audit Versus Logs
Audit records are durable business and security evidence. Logs are operational telemetry. Logs may expire or be sampled; required audit history must not depend on log retention.

21.42 Telemetry Retention
Retention varies by telemetry class and environment. Minimums and deletion rules are defined under Section 24. Production error and incident telemetry must remain available long enough for investigation while avoiding unnecessary retention of sensitive content.

21.43 Operational Acceptance Requirements
The platform is not operationally ready until:
- Critical requests and background work are correlated.
- Services expose liveness and readiness.
- APIs, workers, queues, scheduler, workflows, database, integrations, AI, and notifications are monitored.
- Critical alerts have owners and runbooks.
- Dead-letter work can be inspected and safely replayed.
- Maintenance and emergency controls are tested.
- Incident severity and lifecycle are documented.
- SLOs are measurable.
- Operators can identify affected tenant and external side effects.
- Telemetry redaction is validated.

21.44 Section Decisions
Observability is built into every service; logs, metrics, traces, audit, and product records have distinct purposes; correlation spans synchronous and asynchronous execution; alerts must be actionable; replay requires current-state and idempotency checks; provider degradation is isolated where possible; incidents follow a defined lifecycle; emergency controls are explicit and audited; and production operation requires measurable SLOs and tested runbooks.

---

Section 22 — Testing & Quality Assurance

22.1 Purpose
This section defines the platform-wide quality strategy, required test layers, environments, data controls, coverage expectations, release gates, and evidence required to claim that a subsystem or release is complete.

22.2 Quality Principles
1. Tests verify behavior and boundaries, not implementation trivia.
2. Critical security and tenant rules require direct negative tests.
3. Every defect should produce a regression test when practical.
4. Provider integrations require contract tests and controlled fixtures.
5. AI output quality requires evaluation, not only schema tests.
6. A passing happy path is insufficient.
7. Test environments must not rely on production credentials or unrestricted production data.
8. Flaky tests are defects.
9. Migrations and rollback behavior are part of quality.
10. Release evidence must be reproducible.

22.3 Test Pyramid
The platform uses:
- Unit tests for domain rules and pure logic
- Component and service tests for module behavior
- Database integration tests for persistence and constraints
- API tests for contracts and authorization
- Workflow and worker tests for durable execution
- Connector contract tests for external systems
- UI component and accessibility tests
- End-to-end tests for critical journeys
- Load, resilience, security, and recovery tests for production readiness

22.4 Unit Tests
Unit tests cover configuration resolution, state transitions, scoring, classification rules, validation, idempotency-key generation, permission decisions, retry classification, metric calculations, and other deterministic logic. External calls are excluded through defined interfaces.

22.5 Database Tests
Database tests verify:
- Constraints
- Foreign keys
- Tenant scoping
- Unique rules
- Index-dependent query behavior where critical
- Transaction boundaries
- Concurrency behavior
- Soft-delete and archival semantics
- Effective-date overlap prevention
- Audit immutability

22.6 Migration Tests
Every migration must be tested from the prior supported schema. Tests include upgrade, startup compatibility, data preservation, backfill behavior, lock and duration risk, and rollback or forward-fix procedure. Destructive migrations require explicit approval and verified backup.

22.7 API Contract Tests
API tests verify request and response schemas, status codes, standard errors, pagination, filtering, idempotency, concurrency conflicts, authorization, rate limits, and redaction. Published API changes require compatibility review.

22.8 Authentication and Authorization Tests
Required cases include unauthenticated access, expired session, revoked session, inactive membership, insufficient permission, wrong scope, explicit deny, sensitive-action permission, and support-session restriction.

22.9 Tenant-Isolation Test Suite
Every tenant-scoped repository, service, API, workflow, export, search, notification, integration, AI context builder, and report must have cross-tenant negative tests. These tests attempt access using valid identities from the wrong organization and location.

22.10 Workflow Tests
Workflow tests cover success, retryable failure, non-retryable failure, timeout, cancellation, approval pause, approval rejection, manual resume, duplicate dispatch, worker crash, idempotent replay, dead-letter movement, and compensation.

22.11 Scheduler Tests
Scheduler tests verify timezone behavior, daylight-saving transitions, missed-run handling, duplicate prevention, disabled schedules, catch-up rules, and clock-boundary conditions.

22.12 Connector Contract Tests
Every connector must pass a shared suite for authentication handling, capability discovery, resource mapping, pagination, cursor behavior, rate limits, normalized errors, webhook validation, idempotency, outbound verification, and redaction. Provider-specific fixtures are versioned.

22.13 Webhook Tests
Webhook tests include valid signature, invalid signature, expired timestamp, replay, duplicate delivery, out-of-order events, malformed payload, unknown resource, mapped resource, unavailable worker, and eventual durable processing.

22.14 AI Task Tests
Each production AI task requires:
- Input-schema tests
- Output-schema tests
- Prompt-version resolution tests
- Routing-policy tests
- Provider-exclusion tests
- Cost and latency-limit tests
- Validation and fallback tests
- Tenant-context isolation tests
- Sensitive-data exclusion tests
- Manual-path tests

22.15 AI Evaluation
Important tasks use versioned evaluation datasets and rubrics. Metrics may include schema validity, factual support, policy compliance, approval rate, edit distance, task-specific correctness, latency, and cost. Model or prompt promotion requires comparison against the current approved baseline.

22.16 UI Component Tests
UI tests cover rendering, state transitions, form validation, permission-based control visibility, keyboard operation, focus management, errors, loading, empty states, degraded states, and destructive-action confirmation.

22.17 Accessibility Tests
Automated accessibility checks are required in CI for core components and pages. Manual testing covers keyboard-only operation, screen-reader interpretation of critical workflows, focus order, dialogs, status messages, data tables, and color-independent meaning.

22.18 End-to-End Tests
Critical journeys include:
- Sign in and authorized organization access
- User invitation and role assignment
- Product configuration and readiness
- Integration connection and mapping
- Workflow approval and external verification
- Review ingestion and response publication
- Content approval and controlled publication
- Lead intake, consent, response, and suppression
- Report generation and delivery
- Product pause, recovery, and audit inspection

22.19 Browser and Device Coverage
The supported browser matrix is defined in Section 26. End-to-end tests cover the supported desktop browsers and essential mobile workflows. Unsupported browser behavior should fail gracefully where possible.

22.20 Performance Tests
Performance tests cover representative API requests, list and search endpoints, dashboard aggregation, queue throughput, large sync batches, report generation, and concurrent workflow execution. Tests use realistic data volumes and measure p50, p95, p99, resource use, and error rate.

22.21 Load and Stress Tests
Load tests validate expected and peak traffic. Stress tests identify degradation and recovery beyond planned capacity. The objective is not merely maximum throughput but predictable failure without data corruption or cross-tenant leakage.

22.22 Resilience and Failure Injection
Controlled tests simulate provider outage, timeout, rate limiting, database connection loss, worker termination, queue delay, duplicate webhook, AI failure, email failure, partial deployment, and stale configuration. Critical workflows must recover according to policy.

22.23 Security Testing
Security testing includes dependency scanning, secret scanning, static analysis, authentication and authorization tests, input validation, injection testing, SSRF controls, file-upload controls, webhook verification, session security, and targeted penetration testing before initial launch and major architectural changes.

22.24 Privacy Testing
Privacy tests verify export scope, deletion policy, retention enforcement, redaction, AI context minimization, analytics exclusion, and prevention of sensitive data in logs and frontend responses.

22.25 Backup and Recovery Testing
Backup restoration must be tested into an isolated environment. Tests verify integrity, application compatibility, recovery-point measurement, required secrets and configuration restoration, and post-restore workflow safety.

22.26 Test Data
Test data must be synthetic or approved and de-identified. It must represent multiple industries, organizations, locations, roles, product states, risk levels, provider conditions, and data sizes. Production credentials are prohibited.

22.27 Fixtures and Factories
Factories should generate valid default entities while allowing explicit edge cases. Shared fixtures must not conceal required fields or tenant scope. Provider fixtures are versioned and identify the source API version.

22.28 Mocks and Stubs
Mocks are used at true external boundaries, not to avoid testing platform integrations. Contract tests validate that mocks remain aligned with real provider behavior. Over-mocking core repositories or authorization is prohibited.

22.29 Test Isolation
Tests must be deterministic, order-independent, and isolated by transaction, schema, database, or environment as appropriate. Parallel tests must not share mutable tenant state.

22.30 Flaky-Test Policy
A flaky test is quarantined only with an owner, issue, reason, and expiration. Critical security, tenant, migration, and release-smoke tests cannot be ignored. Repeated reruns to obtain a pass do not constitute success.

22.31 Coverage Requirements
Coverage is a risk signal, not the sole quality measure. Initial minimums:
- 80% line coverage for core backend domain and service modules
- 90% branch coverage for authorization, tenant scoping, entitlement, approval, consent, idempotency, and state-transition modules
- 100% of defined critical acceptance scenarios represented by tests

Generated code, migrations, and trivial adapters may be treated separately when documented.

22.32 Defect Severity
Defects are classified by production impact. Release-blocking defects include cross-tenant access, secret exposure, unauthorized external action, data corruption, broken migration, inability to restore, broken critical workflow, and unmitigated high-severity security findings.

22.33 Quality Gates
Required pull-request gates include formatting, linting, type checking, unit tests, affected integration tests, migration validation when applicable, secret scanning, dependency checks, and build validation. Main-branch and release gates add end-to-end, staging smoke, security, and deployment checks.

22.34 Test Evidence
A release record should include commit, build artifact, migration set, environment, test suites, results, known exclusions, approved waivers, performance results where required, and approver.

22.35 Waivers
A failed mandatory gate may be waived only by an authorized owner with documented risk, mitigation, expiration, and follow-up. Tenant isolation, active secret exposure, destructive data-loss risk, and untested production migration cannot be waived for normal launch.

22.36 Quality Ownership
Engineers own tests for their changes. Product owners define acceptance scenarios. Security owns security requirements. Operations owns recovery and runbook validation. Quality responsibility is shared and cannot be delegated to one final testing phase.

22.37 Acceptance Requirements
Testing is production-ready when:
- Required suites run in CI.
- Critical domains meet coverage targets.
- Tenant and authorization negative tests pass.
- Migrations are tested.
- Connectors pass contract tests.
- AI tasks pass evaluation thresholds.
- Critical end-to-end journeys pass in staging.
- Accessibility checks pass.
- Backup restoration is demonstrated.
- No release-blocking defect remains unresolved.

22.38 Section Decisions
Quality is continuous; negative boundary tests are mandatory; tenant isolation, permissions, consent, approvals, and idempotency receive elevated coverage; provider connectors use shared contract tests; AI changes require regression evaluation; migrations and recovery are testable deliverables; and completion claims require reproducible evidence rather than informal inspection.

---

Section 23 — Deployment, Release Management & Environments

23.1 Purpose and Boundary
This section operationalizes deployment and release governance. Section 10 defines the selected topology and infrastructure responsibilities. This section defines how code, configuration, migrations, workers, and frontend assets move through environments and become an approved release.

23.2 Environment Model
Required environments are local, test/CI, staging, and production. Preview environments may be used for frontend or isolated review. Environment data, credentials, provider resources, webhooks, storage, queues, and domains must be separated.

23.3 Local Development
Local development must support documented startup, migrations, seed data, tests, worker and scheduler execution, provider stubs, and environment validation. A new engineer should not require undocumented machine-specific setup.

23.4 CI Environment
CI uses ephemeral infrastructure where practical, test-only credentials, deterministic dependencies, and isolated databases. CI must not call production providers or use production secrets.

23.5 Staging
Staging mirrors production architecture closely enough to validate migrations, deployments, workers, scheduler, integrations, monitoring, and end-to-end flows. Provider sandbox accounts or isolated test resources are required where supported.

23.6 Production
Production uses approved artifacts, production-only secrets, restricted administrative access, active monitoring, backups, and release records. Direct ad hoc code changes on production hosts are prohibited.

23.7 Environment Configuration
Environment variables and secret references are validated at startup. Configuration definitions identify required, optional, sensitive, environment-specific, and deprecated values. Missing critical configuration prevents readiness.

23.8 Secret Handling
Secrets are stored in approved secret managers or protected platform facilities, never committed to repositories, build logs, frontend bundles, or AI context. Rotation and revocation procedures are documented.

23.9 Source Control
Main is protected. Changes use reviewed pull requests except documented emergency procedure. Required checks, reviewer rules, branch freshness, and signed or attributable commits should be configured according to repository capability.

23.10 Build Artifacts
Deployments use immutable, versioned artifacts identified by commit SHA and build metadata. The same tested artifact should be promoted between compatible environments rather than rebuilt differently without traceability.

23.11 Continuous Integration
CI performs dependency installation with lockfile enforcement, formatting, linting, type checking, unit tests, integration tests, migration checks, security scanning, and builds. Changes trigger only relevant extended suites where safe, while release branches run the complete required set.

23.12 Release Types
Release types include standard, configuration-only, migration, high-risk, dependency/security, and emergency. Each type has defined approvals and verification depth.

23.13 Release Record
Every production release records:
- release_id and version
- commit and artifact identifiers
- included changes
- schema migration identifiers
- configuration changes
- feature flags
- risk classification
- approvals
- deployment timeline
- validation results
- rollback plan
- incidents or deviations

23.14 Deployment Order
The default safe order is:
1. Pre-deployment checks
2. Backward-compatible schema expansion
3. Backend and worker artifact deployment
4. Readiness verification
5. Frontend deployment
6. Controlled feature activation
7. Smoke tests
8. Monitoring observation
9. Release completion

The exact order may differ when compatibility analysis requires it.

23.15 Database Migration Deployment
Migrations are reviewed for compatibility, lock risk, duration, data preservation, and rollback. Expand-and-contract is preferred. Long backfills run as observable jobs rather than blocking migrations.

23.16 Worker Deployment
Workers drain or stop accepting new work before termination when required. Job payloads and workflow definitions must remain compatible during rolling deployment. In-flight work records the worker version.

23.17 Scheduler Deployment
Only the elected active scheduler dispatches production schedules. Deployment prevents duplicate leaders and validates schedule state after restart.

23.18 Frontend Deployment
Frontend deployment validates build output, environment references, API compatibility, route health, authentication, and critical workflows. Preview environments must not receive production secrets.

23.19 Backend Deployment
Backend deployment validates migrations, health, readiness, dependency access, version endpoint, and standard smoke requests. A process that starts but is not safe to serve remains unready.

23.20 Feature Rollout
Features may progress through disabled, internal, selected tenants, percentage or cohort rollout, and general availability. Targeting must be deterministic, auditable, and independent of authorization.

23.21 Configuration Release
Configuration changes use the versioned administration system. High-impact production configuration receives validation, preview, approval, and rollback planning comparable to code changes.

23.22 Rollback
Rollback may include artifact rollback, feature disablement, configuration supersession, queue pause, or compensating migration. Database rollback is not assumed safe. Every high-risk release states the supported recovery path before deployment.

23.23 Hotfixes
Hotfixes minimize scope, retain review and audit, run mandatory targeted tests, and are followed by full reconciliation into normal history. Emergency urgency does not permit hidden changes or skipped tenant/security checks.

23.24 Release Approval
Production approval considers test evidence, migration risk, security findings, operational readiness, monitoring, support coverage, and rollback. The author should not be the sole approver of a high-risk release.

23.25 Change Freeze
A temporary freeze may apply during incidents, high-risk business periods, or error-budget exhaustion. Security repairs and incident mitigation follow controlled exceptions.

23.26 Deployment Verification
Verification includes version identity, liveness, readiness, database schema state, worker heartbeats, scheduler leadership, queue processing, critical API smoke tests, frontend route checks, integration read checks, and telemetry arrival.

23.27 Post-Deployment Observation
High-risk releases have a defined observation window with owners and success indicators. A release is not complete merely when the deployment command succeeds.

23.28 Failed Deployment
A failed deployment triggers halt, scope assessment, rollback or mitigation, incident handling where warranted, and release-record update. Repeated blind redeployment is prohibited.

23.29 Dependency Updates
Dependencies are pinned through lockfiles. Automated updates still require tests. Major framework, authentication, database, or provider-SDK changes require compatibility review and staged rollout.

23.30 Versioning
Application releases use a consistent versioning strategy and always retain commit identity. APIs, events, connectors, workflow definitions, configuration schemas, and AI prompts use their own compatibility-aware versions.

23.31 Release Documentation
Release notes distinguish user-visible changes, operational changes, migrations, deprecations, known limitations, and required administrator actions.

23.32 Environment Promotion
Promotion requires passing the gates for the target environment. Staging approval does not automatically authorize production when production-specific risk differs.

23.33 Production Access
Production shell, database, secret, and deployment access are least-privilege, MFA-protected where supported, attributable, and reviewed. Routine application operations use administrative tools instead of shell access.

23.34 Drift Detection
The platform should detect drift among source-controlled configuration, deployed artifacts, schema versions, scheduler definitions, and approved environment configuration. Undocumented drift is treated as an operational defect.

23.35 Initial Release Pipeline
The initial pipeline may remain pragmatic: GitHub, automated CI, Vercel frontend deployment, controlled Hetzner backend/worker deployment, Supabase migrations, smoke tests, and documented approval. It must preserve artifact identity, repeatability, and rollback even without complex orchestration.

23.36 Acceptance Requirements
Release management is production-ready when:
- Environments are isolated.
- Secrets are not in repositories or artifacts.
- CI gates run automatically.
- Artifacts are immutable and identifiable.
- Migrations are validated before production.
- Worker and scheduler deployment avoid duplicate or lost work.
- Feature rollout and rollback are supported.
- Production releases have approvals and records.
- Deployment verification is automated or documented and reproducible.
- Emergency releases remain attributable and reconciled.

23.37 Section Decisions
Deployments promote tested immutable artifacts; environments are isolated; production changes use controlled releases; schema changes favor expand-and-contract; workers and workflows remain version-compatible; feature flags support rollout but not permission; rollback is planned before high-risk deployment; and successful release requires post-deployment verification, not only artifact delivery.

---

Section 24 — Data Governance, Retention, Privacy & Recovery

24.1 Purpose
This section consolidates the operational governance of platform data. It complements Section 9 security and privacy controls without weakening them.

24.2 Data Ownership
Customer business data remains associated with the applicable customer organization subject to contracts and law. LILOs owns platform software, aggregate operational methods, and internal records as contractually defined. Provider-derived data remains subject to provider terms. Ownership and processing rights must be documented rather than inferred.

24.3 Data Stewardship
Every major data domain has an owner responsible for definitions, quality, access, retention, and lifecycle. Product owners steward product data; platform owners steward identity, audit, configuration, and shared registries.

24.4 Data Classification
Required classes are:
- public
- business_internal
- client_confidential
- personal_data
- restricted
- secret

Classification affects access, encryption, logging, export, AI routing, retention, and deletion.

24.5 Data Inventory
The platform maintains an inventory of major data stores, domains, purposes, owners, classifications, processors, retention policies, backup coverage, and residency.

24.6 Data Lineage
Material metrics, reports, AI analyses, and external actions should be traceable to source records, synchronization executions, transformation versions, configuration, and approval where applicable.

24.7 Source and Authority
The system distinguishes source, normalized record, authoritative record, derived record, and published artifact. Provider data is not automatically authoritative for all business facts.

24.8 Data Minimization
Collect and retain only information required for a defined product, legal, security, or operational purpose. Sensitive fields should not be copied into unrelated records, logs, notifications, analytics, or AI context.

24.9 Retention Policy Registry
Retention policies are versioned by data category, scope, legal basis or business purpose, active retention, archive period, deletion method, legal-hold behavior, and owner.

24.10 Default Retention Targets
Initial defaults, subject to contract and law:
- Security and administrative audit: 24 months minimum
- Workflow and external-action history: 24 months
- Operational logs: 30–90 days depending on severity and sensitivity
- Traces: 14–30 days with longer incident retention
- Provider raw payloads: shortest period required for diagnosis, normally 30–90 days
- AI execution metadata: 24 months; raw prompt/output content according to task sensitivity and approved purpose
- Published reports and content revisions: retained for customer history while account is active and through contracted post-termination period
- Backups: rolling policy sufficient to meet RPO and recovery requirements

Specific policies may impose longer or shorter periods.

24.11 Archiving
Archiving removes data from active operational paths while preserving authorized historical access. Archived data remains classified, encrypted, access-controlled, and subject to deletion.

24.12 Deletion
Deletion workflows identify primary records, derived records, search indexes, object storage, caches, exports, and downstream processors. Deletion must not silently break mandatory audit or legal-hold requirements.

24.13 Soft Delete Versus Erasure
Soft deletion supports application lifecycle and recovery but is not equivalent to privacy erasure. True erasure or irreversible anonymization follows the applicable policy.

24.14 Anonymization and Pseudonymization
Anonymization must be irreversible to be treated as non-personal data. Pseudonymized data remains protected. Identifiers should be replaced where analytical value can be retained without direct identity.

24.15 Data Subject and Customer Requests
Supported requests may include access, correction, export, deletion, and restriction. Requests require identity verification, scope determination, legal review where required, execution tracking, and response evidence.

24.16 Legal Hold
Legal hold prevents deletion of specified data despite ordinary retention expiry. Holds are restricted, documented, scoped, reviewed, and lifted explicitly.

24.17 Data Export
Exports are scoped, permissioned, rate-limited, audited, integrity-checked where appropriate, and delivered securely. Exports identify schema, time range, source, and omitted restricted fields.

24.18 Offboarding Data Handling
Offboarding records export availability, retention period, credential revocation, deletion schedule, legal hold, and final confirmation. Subscription termination does not immediately erase required audit or contractual records.

24.19 Raw Provider Payloads
Raw payloads may be retained for debugging, reconciliation, or evidence. They are not the canonical product model, must be encrypted and access-restricted, and must follow a short explicit retention policy.

24.20 AI Data Governance
AI requests follow task purpose, minimum context, provider restrictions, retention settings, and organization policy. Secrets and unrelated tenant data are prohibited. Training use must be disabled where required and supported. Raw prompts and outputs are retained only as needed for audit, evaluation, or product operation.

24.21 Analytics Data
Analytics events exclude secrets and unnecessary client content. User-behavior analytics use pseudonymous identifiers where practical and remain separate from business source data.

24.22 Data Quality
Data-quality dimensions include completeness, validity, uniqueness, consistency, timeliness, and authority. Quality findings must distinguish missing data from zero and delayed data from current data.

24.23 Correction and Reprocessing
Corrections preserve prior source and transformation history. Derived metrics and reports may be reprocessed, but published immutable reports retain their original data-as-of snapshot unless issued as a new revision.

24.24 Backup Scope
Backups cover the primary database, required object storage, configuration and secret references needed for restoration, workflow definitions, and other critical state. Source repositories and deployment artifacts use their own durable systems.

24.25 Backup Strategy
The production database requires automated point-in-time or frequent incremental protection plus scheduled full backups according to provider capability. Backup jobs are monitored and failures alert operators.

24.26 Backup Security
Backups are encrypted, access-restricted, environment-separated, and protected from ordinary application deletion. Backup credentials are separate from application credentials where practical.

24.27 Recovery Point Objective
Initial targets:
- Core transactional database: RPO ≤ 15 minutes
- Configuration, audit, workflow, and integration state: covered by the core database RPO
- Critical object storage: RPO ≤ 24 hours unless provider versioning offers stronger protection

Any subsystem unable to meet its target must document the gap before production approval.

24.28 Recovery Time Objective
Initial targets:
- Critical platform services: RTO ≤ 4 hours for recoverable infrastructure failure
- Core database restoration: RTO ≤ 4 hours under documented recovery scenario
- Non-critical analytics or historical recomputation: RTO ≤ 24 hours

Provider-wide regional failure may require a separately documented recovery strategy.

24.29 Restore Testing
At least quarterly, and before initial production launch, a representative backup is restored into an isolated environment. The test validates integrity, schema compatibility, application startup, critical records, and post-restore safety.

24.30 Disaster Recovery
Disaster scenarios include database loss, host loss, object-storage loss, credential compromise, corrupted deployment, provider outage, and accidental destructive action. Each scenario defines detection, decision authority, restoration sequence, communication, and validation.

24.31 Recovery Consistency
After restore, external provider state may be newer than platform state. The platform must pause unsafe writes and reconcile provider state before resuming actions that could duplicate or overwrite data.

24.32 Data Residency
Residency requirements are recorded by organization and data classification. Provider and region selection must respect documented restrictions. The initial platform should not claim residency guarantees it cannot technically enforce.

24.33 Cross-Border Processing
Where applicable, processors, locations, and contractual safeguards are documented. Product routing and AI-provider routing must honor restrictions.

24.34 Encryption
Sensitive data is encrypted in transit and at rest using platform and provider capabilities. Application-level encryption is used for secrets and especially sensitive fields where required.

24.35 Key and Credential Recovery
Recovery procedures address loss or compromise of signing keys, OAuth credentials, database credentials, and encryption keys. Rotation must avoid uncontrolled loss of decryptability.

24.36 Data Breach and Exposure
Suspected exposure follows Section 9 incident controls and Section 21 incident operations. Data lineage and audit should support identification of affected records, tenants, time range, and processors.

24.37 Acceptance Requirements
Data governance is production-ready when:
- Major data domains are inventoried and classified.
- Retention policies are registered and enforceable.
- Export and deletion are scoped and audited.
- Legal hold is supported where required.
- Raw provider and AI data have explicit retention.
- Backups are automated and monitored.
- RPO and RTO are documented and tested.
- Restore testing succeeds.
- Post-restore external-state reconciliation is documented.
- Data residency claims are accurate.

24.38 Section Decisions
Data has explicit ownership, authority, classification, purpose, lineage, and retention; deletion and archiving are distinct; raw provider and AI content receive limited controlled retention; backups are encrypted and tested; recovery targets are measurable; and restoration must account for external systems that may have advanced beyond the recovered platform state.

---

Section 25 — Extensibility, Internal SDKs & Plugin Architecture

25.1 Purpose
This section defines how new products, connectors, providers, workflows, permissions, events, notifications, configuration schemas, and other extensions are added without modifying core systems unpredictably.

25.2 Initial Scope
The initial architecture is an internal extension framework within the modular monolith and worker system. It is not a public marketplace and does not permit arbitrary third-party code execution in production.

25.3 Extension Principles
- Explicit contracts over convention alone
- Registration over hidden discovery
- Versioning over in-place behavior changes
- Least privilege
- Tenant and environment awareness
- Test harnesses
- No direct database or provider bypass
- Safe deprecation

25.4 Extension Manifest
Every extension includes a manifest with identifier, type, owner, version, platform compatibility, capabilities, required permissions, configuration schema, events, dependencies, migrations, health checks, documentation, and lifecycle state.

25.5 Extension Types
Supported internal extension types include:
- Product module
- Connector
- AI provider adapter
- AI task
- Workflow definition package
- Event consumer
- Notification channel or template package
- Report or metric provider
- Configuration package
- Publication adapter

25.6 Internal SDK
The internal SDK provides typed contracts and utilities for tenant context, authorization, audit, events, workflows, configuration, secrets references, connector execution, AI tasks, notifications, errors, idempotency, and observability.

25.7 SDK Boundary
The SDK exposes supported abstractions, not unrestricted access to core database tables or infrastructure clients. Extensions request platform capabilities through services.

25.8 Product Registration
A product registers metadata, states, configuration schema, readiness checks, permissions, events, workflows, navigation contributions, metrics, and administrative capabilities. Registration does not automatically enable the product.

25.9 Capability Registration
Capabilities use namespaced identifiers and versioned contracts. Capability discovery is explicit and may depend on platform version, provider account, entitlement, and environment.

25.10 Connector SDK
The connector SDK standardizes authentication, secret references, account and resource discovery, mappings, sync, cursors, webhooks, outbound actions, verification, reconciliation, error normalization, rate limits, health, and contract tests.

25.11 Workflow Registration
Workflows register definition key, version, input schema, output schema, steps, retry policy, timeout, approval points, cancellation behavior, compensation, and ownership. Existing executions remain bound to a compatible definition version.

25.12 Event Registration
Events are namespaced, versioned, schema-defined, tenant-scoped, and documented. Consumers declare supported versions and idempotency behavior.

25.13 Permission Registration
Extensions register permission keys, descriptions, scopes, sensitivity, and implied dependencies. Extensions cannot create superuser behavior or bypass the central authorization service.

25.14 AI Provider Adapter Registration
Adapters declare modalities, structured-output support, tool support, context limits, data classifications, regions, retention characteristics, pricing, health checks, and normalized error behavior.

25.15 AI Task Registration
Tasks declare business purpose, owner, input/output schemas, risk, routing policy, validators, limits, approval policy, evaluation dataset, and fallback. Informal production prompts are prohibited.

25.16 Notification Registration
Extensions register event triggers, template schemas, supported channels, mandatory status, default preferences, escalation rules, and redaction behavior.

25.17 Configuration Schema Registration
Schemas define keys, types, scopes, defaults, inheritance, override restrictions, sensitivity, validation, approval, and migration. Schema changes follow compatibility rules.

25.18 UI Extension Points
Internal modules may contribute routes, navigation, dashboards, forms, and approval views through defined interfaces. They must use the shared design system, authorization, loading/error states, and accessibility standards.

25.19 Database Extensions
New tables and migrations use shared conventions for UUIDs, timestamps, tenant keys, audit references, and indexes. Modules may not alter another module’s tables without an approved architecture change and migration ownership.

25.20 Dependency Rules
Core may not depend on product modules. Products may depend on core interfaces. Products communicate with one another through approved services, events, and workflows, not private table access.

25.21 Compatibility
Compatibility is tracked among platform version, SDK version, extension version, event schema, configuration schema, and workflow definition. Incompatible extensions fail registration or readiness rather than executing unpredictably.

25.22 Loading and Discovery
The initial build uses explicit source-controlled registration at application startup. Dynamic remote code loading is prohibited. Registration failures block the affected extension and surface diagnostics without necessarily disabling unrelated products.

25.23 Extension Lifecycle
States include development, testing, approved, active, deprecated, disabled, retired. Promotion requires tests, security review appropriate to risk, documentation, and ownership.

25.24 Extension Security
Extensions receive only necessary capabilities. They cannot access raw secrets, unrestricted tenant data, production shell, or direct provider clients outside the connector framework.

25.25 Extension Testing
Every extension supplies unit tests, platform contract tests, tenant-isolation tests, permission tests, lifecycle tests, and type-specific suites. Connectors and AI tasks use their specialized harnesses.

25.26 Extension Observability
Extensions use platform telemetry and include extension identifier and version. They cannot establish unapproved external telemetry that exports client data.

25.27 Extension Failure Isolation
An extension failure should be contained to the affected module, workflow, provider, or tenant where possible. Circuit breakers, queue isolation, and runtime controls must be available according to risk.

25.28 Partner Extensions
Future partner extensions require package signing, review, sandboxing, stricter capability grants, commercial terms, and support ownership. These controls are deferred until partner extensibility is approved.

25.29 Deprecation
Deprecation includes notice, replacement, migration path, compatibility period, telemetry on remaining use, and retirement date. Event schemas, connector versions, and configuration keys must not disappear without migration.

25.30 Acceptance Requirements
The extension framework is production-ready when:
- Registries and manifests are explicit.
- Modules use shared SDK contracts.
- Core does not depend on product internals.
- Permissions and configuration are registered.
- Compatibility is validated.
- Extensions pass shared tests.
- Dynamic arbitrary code loading is absent.
- Failures are observable and containable.
- Deprecation and migration are supported.

25.31 Section Decisions
LILOs uses an internal, typed, source-controlled extension framework; all extension types register explicit contracts; extensions consume platform services instead of direct infrastructure; compatibility and lifecycle are versioned; arbitrary third-party runtime code is excluded from the initial build; and future partner extensibility requires additional sandbox and trust controls.

---

Section 26 — Non-Functional Requirements

26.1 Purpose
This section defines measurable platform-wide performance, reliability, security, accessibility, recovery, maintainability, and cost targets. Targets apply to production unless otherwise stated and may be tightened through approved revisions.

26.2 Availability
- Core authenticated platform API monthly availability target: 99.9%.
- Client and agency web application availability target: 99.9%, excluding failure of optional third-party embeds.
- Critical background execution services availability target: 99.5%.
- Individual external provider availability is reported separately, but degraded providers must not unnecessarily disable unrelated platform functions.

26.3 API Latency
For normal non-reporting requests under expected load:
- p50 server latency ≤ 250 ms
- p95 ≤ 750 ms
- p99 ≤ 2,000 ms

Long-running analysis, synchronization, generation, publication, and export must use asynchronous workflows rather than holding HTTP requests open.

26.4 API Error Rate
Platform-caused 5xx responses should remain below 0.5% over a rolling 30-day window for core APIs, excluding verified provider failures surfaced through normalized responses.

26.5 UI Performance
For supported modern browsers on a typical broadband connection:
- Core application shell should become interactable within 3 seconds at p75.
- Primary route transition with cached shell should render meaningful content within 2 seconds at p75.
- User actions must show acknowledgment within 100 ms even when work continues asynchronously.

26.6 Worker and Queue Performance
- Critical lead and review intake jobs should begin processing within 60 seconds at p95 under expected load.
- Ordinary scheduled jobs should begin within 5 minutes of planned time at p95.
- Queue oldest-message age must remain below the applicable workflow SLO.
- Worker recovery after process failure should resume eligible work within 5 minutes.

26.7 Workflow Completion
Task-specific targets apply, but initial objectives include:
- Low-latency classifications: p95 completion ≤ 30 seconds.
- Routine draft-generation workflows: p95 ≤ 2 minutes.
- Standard provider synchronization: 95% complete within 15 minutes of schedule or event receipt, subject to provider limits.
- Large reports and content generation: explicit progress and completion target defined by workflow rather than synchronous timeout.

26.8 Data Freshness
- Webhook-supported operational data: visible within 5 minutes at p95 after valid provider delivery.
- Polling-based operational data: within the configured polling interval plus 10 minutes.
- Daily Search Console or Analytics data: marked with provider data-as-of date and refreshed within 24 hours of provider availability.
- Dashboards must display last successful sync and stale state.

26.9 Reliability
- Duplicate inbound events must not create duplicate business records or external actions.
- Eligible retries must be bounded and idempotent.
- No acknowledged durable job may be silently lost.
- External writes must be verified or enter reconciliation.
- Critical workflows require a manual completion path.

26.10 Scalability
The initial architecture must support at least:
- 500 organizations
- 2,500 locations
- 10,000 active users
- 1 million workflow/job executions per month
- 10 million normalized metric observations per month

These are design targets, not a requirement to provision full capacity before demand. Capacity testing must validate the next planned operating tier before exceeding 70% of measured safe capacity.

26.11 Tenant Isolation
Cross-tenant data access target is zero. Any confirmed cross-tenant exposure is SEV-1 and a release blocker until contained and remediated.

26.12 Security
- All production traffic uses TLS.
- Secrets are never stored plaintext in repositories or frontend bundles.
- Sensitive administrative access uses MFA where provider capability permits.
- Critical vulnerabilities with known exploitation require immediate triage and remediation target within 72 hours or compensating control.
- High-severity vulnerabilities target remediation within 14 days; medium within 60 days, subject to documented risk review.

26.13 Accessibility
Core authenticated workflows and public authentication surfaces target WCAG 2.2 AA. Critical workflows must be keyboard operable and usable with supported screen readers. Automated violations classified serious or critical block release unless formally waived with remediation date.

26.14 Browser Support
Support current and previous major versions of Chrome, Edge, Firefox, and Safari. Essential approval, notification, and lead workflows should remain usable on current iOS Safari and Android Chrome. Unsupported legacy browsers receive a clear message rather than silent malfunction.

26.15 Responsive Behavior
Agency-heavy analysis may be desktop-optimized, but mobile must support authentication, notifications, approval review, lead response, incident acknowledgment, and critical account status.

26.16 Backup Reliability
- Automated backup job success target: 99.9% monthly.
- Backup failures alert within 15 minutes of detection.
- Quarterly restore test success is mandatory.
- RPO and RTO follow Section 24.

26.17 Recovery
- Critical service RTO ≤ 4 hours.
- Core database RPO ≤ 15 minutes.
- Recovery procedures must preserve tenant scope and pause unsafe external writes until reconciliation.

26.18 Observability Coverage
100% of production services must emit structured logs, version identity, liveness, readiness, and critical error metrics. 100% of critical alerts require an owner and runbook. Critical synchronous and asynchronous paths must carry correlation identifiers.

26.19 Maintainability
- Core modules must have explicit owners and documentation.
- New behavior must not introduce circular module dependencies.
- Critical architectural decisions require ADRs.
- Unsupported duplicate implementations are prohibited.
- Deprecated contracts must have removal plans.
- A fresh development environment should be bootstrappable from documented instructions in one working day or less.

26.20 Test Quality
Critical authorization, tenant, approval, consent, and state-transition modules require 90% branch coverage. Core backend domain and service modules require 80% line coverage. All platform-wide acceptance scenarios must have recorded evidence.

26.21 Release Reliability
- Production deployment success target: ≥ 95% without emergency rollback over a rolling quarter.
- Change failure rate target: < 10% for production releases.
- Mean time to restore for SEV-1/SEV-2 platform failures target: < 4 hours.

26.22 Provider Failure Behavior
A single provider outage should degrade only dependent capabilities. The platform must continue to allow status viewing, manual work, and unrelated products where safe. Provider writes are queued or blocked according to idempotency and reconciliation policy.

26.23 AI Latency and Budget
Every AI task defines a latency and cost ceiling. Initial defaults:
- Classification tasks: p95 ≤ 15 seconds; maximum estimated execution cost $0.02 unless task policy overrides.
- Short draft tasks: p95 ≤ 45 seconds; maximum $0.10.
- Long-form or multi-document tasks: asynchronous; task-specific maximum cost and approval for estimates above $1.00.
- Monthly organization budgets and alert thresholds are configurable.

26.24 AI Quality
Production AI tasks target:
- ≥ 99% schema-valid result after allowed repair/fallback
- Zero publication of output failing mandatory policy validation
- Task-specific approval and factual-support thresholds defined before promotion
- Quality regression alerts when approved baseline degrades beyond configured tolerance

26.25 Notification Delivery
Platform email notifications target 99% accepted-by-provider rate excluding invalid recipients and recipient-provider rejection. Critical delivery failures become visible within 15 minutes. SMS targets depend on the selected provider and consent rules.

26.26 Cost Efficiency
The platform must attribute major variable costs by product and organization where feasible. Cost anomalies exceeding 25% above a trailing comparable baseline trigger review. Architecture changes that materially increase recurring cost require documented justification.

26.27 Data Integrity
Confirmed silent data corruption target is zero. Constraints, reconciliation, and verification should detect inconsistent state. Data repair must preserve evidence and audit.

26.28 Privacy
Sensitive content must not enter logs, analytics, or AI context without approved need. Privacy deletion and export requests are tracked to completion within the applicable legal or contractual period.

26.29 Supportability
Authorized operators must be able to identify product state, readiness, integration health, workflow status, data freshness, and recent failures without direct database access for ordinary incidents.

26.30 Target Review
Non-functional targets are reviewed at least quarterly and after major incidents or architecture changes. Tightening targets requires capacity and cost analysis; weakening targets requires formal approval and rationale.

26.31 Acceptance Requirements
A production release must provide measured evidence for availability instrumentation, latency, error rate, queue delay, data freshness, backup, restore, accessibility, security, test coverage, and critical workflow reliability. Unmeasured claims such as “fast” or “scalable” do not satisfy this section.

26.32 Section Decisions
The platform adopts explicit initial SLOs and capacity targets; long-running work is asynchronous; provider failures are isolated; core database recovery targets are RPO 15 minutes and RTO 4 hours; accessibility targets WCAG 2.2 AA; AI tasks have task-specific cost and latency ceilings; and every non-functional claim requires measurable evidence.

---

Section 27 — Platform-Wide Acceptance Requirements

27.1 Purpose
This final section defines the minimum evidence required to declare the first production LILOs platform release ready. It consolidates, but does not replace, subsystem acceptance requirements in Sections 1–26.

27.2 Acceptance Governance
Production acceptance requires named approvers for engineering, product, security, operations, and business ownership. An unresolved mandatory requirement must be recorded as a blocker or an explicitly approved deferred item. Silence is not acceptance.

27.3 Specification Integrity
Before implementation acceptance:
- Sections 1–27 are present and internally consistent.
- Defined terms and ownership boundaries are normalized.
- Architecture decisions are traceable.
- Known conflicts are resolved or explicitly documented.
- The roadmap references current section numbers.

27.4 Repository and Architecture
The repository must implement the approved modular architecture, documented frontend/backend/worker boundaries, shared platform services, migration framework, environment configuration, and architecture decision records. Product modules must not duplicate core systems.

27.5 Tenant and Identity Foundation
The release must support organizations, locations, users, memberships, scoped roles, permissions, session revocation, and tenant-aware repositories and services. Cross-tenant negative tests must pass.

27.6 Administration and Configuration
The release must support product registry, entitlements, readiness, configuration resolution, business facts, policy versions, feature flags, runtime controls, integration mapping, onboarding, offboarding, and auditable support access.

27.7 Workflow Foundation
Durable workflows must support execution records, steps, queueing, workers, scheduler, retry, timeout, idempotency, cancellation, approval pause/resume, dead-letter handling, replay, and diagnostics.

27.8 Integration Foundation
The platform must support provider and connector registries, secure authentication, capability discovery, resource mapping, full and incremental sync, webhooks, polling, outbound actions, verification, reconciliation, rate limiting, circuit breaking, and connector contract tests.

27.9 AI Foundation
The AI gateway must support task registry, provider adapters, model registry, routing, prompt versioning, structured outputs, validation, limits, usage records, fallback, approval, evaluation, tenant-isolated context, and manual alternatives.

27.10 Notification Foundation
In-app and email notifications must support templates, preferences, mandatory notices, delivery records, retry, failure visibility, and tenant scope.

27.11 Required Initial Product Proof
At minimum, one complete production vertical slice must prove connection, synchronization, proposed action, approval, provider write, verification, reconciliation, audit, diagnostics, and tenant isolation. The roadmap identifies Google Business Profile as the preferred vertical slice.

27.12 Product Acceptance
Any product included in the first production release must satisfy its product-specific acceptance criteria, operational states, permissions, reporting, failure handling, recovery, onboarding, and documentation. Products not meeting those requirements remain disabled or explicitly pilot-only.

27.13 User Experience
Agency and client surfaces must enforce scope and entitlement, expose complete loading/empty/error/degraded states, support critical workflows without database access, display data freshness, show approval consequences, and meet accessibility requirements.

27.14 Security
Mandatory controls include least privilege, tenant isolation, encryption, secret management, secure sessions, MFA policy, webhook verification, audit, sensitive-data redaction, dependency and secret scanning, incident response, and no unresolved critical security findings.

27.15 Privacy and Data Governance
Data inventory, classification, retention, export, deletion, legal hold where required, AI data-use restrictions, raw-payload retention, backups, restore testing, RPO, RTO, and disaster-recovery procedures must be documented and operational.

27.16 Observability and Operations
Production services must emit required telemetry. Dashboards, alerts, runbooks, incident lifecycle, queue and worker visibility, integration monitoring, AI monitoring, maintenance mode, emergency controls, and SLO measurement must be active.

27.17 Testing
Mandatory suites include unit, database, migration, API, authorization, tenant isolation, workflow, connector contract, AI evaluation, UI, accessibility, end-to-end, load for critical capacity, security, and backup restore. Required gates must pass.

27.18 Deployment and Release
Production uses an approved immutable artifact, validated migrations, environment isolation, protected secrets, deployment records, smoke tests, monitoring activation, rollback or mitigation plan, and post-deployment verification.

27.19 Documentation
Required documentation includes:
- Architecture overview
- Local setup
- Environment configuration
- Migration procedure
- Deployment and rollback
- Operator guide
- Product onboarding
- Integration connection and recovery
- Security and incident response
- Backup and restore
- Data export and deletion
- Critical runbooks
- API and event contracts
- Known limitations

27.20 Operational Ownership
Every critical service, workflow, connector, AI task, dashboard, alert, runbook, and product has an owner. Escalation paths and support responsibilities are documented.

27.21 Pilot Acceptance
A pilot organization must complete the intended critical workflows using production-equivalent controls. Pilot acceptance verifies onboarding, permissions, integrations, approval, external action, reporting, failure recovery, and audit.

27.22 Acceptance Evidence Package
The final package includes:
- Release identifier
- Approved specification and roadmap versions
- Implementation status by requirement
- Test reports
- Security findings and disposition
- Migration evidence
- Deployment evidence
- Monitoring screenshots or exported configuration
- Backup restore evidence
- Accessibility evidence
- Pilot results
- Known limitations
- Approvals

27.23 Release Blockers
The following block production launch:
1. Confirmed cross-tenant access.
2. Plaintext or exposed production secret.
3. Unauthorized external write path.
4. Missing audit for high-impact action.
5. Broken consent or opt-out enforcement.
6. Unverified destructive migration.
7. Failed backup restore.
8. Unresolved critical security vulnerability.
9. Critical workflow unable to recover or complete manually.
10. Missing monitoring for database, workers, queues, or critical integrations.
11. Production release without rollback or mitigation plan.
12. Required acceptance evidence unavailable.

27.24 Permitted Deferred Scope
The initial production release may defer:
- General-purpose CRM
- Public plugin marketplace
- Arbitrary third-party code execution
- Drag-and-drop automation builder
- Kubernetes or distributed event-streaming infrastructure
- Full white-labeling
- Unrestricted autonomous operator actions
- Additional products and connectors not approved for the pilot

Deferred capabilities must not be represented as production-ready.

27.25 Conditional Acceptance
A non-critical item may be conditionally accepted only with risk statement, owner, mitigation, due date, and explicit approver. Conditional acceptance cannot be used for the release blockers in 27.23.

27.26 Final Production Readiness Decision
The release is accepted only when the evidence package is complete, required approvers have signed off, blockers are closed, pilot validation passes, monitoring and backups are active, and the deployed artifact matches the approved release record.

27.27 Post-Launch Verification
Within the first operating period, the team reviews incidents, SLOs, cost, provider behavior, data freshness, support burden, and pilot outcomes. Findings become prioritized roadmap work rather than undocumented emergency changes.

27.28 Final Section Decisions
The platform is not complete because code exists or a deployment succeeds. Completion requires architecture conformity, tenant isolation, secure administration, durable workflows, verified integrations, controlled AI, operational products, accessible user experience, measurable reliability, tested recovery, complete documentation, pilot proof, and an approved evidence package. Deferred scope remains explicit and disabled until separately accepted.

