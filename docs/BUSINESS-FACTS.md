# Business facts

Business facts are immutable revisions scoped to an organization and optionally a location. Each
preserves stable identity, key, validated typed value, source, authority, effective period,
supersession, actor, reason, and approval. Provider, imported, industry, system-derived, or AI
evidence is never authoritative merely because it exists.

Approval activates one revision and supersedes prior current history without rewriting content.
Resolution considers active approved revisions at the requested UTC instant, ranks explicit
authority before scope specificity, and returns `resolved`, `missing`, or `ambiguous`. Equal-
authority conflicts are surfaced rather than silently selected. Mutations and audit are atomic.
