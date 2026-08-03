# Governed configuration

Definitions are immutable seeded schemas. Revisions are organization-owned, limited to 65,536
bytes, eight nesting levels and 500 entries, and reject secret-bearing keys. Unknown production
keys have no generic route.

Resolution order is platform baseline, industry default, organization, location, then product.
Agency, workflow, resource and task layers await their owning models. Each schema declares
`replace`, `object_merge`, or `append_unique`; arrays are never merged implicitly. Resolution
returns contributing record/version trace and validation. Future/expired periods obey UTC without a
scheduler. Approved content is immutable; rollback creates a superseding revision.
