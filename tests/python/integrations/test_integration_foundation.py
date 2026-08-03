import hashlib

from apps.api.app.integrations.models import IntegrationConnection, OAuthAuthorizationIntent


def test_oauth_schema_stores_hash_and_secret_references_only() -> None:
    intent = set(OAuthAuthorizationIntent.__table__.columns.keys())
    connection = set(IntegrationConnection.__table__.columns.keys())
    assert {"state_hash", "expires_at", "consumed_at", "exact_redirect_uri"} <= intent
    assert (
        "state" not in intent
        and "access_token" not in connection
        and "refresh_token" not in connection
    )
    assert len(hashlib.sha256(b"fixture-state").hexdigest()) == 64
