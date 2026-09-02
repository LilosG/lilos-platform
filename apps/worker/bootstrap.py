"""Worker ORM model bootstrap.

The standalone worker process only imports ``execution.models`` and
``observability.models`` at startup through the ``runtime`` module.
Workflow handlers import their domain models lazily — but if SQLAlchemy
metadata has already been compiled when the first query runs, foreign-key
resolution fails with ``NoReferencedTableError``.

This module imports every model module a registered workflow handler may
reach, so all table metadata is registered before the worker claims its
first job. It is deliberately NOT a ``*`` import — each module is listed
explicitly so a missing module fails at worker startup rather than at
the first handler invocation.
"""

# ── Core domain models (always needed) ──────────────────────────────────────
import apps.api.app.access_control.models  # noqa: F401  — membership / roles
import apps.api.app.administration.models  # noqa: F401  — BusinessFactRevision

# ── AI / agent models ───────────────────────────────────────────────────────
import apps.api.app.agents.models  # noqa: F401  — AgentSession / AgentRun
import apps.api.app.ai.models  # noqa: F401  — AIExecution, AITaskDefinition
import apps.api.app.audit.models  # noqa: F401  — AuditEvent
import apps.api.app.authentication.models  # noqa: F401  — UserProfile
import apps.api.app.integrations.models  # noqa: F401  — IntegrationConnection
import apps.api.app.locations.models  # noqa: F401  — Location
import apps.api.app.organizations.models  # noqa: F401  — Organization

# ── Product models (reachable from registered handlers) ─────────────────────
import apps.api.app.products.content.models  # noqa: F401
import apps.api.app.products.gbp.models  # noqa: F401
import apps.api.app.products.gbp.operations_models  # noqa: F401
import apps.api.app.products.gbp.post_generation_models  # noqa: F401
import apps.api.app.products.leads.models  # noqa: F401
import apps.api.app.products.reviews.models  # noqa: F401
import apps.api.app.products.seo.models  # noqa: F401
