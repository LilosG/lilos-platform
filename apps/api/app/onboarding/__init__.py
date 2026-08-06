"""Client-onboarding orchestration: a read model composing existing services.

Introduces no new authoritative business logic. Every fact reported here is
resolved live from the owning domain service (organizations, locations,
domains, profiles, administration's services/business-facts/entitlements/
policies/onboarding-checklist, access-control memberships/invitations) at
request time, so it can never drift from what those services would report
directly.
"""
