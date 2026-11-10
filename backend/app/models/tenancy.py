import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantOwned, Timestamps, UUIDPk


class Tenant(UUIDPk, Timestamps, Base):
    """A customer of the platform. Not RLS-protected (platform-level table)."""

    __tablename__ = "tenant"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ErpConnection(UUIDPk, Timestamps, TenantOwned, Base):
    """Credentials and endpoint of one ERP database of a tenant."""

    __tablename__ = "erp_connection"

    kind: Mapped[str] = mapped_column(String(32), default="odoo")
    version: Mapped[str] = mapped_column(String(16), default="18.0")
    base_url: Mapped[str] = mapped_column(String(500))
    database: Mapped[str] = mapped_column(String(200))
    username: Mapped[str] = mapped_column(String(200))
    # Reference to the secret (``env:NAME`` or ``aws:ARN``), never the secret itself.
    secret_ref: Mapped[str] = mapped_column(String(500))
    # Shared secret used by the Odoo addon to sign login tokens (reference, not the value).
    sso_secret_ref: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Company(UUIDPk, Timestamps, TenantOwned, Base):
    """A legal entity (``res.company`` in Odoo). Billing unit of the platform."""

    __tablename__ = "company"
    __table_args__ = (UniqueConstraint("tenant_id", "erp_connection_id", "erp_id"),)

    erp_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_connection.id", ondelete="CASCADE")
    )
    erp_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    vat: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SsoNonce(Base):
    """Login tokens already used (replay protection). Platform-level table."""

    __tablename__ = "sso_nonce"

    jti: Mapped[str] = mapped_column(String(128), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
