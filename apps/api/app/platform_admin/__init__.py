"""Additive cross-organization platform administrator primitive.

This module sits alongside the existing per-organization RBAC engine in
``apps.api.app.access_control`` without modifying it. A platform administrator
is not an organization member; it is a narrow, explicitly-granted, revocable
flag on a user profile that authorizes platform-scoped bootstrap operations
(creating organizations and locations, bootstrapping the first owner) which
have no organization to scope authorization to yet.
"""
