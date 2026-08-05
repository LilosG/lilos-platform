"""Encrypted-at-rest secret storage backing OAuth credential references.

`IntegrationConnection.credential_reference` is a bounded, opaque pointer
(`String(500)`) -- it never holds plaintext or even ciphertext directly, since a
Fernet-encrypted JSON blob of `{"access_token": ..., "refresh_token": ...}` can
exceed that width. Instead, secrets are stored in the dedicated `provider_secrets`
table and `credential_reference` holds the row's UUID as a string.

Key rotation design: `key_version` records which configured key encrypted a row.
This initial implementation supports exactly one active key at a time
(`Settings.secret_encryption_key`, versioned by
`Settings.secret_encryption_key_version`); every write stamps the current version,
and reads require an exact version match. Rotating the key is a deliberate,
separate operational procedure this pass makes possible but does not automate:
(1) generate a new Fernet key and assign it the next version number; (2) extend
this store to accept a keyring of {version: key} for decryption during the
transition, since the current single-key design cannot decrypt a retired version;
(3) run an explicit re-encryption pass over every row where `key_version` is below
the new version, decrypting with the retired key and re-encrypting with the new
one; (4) once no row references a retired version, remove it from configuration.
No keyring support or re-encryption script exists yet -- only the `key_version`
column and this documented procedure are in place.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.config import Settings
from apps.api.app.database.base import Base, UUIDPrimaryKeyMixin


class SecretUnavailableError(Exception):
    """Raised when the encryption key is unconfigured/invalid or a secret cannot be read."""


class ProviderSecret(UUIDPrimaryKeyMixin, Base):
    """Opaque Fernet-encrypted ciphertext row referenced by `credential_reference`."""

    __tablename__ = "provider_secrets"

    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@dataclass(slots=True)
class FernetSecretStore:
    """`SecretStore` implementation backed by Fernet symmetric encryption.

    Bound to one request-scoped `AsyncSession` at construction time so that the
    `put`/`get`/`delete` method signatures can match the narrow `SecretStore`
    Protocol (`apps.api.app.integrations.service.SecretStore`) exactly, with no
    session parameter on each call.
    """

    session: AsyncSession
    fernet: Fernet
    key_version: int

    @classmethod
    def create(cls, session: AsyncSession, settings: Settings) -> "FernetSecretStore":
        if not settings.secret_encryption_key:
            raise SecretUnavailableError("secret encryption key is not configured")
        try:
            fernet = Fernet(settings.secret_encryption_key.encode("utf-8"))
        except ValueError as exc:
            raise SecretUnavailableError("secret encryption key is invalid") from exc
        return cls(
            session=session, fernet=fernet, key_version=settings.secret_encryption_key_version
        )

    async def put(self, value: str) -> str:
        ciphertext = self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        row = ProviderSecret(ciphertext=ciphertext, key_version=self.key_version)
        self.session.add(row)
        await self.session.flush()
        return str(row.id)

    async def get(self, reference: str) -> str:
        row = await self._get_row(reference)
        if row.key_version != self.key_version:
            raise SecretUnavailableError(
                "secret was encrypted under a retired key version; rotation not yet supported"
            )
        try:
            return self.fernet.decrypt(row.ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretUnavailableError("secret ciphertext could not be decrypted") from exc

    async def delete(self, reference: str) -> None:
        try:
            row_id = UUID(reference)
        except ValueError as exc:
            raise SecretUnavailableError("secret reference is malformed") from exc
        row = await self.session.get(ProviderSecret, row_id)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def _get_row(self, reference: str) -> ProviderSecret:
        try:
            row_id = UUID(reference)
        except ValueError as exc:
            raise SecretUnavailableError("secret reference is malformed") from exc
        row = await self.session.get(ProviderSecret, row_id)
        if row is None:
            raise SecretUnavailableError("secret reference not found")
        return row
