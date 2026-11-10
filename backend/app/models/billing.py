"""Commercial model: subscription per company and module."""

import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantOwned, Timestamps, UUIDPk


class Module(enum.StrEnum):
    LIQUIDITY = "liquidity"  # base module, required by every other module
    FORECAST = "forecast"
    COLLECT = "collect"
    PAYMENTS = "payments"
    FINANCING = "financing"
    GROUP = "group"
    AI = "ai"
    DIRECT_BANKING = "direct_banking"


# Modules that must be active on the same company for a module to work.
MODULE_REQUIRES: dict[Module, set[Module]] = {
    m: {Module.LIQUIDITY} for m in Module if m is not Module.LIQUIDITY
}


class Entitlement(UUIDPk, Timestamps, TenantOwned, Base):
    """Module ``module`` is contracted for ``company`` between the two dates (inclusive)."""

    __tablename__ = "entitlement"
    __table_args__ = (UniqueConstraint("tenant_id", "company_id", "module", "valid_from"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"), index=True
    )
    module: Mapped[Module] = mapped_column(
        Enum(Module, name="module", values_callable=lambda e: [m.value for m in e])
    )
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)

    def is_active_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)
