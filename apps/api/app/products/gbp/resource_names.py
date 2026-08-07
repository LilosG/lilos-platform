"""Canonical Google Business Profile resource-name construction.

Google exposes GBP through two API surfaces with DIFFERENT resource-name
conventions:

* Business Information API v1 (``mybusinessbusinessinformation.googleapis.com``):
  - ``accounts.locations.list`` returns ``Location.name`` as
    ``locations/{locationId}``.
  - ``locations.get`` / ``locations.patch`` use ``locations/{locationId}``
    (NOT account-qualified).

* My Business API v4 (``mybusiness.googleapis.com``) — legacy but required
  for reviews and localPosts:
  - ``accounts.locations.reviews`` and ``accounts.locations.localPosts`` use
    ``accounts/{accountId}/locations/{locationId}`` as the location parent.

The canonical location identity persisted on ``GBPLocation.external_location_id``
is therefore the v1 resource name ``locations/{locationId}`` — exactly what
``accounts.locations.list`` returns.  v1 endpoints consume it directly; the
legacy v4 endpoints wrap it with ``accounts/{accountId}/``.

This module is the SINGLE place that translates between the canonical identity
and any API-specific resource name.  Services and handlers must never
concatenate these strings themselves.
"""

from __future__ import annotations

LOCATION_PREFIX = "locations/"
_ACCOUNT_PREFIX = "accounts/"


def normalize_location_name(raw_name: str) -> str:
    """Return the canonical v1 location resource name ``locations/{locationId}``.

    Accepts any historical representation that may appear in Google responses
    or persisted rows:

    - ``locations/123``               (current v1 — returned as ``Location.name``)
    - ``accounts/456/locations/123``  (legacy/v4 account-qualified form)
    - ``123``                         (bare id)

    Raises ``ValueError`` when no location id can be extracted.
    """
    if not raw_name:
        raise ValueError("empty GBP location name")
    name = raw_name.strip()
    # Strip an optional account prefix: accounts/{accountId}/locations/{id}
    marker = "/locations/"
    if marker in name:
        name = name[name.rfind(marker) + len(marker) :]
    # What remains is either the bare id or ``locations/{id}``.
    if name.startswith(LOCATION_PREFIX):
        return name
    if not name:
        raise ValueError("empty GBP location name")
    return f"{LOCATION_PREFIX}{name}"


def location_id_from_name(raw_name: str) -> str:
    """Return the bare ``{locationId}`` portion of any location resource name."""
    return normalize_location_name(raw_name).removeprefix(LOCATION_PREFIX)


def v1_location_name(canonical: str) -> str:
    """The Business Information v1 resource name: ``locations/{locationId}``.

    This is exactly the canonical identity, returned unchanged so callers can
    use it directly in v1 ``locations.get`` / ``locations.patch`` paths.
    """
    return normalize_location_name(canonical)


def _bare_account_id(account_external_id: str) -> str:
    """Return the bare ``{accountId}``, stripping a leading ``accounts/``."""
    if not account_external_id:
        raise ValueError("empty GBP account id")
    if account_external_id.startswith(_ACCOUNT_PREFIX):
        return account_external_id[len(_ACCOUNT_PREFIX) :]
    return account_external_id


def v4_location_parent(account_external_id: str, canonical: str) -> str:
    """The My Business v4 location parent: ``accounts/{accountId}/locations/{locationId}``.

    Required by legacy v4 endpoints (reviews, localPosts) that are NOT
    available on the Business Information v1 surface.  Accepts the account id
    in either bare (``123``) or prefixed (``accounts/123``) form.
    """
    bare = _bare_account_id(account_external_id)
    return f"{_ACCOUNT_PREFIX}{bare}/{normalize_location_name(canonical)}"


def v4_review_name(account_external_id: str, canonical: str, external_review_id: str) -> str:
    """The v4 review resource name: ``accounts/{a}/locations/{l}/reviews/{r}``."""
    if not external_review_id:
        raise ValueError("empty GBP review id")
    return f"{v4_location_parent(account_external_id, canonical)}/reviews/{external_review_id}"


def v4_localposts_parent(account_external_id: str, canonical: str) -> str:
    """The v4 localPosts collection parent: ``accounts/{a}/locations/{l}``.

    Append ``/localPosts`` for the create endpoint.
    """
    return v4_location_parent(account_external_id, canonical)
