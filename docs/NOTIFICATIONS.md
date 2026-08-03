# Notification Foundation

Phase 6 stores bounded, non-executable templates, organization-scoped events, recipient/channel deliveries, preferences, and retained attempts. Events and recipient deliveries are uniquely deduplicated. Critical events cannot be suppressed by ordinary preferences. Quiet hours, channel eligibility, mandatory delivery, and escalation are resolved from the Phase 4 notification-policy registry.

Delivery is delegated to Phase 5 jobs; this module does not create another retry runtime. Providers implement a narrow adapter and receive a rendered reference only after commit. Templates, audit events, and logs must never contain credentials, bearer or invitation tokens, or unrestricted provider responses. Production email/SMS/push providers remain deferred.
